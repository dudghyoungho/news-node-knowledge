# backend/news/urls.py

from django.urls import path
# [핵심] views 패키지 내부의 각 모듈을 명시적으로 임포트
from .views import (
    auth_views,
    article_views,
    stats_views,
    data_views,
    rag_views,
    page_views,
    log_views
)

urlpatterns = [
    # 1. 인증 관련 (auth_views)
    path('auth/google/', auth_views.google_login, name='google_login'),

    # 2. 익스텐션 기능 (article_views)
    path('summarize/', article_views.summarize, name='summarize'), 
    path('save/', article_views.save_article, name='save_article'),

    # 3. 데이터 API (stats_views, data_views)
    # [수정] 통계는 stats_views, 그래프 데이터는 data_views로 연결
    path('stats/', stats_views.get_dashboard_stats, name='dashboard_stats'),
    path('graph/data/', data_views.get_knowledge_graph, name='get_knowledge_graph'),

    # 4. RAG 기능 API (rag_views) - Bridge, Review, External
    path('articles/<int:article_id>/bridge/', rag_views.article_bridge_view, name='article-bridge'),
    path('rag/review/', rag_views.review_recommendation, name='rag_review'),
    path('rag/external/', rag_views.external_recommendation, name='rag_external'),
    path('rag/context/<int:article_id>/', rag_views.context_recommendation, name='rag_context'),

    # 5. HTML 페이지 렌더링 (page_views)
    path('dashboard/', page_views.dashboard_page, name='dashboard'),
    path('graph/', page_views.graph_page, name='graph_view'),
    path('privacy/', page_views.privacy_policy, name='privacy_policy'),

    # 6. 로그 관련 (log_views)
    path('logs/', log_views.LogCreateView.as_view(), name='log-create'),
]