import json
import logging
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Article
from .crawler import fetch_naver_news
from .ai_service import summarize_stream

# 로그를 남기기 위한 설정 (터미널에서 에러를 더 잘 보기 위함)
logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def summarize(request):
    try:
        data = json.loads(request.body)
        url = data.get('url')

        if not url:
            return JsonResponse({'error': 'URL이 필요합니다.'}, status=400)

        # 1. 이미 저장된 기사인지 확인
        if Article.objects.filter(url=url, status=Article.Status.SAVED).exists():
            return JsonResponse({'message': '이미 서재에 저장된 기사입니다.', 'status': 'ALREADY_SAVED'}, status=200)

        # 2. 크롤링 수행
        crawled_data = fetch_naver_news(url)
        
        # [수정] 크롤링 결과가 없거나 본문이 비어있을 때 처리
        if not crawled_data or not crawled_data.get('content'):
            print(f"❌ 크롤링 실패: {url}") # 터미널 확인용
            return JsonResponse({'error': '기사 본문을 가져올 수 없습니다. 지원하지 않는 페이지이거나 일시적인 오류입니다.'}, status=400)

        # 3. DB 저장 (또는 업데이트)
        # .get()을 사용하여 키가 없을 경우의 에러를 방지합니다.
        try:
            article, created = Article.objects.update_or_create(
                url=url,
                defaults={
                    'title': crawled_data.get('title', '제목 없음'),
                    'content': crawled_data.get('content', ''),
                    'thumbnail_url': crawled_data.get('thumbnail_url'),
                    'status': Article.Status.PENDING,
                }
            )
        except Exception as db_err:
            print(f"❌ DB 저장 에러: {db_err}")
            return JsonResponse({'error': f'데이터베이스 저장 중 오류가 발생했습니다: {str(db_err)}'}, status=500)

        # 4. 스트리밍 응답 생성
        # AI 요약 서비스 호출
        try:
            return StreamingHttpResponse(
                summarize_stream(article.content),
                content_type='text/event-stream'
            )
        except Exception as ai_err:
            print(f"❌ AI 요약 에러: {ai_err}")
            return JsonResponse({'error': f'AI 요약 생성 중 오류가 발생했습니다: {str(ai_err)}'}, status=500)

    except json.JSONDecodeError:
        return JsonResponse({'error': '잘못된 JSON 형식입니다.'}, status=400)
    except Exception as e:
        # 예상치 못한 모든 에러를 터미널에 출력
        print(f"🔥 서버 내부 에러 발생: {str(e)}")
        return JsonResponse({'error': f'서버 내부 오류: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def save_article(request):
    try:
        data = json.loads(request.body)
        url = data.get('url')

        article = Article.objects.filter(url=url).first()
        if not article:
            return JsonResponse({'error': '기사를 찾을 수 없습니다.'}, status=404)

        article.status = Article.Status.SAVED
        article.save()

        # TODO: 임베딩 로직 위치
        
        return JsonResponse({'message': '성공적으로 저장되었습니다.', 'status': 'SAVED'}, status=200)

    except Exception as e:
        print(f"❌ 저장 에러: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)