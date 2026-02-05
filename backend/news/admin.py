from django.contrib import admin
from django.utils.html import format_html # HTML 태그 렌더링용
from .models import Article, UserActionLog

# 1. 기사(Article) 관리자 (기존 유지 + 일부 개선)
@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('id', 'region', 'title', 'category', 'user', 'status', 'created_at')
    list_filter = ('region', 'status', 'category')
    search_fields = ('title', 'url', 'user__username')
    readonly_fields = ('embedding',) # 벡터 데이터는 수정 불가

# 2. [핵심] 로그(UserActionLog) 관리자 - 메타데이터 확인용
@admin.register(UserActionLog)
class UserActionLogAdmin(admin.ModelAdmin):
    # 목록에 보여줄 컬럼들
    list_display = (
        'id', 
        'user', 
        'region', 
        'category',       # [NEW] 카테고리 확인
        'get_title',      # [NEW] 제목 (너무 길면 자름)
        'dwell_time', 
        'is_valid_view', 
        'image_preview',  # [NEW] 이미지 썸네일 미리보기
        'timestamp'
    )

    # 우측 필터 사이드바
    list_filter = (
        'region', 
        'is_valid_view', 
        'category',       # [NEW] 카테고리별로 모아보기 가능
        'timestamp'
    )

    # 검색 기능
    search_fields = ('user__username', 'article_url', 'title')

    # 상세 페이지에서 읽기 전용으로 설정 (로그는 수정하면 안 되므로)
    readonly_fields = ('timestamp', 'image_preview_large')

    # -----------------------------------------------
    # 커스텀 메서드 (Custom Methods)
    # -----------------------------------------------

    # 1. 제목이 너무 길면 잘라서 보여주기
    def get_title(self, obj):
        if not obj.title:
            return "-"
        return obj.title[:30] + "..." if len(obj.title) > 30 else obj.title
    get_title.short_description = "제목 (Title)"

    # 2. 리스트용 작은 이미지 미리보기
    def image_preview(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" style="width: 50px; height: 30px; object-fit: cover; border-radius: 4px;" />', obj.image_url)
        return "-"
    image_preview.short_description = "썸네일"

    # 3. 상세 페이지용 큰 이미지 미리보기
    def image_preview_large(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" style="max-width: 300px; height: auto;" />', obj.image_url)
        return "이미지 없음"
    image_preview_large.short_description = "이미지 원본"