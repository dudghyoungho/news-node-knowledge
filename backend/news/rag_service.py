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
    [Upgrade] Hallucination 방지를 위한 Grounding 강화 버전
    """
    now = timezone.now()
    threshold_time = now - timedelta(days=1) 

    # 1. 대상 기사 선정 (기존 로직 유지)
    candidates = Article.objects.filter(
        user=user, 
        created_at__lte=threshold_time, 
        status=Article.Status.SAVED,
        region=region
    )
    
    if not candidates.exists():
        candidates = Article.objects.filter(user=user, status=Article.Status.SAVED, region=region)

    if not candidates.exists():
        msg = "No articles saved yet." if region == 'AU' else "아직 저장된 기사가 없습니다."
        return {"message": msg}

    target = random.choice(list(candidates))

    # 2. 페르소나 선택
    modes = ["quiz", "debate", "action"]
    selected_mode = random.choice(modes)
    
    # [NEW] 엔티티 정보가 있다면 힌트로 제공 (NER 결과 활용)
    # target.entities가 JSONField나 문자열이라고 가정
    entity_hint = ""
    if hasattr(target, 'entities') and target.entities:
        entity_hint = f"Key Entities: {target.entities}"

    # 3. [핵심] 프롬프트 고도화 (Grounding & Fact-Check)
    if region == 'AU':
        if selected_mode == "quiz":
            system_role = "You are a strict Examiner. You verify facts based ONLY on the provided text."
            # [전략] 빈칸 채우기(Fill-in-the-blank)가 환각이 가장 적습니다.
            instruction = (
                "Create a 'Fill-in-the-blank' quiz based on a specific fact in the summary. "
                "The answer must be a specific word (Entity) found in the text. "
                "Do not use external knowledge. Do not ask 'What is the main topic?'"
            )
            emoji = "🧩 [Quiz] "
        elif selected_mode == "debate":
            system_role = "You are a Critical Thinking Partner."
            instruction = "Identify the most controversial point in the summary and ask a provocative 'Dilemma' question."
            emoji = "⚖️ [Debate] "
        else: # action
            system_role = "You are a Practical Career Coach."
            instruction = "Based on the specific technology or event in the summary, ask: 'How will you apply [Specific Fact] to your work tomorrow?'"
            emoji = "🚀 [Action] "
            
        full_prompt = (
            f"Strictly base your response on the following text.\n\n"
            f"[Source Text]\nTitle: {target.title}\nSummary: {target.summary}\n{entity_hint}\n\n"
            f"[Task]\n{instruction}\n\n"
            f"Constraint: Keep it short (1 sentence). English only. Do NOT provide the answer."
        )

    else: # KR
        if selected_mode == "quiz":
            system_role = "너는 팩트 기반의 깐깐한 퀴즈 출제자야."
            # [전략] 사실 관계 확인 문제로 유도
            instruction = (
                "외부 지식을 쓰지 말고, 오직 '요약문'에 있는 구체적인 사실(숫자, 기업명, 인물)을 묻는 퀴즈를 내. "
                "정답은 요약문 안에서 찾을 수 있어야 해. (빈칸 채우기 형식 추천)"
            )
            emoji = "🧩 [퀴즈] "
        elif selected_mode == "debate":
            system_role = "너는 비판적 사고를 돕는 토론 파트너야."
            instruction = "요약문의 핵심 주장을 하나 꼬집어서, 사용자가 고민할만한 '반론'이나 '딜레마'를 질문해줘."
            emoji = "⚖️ [생각] "
        else: # action
            system_role = "너는 실천을 돕는 코치야."
            instruction = "이 지식을 내일 당장 업무나 삶에 적용할 수 있도록, 요약문의 핵심 키워드를 포함해서 구체적인 질문을 던져줘."
            emoji = "🚀 [실천] "

        full_prompt = (
            f"다음 텍스트에 있는 내용으로만 생성하세요. 외부 지식 금지.\n\n"
            f"[소스 텍스트]\n제목: {target.title}\n요약: {target.summary}\n{entity_hint}\n\n"
            f"[지시사항]\n{instruction}\n\n"
            f"조건: 1-2문장으로 짧게. 정답은 말하지 마. 한국어로 작성."
        )

    try:
        # temperature를 0.3~0.5 정도로 낮추면 환각이 줄어듭니다. (호출 함수에서 설정 가능하면 변경 추천)
        comment = get_completion(full_prompt, system_role=system_role)
        
        # [Optional] 퀴즈일 경우 정답을 사용자가 생각할 수 있게 유도
        if selected_mode == "quiz":
            final_comment = f"{emoji} {comment}"
        else:
            final_comment = f"{emoji} {comment}"
            
    except Exception as e:
        # logger.error(f"복기 생성 실패: {e}")
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
def recommend_mixed_portfolio(user, region=None, limit=3):
    """
    [Portfolio Recommendation v3 - Final Safe Version]
    1. Cold Start 대응: 유저 벡터 없으면 최신 기사 추천
    2. Hybrid Pool: (Vector Top 50) + (Random Recent 50) 혼합하여 필터버블 방지
    3. Safety Net: 읽은 기사 제외 후 후보 없으면 포함해서 추천
    """
    
    # ---------------------------------------------------------
    # [Case 1] 유저 벡터가 없는 경우 (완전 초기 사용자)
    # ---------------------------------------------------------
    if not hasattr(user, 'profile') or user.profile.embedding_user is None:
        return recommend_random_recent(user, region, limit)

    user_vector = user.profile.embedding_user
    
    try:
        # [Step 1] 내가 이미 본 기사 목록 가져오기
        viewed_ids = list(UserActionLog.objects.filter(
            user=user, 
            action__in=['read', 'star', 'save']
        ).values_list('article_id', flat=True))
        
        # 제외할 ID 목록 (본 것 + 내가 쓴 것)
        exclude_ids = viewed_ids + list(Article.objects.filter(user=user).values_list('id', flat=True))

        # [Step 2] 기본 쿼리셋 (임베딩 있는 것만)
        base_qs = Article.objects.filter(embedding_pytorch__isnull=False)
        if region:
            base_qs = base_qs.filter(region=region)

        # ---------------------------------------------------------
        # [Case 2] 읽은 거 빼니까 남는 게 없는 경우 (DB 기사 부족 방어)
        # ---------------------------------------------------------
        # 일단 제외하고 찾아봄
        candidates_qs = base_qs.exclude(id__in=exclude_ids)
        
        # 만약 남는 게 없으면? 필터 해제 (본 거라도 추천)
        if not candidates_qs.exists():
            candidates_qs = base_qs 
        
        # 그래도 없으면? (DB가 진짜 텅 빔) -> 빈 배열 리턴 (어쩔 수 없음)
        if not candidates_qs.exists():
            return []

        # ---------------------------------------------------------
        # [Step 3] Group A: 취향 기반 (Vector Similarity Top 50)
        # ---------------------------------------------------------
        # 여기서 annotate로 distance를 계산해둠
        group_a = list(candidates_qs.annotate(
            distance=CosineDistance('embedding_pytorch', user_vector)
        ).order_by('distance')[:50])

        # ---------------------------------------------------------
        # [Step 4] Group B: 다양성 기반 (Recent Random 50)
        # ---------------------------------------------------------
        # 최신순 100개 중 랜덤 50개 추출 (벡터 무관 -> 필터 버블 파괴)
        recent_pool = list(base_qs.order_by('-created_at')[:100])
        group_b = random.sample(recent_pool, min(len(recent_pool), 50))

        # ---------------------------------------------------------
        # [Step 5] Pool 병합 (중복 제거)
        # ---------------------------------------------------------
        # 딕셔너리로 병합 (ID 기준 중복 제거)
        # Group B 아이템들은 distance가 없을 수 있으므로 처리 필요
        pool_dict = {}
        
        # Group A 먼저 넣음 (distance 있음)
        for a in group_a:
            pool_dict[a.id] = a
            
        # Group B 넣음 (이미 있으면 패스, 없으면 distance 가짜 값 부여)
        for b in group_b:
            if b.id not in pool_dict:
                # distance 속성이 없으면 0.5 (중간) 정도로 설정
                if not hasattr(b, 'distance'):
                    setattr(b, 'distance', 0.5) 
                pool_dict[b.id] = b

        # 최종 Pool 리스트
        pool = list(pool_dict.values())

        if not pool: 
            return recommend_random_recent(user, region, limit)

        # ---------------------------------------------------
        # Slot Filling (슬롯 채우기)
        # ---------------------------------------------------
        final_selection = []
        selected_ids = set()

        # [Slot 1] Deep Dive (Group A 우선)
        # 취향에 맞으면서도 Insight/Opinion 기사를 최우선
        candidates_s1 = [a for a in group_a if a.article_type in ['INSIGHT', 'OPINION', 'TUTORIAL']]
        
        if candidates_s1:
            pick1 = candidates_s1[0]
            pick1.reason_tag = "🎯 Deep Dive"
        elif group_a:
            pick1 = group_a[0]
            pick1.reason_tag = "🔥 Top Pick"
        else:
             # Group A가 비었으면 pool 전체에서
             pick1 = pool[0]
             pick1.reason_tag = "🔥 Trending"
        
        final_selection.append(pick1)
        selected_ids.add(pick1.id)


        # [Slot 2] Broaden View (Category Extension)
        # Slot 1과 같은 카테고리 기사 추천
        target_category = pick1.category
        candidates_s2 = [a for a in pool if a.category == target_category and a.id not in selected_ids]
        
        if candidates_s2:
            # 상위권만 뽑지 말고 랜덤성 부여
            pick2 = random.choice(candidates_s2[:5]) 
            pick2.reason_tag = f"📂 {target_category}"
        else:
            # 없으면 차순위
            remain = [a for a in pool if a.id not in selected_ids]
            if remain:
                # 거리순 정렬해서 가장 가까운 놈으로
                remain.sort(key=lambda x: getattr(x, 'distance', 1.0))
                pick2 = remain[0]
                pick2.reason_tag = "⚡ Recommended"
            else:
                return format_results(final_selection)
        
        final_selection.append(pick2)
        selected_ids.add(pick2.id)


        # [Slot 3] Serendipity (Discovery)
        # ★ 핵심: Group B(랜덤 풀)에서 우선적으로 찾음
        candidates_s3 = [
            a for a in group_b 
            if a.id not in selected_ids and a.category != target_category
        ]

        if candidates_s3:
            pick3 = random.choice(candidates_s3)
            pick3.reason_tag = "✨ Discovery"
        else:
            # Group B에 마땅한 게 없으면 전체 Pool에서 랜덤
            remain = [a for a in pool if a.id not in selected_ids]
            if remain:
                pick3 = random.choice(remain)
                pick3.reason_tag = "🎲 Random Pick"
            else:
                return format_results(final_selection)

        final_selection.append(pick3)

        return format_results(final_selection)

    except Exception as e:
        logger.error(f"Portfolio Rec Error: {e}")
        # 에러 나면 빈 배열 대신 랜덤 추천이라도 던짐 (Fallback)
        return recommend_random_recent(user, region, limit)

def format_results(article_list):
    """ 최종 결과를 JSON 대응 딕셔너리 리스트로 변환 """
    results = []
    for article in article_list:
        dist = getattr(article, 'distance', 1.0)
        similarity_score = max(0, 1 - dist)
        
        raw_text = article.summary if article.summary else article.content
        display_summary = clean_html(raw_text)[:150] + "..." if raw_text else ""
        
        results.append({
            "id": article.id,
            "title": article.title,
            "summary": display_summary,
            "url": article.url,
            "thumbnail": article.thumbnail_url or "",
            "date": article.created_at.strftime("%Y-%m-%d") if article.created_at else "",
            "region": article.region,
            "similarity": round(similarity_score * 100, 1),
            "source": "My Library",
            "reason_tag": getattr(article, 'reason_tag', 'Recommended'),
            "reason_desc": getattr(article, 'reason_desc', '')
        })
    return results

def recommend_random_recent(user, region, limit=3):
    """ [Fallback] 아무 기사나 뿌려서 빈 화면 방지 """
    qs = Article.objects.all()
    if region: qs = qs.filter(region=region)
    
    # 1. 임베딩 된 것 우선, 없으면 전체에서 최신순
    candidates = list(qs.filter(embedding_pytorch__isnull=False).order_by('-created_at')[:50])
    if not candidates:
        candidates = list(qs.order_by('-created_at')[:20])

    if not candidates: return []
        
    picks = random.sample(candidates, min(len(candidates), limit))
    for p in picks:
        p.distance = 0.5
        p.reason_tag = "🆕 New Arrival"
    return format_results(picks)