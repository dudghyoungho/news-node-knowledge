from django.contrib import admin
from .models import Article

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    # 1. 목록에 보여줄 컬럼들 (user 포함)
    list_display = ('id', 'title', 'user', 'status', 'created_at')
    
    # 2. 우측 사이드바 필터 (유저별, 상태별 보기)
    list_filter = ('user', 'status', 'created_at')
    
    # 3. 검색 기능 (제목, 유저 아이디로 검색 가능)
    search_fields = ('title', 'url', 'user__username', 'user__email')
    
    # 4. 클릭했을 때 수정 페이지로 넘어갈 컬럼
    list_display_links = ('title',)