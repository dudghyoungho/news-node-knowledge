from django.urls import path
from . import views

urlpatterns = [
    path('auth/google/', views.google_login, name='google_login'),

    path('summarize/', views.summarize, name='summarize'), 
    
    path('save/', views.save_article, name='save_article'),

    path('api/graph/', views.get_knowledge_graph, name='get_knowledge_graph'),
    path('api/stats/', views.get_dashboard_stats, name='dashboard_stats'),

    path('dashboard/', views.dashboard_page, name='dashboard'),
    path('graph/', views.graph_page, name='graph_view'),

    path('api/rag/context/<int:article_id>/', views.context_recommendation, name='rag_context'),
    path('api/rag/review/', views.review_recommendation, name='rag_review'),
    path('api/rag/external/', views.external_recommendation, name='rag_external'),
]