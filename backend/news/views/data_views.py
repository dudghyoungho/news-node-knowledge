from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from pgvector.django import CosineDistance
from ..models import Article
from itertools import combinations # [NEW] 기사 쌍(Pair) 조합을 위해 추가

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_knowledge_graph(request):
    articles = Article.objects.filter(user=request.user, status=Article.Status.SAVED)

    nodes = []
    links = []
    existing_nodes = set()
    
    entity_map = {}

    # ==========================================
    # 1. 노드 생성 및 카테고리 연결
    # ==========================================
    for article in articles:
        article_id = f"article_{article.id}"
        category_name = article.category if article.category else "기타"
        category_id = f"category_{category_name}"

        if article_id not in existing_nodes:
            nodes.append({
                "id": article_id, "name": article.title, "group": 1,
                "url": article.url, "val": 10,
                "summary": article.summary if article.summary else "요약 내용이 없습니다.",
                "img": article.thumbnail_url
            })
            existing_nodes.add(article_id)

        if category_id not in existing_nodes:
            nodes.append({
                "id": category_id, "name": category_name, "group": 2,
                "url": "", "val": 20
            })
            existing_nodes.add(category_id)

        links.append({
            "source": article_id, "target": category_id, "value": 1, "type": "category" 
        })

        # ==========================================
        # 3. 개체명(NER) 공통 키워드 수집
        # ==========================================
        if article.entities:
            extracted_entities = []
            
            if isinstance(article.entities, dict):
                for key, val_list in article.entities.items():
                    if isinstance(val_list, list):
                        extracted_entities.extend(val_list)
            elif isinstance(article.entities, list):
                extracted_entities = article.entities

            # 교집합을 찾기 위해 추출 개수를 3개에서 5개로 살짝 늘립니다.
            for entity_name in extracted_entities[:5]: 
                entity_name = str(entity_name).strip()
                if not entity_name or entity_name.startswith("_status"):
                    continue

                if entity_name not in entity_map:
                    entity_map[entity_name] = []
                # 중복 추가 방지
                if article.id not in entity_map[entity_name]:
                    entity_map[entity_name].append(article.id)

    # ==========================================
    # [NEW] 3-1. 엄격한 조건(Threshold) 기반 교집합 연결
    # ==========================================
    # 두 기사 간에 겹치는 키워드를 모아둘 딕셔너리 {(기사A, 기사B): ['키워드1', '키워드2']}
    pair_shared_entities = {}

    for entity_name, art_ids in entity_map.items():
        if len(art_ids) > 1:
            # 해당 키워드를 공유하는 기사들로 가능한 모든 두 기사 쌍(Pair) 생성
            for pair in combinations(sorted(art_ids), 2): 
                if pair not in pair_shared_entities:
                    pair_shared_entities[pair] = []
                pair_shared_entities[pair].append(entity_name)

    # 🚨 거미줄 방지 기준점: 최소 2개 이상의 키워드가 겹쳐야만 선을 긋습니다!
    MIN_SHARED_ENTITIES = 2 

    for (art_A, art_B), shared_ents in pair_shared_entities.items():
        if len(shared_ents) >= MIN_SHARED_ENTITIES:
            # 라벨 텍스트 만들기 (예: "#OpenAI, #SamAltman")
            label_str = ", ".join([f"#{e}" for e in shared_ents[:2]])
            if len(shared_ents) > 2:
                 label_str += f" +{len(shared_ents)-2}" # 3개 이상 겹치면 "+1" 등으로 축약

            links.append({
                "source": f"article_{art_A}",
                "target": f"article_{art_B}",
                "value": len(shared_ents), # 겹치는 개수에 따라 선의 가중치 부여
                "type": "shared_entity", 
                "label": label_str 
            })

    # ==========================================
    # 2. 벡터 기반 의미적 연결 (Semantic Links) 생성
    # ==========================================
    articles_with_embedding = articles.exclude(embedding_pytorch__isnull=True)
    
    DISTANCE_THRESHOLD = 0.45  
    MAX_SEMANTIC_LINKS = 1    

    for article in articles_with_embedding:
        similar_articles = articles_with_embedding.annotate(
            distance=CosineDistance('embedding_pytorch', article.embedding_pytorch)
        ).exclude(
            id=article.id 
        ).filter(
            distance__lt=DISTANCE_THRESHOLD 
        ).order_by('distance')[:MAX_SEMANTIC_LINKS] 

        for sim_art in similar_articles:
            if article.id < sim_art.id:
                links.append({
                    "source": f"article_{article.id}",
                    "target": f"article_{sim_art.id}",
                    "value": round(1 - sim_art.distance, 2), 
                    "type": "semantic" 
                })

    return JsonResponse({"nodes": nodes, "links": links})
    return JsonResponse({"nodes": nodes, "links": links})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_reading_statistics(request):
    """
    최근 7일간 날짜별 읽은(저장한) 기사 개수를 반환합니다.
    Format: [{ "date": "2024-01-22", "count": 5 }, ...]
    """
    # 1. 날짜별 그룹화 (SAVED 상태만)
    stats = Article.objects.filter(user=request.user, status=Article.Status.SAVED) \
        .annotate(date=TruncDate('created_at')) \
        .values('date') \
        .annotate(count=Count('id')) \
        .order_by('date')

    # 2. 데이터 정제 (최근 데이터만 보낸다거나 하는 로직 추가 가능)
    # 쿼리셋 결과는 date 객체이므로 문자열로 변환 필요
    result = [
        {
            "date": item['date'].strftime('%Y-%m-%d'), 
            "count": item['count']
        } 
        for item in stats
    ]

    return JsonResponse(result, safe=False)