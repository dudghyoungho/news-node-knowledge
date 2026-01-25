# backend/news/views/rag_views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..rag_service import find_connected_articles, review_past_knowledge, recommend_external_articles
from django.shortcuts import get_object_or_404
from ..models import Article

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def context_recommendation(request, article_id):
    """현재 보고 있는 기사(article_id)와 연관된 내 서재 글 추천"""
    article = get_object_or_404(Article, id=article_id, user=request.user)
    connections = find_connected_articles(article)
    return Response(connections)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def review_recommendation(request):
    """과거의 글 복기 추천 (대시보드용)"""
    data = review_past_knowledge(request.user)
    
    # 1. 데이터가 아예 없는 경우 (None)
    if not data:
        return Response({"message": "저장된 기사가 없습니다."})

    # 2. [수정됨] 서비스가 기사 대신 '안내 메시지'를 보낸 경우 처리
    if 'message' in data:
        return Response(data) # {"message": "아직 24시간이..."} 그대로 프론트로 전달

    # 3. 정상적으로 기사가 반환된 경우
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
    """DB 밖의 기사 추천"""
    data = recommend_external_articles(request.user)
    return Response(data)