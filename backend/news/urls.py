# backend/news/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # 1. 인증 관련
    path('auth/google/', views.google_login, name='google_login'),

    # 2. 익스텐션 기능 (크롤링/저장)
    path('summarize/', views.summarize, name='summarize'), 
    path('save/', views.save_article, name='save_article'),

    # 3. 데이터 API (JSON 반환) - 경로를 깔끔하게 정리
    # [수정] /api/news/stats/ 로 접근 가능하게 변경
    path('stats/', views.get_dashboard_stats, name='dashboard_stats'),
    
    # [수정] /api/news/graph/data/ 로 명확하게 변경 (HTML 뷰와 구분)
    path('graph/data/', views.get_knowledge_graph, name='get_knowledge_graph'),

    # 4. RAG 기능 API
    path('rag/review/', views.review_recommendation, name='rag_review'),
    path('rag/external/', views.external_recommendation, name='rag_external'),
    path('rag/context/<int:article_id>/', views.context_recommendation, name='rag_context'),

    # 5. HTML 페이지 렌더링 (Template)
    # [참고] config/urls.py 때문에 실제 주소는 /api/news/dashboard/ 가 됨.
    # 나중에 config/urls.py에서 분리하는 것을 추천하지만, 지금은 그대로 둠.
    path('dashboard/', views.dashboard_page, name='dashboard'),
    path('graph/', views.graph_page, name='graph_view'),

    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('logs/', views.LogCreateView.as_view(), name='log-create'),
]