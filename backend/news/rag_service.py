import os
import requests
import logging
import re
import html
import random
import numpy as np
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from .models import Article
from .ai_service import get_completion  # ai_service에서 가져오기
from pgvector.django import CosineDistance


# 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ---------------------------------------------------------
# 1. [Helper] HTML 태그 제거
# ---------------------------------------------------------
def clean_html(raw_html):
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return html.unescape(cleantext)

# ---------------------------------------------------------
# 2. [Search] 검색 엔진 (Naver & NewsAPI 분기)
# ---------------------------------------------------------
def search_naver(keyword):
    """ 한국 뉴스 검색 (네이버) """
    client_id = settings.NAVER_CLIENT_ID
    client_secret = settings.NAVER_CLIENT_SECRET
    
    if not client_id or not client_secret:
        return []

    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {"query": keyword, "display": 5, "sort": "sim"}

    try:
        response = requests.get(url, headers=headers, params=params)
        items = response.json().get("items", [])
        
        results = []
        for item in items:
            link = item.get("link", "")
            # 네이버 뉴스 포털 링크 우선 필터링 (요약 품질 위해)
            if "news.naver.com" not in link:
                continue
                
            results.append({
                "title": clean_html(item.get("title", "")),
                "link": link,
                "pubDate": item.get("pubDate", ""),
                "source": "Naver News"
            })
        return results
    except Exception as e:
        logger.error(f"Naver Search Error: {e}")
        return []

