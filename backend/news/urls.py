# backend/news/urls.py

from django.urls import path
from . import views  # <--- 내 옆에 있는 views.py를 가져옴

urlpatterns = [
    path('summarize/', views.summarize, name='summarize'),
    path('save/', views.save_article, name='save_article'),

    path('auth/google/', views.google_login, name="google_login"),
]