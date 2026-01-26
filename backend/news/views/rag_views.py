from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from ..models import Article
# region 인자를 받도록 수정된 서비스 함수들 임포트
from ..rag_service import find_connected_articles, review_past_knowledge, recommend_external_articles

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def context_recommendation(request, article_id):
    """현재 글과 연관된 글 추천"""
    article = get_object_or_404(Article, id=article_id, user=request.user)
    # 기사 객체 자체에 region 정보가 있으므로 별도 파라미터 불필요
    connections = find_connected_articles(article)
    return Response(connections)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def review_recommendation(request):
    """과거의 글 복기 (Time Capsule)"""
    # [핵심] URL 파라미터에서 region 수신 (없으면 KR)
    region = request.GET.get('region', 'KR') 
    
    # 서비스 함수에 region 전달
    data = review_past_knowledge(request.user, region=region)
    
    if not data:
        msg = "No articles saved yet." if region == 'AU' else "저장된 기사가 없습니다."
        return Response({"message": msg})

    if 'message' in data:
        return Response(data)

    return Response({
        "id": data['article'].id,
        "title": data['article'].title,
        "date": data['article'].created_at.strftime('%Y-%m-%d'),
        "url": data['article'].url,
        "comment": data['comment']
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def external_recommendation(request):
    """지식 확장 (Discovery)"""
    # [핵심] URL 파라미터에서 region 수신
    region = request.GET.get('region', 'KR')
    
    # 서비스 함수에 region 전달 -> 여기서 NewsAPI(AU) vs Naver(KR) 갈림
    data = recommend_external_articles(request.user, region=region)
    return Response(data)