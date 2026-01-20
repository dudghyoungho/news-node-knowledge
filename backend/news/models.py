from django.db import models
from django.conf import settings  # [추가] User 모델 참조를 위해 임포트
from pgvector.django import VectorField

class Article(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', '요약 생성 중'
        SAVED = 'SAVED', '저장 완료'
        ARCHIVED = 'ARCHIVED', '나중에 읽기'

    # [추가] 0. 사용자 연결 (누가 저장했는가?)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='articles',
        help_text="이 기사를 소유한 사용자"
    )

    # 1. 기본 정보
    title = models.CharField(max_length=500, help_text="기사 제목")
    
    # [수정] unique=True 제거 -> 여러 사용자가 같은 URL을 저장할 수 있어야 함
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
        # 관리자 페이지에서 보기 편하게 유저명 포함
        return f"[{self.user.username}] {self.title}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['url']),
            models.Index(fields=['created_at']),
        ]
        # [추가] 복합 유니크 제약 조건
        # "한 유저(user)는 같은 주소(url)를 중복해서 저장할 수 없다"는 규칙 생성
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'url'], 
                name='unique_user_article_url'
            )
        ]