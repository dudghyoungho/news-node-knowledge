from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from urllib.parse import urlparse
from .models import Article, UserActionLog, UserProfile

# ========================================================
# 1. UserProfile - 유저 타워 (Vector 상태 확인용)
# ========================================================
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user_info', 'vector_status', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('updated_at', 'vector_details')

    def user_info(self, obj):
        return obj.user.username
    user_info.short_description = "User"

    def vector_status(self, obj):
        if obj.embedding_user is not None:
            return format_html(
                '<span style="color: green; font-weight:bold;">✅ Active (768-dim)</span>'
            )
        return format_html('<span style="color: red;">❌ No Vector</span>')
    vector_status.short_description = "Preference Vector"

    def vector_details(self, obj):
        info = []
        if obj.embedding_user is not None:
            info.append(f"Main Vector: {len(obj.embedding_user)} dimensions")
        else:
            info.append("Main Vector: None")
            
        if obj.embedding_user_openai is not None:
            info.append(f"OpenAI Backup: {len(obj.embedding_user_openai)} dimensions")
        
        return "\n".join(info)
    vector_details.short_description = "Vector Meta Info"


# ========================================================
# 2. Article - 아이템 타워 (분류 및 인사이트 시각화)
# ========================================================
@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    # [수정] entities_summary 추가 (NER 결과 확인용)
    list_display = (
        'id',
        'type_badge',       
        'category_colored',
        'entities_summary', # [New] NER 요약 컬럼 추가
        'source_display',   
        'title_short', 
        'region_flag',      
        'status_icon',      
        'vector_check',     
        'created_at_fmt'
    )
    
    list_filter = (
        'article_type', 
        'category',     
        'region',       
        'status', 
        'source',       
        'created_at'
    )
    
    search_fields = ('title', 'url', 'summary')
    exclude = ('embedding_pytorch', 'embedding_openai') 
    
    # [수정] entities 필드를 상세 화면에서 볼 수 있도록 readonly_fields에 추가
    readonly_fields = ('created_at', 'updated_at', 'vector_info', 'entities')
    list_per_page = 20

    # -----------------------------------------------------
    # [New] NER 개체명 요약 표시
    # -----------------------------------------------------
    def entities_summary(self, obj):
        if not obj.entities:
            return format_html('<span style="color: #ccc;">-</span>')
        
        html = []
        # 주요 라벨에 대한 색상 지정
        label_colors = {
            'PERSON': '#007bff',  # 파란색 (인물)
            'ORG':    '#28a745',  # 초록색 (조직/기업)
            'GPE':    '#dc3545',  # 빨간색 (국가/도시)
        }
        
        # entities 딕셔너리 순회
        for label, items in obj.entities.items():
            if not items: continue
            
            color = label_colors.get(label, '#6c757d') # 기본 회색
            count = len(items)
            # 툴팁(title 속성)에 실제 추출된 단어들을 5개까지만 보여줌
            tooltip = ", ".join(items[:10])
            
            tag = (
                f'<span title="{tooltip}" style="background-color: {color}; color: white; '
                f'padding: 2px 6px; border-radius: 10px; font-size: 10px; margin-right: 4px; font-weight: bold; cursor: help;">'
                f'{label} {count}</span>'
            )
            html.append(tag)
            
        return format_html("".join(html))
    
    entities_summary.short_description = "NER (Keywords)"

    # -----------------------------------------------------
    # 1. 기사 성격 (Type) 배지
    # -----------------------------------------------------
    def type_badge(self, obj):
        styles = {
            'FACT':     ('background-color: #e2e6ea; color: #495057;', '📰 FACT'),
            'INSIGHT':  ('background-color: #6f42c1; color: white;',    '💡 INSIGHT'), 
            'OPINION':  ('background-color: #fd7e14; color: white;',    '🗣️ OPINION'),
            'TUTORIAL': ('background-color: #20c997; color: white;',    '📚 GUIDE'),
        }
        style, label = styles.get(obj.article_type, ('background-color: #fff; border: 1px solid #ddd;', '-'))
        
        return format_html(
            '<div style="{} padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; text-align: center; width: 80px;">{}</div>',
            style, label
        )
    type_badge.short_description = "Type"
    type_badge.admin_order_field = 'article_type'

    # -----------------------------------------------------
    # 2. 카테고리 색상 코드
    # -----------------------------------------------------
    def category_colored(self, obj):
        colors = {
            'Economy':    '#007bff', 
            'Technology': '#28a745', 
            'Society':    '#fd7e14', 
            'Life':       '#e83e8c', 
            'Sports':     '#17a2b8', 
            'General':    '#6c757d', 
        }
        color = colors.get(obj.category, '#333')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.category
        )
    category_colored.short_description = "Category"

    # -----------------------------------------------------
    # 3. 출처 표시
    # -----------------------------------------------------
    def source_display(self, obj):
        if obj.source == 'RSS':
            return format_html('<span style="color: #6610f2; font-weight: bold;">📡 RSS</span>')
        return format_html('<span style="color: #28a745; font-weight: bold;">👤 User</span>')
    source_display.short_description = "Source"

    # -----------------------------------------------------
    # 유틸리티
    # -----------------------------------------------------
    def region_flag(self, obj):
        flags = {'KR': '🇰🇷', 'AU': '🇦🇺'}
        return flags.get(obj.region, obj.region)
    region_flag.short_description = "Region"

    def title_short(self, obj):
        title = obj.title or "No Title"
        short = title[:30] + "..." if len(title) > 30 else title
        return format_html('<a href="{}" target="_blank" title="{}">{}</a>', obj.url, title, short)
    title_short.short_description = "Title (Click)"

    def status_icon(self, obj):
        icons = {'SAVED': '✅', 'PENDING': '⏳', 'ARCHIVED': '📦'}
        return icons.get(obj.status, obj.status)
    status_icon.short_description = "Stat"

    def vector_check(self, obj):
        color = "#28a745" if obj.embedding_pytorch is not None else "#dee2e6"
        return format_html('<div style="width: 12px; height: 12px; background-color: {}; border-radius: 50%; margin: 0 auto;"></div>', color)
    vector_check.short_description = "Vec"

    def created_at_fmt(self, obj):
        local_time = timezone.localtime(obj.created_at)
        return local_time.strftime("%m-%d %H:%M")
    
    created_at_fmt.short_description = "Published At"
    created_at_fmt.admin_order_field = 'created_at'

    def vector_info(self, obj):
        info = []
        if obj.embedding_pytorch is not None:
            info.append(f"✅ S-RoBERTa Vector Loaded (Length: {len(obj.embedding_pytorch)})")
        else:
            info.append("❌ No Local Vector")
        return "\n".join(info)


