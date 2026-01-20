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

from .models import Article
from .crawler import fetch_naver_news
from .ai_service import summarize_stream

# 로그 설정
logger = logging.getLogger(__name__)
User = get_user_model()

# ---------------------------------------------------------
# 1. 인증 (Google Login)
# ---------------------------------------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
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
# backend/news/views.py

# ... (기존 임포트 유지)

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

        # 3. DB 객체 생성 (일단 내용은 빈 상태로)
        article, created = Article.objects.update_or_create(
            user=request.user,
            url=url,
            defaults={
                'title': crawled_data.get('title', '제목 없음'),
                'content': crawled_data.get('content', ''),
                'thumbnail_url': crawled_data.get('thumbnail_url'),
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

    try:
        article.status = Article.Status.SAVED
        article.save()

        # TODO: 임베딩 생성 로직이 있다면 여기에 추가 (Celery 등 비동기 추천)

        return Response({'message': '성공적으로 저장되었습니다.', 'status': 'SAVED'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"❌ 저장 에러: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)