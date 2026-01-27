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
    대시보드 통계 API (다국어 페르소나 지원)
    """
    user = request.user
    # [1] 요청된 리전 확인 (기본값 KR)
    region = request.GET.get('region', 'KR') 
    
    today = timezone.now().date()
    last_week = today - timedelta(days=6)

    # -------------------------------------------------
    # 1. 주간 독서량
    # -------------------------------------------------
    daily_counts = (
        Article.objects.filter(user=user, status=Article.Status.SAVED, created_at__date__gte=last_week)
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    
    daily_data_map = {item['date']: item['count'] for item in daily_counts}
    daily_result = []
    
    for i in range(7):
        target_date = last_week + timedelta(days=i)
        daily_result.append({
            "date": target_date.strftime('%m-%d'),
            "count": daily_data_map.get(target_date, 0)
        })

    # -------------------------------------------------
    # 2. 카테고리 분포
    # -------------------------------------------------
    category_counts = (
        Article.objects.filter(user=user, status=Article.Status.SAVED)
        .values('category')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # -------------------------------------------------
    # 3. 페르소나 결정 (다국어 지원)
    # -------------------------------------------------
    # 기본값 설정
    persona = "지식 탐험가 🔭" if region == 'KR' else "Knowledge Explorer 🔭"

    if category_counts:
        # 가장 많이 읽은 카테고리 (DB에 저장된 원본 값, 예: 'Economy' or '경제')
        top_category_raw = category_counts[0]['category']
        
        # 대소문자 통일을 위해 소문자 변환 후 비교 (영어의 경우)
        top_cat_key = top_category_raw.lower() if top_category_raw else ""

        if region == 'KR':
            # [한국어 모드]
            # DB에 영어가 들어있든 한글이 들어있든 -> 한국어 페르소나 출력
            kr_map = {
                # [IT/Tech]
                'it/과학': '미래 설계자 🚀', 'it': '미래 설계자 🚀', 'science': '미래 설계자 🚀', 
                'technology': '미래 설계자 🚀', 'tech': '미래 설계자 🚀',
                # [Economy]
                '경제': '시장 분석가 📈', 'business': '시장 분석가 📈', 'economy': '시장 분석가 📈',
                # [Politics]
                '정치': '사회 전략가 ⚖️', 'politics': '사회 전략가 ⚖️',
                # [World]
                '세계': '글로벌 리더 🌏', 'world': '글로벌 리더 🌏', 'general': '글로벌 리더 🌏',
                # [Society]
                '사회': '휴머니스트 🤝', 'society': '휴머니스트 🤝', 'health': '휴머니스트 🤝',
                # [Life/Culture]
                '생활/문화': '트렌드 세터 ✨', 'entertainment': '트렌드 세터 ✨', 'sports': '트렌드 세터 ✨'
            }
            persona = kr_map.get(top_cat_key, f"{top_category_raw} 전문가 🎓")

        else:
            # [호주/영어 모드]
            # DB에 영어가 들어있든 한글이 들어있든 -> 영어 페르소나 출력
            au_map = {
                # [IT/Tech]
                'it/과학': 'Future Architect 🚀', 'it': 'Future Architect 🚀', 'science': 'Future Architect 🚀', 
                'technology': 'Future Architect 🚀', 'tech': 'Future Architect 🚀',
                # [Economy]
                '경제': 'Market Analyst 📈', 'business': 'Market Analyst 📈', 'economy': 'Market Analyst 📈',
                # [Politics]
                '정치': 'Social Strategist ⚖️', 'politics': 'Social Strategist ⚖️',
                # [World]
                '세계': 'Global Leader 🌏', 'world': 'Global Leader 🌏', 'general': 'Global Leader 🌏',
                # [Society]
                '사회': 'Humanist 🤝', 'society': 'Humanist 🤝', 'health': 'Health Expert 🏥',
                # [Life/Culture]
                '생활/문화': 'Trend Setter ✨', 'entertainment': 'Trend Setter ✨', 'sports': 'Sports Fan ⚽'
            }
            persona = au_map.get(top_cat_key, f"{top_category_raw} Expert 🎓")

    return Response({
        "daily_activity": daily_result,
        "category_distribution": list(category_counts),
        "persona": persona,
        "total_articles": Article.objects.filter(user=user, status=Article.Status.SAVED).count()
    })