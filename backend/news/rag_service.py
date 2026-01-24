import os
import random
from datetime import timedelta
from django.utils import timezone
from pgvector.django import CosineDistance
from .models import Article
from .ai_service import get_embedding, get_completion
import requests

import numpy as np
from django.db.models import F

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX")

# ---------------------------------------------------------
# 1. 맥락 연결 (Context Connection)
# ---------------------------------------------------------
def find_connected_articles(current_article):
    """
    현재 기사와 가장 유사한 과거 기사를 찾고, 연결 고리(멘트)를 생성합니다.
    """
    # 1. 유사도 검색 (본인은 제외)
    similar_articles = Article.objects.annotate(
        distance=CosineDistance('embedding', current_article.embedding)
    ).exclude(id=current_article.id).order_by('distance')[:3] # 상위 3개

    if not similar_articles:
        return []

    results = []
    for old_article in similar_articles:
        # 2. GPT에게 연결 고리 설명 요청 (RAG Generation)
        prompt = f"""
        너는 사용자의 지식 사서야. 
        사용자가 방금 [새 기사]를 읽었어. 그런데 서재에 [과거 기사]가 있네.
        두 기사의 연관성을 1문장으로 흥미롭게 설명해줘.
        
        [새 기사]: {current_article.title} - {current_article.summary[:100]}...
        [과거 기사] (저장일: {old_article.created_at.date()}): {old_article.title} - {old_article.summary[:100]}...
        
        형식: "💡 과거의 맥락: [설명]"
        """
        
        comment = get_completion(prompt)
        
        results.append({
            "id": old_article.id,
            "title": old_article.title,
            "date": old_article.created_at.strftime('%Y-%m-%d'),
            "comment": comment
        })
        
    return results

# ---------------------------------------------------------
# 2. 지식 복기 (Review Mode) - ★ 이 부분이 누락되었었습니다
# ---------------------------------------------------------
def review_past_knowledge(user):
    """
    오래된 기사를 하나 뽑아서 '복기' 멘트를 생성합니다.
    """
    # 3개월(90일) 이상 된 기사 중 하나 랜덤 선택 (데이터가 없으면 7일로 완화)
    threshold_date = timezone.now() - timedelta(days=90)
    old_articles = Article.objects.filter(user=user, created_at__lte=threshold_date)
    
    # 만약 너무 오래된 글이 없으면, 일주일 전 글이라도 가져옴
    if not old_articles.exists():
        threshold_date = timezone.now() - timedelta(days=7)
        old_articles = Article.objects.filter(user=user, created_at__lte=threshold_date)

    if not old_articles.exists():
        return None

    target_article = random.choice(list(old_articles))

    prompt = f"""
    이 기사는 사용자가 {target_article.created_at.date()}에 저장한 글이야.
    시간이 지난 지금 시점에서, 이 기사를 다시 읽어야 할 이유를 '질문' 형태로 던져줘.
    예측이 맞았는지 확인하거나, 당시의 상황과 지금을 비교해보라는 식으로 유도해.
    
    [기사 제목]: {target_article.title}
    [기사 요약]: {target_article.summary}
    """
    
    review_comment = get_completion(prompt)
    
    return {
        "article": target_article,
        "comment": review_comment
    }