def search_newsapi(keyword):
    """ 
    호주/글로벌 뉴스 검색 (NewsAPI) 
    - [수정 1] 신뢰할 수 있는 언론사(도메인) 필터링 적용
    - [수정 2] summary 필드 매핑 (내용 표시)
    """
    api_key = os.environ.get("NEWSAPI_KEY") 
    if not api_key:
        logger.warning("NewsAPI Key missing")
        return []

    url = "https://newsapi.org/v2/everything"
    
    # ★ 신뢰할 수 있는 언론사 도메인 리스트 (호주 중심 + 글로벌 메이저)
    # abc.net.au (호주 공영), smh.com.au (시드니 모닝 헤럴드), theage.com.au (디 에이지)
    # bbc.com, reuters.com, bloomberg.com, cnn.com, theguardian.com
    trusted_domains = (
        "abc.net.au,smh.com.au,theage.com.au,"
        "bbc.com,reuters.com,bloomberg.com,cnn.com,theguardian.com,"
        "nytimes.com,wsj.com,cnbc.com"
    )

    params = {
        "q": keyword,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": 5,
        "domains": trusted_domains, # ★ 여기서 언론사를 강제합니다.
        "apiKey": api_key
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        # 에러 체크
        if data.get("status") != "ok":
            logger.error(f"NewsAPI Error: {data.get('message')}")
            return []

        articles = data.get("articles", [])
        
        results = []
        for item in articles:
            # 내용이 없으면 건너뛰기
            description = item.get("description")
            if not description:
                continue

            results.append({
                "title": item.get("title"),
                "link": item.get("url"),
                "pubDate": item.get("publishedAt", "")[:10],
                "source": item.get("source", {}).get("name", "NewsAPI"),
                
                # ★ [핵심 수정] 프론트엔드가 'summary'를 찾으므로 여기에 할당
                "summary": description, 
                "snippet": description  # 혹시 몰라 snippet에도 넣어둠
            })
        return results
    except Exception as e:
        logger.error(f"NewsAPI Request Exception: {e}")
        return []

# ---------------------------------------------------------
# 3. [Feature] DB 내부 연관 기사 추천 (find_connected_articles)
# ---------------------------------------------------------
def find_connected_articles(target_article):
    """
    현재 읽는 기사와 유사한 내 서재의 기사를 찾습니다.
    (같은 국가 region 기사끼리만 매칭)
    """
    if not target_article.embedding:
        return []

    # [수정] 같은 유저 + SAVED + ★같은 Region★
    user_articles = Article.objects.filter(
        user=target_article.user, 
        status=Article.Status.SAVED,
        region=target_article.region
    ).exclude(id=target_article.id).exclude(embedding__isnull=True)

    target_vec = np.array(target_article.embedding)
    recommendations = []

    for article in user_articles:
        current_vec = np.array(article.embedding)
        
        # 코사인 유사도 계산
        norm_a = np.linalg.norm(target_vec)
        norm_b = np.linalg.norm(current_vec)
        
        if norm_a == 0 or norm_b == 0: continue
        
        similarity = np.dot(target_vec, current_vec) / (norm_a * norm_b)
        
        # 유사도 0.75 이상인 글만 추천
        if similarity > 0.75: 
            recommendations.append({
                "id": article.id,
                "title": article.title,
                "similarity": round(float(similarity), 2),
                "summary": article.summary
            })
    
    # 유사도 높은 순 정렬 후 상위 3개 반환
    recommendations.sort(key=lambda x: x['similarity'], reverse=True)
    return recommendations[:3]

# ---------------------------------------------------------
# 4. [Feature] 과거 기사 복기 (review_past_knowledge)
# ---------------------------------------------------------
def review_past_knowledge(user, region='KR'):
    """
    [Upgrade] 3가지 페르소나(퀴즈/토론/실천) 복기.
    Region에 따라 언어(한글/영어)와 말투를 변경.
    """
    now = timezone.now()
    threshold_time = now - timedelta(days=1) 

    # 1. 대상 기사 선정 (해당 Region + SAVED + 24시간 경과)
    candidates = Article.objects.filter(
        user=user, 
        created_at__lte=threshold_time, 
        status=Article.Status.SAVED,
        region=region
    )
    
    # (Fallback) 없으면 전체 SAVED 중 해당 Region
    if not candidates.exists():
        candidates = Article.objects.filter(
            user=user, 
            status=Article.Status.SAVED,
            region=region
        )

    if not candidates.exists():
        msg = "No articles saved yet." if region == 'AU' else "아직 저장된 기사가 없습니다."
        return {"message": msg}

    target = random.choice(list(candidates))

    # 2. 페르소나 랜덤 선택
    modes = ["quiz", "debate", "action"]
    selected_mode = random.choice(modes)
    
    # 3. [핵심] 프롬프트 분기 (KR / AU)
    if region == 'AU':
        if selected_mode == "quiz":
            system_role = "You are a sharp Quiz Master."
            instruction = "Create only one 'True/False' or 'Short multiple-choice' quiz based on this article. Do not reveal the answer."
            emoji = "🧩 [Quiz] "
        elif selected_mode == "debate":
            system_role = "You are a Critical Thinking Partner."
            instruction = "Identify the main argument and propose a 'Counter-argument' or 'Dilemma' to provoke thought."
            emoji = "⚖️ [Debate] "
        else: # action
            system_role = "You are a Growth Coach."
            instruction = "Ask a specific question on how to apply this knowledge to real life or work."
            emoji = "🚀 [Action] "
            
        full_prompt = (
            f"[Article]\nTitle: {target.title}\nSummary: {target.summary}\n\n"
            f"[Task]\n{instruction}\n\nConstraint: Keep it short (1-2 sentences). English only."
        )

    else: # KR
        if selected_mode == "quiz":
            system_role = "너는 날카로운 퀴즈 출제자야."
            instruction = "이 기사의 핵심 내용으로 'OX 퀴즈'나 '짧은 객관식'을 내줘. 정답은 숨겨."
            emoji = "🧩 [퀴즈] "
        elif selected_mode == "debate":
            system_role = "너는 비판적 사고를 돕는 토론 파트너야."
            instruction = "핵심 주장에 대한 '반대 의견'이나 '딜레마'를 질문으로 던져줘."
            emoji = "⚖️ [생각] "
        else: # action
            system_role = "너는 성장을 돕는 라이프 코치야."
            instruction = "이 내용을 실제 삶에 적용할 수 있는 '구체적인 질문'을 던져줘."
            emoji = "🚀 [실천] "

        full_prompt = (
            f"[기사 정보]\n제목: {target.title}\n요약: {target.summary}\n\n"
            f"[지시사항]\n{instruction}\n\n조건: 1-2문장으로 짧게. 한국어로 작성."
        )

    try:
        # ai_service의 get_completion 사용
        comment = get_completion(full_prompt, system_role=system_role)
        final_comment = emoji + comment
    except Exception as e:
        logger.error(f"복기 생성 실패: {e}")
        final_comment = "Do you remember this?" if region == 'AU' else "이 기사, 기억나시나요?"
    
    return {"article": target, "comment": final_comment}

# ---------------------------------------------------------
# 5. [Feature] 외부 기사 추천 (recommend_external_articles)
# ---------------------------------------------------------
def recommend_external_articles(user, region='KR'):
    """
    [Upgrade] Region에 따라:
    1. 키워드 추출 언어 변경 (영어/한글)
    2. 검색 엔진 변경 (NewsAPI/Naver)
    """
    recent_articles = Article.objects.filter(
        user=user, 
        region=region
    ).order_by('-created_at')[:10]
    
    # 기본 키워드 (Fallback)
    keywords = ["Tech", "Economy", "Science"] if region == 'AU' else ["기술", "경제", "과학"]

    # 1. 키워드 추출 (AI)
    if recent_articles.exists():
        titles = ", ".join([a.title for a in recent_articles])
        try:
            if region == 'AU':
                prompt = (
                    f"User's recent reading: [{titles}]\n"
                    "Recommend 3 distinct English search keywords to broaden interest.\n"
                    "Output: keyword1, keyword2, keyword3 (comma separated)."
                )
            else:
                prompt = (
                    f"사용자가 최근 읽은 글: [{titles}]\n"
                    "관심사를 넓힐 수 있는 서로 다른 주제의 검색 키워드 3개를 추천해줘.\n"
                    "출력: 키워드1, 키워드2, 키워드3 (콤마로만 구분)."
                )
            
            response = get_completion(prompt).strip()
            keywords = [k.strip().replace('"', '').replace("'", "") for k in response.split(',')]
        except Exception as e:
            logger.error(f"키워드 생성 실패: {e}")

    # 안전장치
    default_kw = "World News" if region == 'AU' else "주요 뉴스"
    while len(keywords) < 3:
        keywords.append(default_kw)
    keywords = keywords[:3]

    final_articles = []
    seen_urls = set()

    # 2. 검색 실행 (분기)
    for kw in keywords:
        if region == 'AU':
            results = search_newsapi(kw)
        else:
            results = search_naver(kw)
            
        for article in results:
            url = article.get('link')
            if url and url not in seen_urls:
                article['keyword_label'] = kw # 뱃지용
                final_articles.append(article)
                seen_urls.add(url)
                break 

    return {
        "keyword": ", ".join(keywords),
        "articles": final_articles
    }

# ---------------------------------------------------------
# 6. [NEW] 벡터 기반 추천 (recommend_by_vector)
# ---------------------------------------------------------
def recommend_by_vector(user, region=None, limit=3):
    """
    [Diversity Upgrade] 
    초기 유저의 '편향(Overfitting)'을 막기 위해 
    Top-K 후보군(Pool)을 뽑은 뒤 랜덤으로 선택하는 방식 적용
    """
    
    # 1. 유저 프로필 및 벡터 존재 확인
    if not hasattr(user, 'profile') or user.profile.embedding_user is None:
        return []

    user_vector = user.profile.embedding_user

    try:
        # 2. 쿼리셋 구성 (벡터 거리 계산)
        candidates = Article.objects.annotate(
            distance=CosineDistance('embedding_pytorch', user_vector)
        ).exclude(
            embedding_pytorch__isnull=True
        )

        # [필터] Region 적용
        if region:
            candidates = candidates.filter(region=region)

        # ---------------------------------------------------------
        # 3. [핵심] 다양성 확보 로직 (Candidate Pool Sampling)
        # ---------------------------------------------------------
        
        # (A) 너무 가까운 기사(본인 등) 제외 (거리 0.001 미만)
        # 같은 기사가 중복 추천되는 것을 방지
        candidates = candidates.filter(distance__gt=0.001)

        # (B) 후보군 크기 설정 (Pool Size)
        # 데이터가 적을 땐 30개, 많을 땐 15개 정도를 후보로 둠
        pool_size = 30 
        
        # (C) 상위 N개 후보 가져오기 (이 안에는 '가장 가까운 것' + '적당히 가까운 것'이 섞임)
        top_candidates = list(candidates.order_by('distance')[:pool_size])

        # (D) 후보군이 요청한 개수보다 적으면 그냥 다 줌
        if len(top_candidates) <= limit:
            final_selection = top_candidates
        else:
            # (E) ★ 랜덤 샘플링 (Shuffle) ★
            # 상위 30개 중에서 무작위로 3개를 뽑음 -> 편향 방지 & 매번 다른 결과
            final_selection = random.sample(top_candidates, limit)

            # (선택적) 만약 더 정교하게 하려면, 여기서 카테고리가 겹치지 않게 뽑을 수도 있음
            # 하지만 지금은 Random Sample만으로도 충분한 다양성이 확보됨.

        # 4. 결과 포맷팅
        results = []
        for article in final_selection:
            # 거리(0~2)를 유사도(%)로 변환
            similarity_score = max(0, 1 - article.distance) 

            results.append({
                "id": article.id,
                "title": article.title,
                "summary": article.summary[:100] + "..." if article.summary else "",
                "region": article.region,
                "similarity": round(similarity_score * 100, 1), 
                "source": "Vector Rec" 
            })
        
        # (F) 최종 결과도 유사도 순으로 다시 정렬해서 보여줌 (사용자 경험 위해)
        results.sort(key=lambda x: x['similarity'], reverse=True)
            
        return results

    except Exception as e:
        logger.error(f"Vector Recommendation Error: {e}")
        return []