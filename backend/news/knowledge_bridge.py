import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from pgvector.django import CosineDistance

# UserActionLog를 포함하여 필요한 모델 임포트
from .models import Article, UserActionLog
from .ai_service import get_completion

logger = logging.getLogger(__name__)

# [Helper] 교집합 추출
def calculate_real_matches(anchor, target):
    if not anchor or not target:
        return []
    if not anchor.entities or not target.entities:
        return []
    
    matches = set()
    for label in ['PERSON', 'ORG', 'GPE']:
        a_vals = set(anchor.entities.get(label, []))
        t_vals = set(target.entities.get(label, []))
        matches.update(a_vals & t_vals) 
    return list(matches)[:3]

def get_knowledge_bridge(user, current_article_id, region='KR'):
    # 1. 사용자 데이터 조회
    user_article_ids = list(UserActionLog.objects.filter(
        user=user, 
        action__in=['read', 'star', 'save']
    ).values_list('article_id', flat=True))
    
    authored_ids = list(Article.objects.filter(user=user).values_list('id', flat=True))
    combined_user_ids = list(set(user_article_ids + authored_ids))

    try:
        anchor = Article.objects.get(id=current_article_id)
    except Article.DoesNotExist:
        return None

    # 2. Slot A (Origin) 실행 - 배경 지식은 조금 느슨해도 됨 (0.75)
    slot_a = get_slot_a_origin(user, anchor, region, combined_user_ids)
    
    # 3. 중복 방지 (Anchor + Slot A 제외)
    exclude_ids = [anchor.id]
    if slot_a and slot_a.get('article'):
        exclude_ids.append(slot_a['article']['id'])

    # 4. Slot B (Verdict) 실행 - 검증은 엄격해야 함 (0.65)
    slot_b = get_slot_b_verdict(user, anchor, region, combined_user_ids, exclude_ids)
    
    return {
        "anchor": {
            "title": anchor.title,
            "summary": anchor.summary,
            "date": anchor.created_at.strftime('%Y-%m-%d'),
            "category": anchor.category or "General"
        },
        "slot_a": slot_a,
        "slot_b": slot_b
    }

# =========================================================
# Slot A: [The Origin] 발단 찾기 (Threshold: 0.75)
# =========================================================
def get_slot_a_origin(user, anchor, region, combined_user_ids):
    now = timezone.now()
    # 1. [Strict] 과거 기사 우선
    candidates = Article.objects.filter(
        region=region,
        created_at__lt=anchor.created_at, # 현재보다 과거
        embedding_pytorch__isnull=False
    ).exclude(id=anchor.id)

    # 2. [Fallback] 없으면 전체 검색
    if not candidates.exists():
        candidates = Article.objects.filter(
            region=region,
            embedding_pytorch__isnull=False
        ).exclude(id=anchor.id)

    if not candidates.exists():
        return None

    # 벡터 검색
    target = candidates.annotate(
        distance=CosineDistance('embedding_pytorch', anchor.embedding_pytorch)
    ).order_by('distance').first()

    # [기준] 배경 지식은 관련성이 조금 낮아도 허용 (0.75)
    if not target or target.distance > 0.65:
        return None

    # [AI 프롬프트 다국어 처리]
    if region == 'KR':
        prompt = (f"기사 A (과거): '{target.title}'\n기사 B (현재): '{anchor.title}'\n"
                  "기사 A가 기사 B의 배경이나 원인이 되는 이유를 한 문장으로 간략히 설명해.")
        sys_role = "너는 뉴스 역사가야."
        default_comment = "이 뉴스의 배경이 되는 기사입니다."
    else:
        prompt = (f"Article A (Past): '{target.title}'\nArticle B (Present): '{anchor.title}'\n"
                  "Explain briefly how A provides context for B in one sentence.")
        sys_role = "You are a News Historian."
        default_comment = "This article provides context for the current news."

    try:
        comment = get_completion(prompt, system_role=sys_role)
    except:
        comment = default_comment

    return {
        "article": {
            "id": target.id,
            "title": target.title,
            "url": target.url,
            "date": target.created_at.strftime('%Y-%m-%d'),
            "summary": target.summary,
            "thumbnail": target.thumbnail_url,
            "category": target.category or "General",
            "source": target.source,
            "entities": target.entities 
        },
        "comment": comment,
        "is_global": True,
        "type": "ORIGIN",
        "matches": calculate_real_matches(anchor, target)
    }


# =========================================================
# Slot B: [The Verdict] 검증하기 (Threshold: 0.65 - 엄격)
# =========================================================
def get_slot_b_verdict(user, anchor, region, combined_user_ids, exclude_ids):
    # 1. 후보군 조회 (중복 제외)
    candidates = Article.objects.filter(
        region=region,
        embedding_pytorch__isnull=False
    ).exclude(id__in=exclude_ids)

    if not candidates.exists():
        return None

    # 2. 벡터 검색
    target = candidates.annotate(
        distance=CosineDistance('embedding_pytorch', anchor.embedding_pytorch)
    ).order_by('distance').first()

    # [핵심 수정] 검증(Verdict)은 관련성이 높아야 함. 
    # 거리가 0.65보다 멀면(관련성 낮음) 차라리 안 보여주는 게 나음.
    if not target or target.distance > 0.65: 
        return None

    # [AI 프롬프트 다국어 처리]
    if region == 'KR':
        prompt = (f"기사 A: '{target.title}'\n기사 B: '{anchor.title}'\n"
                  "두 기사의 핵심 연결고리나 대조되는 점을 한 문장으로 설명해.")
        sys_role = "너는 데이터 분석가야."
        default_comment = "관련된 심층 보도입니다."
    else:
        prompt = (f"Article A: '{target.title}'\nArticle B: '{anchor.title}'\n"
                  "What is the key connection or contrast between these two? Keep it short in one sentence.")
        sys_role = "You are a Data Analyst."
        default_comment = "This is a related in-depth report."

    try:
        comment = get_completion(prompt, system_role=sys_role)
    except:
        comment = default_comment

    return {
        "article": {
            "id": target.id,
            "title": target.title,
            "url": target.url,
            "date": target.created_at.strftime('%Y-%m-%d'),
            "summary": target.summary,
            "thumbnail": target.thumbnail_url,
            "category": target.category or "General",
            "source": target.source,
            "entities": target.entities
        },
        "comment": comment,
        "is_global": True,
        "type": "VERDICT",
        "matches": calculate_real_matches(anchor, target)
    }