# ---------------------------------------------------------
# 3. 외부 확장 (External Discovery)
# ---------------------------------------------------------
def search_web_for_articles(keyword):
    """
    Google Custom Search API를 사용하여 실제 기사 원문 링크를 가져옵니다.
    """
    # ★ 수정된 안전한 체크 로직
    # 키가 아예 없거나(None), 빈 문자열이거나, 초기값이 들어있는 경우 체크
    is_invalid_key = (
        GOOGLE_API_KEY is None or 
        GOOGLE_API_KEY == "" or 
        "발급받은" in GOOGLE_API_KEY
    )

    if is_invalid_key: 
        return [
            {
                "title": f"[Demo] '{keyword}' 관련 기사 (API 키 설정 필요)",
                "url": f"https://www.google.com/search?q={keyword}",
                "snippet": ".env 파일에 구글 API 키를 설정하면 실제 기사 원문으로 연결됩니다."
            }
        ]

    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': GOOGLE_API_KEY,
            'cx': GOOGLE_SEARCH_CX,
            'q': keyword,
            'num': 3,
            'dateRestrict': 'm1',
            'lr': 'lang_ko' # 한국어 뉴스 중심
        }
        
        response = requests.get(url, params=params)
        
        # 응답 상태 체크
        if response.status_code != 200:
            print(f"구글 검색 API 에러: {response.text}")
            raise Exception("API Error")

        data = response.json()
        results = []
        
        if 'items' in data:
            for item in data['items']:
                results.append({
                    "title": item['title'],
                    "url": item['link'],  # ★ 여기가 바로 '기사 원문 주소'입니다!
                    "snippet": item.get('snippet', '내용 요약 없음').replace('\n', '')
                })
        
        return results

    except Exception as e:
        print(f"외부 검색 실패: {e}")
        # 실패 시 구글 검색 링크로 대체 (Fallback)
        return [
            {
                "title": f"'{keyword}' 구글 검색 결과 보기",
                "url": f"https://www.google.com/search?q={keyword}",
                "snippet": "검색 정보를 가져오는 데 실패하여 검색 페이지로 연결합니다."
            }
        ]

def recommend_external_articles(user):
    """
    [벡터 기반 알고리즘]
    사용자의 전체 관심사 벡터의 평균(Centroid)을 구하고,
    그 중심에 가장 가까운 '대표 기사'를 찾아 외부 검색 키워드를 추출합니다.
    """
    
    # 1. 사용자가 저장한 기사들의 벡터 가져오기
    saved_articles = Article.objects.filter(user=user, status=Article.Status.SAVED)
    
    if not saved_articles.exists():
        # 저장된 기사가 없으면 기본값
        return {"keyword": "최신 IT 트렌드", "items": []}

    # 2. 사용자 페르소나 벡터(평균 벡터) 계산
    # 모든 기사의 임베딩을 가져와서 numpy로 평균을 냅니다.
    embeddings = [np.array(a.embedding) for a in saved_articles if a.embedding is not None]
    
    if not embeddings:
        return {"keyword": "일반 뉴스", "items": []}

    # 축(axis=0)을 기준으로 평균을 구함 -> [0.1, 0.2, ...] 하나의 벡터가 됨
    user_persona_vector = np.mean(embeddings, axis=0).tolist()

    # 3. 평균 벡터와 가장 유사한 '나의 대표 기사' 1개 찾기
    # (내 서재 전체에서 이 평균 벡터와 거리가 가장 가까운 녀석을 찾음)
    representative_article = Article.objects.filter(user=user).annotate(
        distance=CosineDistance('embedding', user_persona_vector)
    ).order_by('distance').first()

    # 4. GPT에게 키워드 추출 요청 (대표 기사 기반)
    prompt = f"""
    이 기사는 사용자의 전체 관심사를 통계적으로 대표하는 글이다.
    
    [제목]: {representative_article.title}
    [요약]: {representative_article.summary}
    
    위 내용을 바탕으로, 이 사용자가 인터넷에서 검색해볼 만한 '심화 탐구 주제'를 
    가장 잘 나타내는 **검색 키워드 1개(명사)**만 추출해.
    추상적인 단어보다는 구체적인 기술명이나 현상 이름을 선호해.
    (예: 생성형 AI, 자율주행, 금리 인하, 양자 역학)
    """
    
    # 창의성을 낮춰서(0.3) 정확한 키워드 유도
    keyword = get_completion(prompt, temperature=0.3).strip()
    
    # 5. 외부 검색 수행 (이전과 동일)
    search_results = search_web_for_articles(keyword)
    
    # 6. 추천 멘트 생성
    recommendations = []
    for item in search_results:
        reco_prompt = f"""
        사용자 관심사 중심 키워드: {keyword}
        발견한 외부 기사: {item['title']} - {item['snippet']}
        
        이 기사를 추천하는 이유를 한 문장으로 써줘.
        """
        reason = get_completion(reco_prompt)
        recommendations.append({
            "title": item['title'],
            "url": item['url'],
            "reason": reason
        })
        
    return {
        "keyword": keyword,
        "items": recommendations
    }