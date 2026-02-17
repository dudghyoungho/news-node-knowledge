import numpy as np
from datetime import timedelta
from django.utils import timezone
from pgvector.django import CosineDistance
from .models import UserProfile

def update_user_vector(user, article_vector, weight=0.1):
    """
    유저가 기사를 읽거나 저장했을 때, 유저의 취향 벡터를 업데이트합니다.
    weight: 반영 비율 (CLICK=0.01, READ=0.05, SAVE=0.2 추천)
    """
    if not article_vector:
        return

    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # 1. 아직 유저 벡터가 없으면 -> 기사 벡터 그대로 복사 (초기화)
    if profile.embedding_user is None:
        profile.embedding_user = article_vector
        profile.save()
        print(f"✨ [Profile] Initialized for {user.username}")
        return

    # 2. 이동 평균 (Moving Average) 계산
    # New Vector = (Old * (1-w)) + (New * w)
    current_vec = np.array(profile.embedding_user)
    target_vec = np.array(article_vector)
    
    new_vec = (current_vec * (1 - weight)) + (target_vec * weight)
    
    # 벡터 저장
    profile.embedding_user = new_vec.tolist()
    profile.save()
    print(f"📈 [Profile] Updated for {user.username} (Weight: {weight})")



# [Scoring Weights] 비즈니스 로직에 따라 조절
WEIGHTS = {
    'VECTOR': 0.4,   # 의미적 유사성 (기본)
    'ENTITY': 0.4,   # [중요] 키워드/인물 일치 (환각 방지 핵심)
    'RECENCY': 0.1,  # 최신성 (너무 옛날 기사는 점수 깎기)
    'CATEGORY': 0.1  # 같은 카테고리 여부
}

def calculate_hybrid_score(anchor, target):
    """
    앵커 기사와 타겟 기사 간의 하이브리드 추천 점수를 계산 (0.0 ~ 1.0)
    """
    scores = {}

    # 1. Vector Score (Cosine Distance -> Similarity)
    # distance가 0.1이면 similarity는 0.9
    # DB에서 이미 distance를 계산해서 가져왔다고 가정
    vec_dist = getattr(target, 'distance', 1.0) 
    scores['vector'] = max(0, 1 - vec_dist)

    # 2. Entity Score (Jaccard Similarity)
    # 두 기사의 등장인물/조직이 얼마나 겹치는지
    anchor_ents = set(parse_entities(anchor.entities))
    target_ents = set(parse_entities(target.entities))
    
    if anchor_ents and target_ents:
        intersection = len(anchor_ents & target_ents)
        union = len(anchor_ents | target_ents)
        scores['entity'] = intersection / union if union > 0 else 0
        
        # [Bonus] 만약 교집합이 하나라도 있으면 최소 점수 보장 (스포츠 기사 억지 연결 방지)
        if intersection > 0:
            scores['entity'] = max(scores['entity'], 0.5) 
    else:
        scores['entity'] = 0.0

    # 3. Recency Score (Time Decay)
    # 날짜 차이가 클수록 점수가 낮아짐 (반감기 적용)
    days_diff = abs((anchor.created_at - target.created_at).days)
    # 예: 0일차=1.0, 30일차=0.5, 90일차=0.25 ...
    scores['recency'] = 1 / (1 + (days_diff / 30)) 

    # 4. Category Score
    scores['category'] = 1.0 if anchor.category == target.category else 0.0

    # 5. 최종 가중치 합산
    final_score = (
        scores['vector'] * WEIGHTS['VECTOR'] +
        scores['entity'] * WEIGHTS['ENTITY'] +
        scores['recency'] * WEIGHTS['RECENCY'] +
        scores['category'] * WEIGHTS['CATEGORY']
    )
    
    return final_score

# [Helper] 엔티티 파싱 (JSONField 구조에 따라 수정 필요)
def parse_entities(entity_data):
    if not entity_data:
        return []
    # 예: {'PERSON': ['손흥민', '클린스만'], 'ORG': ['토트넘']}
    all_values = []
    if isinstance(entity_data, dict):
        for key, val_list in entity_data.items():
            if isinstance(val_list, list):
                all_values.extend(val_list)
    return all_values