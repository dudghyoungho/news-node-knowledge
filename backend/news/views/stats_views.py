# backend/news/views/stats_views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from ..models import Article

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dashboard_stats(request):
    """
    대시보드에 필요한 모든 통계 데이터를 한 번에 반환합니다.
    1. 최근 7일간 독서량 (Bar Chart)
    2. 카테고리별 비중 (Doughnut Chart)
    3. 사용자 페르소나 (Dominant Category)
    """
    user = request.user
    today = timezone.now().date()
    last_week = today - timedelta(days=6)

    # -------------------------------------------------
    # 1. 주간 독서량 (최근 7일)
    # -------------------------------------------------
    daily_counts = (
        Article.objects.filter(user=user, status=Article.Status.SAVED, created_at__date__gte=last_week)
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    
    # DB에 데이터가 없는 날짜도 0으로 채워주기 (프론트엔드 처리가 편해짐)
    daily_data_map = {item['date']: item['count'] for item in daily_counts}
    daily_result = []
    
    for i in range(7):
        target_date = last_week + timedelta(days=i)
        daily_result.append({
            "date": target_date.strftime('%m-%d'),
            "count": daily_data_map.get(target_date, 0)
        })

    # -------------------------------------------------
    # 2. 카테고리 분포 (관심사 분석)
    # -------------------------------------------------
    category_counts = (
        Article.objects.filter(user=user, status=Article.Status.SAVED)
        .values('category')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # -------------------------------------------------
    # 3. 페르소나 결정 (가장 많이 읽은 카테고리 기준)
    # -------------------------------------------------
    persona = "지식 탐험가 🔭" # 기본값
    if category_counts:
        top_category = category_counts[0]['category']
        persona_map = {
            'IT/과학': '미래 설계자 🚀',
            '경제': '시장 분석가 📈',
            '정치': '사회 전략가 ⚖️',
            '세계': '글로벌 리더 🌏',
            '사회': '휴머니스트 🤝',
            '생활/문화': '트렌드 세터 ✨'
        }
        # 매핑된 게 없으면 그냥 카테고리 이름 사용
        persona = persona_map.get(top_category, f"{top_category} 전문가 🎓")

    return Response({
        "daily_activity": daily_result,
        "category_distribution": list(category_counts),
        "persona": persona,
        "total_articles": Article.objects.filter(user=user, status=Article.Status.SAVED).count()
    })