from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from ..models import Article

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_knowledge_graph(request):
    articles = Article.objects.filter(user=request.user, status=Article.Status.SAVED)

    nodes = []
    links = []
    existing_nodes = set()

    for article in articles:
        article_id = f"article_{article.id}"
        category_name = article.category if article.category else "기타"
        category_id = f"category_{category_name}"

        if article_id not in existing_nodes:
            nodes.append({
                "id": article_id,
                "name": article.title,
                "group": 1,
                "url": article.url,
                "val": 10,
                "summary": article.summary if article.summary else "요약 내용이 없습니다.",
            })
            existing_nodes.add(article_id)

        if category_id not in existing_nodes:
            nodes.append({
                "id": category_id,
                "name": category_name,
                "group": 2,
                "url": "",
                "val": 20
            })
            existing_nodes.add(category_id)

        links.append({
            "source": article_id,
            "target": category_id,
            "value": 1
        })

    return JsonResponse({"nodes": nodes, "links": links})