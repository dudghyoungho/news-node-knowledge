from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from urllib.parse import urlparse
from .models import Article, UserActionLog, UserProfile

# ... (UserProfileAdmin은 그대로 유지한다고 가정) ...

# ========================================================
# 2. UserActionLog - 행동 및 출처(Source) 확인 [기존 유지]
# ========================================================
@admin.register(UserActionLog)
class UserActionLogAdmin(admin.ModelAdmin):
    list_display = (
        'action_badge',   
        'source_site',    
        'dwell_time_sec', 
        'user', 
        'title_short', 
        'timestamp',
    )
    list_filter = ('action', 'region', 'timestamp', 'category')
    search_fields = ('user__username', 'article_url', 'title')
    readonly_fields = ('timestamp', 'article_link')

    def action_badge(self, obj):
        colors = {
            'SAVE': '#28a745', 
            'READ': '#007bff', 
            'CLICK': '#6c757d', 
        }
        color = colors.get(obj.action, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 7px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = "Action"

    def source_site(self, obj):
        if not obj.article_url:
            return "-"
        try:
            domain = urlparse(obj.article_url).netloc
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
            
            clean_domain = domain.replace('www.', '').replace('m.', '')
            return format_html('<span style="color: #666;">{}</span>', clean_domain)
        except:
            return "?"
    source_site.short_description = "Source (Site)"

    def dwell_time_sec(self, obj):
        style = "font-weight: bold; color: blue;" if obj.dwell_time >= 30 else ""
        return format_html('<span style="{}">{}초</span>', style, obj.dwell_time)
    dwell_time_sec.short_description = "Time"

    def title_short(self, obj):
        if not obj.title: return "-"
        return obj.title[:30] + "..." if len(obj.title) > 30 else obj.title
    title_short.short_description = "Title"

    def article_link(self, obj):
        if obj.article:
            return format_html(
                '<a href="/admin/news/article/{}/change/" style="color: blue;">🔗 DB 연결됨 (ID: {})</a>', 
                obj.article.id, obj.article.id
            )
        return format_html('<span style="color: #999;">- (Web Only)</span>')
    article_link.short_description = "DB Link"


# ========================================================
# 3. Article - 기사 및 분류(Type) 확인 [업그레이드]
# ========================================================
@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    # [변경] type_badge 추가하여 리스트에서 바로 확인 가능
    list_display = ('title_short', 'category', 'type_badge', 'status_badge', 'has_vector', 'created_at')
    
    # [변경] article_type 필터 추가 (FACT만 보기, INSIGHT만 보기 등 가능)
    list_filter = ('article_type', 'category', 'status', 'region', 'source')
    
    search_fields = ('title', 'url')
    exclude = ('embedding_pytorch', 'embedding_openai')
    readonly_fields = ('created_at', 'vector_status_check')

    def title_short(self, obj):
        return obj.title[:30] + "..." if len(obj.title) > 30 else obj.title
    title_short.short_description = "제목"

    # [NEW] 기사 성격(Type) 배지 표시
    def type_badge(self, obj):
        # 타입별 색상 지정
        colors = {
            'FACT': '#6c757d',     # 회색 (단순 보도)
            'INSIGHT': '#6f42c1',  # 보라색 (심층 분석) - 눈에 띄게
            'OPINION': '#fd7e14',  # 주황색 (사설)
            'TUTORIAL': '#20c997', # 청록색 (가이드)
        }
        color = colors.get(obj.article_type, '#333')
        label = obj.get_article_type_display() or "-"
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color, label
        )
    type_badge.short_description = "Type"
    type_badge.admin_order_field = 'article_type' # 정렬 가능하게 설정

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