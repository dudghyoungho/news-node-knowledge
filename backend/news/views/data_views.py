import numpy as np
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from ..models import Article

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_knowledge_graph(request):
    # 1. 기사 가져오기 (임베딩이 있는 것만 필터링하면 더 좋지만, 없으면 계산에서 제외)
    articles = Article.objects.filter(user=request.user, status=Article.Status.SAVED)

    nodes = []
    links = []
    existing_nodes = set()

    # --- [A] 노드 및 카테고리 링크 생성 (기존 로직 + type 추가) ---
    for article in articles:
        article_id = f"article_{article.id}"
        # 카테고리가 없으면 '기타', 객체라면 이름 추출 (문자열 변환 안전 장치)
        category_name = str(article.category) if article.category else "기타"
        category_id = f"category_{category_name}"

        # 1. 기사 노드 생성
        if article_id not in existing_nodes:
            nodes.append({
                "id": article_id,
                "name": article.title,
                "group": 1,
                "url": article.url,
                "val": 10,
                "summary": article.summary if article.summary else "요약 내용이 없습니다.",
                "img": article.thumbnail_url,
            })
            existing_nodes.add(article_id)

        # 2. 카테고리 노드 생성
        if category_id not in existing_nodes:
            nodes.append({
                "id": category_id,
                "name": category_name,
                "group": 2,
                "url": "",
                "val": 20
            })
            existing_nodes.add(category_id)

        # 3. [Type 명시] 카테고리 연결 (실선용)
        links.append({
            "source": article_id,
            "target": category_id,
            "value": 1,
            "type": "category"  # ★ 프론트엔드에서 실선으로 구분
        })

    # --- [B] 의미적 연결 (Semantic Linking) 추가 ---
    # 임베딩이 존재하는 기사만 추려서 리스트로 변환
    article_list = [a for a in articles if a.embedding is not None]
    
    # 기사끼리 1:1 비교 (O(N^2)) - 개인 서재 규모에서는 충분히 빠름
    for i in range(len(article_list)):
        for j in range(i + 1, len(article_list)):
            art_a = article_list[i]
            art_b = article_list[j]

            # 1. 같은 카테고리는 이미 실선으로 연결됐으므로 제외 (선택사항)
            #    (유령 연결은 서로 다른 카테고리일 때 가장 효과적입니다)
            if art_a.category == art_b.category:
                continue

            # 2. 코사인 유사도 계산
            vec_a = np.array(art_a.embedding)
            vec_b = np.array(art_b.embedding)

            norm_a = np.linalg.norm(vec_a)
            norm_b = np.linalg.norm(vec_b)

            # 0으로 나누기 방지
            if norm_a == 0 or norm_b == 0:
                continue

            similarity = np.dot(vec_a, vec_b) / (norm_a * norm_b)

            # 3. 임계값 체크 (0.78 이상이면 '맥락'이 같다고 판단)
            if similarity > 0.78:
                links.append({
                    "source": f"article_{art_a.id}",
                    "target": f"article_{art_b.id}",
                    "value": 0.5,      # 연결 강도 (약하게)
                    "type": "semantic" # ★ 프론트엔드에서 점선으로 구분
                })

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