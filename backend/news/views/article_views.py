import logging
import threading
from django.shortcuts import get_object_or_404
from django.http import StreamingHttpResponse 
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

# 모델 및 로직 임포트
from ..models import Article, UserActionLog
from ..recommendation import update_user_vector
from ..crawler import extract_article 
from ..ai_service import summarize_stream, get_embedding, classify_news
from ..nlp_utils import extract_entities # [New] NER 함수 임포트

logger = logging.getLogger(__name__)

# =========================================================
# 1. 요약 스트리밍 View
# =========================================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def summarize(request):
    """
    URL을 받아 기사를 크롤링하고, 국적(Region)에 맞춰 요약을 스트리밍합니다.
    [수정] 크롤링 시점에 NER(개체명) 추출하여 저장.
    """
    url = request.data.get('url')
    region = request.data.get('region', 'KR') 

    if not url:
        return Response({'error': 'URL이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    # 이미 저장된 기사인지 확인
    if Article.objects.filter(user=request.user, url=url, status=Article.Status.SAVED).exists():
        return Response({'message': '이미 서재에 저장된 기사입니다.', 'status': 'ALREADY_SAVED'}, status=status.HTTP_200_OK)

    try:
        # 1. 크롤링
        crawled_data = extract_article(url)
        
        if not crawled_data or not crawled_data.get('content'):
            return Response({'error': '기사 본문을 가져올 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        # ---------------------------------------------------------
        # 2. 카테고리 및 기사 성격(Type) 분류
        # ---------------------------------------------------------
        ai_result = classify_news(crawled_data['content'], region=region)
        
        category = ai_result.get('category', 'General')
        article_type = ai_result.get('type', 'FACT') 

        print(f"[{region}] AI 분류 결과 : Category={category}, Type={article_type}")

        # ---------------------------------------------------------
        # [New] 2-1. NER 개체명 추출 (추가된 부분)
        # ---------------------------------------------------------
        try:
            # 본문 내용을 바탕으로 인물/조직/장소 추출
            extracted_entities = extract_entities(crawled_data['content'], region=region)
            # 결과 예: {'PERSON': ['민희진'], 'ORG': ['하이브']}
        except Exception as e:
            print(f"⚠️ [NER Warning] 추출 실패: {e}")
            extracted_entities = {}

        # 3. DB 임시 저장 (Pending 상태)
        article, created = Article.objects.update_or_create(
            user=request.user,
            url=url,
            defaults={
                'title': crawled_data.get('title', '제목 없음'),
                'content': crawled_data.get('content', ''),
                'thumbnail_url': crawled_data.get('thumbnail_url'),
                
                'category': category,
                'article_type': article_type, 
                
                # [New] 개체명 저장
                'entities': extracted_entities,

                'region': region,
                'status': Article.Status.PENDING,
            }
        )

        # 4. 스트리밍 함수 정의
        def stream_and_save():
            full_summary_list = []
            try:
                # 여기서 summarize_stream은 제너레이터(yield)
                for chunk in summarize_stream(article.content, region=region):
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode('utf-8')
                        full_summary_list.append(chunk_str)
                        yield chunk # 바이너리 그대로 전송
                    else:
                        full_summary_list.append(str(chunk))
                        yield str(chunk) # 문자열 전송
                
                # 스트리밍 완료 후 1차 저장 (요약문만)
                final_summary = "".join(full_summary_list)
                if final_summary:
                    article.summary = final_summary
                    article.save()
                    print(f"✅ [{region}] DB 요약 저장 완료 (길이: {len(final_summary)})")
                
            except Exception as e:
                print(f"🔥 스트리밍 중 에러: {e}")
                # 에러 메시지도 클라이언트에 전송
                yield f"Error: {str(e)}"

        return StreamingHttpResponse(stream_and_save(), content_type='text/event-stream')

    except Exception as e:
        logger.error(f"🔥 요약 중 서버 에러: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =========================================================
# 2. 백그라운드 작업 (임베딩 + 로그 + 추천반영)
# =========================================================
def run_embedding_task(article_id):
    """
    [백그라운드 스레드]
    1. 임베딩 생성 (PyTorch/OpenAI)
    2. UserActionLog 기록 (SAVE)
    3. UserProfile 벡터 업데이트 (추천 시스템 반영)
    """
    try:
        # DB 연결 (스레드 내부라 새로 가져옴)
        try:
            article = Article.objects.get(id=article_id)
        except Article.DoesNotExist:
            print(f"❌ 기사를 찾을 수 없음 (ID: {article_id})")
            return

        print(f"🔄 [Background] 작업 시작: {article.title}")
        
        # --- Step A: 임베딩 생성 ---
        try:
            # 입력 텍스트 구성
            input_text = f"[{article.category}] {article.title}. {article.summary}"
            
            # 임베딩 생성 API 호출
            vectors = get_embedding(input_text)
            
            updated = False
            if vectors.get('pytorch'):
                article.embedding_pytorch = vectors['pytorch']
                updated = True
            
            if vectors.get('openai'):
                article.embedding_openai = vectors['openai']
                updated = True
                
            if updated:
                article.save()
                print(f"✅ [Embedding] 저장 완료")
            else:
                print(f"⚠️ [Embedding] 생성 실패 (API 응답 없음)")
        
        except Exception as e:
            print(f"🔥 [Embedding] 에러 발생: {e}")

        # --- Step B: 로그 및 추천 업데이트 ---
        try:
            user = article.user
            
            # 로그 기록 (행동: SAVE)
            UserActionLog.objects.create(
                user=user,
                article=article,
                article_url=article.url,
                action='SAVE', # 명시적 문자열 사용
                region=article.region,
                title=article.title,
                description=article.summary[:200] if article.summary else "",
                image_url=article.thumbnail_url,
                category=article.category,
                dwell_time=999, 
                is_valid_view=True
            )
            print(f"📝 [Log] UserActionLog 저장 완료 (SAVE)")

            # 추천 벡터 업데이트 (User Tower)
            if article.embedding_pytorch:
                # 가중치 0.2 (저장은 꽤 강력한 시그널)
                update_user_vector(user, article.embedding_pytorch, weight=0.2)
                print(f"📈 [Recommendation] 유저 취향 업데이트 완료 (Weight: 0.2)")

        except Exception as e:
            print(f"🔥 [Log/Rec] 에러 발생: {e}")

    except Exception as e:
        print(f"🔥 백그라운드 작업 치명적 에러: {e}")


# =========================================================
# 3. 저장 확정 View
# =========================================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_article(request):
    """
    요약 확정 및 저장 (임베딩은 백그라운드 처리)
    """
    url = request.data.get('url')
    summary_text = request.data.get('summary')
    region = request.data.get('region', 'KR')
    
    if not url:
        return Response({'error': 'URL이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    article = get_object_or_404(Article, user=request.user, url=url)

    try:
        # 1. 텍스트 정보 우선 저장 (빠른 응답)
        article.status = Article.Status.SAVED
        article.region = region
        if summary_text:
            article.summary = summary_text
        article.save()

        # 2. 백그라운드 작업 시작 (임베딩, 로그, 추천반영)
        # 별도 스레드에서 실행하여 사용자 응답 속도 향상
        thread = threading.Thread(target=run_embedding_task, args=(article.id,))
        thread.start()

        return Response({'message': '성공적으로 저장되었습니다.', 'status': 'SAVED'}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"❌ 저장 에러: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)