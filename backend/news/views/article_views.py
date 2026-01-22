import logging
from django.shortcuts import get_object_or_404
from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

# 상위 폴더 모듈 임포트
from ..models import Article
from ..crawler import fetch_naver_news
from ..ai_service import summarize_stream, get_embedding, classify_news

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def summarize(request):
    url = request.data.get('url')

    if not url:
        return Response({'error': 'URL이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    if Article.objects.filter(user=request.user, url=url, status=Article.Status.SAVED).exists():
        return Response({'message': '이미 서재에 저장된 기사입니다.', 'status': 'ALREADY_SAVED'}, status=status.HTTP_200_OK)

    try:
        crawled_data = fetch_naver_news(url)
        
        if not crawled_data or not crawled_data.get('content'):
            return Response({'error': '기사 본문을 가져올 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        ai_category = classify_news(crawled_data['content'])
        print(f"AI 분류 결과 : {ai_category}")

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

        def stream_and_save():
            full_summary_list = []
            try:
                for chunk in summarize_stream(article.content):
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
                    print(f"✅ DB 저장 완료 (길이: {len(final_summary)})")
                
            except Exception as e:
                print(f"🔥 스트리밍 중 에러: {e}")
                yield f"에러 발생: {e}"

        return StreamingHttpResponse(stream_and_save(), content_type='text/event-stream')

    except Exception as e:
        logger.error(f"🔥 요약 중 서버 에러: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_article(request):
    url = request.data.get('url')
    summary_text = request.data.get('summary')
    
    if not url:
        return Response({'error': 'URL이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    article = get_object_or_404(Article, user=request.user, url=url)

    try:
        article.status = Article.Status.SAVED
        
        if summary_text:
            article.summary = summary_text

        if article.embedding is None:
            print(f"🧠 임베딩 생성 시작: {article.title}")
            full_text = f"{article.title} {article.content} {article.summary}"
            vector = get_embedding(full_text[:8000])
            
            if vector:
                article.embedding = vector
                print("✅ 임베딩 저장 완료")
            else:
                print("⚠️ 임베딩 생성 실패 (API 오류 등)")

        article.save()
        return Response({'message': '성공적으로 저장되었습니다.', 'status': 'SAVED'}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"❌ 저장 에러: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)