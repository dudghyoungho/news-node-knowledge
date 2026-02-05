from django.db import models
from django.conf import settings
from pgvector.django import VectorField

class Article(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', '요약 생성 중'
        SAVED = 'SAVED', '저장 완료'
        ARCHIVED = 'ARCHIVED', '나중에 읽기'

    class Region(models.TextChoices):
        KR = 'KR', 'South Korea'
        AU = 'AU', 'Australia'
    
    class Source(models.TextChoices):
        USER_SAVED = 'USER', '사용자 직접 저장'  # 유저가 확장프로그램/앱에서 저장
        RSS_CRAWLED = 'RSS', 'RSS 자동 수집'   # 서버가 긁어온 추천 후보군

    source = models.CharField(
        max_length=10,
        choices=Source.choices,
        default=Source.USER_SAVED,
        help_text="기사 수집 출처 (RSS: 추천 후보군, USER: 사용자 보관함)"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='articles',
        help_text="이 기사를 소유한 사용자"
    )

    region = models.CharField(
        max_length=10,
        choices=Region.choices,
        default=Region.KR,
        help_text="서비스 지역"
    )

    # [수정 1] URL은 생각보다 깁니다. 200자(기본) -> 1000자로 확장
    url = models.URLField(
        max_length=1000, 
        db_index=True, 
        help_text="기사 원본 링크"
    )
    
    title = models.CharField(max_length=500, help_text="기사 제목")
    content = models.TextField(blank=True, null=True, help_text="기사 본문")
    
    # 3줄 요약
    summary = models.TextField(blank=True, null=True, help_text="AI 3줄 요약")
    
    # [수정 2] 카테고리 계층구조(예: World > Asia > Korea) 대비 50 -> 100 확장
    category = models.CharField(max_length=100, blank=True, null=True, help_text="AI 분류")
    
    # 벡터 데이터 (OpenAI: 1536차원)
    embedding = VectorField(dimensions=1536, blank=True, null=True)

    # [수정 3] ★ 핵심 수정 ★: 썸네일 URL 200자 -> 1000자 확장
    # Guardian 등의 이미지 URL은 해시값이 포함되어 500자도 넘을 수 있음
    thumbnail_url = models.URLField(max_length=1000, blank=True, null=True)
    
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.region}] {self.title} - {self.user.username}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # URL 인덱싱 시, Postgres는 긴 문자열에 대해 B-Tree 인덱스 제한이 있을 수 있으나
            # 1000자 정도는 일반적으로 처리되거나 해시 인덱스로 자동 처리됨.
            models.Index(fields=['url']),
            models.Index(fields=['created_at']),
            models.Index(fields=['region']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'url'], 
                name='unique_user_article_url'
            )
        ]


# ==========================================
# 2. UserActionLog
# ==========================================
class UserActionLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='action_logs',
        db_index=True
    )

    # [수정 4] 여기도 Article과 맞춰서 1000자로 넉넉하게 잡는 게 안전함
    article_url = models.URLField(max_length=1000, help_text="방문한 기사 URL")
    
    region = models.CharField(
        max_length=10,
        choices=Article.Region.choices,
        default=Article.Region.KR
    )

    dwell_time = models.IntegerField(default=0)
    scroll_depth = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)
    is_valid_view = models.BooleanField(default=False)

    title = models.CharField(max_length=500, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    # 이미 잘 설정하셨음 (1000자)
    image_url = models.URLField(max_length=1000, null=True, blank=True)
    
    category = models.CharField(max_length=100, default='General', null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log: {self.user_id} - {self.dwell_time}s"

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['article_url']),
            models.Index(fields=['region']),
        ]