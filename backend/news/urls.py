from django.urls import path
from . import views

urlpatterns = [
    # ------------------------------------------------------------------
    # 1. 인증 (Auth)
    # ------------------------------------------------------------------
    path('auth/google/', views.google_login, name='google_login'),

    # ------------------------------------------------------------------
    # 2. 기사 처리 (Articles)
    # ------------------------------------------------------------------
    # ★ [수정] 익스텐션 요청 주소(/api/news/summarize/)와 일치시킴
    path('summarize/', views.summarize, name='summarize'), 
    
    path('save/', views.save_article, name='save_article'),

    # ------------------------------------------------------------------
    # 3. 데이터 API (JSON)
    # ------------------------------------------------------------------
    path('api/graph/', views.get_knowledge_graph, name='get_knowledge_graph'),
    # ------------------------------------------------------------------
    # 4. 화면 렌더링 (Pages)
    # ------------------------------------------------------------------
    path('dashboard/', views.dashboard_page, name='dashboard'),
    path('graph/', views.graph_page, name='graph_view'),
]