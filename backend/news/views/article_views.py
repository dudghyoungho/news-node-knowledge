import logging
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
    """
    url = request.data.get('url')
    # [추가] 프론트엔드에서 보낸 region 받기 (없으면 KR 기본)
    region = request.data.get('region', 'KR') 

    if not url:
        return Response({'error': 'URL이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    # 이미 저장된 기사인지 확인 (재요약 방지)
    if Article.objects.filter(user=request.user, url=url, status=Article.Status.SAVED).exists():
        return Response({'message': '이미 서재에 저장된 기사입니다.', 'status': 'ALREADY_SAVED'}, status=status.HTTP_200_OK)

    try:
        # 1. 크롤링 (호주 뉴스도 처리할 수 있도록 crawler.py가 수정되어야 함)
        # fetch_naver_news라는 이름이지만, 내부적으로 trafilatura 등을 써서 범용 크롤링을 수행한다고 가정
        crawled_data = extract_article(url)
        
        if not crawled_data or not crawled_data.get('content'):
            return Response({'error': '기사 본문을 가져올 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. [변경] 카테고리 분류 시 Region 전달
        # AU면 영어 카테고리(Economy), KR이면 한국어 카테고리(경제) 반환
        ai_category = classify_news(crawled_data['content'], region=region)
        print(f"[{region}] AI 분류 결과 : {ai_category}")

        # 3. DB에 임시 저장 (Pending 상태)
        article, created = Article.objects.update_or_create(
            user=request.user,
            url=url,
            defaults={
                'title': crawled_data.get('title', '제목 없음'),
                'content': crawled_data.get('content', ''),
                'thumbnail_url': crawled_data.get('thumbnail_url'),
                'category' : ai_category,
                'region': region, # [추가] 국적 정보 저장
                'status': Article.Status.PENDING,
            }
        )

        # 4. 스트리밍 함수 정의
        def stream_and_save():
            full_summary_list = []
            try:
                # [변경] 요약 함수에 Region 전달 (프롬프트 분기용)
                for chunk in summarize_stream(article.content, region=region):
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode('utf-8')
                        full_summary_list.append(chunk_str)
                    else:
                        full_summary_list.append(str(chunk))
                    yield chunk
                
                # 스트리밍 완료 후 최종 요약본 저장
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_article(request):
    """
    요약이 끝난 후, 사용자가 '저장' 버튼을 눌렀을 때 최종 확정하는 로직
    """
    url = request.data.get('url')
    summary_text = request.data.get('summary')
    # [추가] 저장 시에도 region 정보 확인 (혹시 모르니 업데이트)
    region = request.data.get('region', 'KR')
    
    if not url:
        return Response({'error': 'URL이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    article = get_object_or_404(Article, user=request.user, url=url)

    try:
        article.status = Article.Status.SAVED
        article.region = region # 국적 정보 확정 저장
        
        if summary_text:
            article.summary = summary_text

        # 임베딩 생성 (언어 무관하게 텍스트 기반 생성)
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