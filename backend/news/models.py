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


# ==========================================
# 2. UserActionLog: 추천 모델 학습을 위한 행동 로그 (NEW)
# ==========================================
class UserActionLog(models.Model):
    """
    사용자가 뉴스를 읽을 때 발생하는 행동 데이터를 수집합니다.
    Article 모델과 달리, '요약'하지 않은 단순 열람 기록도 모두 포함됩니다.
    Two-Tower 추천 모델의 학습 데이터(Training Data)로 사용됩니다.
    """
    
    # [식별 정보]
    # 개인정보 보호: 이메일 등이 아닌 내부 User ID(Integer)만 외래키로 저장
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='action_logs',
        db_index=True
    )

    # [기사 정보]
    # Article 모델과 FK를 맺지 않는 이유: 
    # 사용자가 아직 '저장'하지 않은 기사(Article DB에 없는 기사)도 로그를 남겨야 하기 때문입니다.
    article_url = models.URLField(max_length=500, help_text="방문한 기사 URL")
    
    # 지역 정보 (추천 시 한국/호주 뉴스 구분용)
    region = models.CharField(
        max_length=10,
        choices=Article.Region.choices,
        default=Article.Region.KR
    )

    # [행동 지표 - Implicit Feedback]
    dwell_time = models.IntegerField(default=0, help_text="체류 시간 (초 단위)")
    scroll_depth = models.IntegerField(default=0, help_text="스크롤 깊이 (0~100%)")
    click_count = models.IntegerField(default=0, help_text="페이지 내 클릭/상호작용 횟수")
    
    # [유효성 판단]
    # 30초 이상 체류하거나 스크롤을 80% 이상 내린 경우 True (학습 시 Positive Sample로 활용)
    is_valid_view = models.BooleanField(default=False)

    # [NEW] 메타데이터 필드 추가 (수집된 정보 저장용)
    # 제목: 필수 요소에 가깝지만, 크롤링 실패 대비 null 허용
    title = models.CharField(max_length=500, null=True, blank=True)
    
    # 설명: 네이버 연예/스포츠는 없을 수 있음 -> null=True 필수
    description = models.TextField(null=True, blank=True)
    
    # 썸네일: UI용으로 있으면 좋음 (Guardian/News.com.au는 잘 줌)
    image_url = models.URLField(max_length=1000, null=True, blank=True)
    
    # 카테고리: 정치, 경제, Sport, World 등
    category = models.CharField(max_length=100, default='General', null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Log: {self.user_id} - {self.dwell_time}s - {self.article_url[:30]}..."

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            # 1. 학습 데이터 추출용: 특정 기간, 특정 유저의 로그 조회 속도 최적화
            models.Index(fields=['user', 'timestamp']),
            # 2. 기사별 인기 분석용
            models.Index(fields=['article_url']),
            # 3. 지역별 학습 데이터 분리용
            models.Index(fields=['region']),
        ]