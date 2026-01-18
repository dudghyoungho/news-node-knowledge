from django.db import models
from pgvector.django import VectorField  # pgvector 필드 임포트

class Article(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', '요약 생성 중'  # 아직 사용자가 '저장' 안 누름
        SAVED = 'SAVED', '저장 완료'       # 내 지식으로 확정
        ARCHIVED = 'ARCHIVED', '나중에 읽기' # 읽진 않았지만 보관

    # 1. 기본 정보
    title = models.CharField(max_length=500, help_text="기사 제목")
    url = models.URLField(unique=True, db_index=True, help_text="기사 원본 링크 (중복 방지)")
    content = models.TextField(blank=True, null=True, help_text="기사 본문 (RAG 검색용)")
    
    # 2. AI 가공 정보
    summary = models.TextField(blank=True, null=True, help_text="AI 3줄 요약")
    category = models.CharField(max_length=50, blank=True, null=True, help_text="AI가 분류한 카테고리 (IT, 경제 등)")
    
    # ★ 3. 핵심: 벡터 데이터 (OpenAI text-embedding-3-small 기준 1536차원)
    embedding = VectorField(dimensions=1536, blank=True, null=True, help_text="임베딩 벡터 데이터")

    # 4. 메타 데이터 & 통계용
    thumbnail_url = models.URLField(blank=True, null=True)
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="최초 생성일 (잔디 심기 기준)")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.status}] {self.title}"

    class Meta:
        # 최신순 정렬 기본
        ordering = ['-created_at']
        # URL 검색이 많으므로 인덱스 추가 (이미 db_index=True 했지만 명시적으로)
        indexes = [
            models.Index(fields=['url']),
            models.Index(fields=['created_at']), # 히트맵 조회 속도 향상
        ]