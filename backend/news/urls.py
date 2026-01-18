from django.urls import path
from . import views

urlpatterns = [
    path('summarize/', views.summarize, name='summarize'),
    path('save/', views.save_article, name='save_article'),
    path('admin/', admin.site.urls),
    path('api/news/', include('news.urls')),
]