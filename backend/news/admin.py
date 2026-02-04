from django.contrib import admin
from .models import Article, UserActionLog

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


@admin.register(UserActionLog)
class UserActionLogAdmin(admin.ModelAdmin):
    # 1. 목록에 보여질 컬럼들 (가독성 향상)
    list_display = (
        'id', 
        'user', 
        'region', 
        'dwell_time', 
        'scroll_depth', 
        'is_valid_view', 
        'timestamp'
    )

    # 2. 우측 사이드바 필터 (데이터 분석용)
    list_filter = (
        'region',           # 국가별 필터
        'is_valid_view',    # 유효/무효 로그 필터
        'timestamp',        # 날짜별 필터
    )

    # 3. 검색창 설정 (유저네임, 기사 URL 검색)
    search_fields = (
        'user__username',   # 사용자명으로 검색
        'article_url',      # URL로 검색
    )

    # 4. (선택사항) 로그 데이터는 수정보다는 조회가 주 목적이므로 읽기 전용으로 설정
    # readonly_fields = ('timestamp',)