import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from pgvector.django import CosineDistance

# UserActionLog를 포함하여 필요한 모델 임포트
from .models import Article, UserActionLog
from .ai_service import get_completion

logger = logging.getLogger(__name__)

# [Helper] 교집합 추출 (유지)
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

    # 2. Slot A (Origin) 실행 - 배경 지식
    slot_a = get_slot_a_origin(user, anchor, region, combined_user_ids)
    
    # 3. 중복 방지 (Anchor + Slot A 제외)
    exclude_ids = [anchor.id]
    if slot_a and slot_a.get('article'):
        exclude_ids.append(slot_a['article']['id'])

    # 4. Slot B (Verdict) 실행 - 검증/대조
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
# Slot A: [The Origin] 발단 찾기 (인과관계 중심)
# =========================================================
def get_slot_a_origin(user, anchor, region, combined_user_ids):
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

    # [Safe Guard] distance가 None이거나 너무 멀면 제외
    if not target or target.distance is None or target.distance > 0.65:
        return None

    # ---------------------------------------------------------
    # [핵심 수정] 프롬프트 고도화: 인과관계(Causality) & 지칭 금지
    # ---------------------------------------------------------
    if region == 'KR':
        system_role = "너는 뉴스 기사 간의 인과관계를 분석하는 '저널리즘 에디터'야."
        prompt = (
            f"[과거 기사]: {target.title}\n(요약: {target.summary})\n\n"
            f"[현재 기사]: {anchor.title}\n(요약: {anchor.summary})\n\n"
            f"[지시사항]\n"
            f"과거 기사의 내용이 현재 사건의 '배경'이나 '원인'이 됨을 설명해줘.\n"
            f"절대 '기사 A', '기사 B'라고 부르지 마.\n"
            f"대신 '과거의 [핵심 키워드] 논란이 이번 결정의 배경이 되었습니다' 처럼 자연스럽게 연결해.\n"
            f"조건: 1문장, 한국어."
        )
        default_comment = "이 사건의 배경이 되는 과거 뉴스입니다."
    else:
        system_role = "You are a Journalism Editor focusing on causality."
        prompt = (
            f"[Past Context]: {target.title}\n(Summary: {target.summary})\n\n"
            f"[Current Issue]: {anchor.title}\n(Summary: {anchor.summary})\n\n"
            f"[Instruction]\n"
            f"Explain how the past event caused or influenced the current issue.\n"
            f"Do NOT use terms like 'Article A' or 'Article B'.\n"
            f"Instead, say something like 'The past controversy regarding [Keyword] set the stage for this decision.'\n"
            f"Constraint: One sentence, English."
        )
        default_comment = "This past event set the stage for today's news."

    try:
        comment = get_completion(prompt, system_role=system_role)
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
# Slot B: [The Verdict] 검증하기 (비교/평가 중심)
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

    # [Safe Guard] distance 체크
    if not target or target.distance is None or target.distance > 0.65: 
        return None

    # ---------------------------------------------------------
    # [핵심 수정] 프롬프트 고도화: 대조(Contrast) & 평가(Insight)
    # ---------------------------------------------------------
    if region == 'KR':
        system_role = "너는 비판적 시각을 가진 '수석 논설위원'이야."
        prompt = (
            f"[비교 대상]: {target.title}\n(요약: {target.summary})\n\n"
            f"[현재 이슈]: {anchor.title}\n(요약: {anchor.summary})\n\n"
            f"[지시사항]\n"
            f"두 기사의 내용을 비교하거나, 과거 사례를 통해 현재를 '평가'해줘.\n"
            f"절대 '기사 A/B'라고 지칭하지 마.\n"
            f"대신 '이전에 우려했던 [키워드]가 현실화되었습니다' 또는 '[과거]와 달리 이번에는 [현재]로 대응하고 있습니다' 처럼 작성해.\n"
            f"조건: 1문장, 한국어."
        )
        default_comment = "유사한 사례와 비교하여 볼 수 있는 심층 보도입니다."
    else:
        system_role = "You are a Chief Editorial Writer offering critical insights."
        prompt = (
            f"[Comparative Context]: {target.title}\n(Summary: {target.summary})\n\n"
            f"[Current Issue]: {anchor.title}\n(Summary: {anchor.summary})\n\n"
            f"[Instruction]\n"
            f"Compare the two events or evaluate the current issue based on the past precedent.\n"
            f"Do NOT use terms like 'Article A' or 'Article B'.\n"
            f"Instead, use a flow like 'Unlike the previous [Event], this time [Action] is being taken.'\n"
            f"Constraint: One sentence, English."
        )
        default_comment = "This related report offers a contrasting perspective."

    try:
        comment = get_completion(prompt, system_role=system_role)
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