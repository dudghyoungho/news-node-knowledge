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

    three_months_ago = anchor.created_at - timedelta(days=90)

    # 1. [Strict] 과거 기사 우선
    candidates = Article.objects.filter(
        region=region,
        created_at__lt=anchor.created_at,
        created_at__gte=three_months_ago, # [추가] 시간 제약
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
    top_candidates = candidates.annotate(
        distance=CosineDistance('embedding_pytorch', anchor.embedding_pytorch)
    ).order_by('distance')[:5] # [변경] 상위 5개 가져옴

    final_target = None

    for cand in top_candidates:
        # 3-1. 거리 체크
        if cand.distance is None or cand.distance > 0.65:
            continue

        # 3-2. 엔티티 교집합 확인 (calculate_real_matches 함수 재사용)
        # matches 리스트가 비어있지 않으면(공통 키워드가 있으면) 합격
        matches = calculate_real_matches(anchor, cand)
        
        # [Soft News] 스포츠/연예는 엔티티 일치가 더 중요함
        if anchor.category in ['Sports', 'Entertainment']:
            if len(matches) > 0:
                final_target = cand
                break # 찾았으면 루프 종료
        else:
            # 정치/사회는 엔티티가 달라도 주제가 같으면(벡터 유사도 높으면) 의미 있을 수 있음
            # 하지만 여기서는 안전하게 엔티티 있으면 우선 선택, 없으면 가장 가까운 놈
            if len(matches) > 0:
                final_target = cand
                break
    
    # 엔티티 겹치는 게 하나도 없으면, 그냥 벡터 1등을 쓸지 말지 결정
    # (여기서는 엄격하게 '없으면 안 보여준다'로 설정하거나, 1등을 Fallback으로 사용)
    if not final_target and top_candidates:
         # 스포츠면 엔티티 없으면 아예 포기 (억지 연결 방지)
         if anchor.category in ['Sports', 'Entertainment']:
             return None
         
         # 정치는 엔티티 없어도 벡터 1등 사용 (추상적 주제 연결 가능)
         if top_candidates[0].distance <= 0.60: # 좀 더 엄격하게
             final_target = top_candidates[0]

    if not final_target:
        return None

    target = final_target

    # ---------------------------------------------------------
    # [핵심 수정] 카테고리별 프롬프트 분기 (Hard vs Soft)
    # ---------------------------------------------------------
    category = anchor.category if anchor.category else "General"
    is_soft_news = category in ['Sports', 'Entertainment', 'Life', 'Health', 'Travel']

    if region == 'KR':
        if is_soft_news:
            # [Soft News] 스포츠/연예는 '인과관계'보다 '관련 소식'으로 연결
            system_role = "너는 스포츠 및 연예계 소식을 전하는 '전문 캐스터'야."
            instruction = (
                "두 기사는 같은 팀, 인물, 혹은 비슷한 상황을 다루고 있어.\n"
                "억지로 원인을 찾지 말고, '한편 [과거 기사 핵심] 소식도 있었는데, 이번에는 [현재 기사 핵심] 상황입니다' 처럼 자연스럽게 연결해줘."
            )
        else:
            # [Hard News] 정치/경제는 '인과관계' 유지
            system_role = "너는 뉴스 기사 간의 인과관계를 분석하는 '저널리즘 에디터'야."
            instruction = (
                "과거 기사의 내용이 현재 사건의 '배경'이나 '원인'이 됨을 설명해줘.\n"
                "대신 '과거의 [핵심 키워드] 논란이 이번 결정의 배경이 되었습니다' 처럼 작성해."
            )
        
        # 공통 제약
        prompt = (
            f"[과거 기사]: {target.title}\n(요약: {target.summary})\n\n"
            f"[현재 기사]: {anchor.title}\n(요약: {anchor.summary})\n\n"
            f"[지시사항]\n{instruction}\n\n"
            f"절대 '기사 A', '기사 B'라고 부르지 마.\n"
            f"조건: 1문장, 한국어."
        )
    else: # Global (English)
        if is_soft_news:
            system_role = "You are a Sports & Entertainment Commentator."
            instruction = (
                "These articles are about the same team, player, or similar vibe.\n"
                "Don't force causality. Just connect them like: 'While [Past Event] happened recently, now [Current Event] is drawing attention.'"
            )
        else:
            system_role = "You are a Journalism Editor focusing on causality."
            instruction = (
                "Explain how the past event caused or influenced the current issue.\n"
                "Use a flow like 'The past controversy regarding [Keyword] set the stage for this decision.'"
            )

        prompt = (
            f"[Past Context]: {target.title}\n(Summary: {target.summary})\n\n"
            f"[Current Issue]: {anchor.title}\n(Summary: {anchor.summary})\n\n"
            f"[Instruction]\n{instruction}\n\n"
            f"Do NOT use 'Article A/B'. Constraint: One sentence, English."
        )

    try:
        comment = get_completion(prompt, system_role=system_role)
    except:
        comment = "관련된 소식입니다." if region == 'KR' else "Related news."

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
    # [핵심 수정] 카테고리별 프롬프트 분기 (Hard vs Soft)
    # ---------------------------------------------------------
    category = anchor.category if anchor.category else "General"
    is_soft_news = category in ['Sports', 'Entertainment', 'Life', 'Health', 'Travel']

    if region == 'KR':
        if is_soft_news:
            # [Soft News] '검증/평가'보다는 '분위기 비교/유사 사례'
            system_role = "너는 스포츠 및 대중문화 트렌드를 읽어주는 '에디터'야."
            instruction = (
                "두 기사의 분위기나 선수/팀의 상황을 가볍게 비교해줘.\n"
                "'이전의 [과거 기사 핵심] 분위기와 마찬가지로, 이번에도 [현재 기사 핵심]으로 긍정적인 흐름을 이어가고 있습니다' "
                "또는 '[과거]와 달리 이번에는 [현재] 상황입니다' 형태로 작성해."
            )
        else:
            # [Hard News] '비판/평가' 유지
            system_role = "너는 비판적 시각을 가진 '수석 논설위원'이야."
            instruction = (
                "두 기사의 내용을 비교하거나, 과거 사례를 통해 현재를 '평가'해줘.\n"
                "'이전에 우려했던 [키워드]가 현실화되었습니다' 처럼 작성해."
            )

        prompt = (
            f"[비교 대상]: {target.title}\n(요약: {target.summary})\n\n"
            f"[현재 이슈]: {anchor.title}\n(요약: {anchor.summary})\n\n"
            f"[지시사항]\n{instruction}\n\n"
            f"절대 '기사 A/B'라고 지칭하지 마.\n"
            f"조건: 1문장, 한국어."
        )

    else: # Global (English)
        if is_soft_news:
            system_role = "You are a Sports & Culture Columnist."
            instruction = (
                "Compare the vibe or situation of the team/player.\n"
                "Say something like: 'Similar to the [Past Event], the team is continuing its momentum with [Current Event].'"
            )
        else:
            system_role = "You are a Chief Editorial Writer offering critical insights."
            instruction = (
                "Compare the two events or evaluate the current issue based on the past precedent.\n"
                "Use a flow like 'Unlike the previous [Event], this time [Action] is being taken.'"
            )

        prompt = (
            f"[Comparative Context]: {target.title}\n(Summary: {target.summary})\n\n"
            f"[Current Issue]: {anchor.title}\n(Summary: {anchor.summary})\n\n"
            f"[Instruction]\n{instruction}\n\n"
            f"Do NOT use 'Article A/B'. Constraint: One sentence, English."
        )

    try:
        comment = get_completion(prompt, system_role=system_role)
    except:
        comment = "흥미로운 비교 기사입니다." if region == 'KR' else "Interesting comparison."

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