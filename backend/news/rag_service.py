import random
from datetime import timedelta
from django.utils import timezone
from pgvector.django import CosineDistance
from .models import Article
from .ai_service import get_embedding, get_completion

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
    외부 검색 API 연동 부분 (현재는 더미 데이터 반환)
    실제 서비스 시 Google Custom Search API 등을 연결해야 합니다.
    """
    # 임시 더미 데이터 (구현 테스트용)
    return [
        {
            "title": f"'{keyword}'의 미래 전망 보고서",
            "url": "https://google.com/search?q=" + keyword,
            "snippet": f"최근 {keyword} 기술이 급격히 발전하며 시장의 판도를 바꾸고 있습니다..."
        },
        {
            "title": f"{keyword} 관련 최신 트렌드 분석",
            "url": "https://google.com/search?q=" + keyword,
            "snippet": f"전문가들은 {keyword} 분야에서 새로운 기회가 창출될 것으로 예측합니다."
        }
    ]

def recommend_external_articles(user):
    """
    사용자의 최근 관심사를 분석하여 DB 밖의 새로운 글을 추천합니다.
    """
    # 1. 최근 읽은 기사 5개 가져오기
    recent_articles = Article.objects.filter(user=user).order_by('-created_at')[:5]
    
    if not recent_articles.exists():
        # 기사가 하나도 없으면 'IT 트렌드' 같은 일반적인 거 리턴
        return {"keyword": "최신 IT 트렌드", "items": []}

    recent_text = " ".join([a.title for a in recent_articles])
    
    # ★ [디버깅용] 콘솔에 AI한테 뭘 보냈는지 찍어보기
    print(f"DEBUG: AI에게 보낸 기사 제목들 -> {recent_text}")

    # 2. GPT 프롬프트 수정 (창의성 억제, 직관적 키워드 유도)
    keyword_prompt = f"""
    사용자가 최근 읽은 기사 제목들이다: "{recent_text}"
    
    이 제목들을 관통하는 **가장 핵심적인 공통 키워드** 1개를 명사로 추출해.
    절대로 제목에 없는 내용을 추론하거나 상상하지 마.
    있는 그대로의 사실에 기반한 키워드여야 해.
    (예시: 반도체, 선거, 인공지능, 부동산)
    """
    
    # temperature=0.3 으로 낮춰서 창의성을 죽임 (사실 기반)
    keyword = get_completion(keyword_prompt).strip()
    
    # 3. 외부 검색 수행
    search_results = search_web_for_articles(keyword)
    
    # 4. RAG: 검색 결과 추천 멘트 작성
    recommendations = []
    for item in search_results:
        reco_prompt = f"""
        사용자 관심 키워드: {keyword}
        발견한 외부 기사: {item['title']} - {item['snippet']}
        
        이 기사를 추천하는 이유를 한 문장으로 써줘. (친절하게)
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