"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse # 추가

# 간단한 메인 페이지 뷰 함수
def home(request):
    return HttpResponse("🚀 Journal Journey 서버가 정상 작동 중입니다!")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/news/', include('news.urls')),
    
    # 루트 경로('')에 접속하면 home 함수 실행
    path('', home), 
]
