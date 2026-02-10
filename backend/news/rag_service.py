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
from .models import Article, UserActionLog
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
            
            # [필터 완화] 네이버 뉴스 포털이 아니더라도 원문 링크가 있으면 허용
            # 만약 네이버 뉴스만 고집하고 싶다면 아래 주석을 해제하세요.
            # if "news.naver.com" not in link:
            #    continue
            
            # [방어 코드] None값 처리
            raw_title = item.get("title") or ""
            raw_desc = item.get("description") or ""
            raw_date = item.get("pubDate") or ""

            results.append({
                "title": clean_html(raw_title),
                "summary": clean_html(raw_desc),
                "url": link,                           # [통일] link -> url
                "thumbnail": "",                       # [통일] 빈 값이라도 필수
                "date": raw_date[:10] if raw_date else "",
                "source": "Naver News"
            })
        return results
    except Exception as e:
        logger.error(f"Naver Search Error: {e}")
        return []

def search_newsapi(keyword):
    """ 
    호주/글로벌 뉴스 검색 (NewsAPI)
    - [수정] 누락된 결과 처리 로직 복구
    - [수정] 키 이름 통일 (url, thumbnail)
    """
    api_key = os.environ.get("NEWSAPI_KEY") 
    if not api_key:
        logger.warning("NewsAPI Key missing")
        return []

    url = "https://newsapi.org/v2/everything"
    
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
        "domains": trusted_domains,
        "apiKey": api_key
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("status") != "ok":
            logger.error(f"NewsAPI Error: {data.get('message')}")
            return []

        articles = data.get("articles", [])
        
        results = []
        for item in articles:
            # 필수 필드 체크
            if not item.get("url") or not item.get("title"):
                continue

            raw_date = item.get("publishedAt") or ""
            
            results.append({
                "title": item.get("title") or "No Title",
                "summary": item.get("description") or "",
                "url": item.get("url"),                     # [통일] link -> url
                "thumbnail": item.get("urlToImage") or "",  # [통일] 썸네일 매핑
                "date": raw_date[:10] if raw_date else "",
                "source": item.get("source", {}).get("name") or "NewsAPI"
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
    1. 키워드 추출 언어 변경
    2. 검색 엔진 변경 및 URL 중복 제거 로직 수정
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
            # 따옴표 제거 및 분리
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
            # [핵심 수정] 모든 검색 함수가 'url' 키를 쓰므로 여기서도 'url' 확인
            url = article.get('url') 
            
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
# 6. [NEW] 벡터 기반 추천 (recommend_by_vector) - [수정됨]
# ---------------------------------------------------------


# backend/news/rag_service.py

def recommend_mixed_portfolio(user, region=None, limit=3):
    """
    [Portfolio Recommendation v2]
    1. Pool Extension: Search up to top 100 to increase chance of finding INSIGHT articles.
    2. Insight Priority: Boost INSIGHT articles to Slot 1 even if similarity is slightly lower.
    3. Strict De-duplication: Prevent duplicates across slots.
    """
    if not hasattr(user, 'profile') or user.profile.embedding_user is None:
        return []

    user_vector = user.profile.embedding_user

    try:
        # [Step 1] Get URLs of articles I've already saved/viewed
        my_saved_urls = Article.objects.filter(user=user).values_list('url', flat=True)

        # [Step 2] Build Candidates Pool - Expand to 100
        candidates = Article.objects.annotate(
            distance=CosineDistance('embedding_pytorch', user_vector)
        ).exclude(
            embedding_pytorch__isnull=True
        ).exclude(
            url__in=my_saved_urls # Exclude my saved articles
        ).exclude(
            user=user # Exclude articles I created
        )

        if region:
            candidates = candidates.filter(region=region)
        
        # ★ Fetch top 100 for diversity
        pool = list(candidates.order_by('distance')[:100])
        
        if not pool: return []

        # ---------------------------------------------------
        # 3. Slot Filling
        # ---------------------------------------------------
        final_selection = []
        selected_ids = set() # For de-duplication

        # ===================================================
        # [Slot 1] Deep Dive (Prioritize Insight)
        # ===================================================
        # Search for insight articles within the entire pool (100)
        insight_candidates = [
            a for a in pool 
            if a.article_type in ['INSIGHT', 'OPINION', 'TUTORIAL']
        ]
        
        if insight_candidates:
            # If insights exist, pick the one with highest similarity
            pick = insight_candidates[0]
            pick.reason_tag = "🎯 Deep Dive"
            pick.reason_desc = "In-depth analysis of your interest"
        else:
            # If no insight in top 100, pick the overall #1
            pick = pool[0]
            pick.reason_tag = "🔥 Top Pick"
            pick.reason_desc = "Most relevant to your taste"
        
        final_selection.append(pick)
        selected_ids.add(pick.id)


        # ===================================================
        # [Slot 2] Broaden View (Expand Category)
        # ===================================================
        target_category = pick.category
        
        # 1. Same category
        # 2. Not already selected
        slot2_candidates = [
            a for a in pool 
            if a.category == target_category and a.id not in selected_ids
        ]
        
        if slot2_candidates:
            # Pick random from top 10 to avoid always picking #1
            range_limit = min(len(slot2_candidates), 10)
            pick = random.choice(slot2_candidates[:range_limit]) 
            
            pick.reason_tag = f"📂 {target_category}"
            pick.reason_desc = f"More from {target_category}"
        else:
            # If no same category, pick the next best relevant one
            remain = [a for a in pool if a.id not in selected_ids]
            if remain:
                pick = remain[0]
                pick.reason_tag = "⚡ Trending"
                pick.reason_desc = "Highly recommended for you"
            else:
                return format_results(final_selection)

        final_selection.append(pick)
        selected_ids.add(pick.id)


        # ===================================================
        # [Slot 3] Serendipity (New Discovery)
        # ===================================================
        # 1. Different category from Slot 1
        # 2. Not already selected
        # 3. ★ Search from rank 10~100 to ensure diversity
        
        slot3_candidates = [
            a for a in pool[10:] 
            if a.id not in selected_ids and a.category != target_category
        ]

        if slot3_candidates:
            pick = random.choice(slot3_candidates)
            pick.reason_tag = "✨ Discovery"
            pick.reason_desc = "Fresh inspiration for you"
        else:
            # Fallback: pick any remaining random
            remain = [a for a in pool if a.id not in selected_ids]
            if remain:
                pick = random.choice(remain) 
                pick.reason_tag = "🎲 Random Pick"
                pick.reason_desc = "Light read you might like"
            else:
                 return format_results(final_selection)

        final_selection.append(pick)

        return format_results(final_selection)

    except Exception as e:
        logger.error(f"Portfolio Recommendation Error: {e}")
        return []

# Helper: Result Formatting
def format_results(article_list):
    results = []
    for article in article_list:
        similarity_score = max(0, 1 - article.distance)
        
        raw_text = article.summary if article.summary else article.content
        clean_text = clean_html(raw_text or "")
        display_summary = clean_text[:150] + "..." if len(clean_text) > 150 else clean_text
        
        safe_thumb = article.thumbnail_url if article.thumbnail_url else ""

        results.append({
            "id": article.id,
            "title": article.title,
            "summary": display_summary,
            "url": article.url,
            "thumbnail": safe_thumb,
            "date": article.created_at.strftime("%Y-%m-%d"),
            "region": article.region,
            "similarity": round(similarity_score * 100, 1),
            "source": "My Library",
            "reason_tag": getattr(article, 'reason_tag', 'Recommended'),
            "reason_desc": getattr(article, 'reason_desc', '')
        })
    
    # Return in fixed order: [Deep Dive] -> [Category] -> [Discovery]
    return results