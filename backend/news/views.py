import logging
import requests
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework import status
from django.http import JsonResponse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.shortcuts import render, redirect  # redirect 추가
from django.contrib.auth import login          # login 함수 추가
from django.conf import settings
from rest_framework.authtoken.models import Token # Token 모델 추가
from rest_framework.permissions import AllowAny
from rest_framework.decorators import authentication_classes # authentication_classes 추가

from .models import Article
from .crawler import fetch_naver_news
from .ai_service import summarize_stream, get_embedding, classify_news

from pgvector.django import CosineDistance
from django.shortcuts import render

# 로그 설정
logger = logging.getLogger(__name__)
User = get_user_model()

# ---------------------------------------------------------
# 1. 인증 (Google Login)
# ---------------------------------------------------------
@api_view(['POST'])
@permission_classes([AllowAny])    # <--- [중요] 누구나 접속 가능하게 허용
@authentication_classes([])
def google_login(request):
    """
    구글 액세스 토큰을 받아 유저를 생성/조회하고 DRF 토큰을 발급합니다.
    """
    access_token = request.data.get('access_token')
    
    # 구글 API로 유저 정보 검증
    verify_url = f"https://www.googleapis.com/oauth2/v3/userinfo?access_token={access_token}"
    response = requests.get(verify_url)
    
    if response.status_code != 200:
        return Response({'error': '유효하지 않은 구글 토큰입니다.'}, status=status.HTTP_400_BAD_REQUEST)
    
    user_info = response.json()
    email = user_info.get('email')
    name = user_info.get('name', '')
    
    if not email:
        return Response({'error': '이메일 정보를 가져올 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

    # 유저 생성 (또는 조회)
    user, created = User.objects.get_or_create(
        username=email, 
        defaults={'first_name': name, 'email': email}
    )
    
    # DRF 토큰 발급
    token, _ = Token.objects.get_or_create(user=user)
    
    return Response({
        'token': token.key,
        'username': user.username,
        'message': '로그인 성공'
    })



# ---------------------------------------------------------
# 2. 뉴스 요약 (AI Streaming)
# ---------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def summarize(request):
    """
    URL을 받아 크롤링 후 AI 요약을 스트리밍하며, 완료 시 자동으로 DB에 저장합니다.
    """
    url = request.data.get('url')

    if not url:
        return Response({'error': 'URL이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    # 1. 이미 저장된 기사인지 확인
    if Article.objects.filter(user=request.user, url=url, status=Article.Status.SAVED).exists():
        return Response({'message': '이미 서재에 저장된 기사입니다.', 'status': 'ALREADY_SAVED'}, status=status.HTTP_200_OK)

    try:
        # 2. 크롤링 수행
        crawled_data = fetch_naver_news(url)
        
        if not crawled_data or not crawled_data.get('content'):
            return Response({'error': '기사 본문을 가져올 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        #2.5 AI 카테고리 자동 분류

        ai_category = classify_news(crawled_data['content'])
        print(f"AI 분류 결과 : {ai_category}")

        # 3. DB 객체 생성 (일단 내용은 빈 상태로)
        article, created = Article.objects.update_or_create(
            user=request.user,
            url=url,
            defaults={
                'title': crawled_data.get('title', '제목 없음'),
                'content': crawled_data.get('content', ''),
                'thumbnail_url': crawled_data.get('thumbnail_url'),
                'category' : ai_category,
                'status': Article.Status.PENDING,
            }
        )

        # ★ 핵심: 제너레이터 래퍼 (Stream을 중간에서 가로채서 저장)
        def stream_and_save():
            full_summary_list = [] # 단어들을 모을 리스트
            
            try:
                # AI 서비스가 주는 단어들을 하나씩 받아서
                for chunk in summarize_stream(article.content):
                    # 1. 리스트에 담고 (나중에 저장용)
                    # (chunk가 bytes일 수도 있고 str일 수도 있음. 상황에 맞춰 처리)
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode('utf-8')
                        full_summary_list.append(chunk_str)
                    else:
                        full_summary_list.append(str(chunk))
                    
                    # 2. 브라우저에게도 바로바로 전달
                    yield chunk
                
                # 스트리밍이 끝나면 모아둔 단어를 합쳐서 DB에 저장
                final_summary = "".join(full_summary_list)
                if final_summary:
                    article.summary = final_summary
                    article.save()
                    print(f"✅ DB 저장 완료 (길이: {len(final_summary)})")
                
            except Exception as e:
                print(f"🔥 스트리밍 중 에러: {e}")
                yield f"에러 발생: {e}"

        # 4. 래퍼 함수를 스트리밍 응답으로 전달
        return StreamingHttpResponse(
            stream_and_save(),
            content_type='text/event-stream'
        )

    except Exception as e:
        logger.error(f"🔥 요약 중 서버 에러: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------
# 3. 기사 최종 저장 (확정)
# ---------------------------------------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_article(request):
    """
    PENDING 상태의 기사를 SAVED 상태로 변경합니다.
    """
    url = request.data.get('url')
    
    if not url:
        return Response({'error': 'URL이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    # 내(user)가 가진 기사 중에서 찾기
    article = get_object_or_404(Article, user=request.user, url=url)
    if not article:
            return JsonResponse({'error': '기사를 찾을 수 없습니다.'}, status=404)

    try:
        article.status = Article.Status.SAVED

        # 임베딩 생성 로직이 추가
        if article.embedding is None:
            print(f"🧠 임베딩 생성 시작: {article.title}")
            
            # 제목과 본문을 합쳐서 벡터를 만드는 게 정확도가 더 높습니다.
            full_text = f"{article.title} {article.content}"
            
            # 텍스트가 너무 길면(8191 토큰 초과) 잘라줘야 에러가 안 납니다.
            # 간단하게 앞부분 8000자만 사용 (뉴스 기사는 보통 이 안에 다 들어감)
            vector = get_embedding(full_text[:8000])
            
            if vector:
                article.embedding = vector
                print("✅ 임베딩 저장 완료")
            else:
                print("⚠️ 임베딩 생성 실패 (다음 기회에...)")


        article.save()

        
        return Response({'message': '성공적으로 저장되었습니다.', 'status': 'SAVED'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"❌ 저장 에러: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_knowledge_graph(request):
    """
    DB에 저장된 기사들을 가져와서 그래프 데이터(Nodes, Links)로 변환
    현재 로직: [기사] --- (속함) --> [카테고리]
    """
    # 1. 로그인한 유저의 '저장된(SAVED)' 기사만 가져오기
    articles = Article.objects.filter(user=request.user, status=Article.Status.SAVED)

    nodes = []
    links = []
    
    # 중복된 카테고리 노드 생성을 방지하기 위한 집합(Set)
    existing_categories = set()

    for article in articles:
        # -------------------------------------------------
        # 1. 기사 노드 생성 (Group 1)
        # -------------------------------------------------
        # 제목이 너무 길면 그래프가 지저분하므로 cut
        short_title = (article.title[:15] + '...') if len(article.title) > 15 else article.title
        
        # 노드 ID를 유니크하게 만들기 위해 'art_' 접두사 사용
        article_node_id = article.title  # 화면에 제목을 띄우기 위해 ID에 제목 사용 (중복 주의)
        
        # 만약 제목이 겹칠 수 있다면 아래처럼 ID 뒤에 숫자를 붙이기
        # article_node_id = f"{short_title}_{article.id}"

        nodes.append({
            "id": article_node_id,   # 그래프 화면에 표시될 텍스트
            "group": 1               # 1번 그룹: 기사 (파란색 등)
        })

        # -------------------------------------------------
        # 2. 카테고리 노드 생성 (Group 2)
        # -------------------------------------------------
        # 카테고리가 없으면 '기타'로 분류
        category_name = article.category if article.category else "기타"
        
        # 카테고리 노드는 중복해서 만들면 안 되므로 검사
        if category_name not in existing_categories:
            nodes.append({
                "id": category_name,
                "group": 2           # 2번 그룹: 카테고리 (주황색 등)
            })
            existing_categories.add(category_name)

        # -------------------------------------------------
        # 3. 링크 연결 (기사 -> 카테고리)
        # -------------------------------------------------
        links.append({
            "source": article_node_id,  # 출발: 기사 제목
            "target": category_name,    # 도착: 카테고리 이름
            "value": 1
        })

    # 최종 데이터 반환
    data = {
        "nodes": nodes,
        "links": links
    }
    return JsonResponse(data)

#[Page] 그래프 화면 렌더링

@xframe_options_exempt
def graph_page(request):
    return render(request, 'news/graph.html')

def dashboard_page(request):
    # 1. URL 파라미터에서 토큰 확인
    token_key = request.GET.get('token')
    
    # 디버깅 로그 (터미널에서 확인 가능)
    print(f"🔍 대시보드 접근 - User: {request.user}, Token: {token_key}")

    if token_key:
        try:
            # 토큰으로 유저 찾기
            token = Token.objects.get(key=token_key)
            user = token.user
            
            # ★ 핵심 수정: backend 파라미터를 명시적으로 지정해야 합니다!
            # 이것이 없으면 세션이 생성되지 않는 경우가 많습니다.
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            print(f"✅ 토큰 로그인 성공! -> {user.username}")
            
            # 토큰 파라미터를 떼고 깨끗한 주소로 다시 이동
            return redirect('dashboard')
            
        except Token.DoesNotExist:
            print("❌ 유효하지 않은 토큰입니다.")
        except Exception as e:
            print(f"❌ 로그인 처리 중 에러: {e}")

    # 2. 로그인 여부 최종 확인
    if not request.user.is_authenticated:
        print("⛔ 로그인되지 않음. 접근 거부.")
        # 에러 페이지 대신, 로그인 유도 메시지가 있는 대시보드를 보여주거나 에러 페이지 렌더링
        return render(request, 'news/dashboard.html', {'error': '로그인이 필요합니다.'})

    # 3. 정상 접근
    return render(request, 'news/dashboard.html')
