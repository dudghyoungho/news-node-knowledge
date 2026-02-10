from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from ..models import Article

# 서비스 로직 임포트
from ..rag_service import (
    find_connected_articles,
    review_past_knowledge, 
    recommend_external_articles, 
    recommend_mixed_portfolio
)
from ..knowledge_bridge import get_knowledge_bridge

# ------------------------------------------------------------------
# Helper: 기사 객체 직렬화 (프론트엔드 렌더링 오류 방지)
# ------------------------------------------------------------------
def serialize_article_simple(article):
    """
    Article 객체(ORM) 또는 Dictionary 데이터를 프론트엔드용 JSON으로 변환.
    데이터 누락으로 인한 JS 오류를 방지하기 위해 기본값을 보장함.
    """
    if not article: return None
    
    # 1. Dictionary 형태인 경우 (knowledge_bridge에서 1차 가공된 데이터)
    if isinstance(article, dict): 
        return {
            "id": article.get('id'),
            "title": article.get('title', "No Title"),
            "summary": article.get('summary', ""), # 누락 시 빈 문자열
            "url": article.get('url', "#"),
            "thumbnail": article.get('thumbnail', ""), # 누락 시 빈 문자열 -> 프론트에서 기본 이미지 처리
            "date": article.get('date', ""),
            "category": article.get('category', "General"),
            "source": article.get('source', "Web"),
            "entities": article.get('entities', {})
        }
    
    # 2. Django ORM 객체인 경우
    return {
        "id": article.id,
        "title": article.title,
        "summary": article.summary,
        "url": article.url,
        "thumbnail": getattr(article, 'thumbnail_url', ""),
        "date": article.created_at.strftime('%Y-%m-%d'),
        "category": article.category or "General",
        "source": getattr(article, 'source', "Web"),
        "entities": article.entities or {}
    }

# ------------------------------------------------------------------
# Helper: 교집합 키워드 찾기 (UI 상단 #태그 표시용)
# ------------------------------------------------------------------
def find_shared_keywords(obj_a, obj_b):
    """
    두 객체(ORM 또는 Dict) 간의 공통 개체명(PERSON, ORG, GPE)을 추출
    """
    if not obj_a or not obj_b:
        return []
    
    # obj_a 엔티티 추출
    if isinstance(obj_a, dict):
        ents_a = obj_a.get('entities', {}) or {}
    else:
        ents_a = getattr(obj_a, 'entities', {}) or {}

    # obj_b 엔티티 추출
    if isinstance(obj_b, dict):
        ents_b = obj_b.get('entities', {}) or {}
    else:
        ents_b = getattr(obj_b, 'entities', {}) or {}

    matches = set()
    target_labels = ['PERSON', 'ORG', 'GPE']
    
    for label in target_labels:
        list_a = ents_a.get(label, []) or []
        list_b = ents_b.get(label, []) or []
        
        # 교집합 계산
        common = set(list_a) & set(list_b)
        matches.update(common)
    
    return list(matches)[:3]

# ------------------------------------------------------------------
# View 1: Knowledge Bridge (최종 연동 버전)
# ------------------------------------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def article_bridge_view(request, article_id):
    """
    [Knowledge Bridge]
    특정 기사를 읽을 때 필요한 모든 정보(Anchor, Slot A, Slot B)를 한 번에 반환
    """
    region = request.GET.get('region', 'KR')
    anchor = get_object_or_404(Article, id=article_id)

    # 1. 서비스 호출
    bridge_data = get_knowledge_bridge(request.user, article_id, region=region)
    
    response_data = {
        "anchor": serialize_article_simple(anchor),
        "slot_a": None,
        "slot_b": None
    }
    
    if not bridge_data:
        return Response(response_data)

    # 2. Slot A 가공
    if bridge_data.get('slot_a'):
        slot_a = bridge_data['slot_a']
        target_a = slot_a['article']
        
        # [최적화] 서비스 레이어에서 이미 matches를 계산했다면 그것을 사용
        keywords = slot_a.get('matches')
        if not keywords: # 없으면 여기서 계산 (Fallback)
            keywords = find_shared_keywords(anchor, target_a)

        response_data['slot_a'] = {
            "article": serialize_article_simple(target_a),
            "comment": slot_a['comment'],
            "is_global": slot_a['is_global'],
            "type": slot_a.get('type', 'ORIGIN'),
            "matches": keywords
        }

    # 3. Slot B 가공
    if bridge_data.get('slot_b'):
        slot_b = bridge_data['slot_b']
        target_b = slot_b['article']

        # [최적화] 서비스 레이어에서 이미 matches를 계산했다면 그것을 사용
        keywords = slot_b.get('matches')
        if not keywords:
            keywords = find_shared_keywords(anchor, target_b)
        
        response_data['slot_b'] = {
            "article": serialize_article_simple(target_b),
            "comment": slot_b['comment'],
            "is_global": slot_b['is_global'],
            "type": slot_b.get('type', 'VERDICT'),
            "matches": keywords
        }

    return Response(response_data)


# ------------------------------------------------------------------
# View 2: Context Recommendation (유사 기사)
# ------------------------------------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def context_recommendation(request, article_id):
    article = get_object_or_404(Article, id=article_id) 
    connections = find_connected_articles(article)
    return Response(connections)


# ------------------------------------------------------------------
# View 3: Review Past Knowledge (과거 복기)
# ------------------------------------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def review_recommendation(request):
    region = request.GET.get('region', 'KR') 
    data = review_past_knowledge(request.user, region=region)
    
    if not data or 'message' in data:
        msg = data.get('message', "No articles saved yet.")
        return Response({"message": msg, "mode": "empty"})

    target_article = data['article'] # ORM 객체
    
    response_payload = {
        "mode": data.get('mode', 'random'),
        "comment": data['comment'],
        "article": serialize_article_simple(target_article)
    }

    # Time Capsule에서 'Insight Linker' 모드일 경우 연결성 계산
    if 'related_article' in data and data['related_article']:
        related = data['related_article'] # ORM 객체
        response_payload['related_article'] = serialize_article_simple(related)
        response_payload['matches'] = find_shared_keywords(related, target_article)

    return Response(response_payload)


# ------------------------------------------------------------------
# View 4: External Discovery (외부 추천)
# ------------------------------------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def external_recommendation(request):
    region = request.GET.get('region', 'KR')
    
    # rag_service 내부에서 이미 직렬화된 dict 리스트를 반환한다고 가정
    search_data = recommend_external_articles(request.user, region=region)
    vector_data = recommend_mixed_portfolio(request.user, region=region, limit=3)
    
    return Response({
        "status": "success",
        "region": region,
        "search_recommendations": search_data, 
        "vector_recommendations": vector_data 
    })