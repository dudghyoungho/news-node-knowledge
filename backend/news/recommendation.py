import numpy as np
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