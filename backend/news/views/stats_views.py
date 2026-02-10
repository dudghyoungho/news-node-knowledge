import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta

# [중요] 모델이 있는 정확한 경로 확인 (보통 ..models)
from ..models import Article, UserActionLog

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dashboard_stats(request):
    """
    대시보드 통계 API
    1. Sidebar (My Knowledge): 저장된 기사(Article) 기준 통계 유지
    2. Main (Context Map): 최근 활동(UserActionLog) 기준 기사 데이터 제공
    """
    try:
        user = request.user
        region = request.GET.get('region', 'KR') 
        
        now = timezone.now()
        last_week_start = now - timedelta(days=6)

        # =================================================
        # 1. [Sidebar] 주간 활동량 (UserActionLog 사용)
        # =================================================
        # 제공해주신 UserActionLog 모델에는 'timestamp' 필드가 있습니다.
        # 기존 500 에러 원인: created_at -> timestamp 로 수정
        daily_counts = (
            UserActionLog.objects.filter(
                user=user, 
                timestamp__gte=last_week_start 
            )
            .annotate(date=TruncDate('timestamp'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        
        daily_data_map = {item['date']: item['count'] for item in daily_counts}
        daily_result = []
        
        for i in range(7):
            target_date = (last_week_start + timedelta(days=i)).date()
            daily_result.append({
                "date": target_date.strftime('%m-%d'),
                "count": daily_data_map.get(target_date, 0)
            })

        # =================================================
        # 2. [Sidebar] 카테고리 분포 (Article - SAVED 기준)
        # =================================================
        # 기존 로직 유지: '저장된' 기사의 카테고리를 분석
        # Article.Status.SAVED 대신 문자열 'SAVED'를 직접 사용하여 Enum 에러 방지
        category_counts = (
            Article.objects.filter(user=user, status='SAVED')
            .values('category')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        
        category_distribution = [
            {"category": item['category'] or "General", "count": item['count']}
            for item in category_counts
        ]

        # =================================================
        # 3. [Sidebar] 페르소나 (로직 유지)
        # =================================================
        persona = "지식 탐험가 🔭" if region == 'KR' else "Knowledge Explorer 🔭"

        if category_distribution:
            top_cat = category_distribution[0]['category']
            top_cat_key = top_cat.lower() if isinstance(top_cat, str) else "general"

            if region == 'KR':
                kr_map = {
                    'it/과학': '미래 설계자 🚀', 'it': '미래 설계자 🚀', 'science': '미래 설계자 🚀', 'technology': '미래 설계자 🚀',
                    '경제': '시장 분석가 📈', 'business': '시장 분석가 📈', 'economy': '시장 분석가 📈',
                    '정치': '사회 전략가 ⚖️', 'politics': '사회 전략가 ⚖️',
                    '세계': '글로벌 리더 🌏', 'world': '글로벌 리더 🌏',
                    '사회': '휴머니스트 🤝', 'society': '휴머니스트 🤝',
                    '생활/문화': '트렌드 세터 ✨', 'entertainment': '트렌드 세터 ✨'
                }
                persona = kr_map.get(top_cat_key, f"{top_cat} 전문가 🎓")
            else:
                au_map = {
                    'it': 'Future Architect 🚀', 'technology': 'Future Architect 🚀',
                    'business': 'Market Analyst 📈', 'economy': 'Market Analyst 📈',
                    'politics': 'Social Strategist ⚖️',
                    'world': 'Global Leader 🌏',
                    'society': 'Humanist 🤝',
                    'entertainment': 'Trend Setter ✨'
                }
                persona = au_map.get(top_cat_key, f"{top_cat} Expert 🎓")

        # =================================================
        # 4. [Main - Context Map] 최근 기사 목록 (중요!)
        # =================================================
        recent_articles = []
        seen_ids = set()

        # (1) UserActionLog 조회 (timestamp 기준 정렬)
        # Context Map은 'Article' 객체가 필요하므로 article__isnull=False 필터링 필수
        logs = UserActionLog.objects.filter(
            user=user, 
            article__isnull=False  # 내부 DB에 기사가 있는 로그만 가져옴
        ).select_related('article').order_by('-timestamp')[:10]

        for log in logs:
            if log.article.id not in seen_ids:
                recent_articles.append({
                    "id": log.article.id,
                    "title": getattr(log.article, 'title', "No Title"),
                    "url": getattr(log.article, 'url', "#"),
                    "date": log.timestamp.strftime('%Y-%m-%d'), # timestamp 사용
                    "thumbnail": getattr(log.article, 'thumbnail_url', ""), # 필드명: thumbnail_url
                    "summary": getattr(log.article, 'summary', ""),
                    "category": getattr(log.article, 'category', "General")
                })
                seen_ids.add(log.article.id)

        # (2) Fallback: 사용자 기록이 없으면(Cold Start) 전체 DB에서 최신 기사 가져오기
        # Knowledge Context Map이 무한 로딩에 걸리지 않도록 필수적임
        if len(recent_articles) < 5:
            fallback_candidates = Article.objects.filter(
                region=region
            ).exclude(id__in=seen_ids).order_by('-created_at')[:(5 - len(recent_articles))]
            
            for art in fallback_candidates:
                recent_articles.append({
                    "id": art.id,
                    "title": art.title,
                    "url": art.url,
                    "date": art.created_at.strftime('%Y-%m-%d'),
                    "thumbnail": art.thumbnail_url, # 필드명: thumbnail_url
                    "summary": art.summary,
                    "category": art.category or "General"
                })

        # =================================================
        # 5. 최종 응답
        # =================================================
        return Response({
            "daily_activity": daily_result,
            "category_distribution": category_distribution,
            "persona": persona,
            "total_articles": Article.objects.filter(user=user, status='SAVED').count(),
            "recent_articles": recent_articles  # 프론트엔드가 기다리는 핵심 데이터
        })

    except Exception as e:
        # 에러 발생 시 로그 출력 및 빈 데이터 반환 (500 페이지 방지)
        logger.error(f"❌ [Dashboard Stats Error]: {str(e)}")
        return Response({
            "error": str(e),
            "recent_articles": [],
            "daily_activity": [],
            "category_distribution": [],
            "persona": "System Error"
        }, status=200)