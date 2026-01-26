from django.db import models
from django.conf import settings
from pgvector.django import VectorField

class Article(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', '요약 생성 중'
        SAVED = 'SAVED', '저장 완료'
        ARCHIVED = 'ARCHIVED', '나중에 읽기'

    # [추가 1] 국가/지역 선택지 정의
    class Region(models.TextChoices):
        KR = 'KR', 'South Korea'  # 한국
        AU = 'AU', 'Australia'    # 호주

    # 0. 사용자 연결
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='articles',
        help_text="이 기사를 소유한 사용자"
    )

    # [추가 2] 국가 필드 (기본값 KR)
    # 대시보드에서 "호주 뉴스만 보기" 등으로 필터링할 때 사용됩니다.
    region = models.CharField(
        max_length=10,
        choices=Region.choices,
        default=Region.KR,
        help_text="서비스 지역 (KR: 한국, AU: 호주)"
    )

    # 1. 기본 정보
    title = models.CharField(max_length=500, help_text="기사 제목")
    url = models.URLField(db_index=True, help_text="기사 원본 링크")
    content = models.TextField(blank=True, null=True, help_text="기사 본문 (RAG 검색용)")
    
    # 2. AI 가공 정보
    summary = models.TextField(blank=True, null=True, help_text="AI 3줄 요약")
    category = models.CharField(max_length=50, blank=True, null=True, help_text="AI가 분류한 카테고리")
    
    # 3. 핵심: 벡터 데이터
    embedding = VectorField(dimensions=1536, blank=True, null=True, help_text="임베딩 벡터 데이터")

    # 4. 메타 데이터
    thumbnail_url = models.URLField(blank=True, null=True)
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="최초 생성일")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.region}] {self.title} - {self.user.username}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['url']),
            models.Index(fields=['created_at']),
            models.Index(fields=['region']), # [추가] 지역별 필터링 속도 향상
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'url'], 
                name='unique_user_article_url'
            )
        ]