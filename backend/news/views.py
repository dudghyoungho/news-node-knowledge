import json
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Article
from .crawler import fetch_naver_news
from .ai_service import summarize_stream

@csrf_exempt
@require_http_methods(["POST"])
def summarize(request):
    """
    [API] 뉴스 요약 요청
    1. URL을 받아 크롤링을 수행합니다.
    2. DB에 'PENDING(요약 중)' 상태로 저장합니다.
    3. AI 요약 결과를 실시간 스트리밍으로 반환합니다.
    """
    try:
        data = json.loads(request.body)
        url = data.get('url')

        if not url:
            return JsonResponse({'error': 'URL이 필요합니다.'}, status=400)

        # 1. 이미 저장된 기사인지 확인
        # (이미 SAVED 상태라면 요약하지 않고 알려줌)
        if Article.objects.filter(url=url, status=Article.Status.SAVED).exists():
            return JsonResponse({'message': '이미 서재에 저장된 기사입니다.', 'status': 'ALREADY_SAVED'}, status=200)

        # 2. 크롤링 수행
        crawled_data = fetch_naver_news(url)
        if not crawled_data:
            return JsonResponse({'error': '기사 본문을 가져올 수 없습니다.'}, status=500)

        # 3. DB에 저장 (또는 업데이트)
        # update_or_create: 이미 있다가 요약만 다시 요청한 경우 대응
        article, created = Article.objects.update_or_create(
            url=url,
            defaults={
                'title': crawled_data['title'],
                'content': crawled_data['content'],
                'thumbnail_url': crawled_data['thumbnail_url'],
                'status': Article.Status.PENDING, # 아직은 '확정' 아님
            }
        )

        # 4. 스트리밍 응답 생성
        # AI가 한 글자씩 뱉는 걸 그대로 브라우저에 토스합니다.
        return StreamingHttpResponse(
            summarize_stream(article.content),
            content_type='text/event-stream' # 스트리밍 표준 타입
        )

    except json.JSONDecodeError:
        return JsonResponse({'error': '잘못된 JSON 형식입니다.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def save_article(request):
    """
    [API] 저장 확정 요청
    요약을 다 읽은 사용자가 '저장' 버튼을 눌렀을 때 호출됩니다.
    상태를 PENDING -> SAVED로 변경합니다.
    """
    try:
        data = json.loads(request.body)
        url = data.get('url')

        article = Article.objects.filter(url=url).first()
        if not article:
            return JsonResponse({'error': '기사를 찾을 수 없습니다.'}, status=404)

        # 상태 변경 (내 지식으로 확정)
        article.status = Article.Status.SAVED
        article.save()

        # TODO: 여기서 나중에 임베딩(Vector) 생성 함수를 호출하면 됩니다.
        
        return JsonResponse({'message': '성공적으로 저장되었습니다.', 'status': 'SAVED'}, status=200)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)