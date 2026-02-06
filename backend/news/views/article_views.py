import logging
import threading
from django.shortcuts import get_object_or_404
from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

# 상위 폴더 모듈 임포트
from ..models import Article
from ..crawler import extract_article 
from ..ai_service import summarize_stream, get_embedding, classify_news

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def summarize(request):
    """
    URL을 받아 기사를 크롤링하고, 국적(Region)에 맞춰 요약을 스트리밍합니다.
    (기존 로직 유지)
    """
    url = request.data.get('url')
    region = request.data.get('region', 'KR') 

    if not url:
        return Response({'error': 'URL이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    if Article.objects.filter(user=request.user, url=url, status=Article.Status.SAVED).exists():
        return Response({'message': '이미 서재에 저장된 기사입니다.', 'status': 'ALREADY_SAVED'}, status=status.HTTP_200_OK)

    try:
        # 1. 크롤링
        crawled_data = extract_article(url)
        
        if not crawled_data or not crawled_data.get('content'):
            return Response({'error': '기사 본문을 가져올 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. 카테고리 분류
        ai_category = classify_news(crawled_data['content'], region=region)
        print(f"[{region}] AI 분류 결과 : {ai_category}")

        # 3. DB 임시 저장
        article, created = Article.objects.update_or_create(
            user=request.user,
            url=url,
            defaults={
                'title': crawled_data.get('title', '제목 없음'),
                'content': crawled_data.get('content', ''),
                'thumbnail_url': crawled_data.get('thumbnail_url'),
                'category' : ai_category,
                'region': region,
                'status': Article.Status.PENDING,
            }
        )

        # 4. 스트리밍
        def stream_and_save():
            full_summary_list = []
            try:
                for chunk in summarize_stream(article.content, region=region):
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode('utf-8')
                        full_summary_list.append(chunk_str)
                    else:
                        full_summary_list.append(str(chunk))
                    yield chunk
                
                final_summary = "".join(full_summary_list)
                if final_summary:
                    article.summary = final_summary
                    article.save()
                    print(f"✅ [{region}] DB 저장 완료 (길이: {len(final_summary)})")
                
            except Exception as e:
                print(f"🔥 스트리밍 중 에러: {e}")
                yield f"에러 발생: {e}"

        return StreamingHttpResponse(stream_and_save(), content_type='text/event-stream')

    except Exception as e:
        logger.error(f"🔥 요약 중 서버 에러: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def run_embedding_task(article_id):
    """
    [백그라운드 작업]
    사용자에게 응답을 보낸 뒤, 뒤에서 조용히 임베딩을 생성하고 저장합니다.
    """
    try:
        # 스레드 안에서는 DB 연결을 새로 잡아야 하므로 article을 ID로 다시 불러옵니다.
        article = Article.objects.get(id=article_id)
        
        print(f"🔄 [Background] 임베딩 생성 시작: {article.title}")
        
        # 입력 텍스트 구성
        input_text = f"[{article.category}] {article.title}. {article.summary}"
        
        # 임베딩 생성 (PyTorch + OpenAI)
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
            print(f"✅ [Background] 임베딩 저장 완료 (ID: {article.id})")
        else:
            print(f"⚠️ [Background] 임베딩 생성 실패 (ID: {article.id})")
            
    except Article.DoesNotExist:
        print(f"❌ 기사를 찾을 수 없음 (ID: {article_id})")
    except Exception as e:
        print(f"🔥 백그라운드 작업 중 에러: {e}")


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
        # 1. 텍스트 정보 우선 저장 (매우 빠름)
        article.status = Article.Status.SAVED
        article.region = region
        if summary_text:
            article.summary = summary_text
        article.save()

        # 2. [핵심] 임베딩 작업을 백그라운드 스레드로 던짐 (기다리지 않음!)
        # embedding_pytorch가 없을 때만 실행
        if article.embedding_pytorch is None:
            thread = threading.Thread(target=run_embedding_task, args=(article.id,))
            thread.start()

        # 3. 사용자에게는 즉시 "성공" 응답 반환 (0.1초 컷)
        return Response({'message': '성공적으로 저장되었습니다.', 'status': 'SAVED'}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"❌ 저장 에러: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)