# ========================================================
# 3. UserActionLog - 행동 로그
# ========================================================
@admin.register(UserActionLog)
class UserActionLogAdmin(admin.ModelAdmin):
    list_display = (
        'action_badge',   
        'source_site_badge', 
        'category_badge',
        'dwell_time_sec', 
        'user', 
        'title_short', 
        'article_link_status', 
        'created_at_fmt',
    )
    list_filter = ('action', 'region', 'timestamp', 'category')
    search_fields = ('user__username', 'article_url', 'title')
    readonly_fields = ('timestamp', 'article_link_detail')

    def action_badge(self, obj):
        colors = {
            'SAVE':  '#28a745', 
            'READ':  '#007bff', 
            'CLICK': '#6c757d', 
        }
        color = colors.get(obj.action, '#333')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = "Action"

    def source_site_badge(self, obj):
        if not obj.article_url: return "-"
        try:
            domain = urlparse(obj.article_url).netloc
            styles = {
                'naver.com': ('#03C75A', '#fff', 'NAVER'),
                'daum.net': ('#F7E600', '#333', 'Daum'),
                'mk.co.kr': ('#F37021', '#fff', '매경'),
                'theguardian.com': ('#052962', '#fff', 'Guardian'),
                'medium.com': ('#000', '#fff', 'Medium'),
            }
            
            for key, (bg, fg, name) in styles.items():
                if key in domain:
                    return format_html(
                        '<span style="background-color: {}; color: {}; padding: 2px 6px; border-radius: 3px; font-size: 10px;">{}</span>',
                        bg, fg, name
                    )
            
            clean_domain = domain.replace('www.', '')
            return format_html('<span style="color: #666; font-size: 11px;">{}</span>', clean_domain)
        except:
            return "?"
    source_site_badge.short_description = "Source"

    def category_badge(self, obj):
        colors = {
            'Economy': '#007bff', 'Technology': '#28a745',
            'Society': '#fd7e14', 'Sports': '#17a2b8'
        }
        color = colors.get(obj.category, '#666')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.category or '-')
    category_badge.short_description = "Category"

    def dwell_time_sec(self, obj):
        if obj.dwell_time >= 30:
            return format_html('<span style="color: #007bff; font-weight: bold;">{}s</span>', obj.dwell_time)
        return format_html('<span style="color: #888;">{}s</span>', obj.dwell_time)
    dwell_time_sec.short_description = "Time"

    def article_link_status(self, obj):
        if obj.article:
            return format_html(
                '<a href="/admin/news/article/{}/change/" style="color: blue; font-weight:bold;">🔗 Linked (ID:{})</a>',
                obj.article.id, obj.article.id
            )
        return format_html('<span style="color: #aaa;">- (Web Only)</span>')
    article_link_status.short_description = "DB Link"

    def article_link_detail(self, obj):
        if obj.article:
            return format_html(
                '<a href="/admin/news/article/{}/change/">Go to Article #{}</a>',
                obj.article.id, obj.article.id
            )
        return "Not linked to an internal Article object."

    def title_short(self, obj):
        if not obj.title: return "-"
        return obj.title[:20] + "..." if len(obj.title) > 20 else obj.title
    title_short.short_description = "Title"

    def created_at_fmt(self, obj):
        return obj.timestamp.strftime("%m-%d %H:%M")
    created_at_fmt.short_description = "Time"