from django.db import models
from django.conf import settings
from pgvector.django import VectorField

# ==========================================
# 1. UserProfile (User Tower) [신규 추가]
# ==========================================
class UserProfile(models.Model):
    """
    [User Tower] 유저의 실시간 취향 상태를 저장하는 모델
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    
    # [핵심] 유저의 취향 벡터 (Item Tower와 동일한 768차원)
    # 유저가 기사를 읽거나 저장할 때마다 이 벡터가 기사 벡터 방향으로 이동합니다.
    embedding_user = VectorField(dimensions=768, blank=True, null=True)
    
    # (선택사항) OpenAI 백업용 벡터 (비교 분석용, 1536차원)
    embedding_user_openai = VectorField(dimensions=1536, blank=True, null=True)
    
    # 마지막 업데이트 시간 (Time Decay 적용 시 필요)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[Profile] {self.user.username}"


# ==========================================
# 2. Article (Item Tower) [기존 유지]
# ==========================================
class Article(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', '요약 생성 중'
        SAVED = 'SAVED', '저장 완료'
        ARCHIVED = 'ARCHIVED', '나중에 읽기'

    class Region(models.TextChoices):
        KR = 'KR', 'South Korea'
        AU = 'AU', 'Australia'
    
    class Source(models.TextChoices):
        USER_SAVED = 'USER', '사용자 직접 저장'
        RSS_CRAWLED = 'RSS', 'RSS 자동 수집'

    source = models.CharField(max_length=10, choices=Source.choices, default=Source.USER_SAVED)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='articles')
    region = models.CharField(max_length=10, choices=Region.choices, default=Region.KR)

    url = models.URLField(max_length=1000, db_index=True)
    title = models.CharField(max_length=500)
    content = models.TextField(blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    
    # 벡터 데이터
    embedding_openai = VectorField(dimensions=1536, blank=True, null=True)
    embedding_pytorch = VectorField(dimensions=768, blank=True, null=True)
    
    thumbnail_url = models.URLField(max_length=1000, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.region}] {self.title}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['url']),
            models.Index(fields=['created_at']),
            models.Index(fields=['region']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['user', 'url'], name='unique_user_article_url')
        ]


# ==========================================
# 3. UserActionLog (Log Data) [보강]
# ==========================================
class UserActionLog(models.Model):
    """
    [User Log] 유저의 모든 행동(클릭, 읽기, 저장)을 기록하여
    실시간 벡터 업데이트 및 향후 AI 학습 데이터로 사용
    """
    # [추가] 행동의 종류를 명확히 구분 (가중치 부여용)
    class ActionType(models.TextChoices):
        CLICK = 'CLICK', '단순 클릭'       # 가중치: 낮음
        READ = 'READ', '정독 (체류시간 김)' # 가중치: 중간
        SAVE = 'SAVE', '요약 및 저장'      # 가중치: 높음 (가장 강력한 시그널)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='action_logs',
        db_index=True
    )

    # [보강] Article 모델과의 연결 (벡터를 바로 찾기 위해 FK 추가, 없으면 Null)
    # 크롤링된 기사라면 Article 객체와 연결하고, 외부 기사라면 Null일 수 있음
    article = models.ForeignKey(
        Article, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='logs',
        help_text="내부 DB에 존재하는 기사일 경우 연결"
    )

    article_url = models.URLField(max_length=1000, help_text="방문한 기사 URL")
    
    # [추가] 어떤 행동이었는지 기록
    action = models.CharField(
        max_length=20, 
        choices=ActionType.choices, 
        default=ActionType.CLICK
    )

    region = models.CharField(max_length=10, choices=Article.Region.choices, default=Article.Region.KR)

    # 수집 데이터 (Chrome Extension 등에서 옴)
    dwell_time = models.IntegerField(default=0, help_text="초 단위 체류시간")
    scroll_depth = models.IntegerField(default=0, help_text="스크롤 내린 깊이(%)")
    click_count = models.IntegerField(default=0)
    is_valid_view = models.BooleanField(default=False, help_text="유효한 조회 여부(예: 10초 이상)")

    # 메타 데이터
    title = models.CharField(max_length=500, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    image_url = models.URLField(max_length=1000, null=True, blank=True)
    category = models.CharField(max_length=100, default='General', null=True, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log: {self.user.username} - {self.action} ({self.dwell_time}s)"

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['article_url']),
            models.Index(fields=['action']), # 행동별 통계 뽑기 용이
        ]