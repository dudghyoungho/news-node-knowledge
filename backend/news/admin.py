from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from urllib.parse import urlparse # [추가] URL 파싱용
from .models import Article, UserActionLog, UserProfile

# ... (UserProfileAdmin은 그대로 유지) ...

# ========================================================
# 2. UserActionLog - 행동 및 출처(Source) 확인 [개선됨]
# ========================================================
@admin.register(UserActionLog)
class UserActionLogAdmin(admin.ModelAdmin):
    list_display = (
        'action_badge',   
        'source_site',    # [변경] 내부/외부 -> 구체적인 출처 사이트
        'dwell_time_sec', 
        'user', 
        'title_short', 
        'timestamp',
    )
    list_filter = ('action', 'region', 'timestamp', 'category') # category 필터 추가 추천
    search_fields = ('user__username', 'article_url', 'title')
    readonly_fields = ('timestamp', 'article_link')

    # 1. 행동 타입 배지 (기존 동일)
    def action_badge(self, obj):
        colors = {
            'SAVE': '#28a745', # 초록
            'READ': '#007bff', # 파랑
            'CLICK': '#6c757d', # 회색
        }
        color = colors.get(obj.action, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 7px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = "Action"

    # 2. [핵심 변경] 출처 사이트 판별 (Source)
    def source_site(self, obj):
        if not obj.article_url:
            return "-"
        
        try:
            domain = urlparse(obj.article_url).netloc
            
            # 주요 사이트 매핑 및 색상 설정
            if 'naver.com' in domain:
                return format_html('<span style="color: #03C75A; font-weight: bold;">NAVER</span>')
            elif 'daum.net' in domain or 'kakao.com' in domain:
                return format_html('<span style="color: #F7E600; font-weight: bold; text-shadow: 0px 0px 1px #000;">Daum/Kakao</span>')
            elif 'bbc.com' in domain or 'bbc.co.uk' in domain:
                return format_html('<span style="color: #BB1919; font-weight: bold;">BBC</span>')
            elif 'cnn.com' in domain:
                return format_html('<span style="color: #CC0000; font-weight: bold;">CNN</span>')
            elif 'theguardian.com' in domain:
                return format_html('<span style="color: #052962; font-weight: bold;">The Guardian</span>')
            elif 'abc.net.au' in domain:
                return format_html('<span style="color: #000000; font-weight: bold;">ABC News</span>')
            elif 'news.com.au' in domain:
                return format_html('<span style="color: #ff424e; font-weight: bold;">News.com.au</span>')
            elif 'youtube.com' in domain:
                return format_html('<span style="color: red; font-weight: bold;">YouTube</span>')
            
            # 그 외 사이트는 도메인만 깔끔하게 표시 (www. 제거)
            clean_domain = domain.replace('www.', '').replace('m.', '')
            return format_html('<span style="color: #666;">{}</span>', clean_domain)
            
        except:
            return "?"
            
    source_site.short_description = "Source (Site)"

    # 3. 체류시간 (기존 동일)
    def dwell_time_sec(self, obj):
        style = "font-weight: bold; color: blue;" if obj.dwell_time >= 30 else ""
        return format_html('<span style="{}">{}초</span>', style, obj.dwell_time)
    dwell_time_sec.short_description = "Time"

    # 4. 제목 줄임 (기존 동일)
    def title_short(self, obj):
        if not obj.title: return "-"
        return obj.title[:30] + "..." if len(obj.title) > 30 else obj.title
    title_short.short_description = "Title"

    # 5. 연결된 기사 링크 (여전히 DB 연결 여부는 여기서 확인 가능)
    def article_link(self, obj):
        if obj.article:
            # DB에 있으면 링크 제공
            return format_html(
                '<a href="/admin/news/article/{}/change/" style="color: blue;">🔗 DB 연결됨 (ID: {})</a>', 
                obj.article.id, obj.article.id
            )
        # DB에 없으면 그냥 텍스트
        return format_html('<span style="color: #999;">- (Web Only)</span>')
    article_link.short_description = "DB Link"



# ========================================================
# 3. Article - 기사 및 벡터 상태 확인 [기존 유지+개선]
# ========================================================
@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title_short', 'category', 'status_badge', 'has_vector', 'created_at')
    list_filter = ('category', 'status', 'region', 'source')
    search_fields = ('title', 'url')
    
    # 벡터 필드는 너무 길어서 목록에서 제외하고, 상태만 표시
    exclude = ('embedding_pytorch', 'embedding_openai')
    readonly_fields = ('created_at', 'vector_status_check')

    def title_short(self, obj):
        return obj.title[:30] + "..." if len(obj.title) > 30 else obj.title
    title_short.short_description = "제목"

    def status_badge(self, obj):
        if obj.status == 'SAVED':
            return format_html('<span style="color: green;">✅ 저장됨</span>')
        return obj.status
    status_badge.short_description = "상태"

    def has_vector(self, obj):
        return obj.embedding_pytorch is not None
    has_vector.boolean = True
    has_vector.short_description = "벡터 유무"

    def vector_status_check(self, obj):
        msg = ""
        if obj.embedding_pytorch:
            msg += f"✅ PyTorch Vector (768-dim) Ready\n"
        else:
            msg += "❌ PyTorch Vector Missing\n"
            
        if obj.embedding_openai:
            msg += f"✅ OpenAI Vector (1536-dim) Ready"
        return msg
    vector_status_check.short_description = "임베딩 상세 상태"