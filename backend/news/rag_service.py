import os
import requests
import logging
import re
import html
import random
import numpy as np
from datetime import timedelta
from django.utils import timezone
from openai import OpenAI
from .models import Article

# 로거 설정 (강제로 출력하도록 설정)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
# 2. [Search] 네이버 뉴스 검색 API (디버깅 강화)
# ---------------------------------------------------------
def search_articles(keyword):
    """
    [수정됨] 네이버 뉴스 포털(news.naver.com) 링크가 있는 기사만 골라냅니다.
    -> AI 요약 및 크롤링 용이성 확보
    """
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.error("🚨 네이버 API 키 누락")
        return []

    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    # [변경점 1] 필터링을 위해 넉넉하게 10개를 가져옵니다.
    params = {"query": keyword, "display": 10, "start": 1, "sort": "sim"}

    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        items = data.get("items", [])
        
        results = []
        for item in items:
            # 네이버 뉴스 링크 필드
            naver_link = item.get("link", "")
            
            # [변경점 2] ★ 핵심 필터링 로직 ★
            # 링크에 'news.naver.com'이나 'sports.news.naver.com' 등이 없으면 버립니다.
            if "news.naver.com" not in naver_link:
                continue

            # 1. 네이버 데이터 정제
            title = clean_html(item.get("title", ""))
            desc = clean_html(item.get("description", ""))
            pub_date = item.get("pubDate", "")

            results.append({
                "title": title,
                "summary": desc,       
                "snippet": desc,
                "description": desc,
                "reason": desc,
                
                # 원문 링크 대신 '네이버 뉴스 링크'를 무조건 사용
                "url": naver_link,
                "link": naver_link,
                
                "img": "", 
                "thumbnail": "",
                "source": "Naver News", # 이제 진짜 네이버 뉴스임
                "date": pub_date
            })

            # 키워드 당 1~2개만 필요하다면 여기서 break 해도 되지만,
            # search_articles 함수 자체는 리스트를 반환하고, 
            # 호출하는 쪽에서 1개를 고르는 게 낫습니다.

        return results

    except Exception as e:
        logger.error(f"네이버 검색 오류: {e}")
        return []

# ---------------------------------------------------------
# 3. [Feature] 외부 기사 추천 (안전장치 포함)
# ---------------------------------------------------------
def recommend_external_articles(user):
    """
    [수정됨] 주제 중복을 피하기 위해 '3개의 서로 다른 키워드'를 뽑아
    각각 1개씩 베스트 기사를 가져오는 다양성 확보 로직
    """
    recent_articles = Article.objects.filter(user=user).order_by('-created_at')[:10] # 범위를 좀 늘림
    
    # 기본 키워드 세트 (읽은 글이 없을 경우 대비)
    keywords = ["IT 트렌드", "국제 경제", "최신 과학 기술"] 

    # 1. LLM에게 서로 다른 3가지 주제의 키워드 요청
    if recent_articles.exists():
        titles = ", ".join([a.title for a in recent_articles])
        try:
            prompt = f"""
            사용자가 최근 읽은 뉴스 제목들이야: [{titles}]
            
            이 사용자의 관심사를 넓힐 수 있는 '서로 다른 주제'의 검색 키워드 3개를 추천해줘.
            
            [조건]
            1. 3개의 키워드는 서로 겹치지 않는 분야여야 함. (예: 반도체, 부동산, 유럽여행)
            2. 콤마(,)로만 구분해서 단어 3개만 딱 출력해. 설명 금지.
            """
            response = get_completion(prompt).strip()
            # 콤마로 분리하여 리스트로 만듦
            keywords = [k.strip().replace('"', '').replace("'", "") for k in response.split(',')]
        except Exception as e:
            logger.error(f"키워드 생성 실패: {e}")
            keywords = ["주요 뉴스", "테크", "경제"]

    # 만약 키워드가 3개 미만이면 기본값으로 채움
    while len(keywords) < 3:
        keywords.append("주요 뉴스")

    # 3개까지만 사용
    keywords = keywords[:3]
    logger.info(f"🤖 다양성 확보를 위한 키워드 3대장: {keywords}")

    final_articles = []
    seen_urls = set() # 중복 기사 방지용

    # 2. 각 키워드별로 검색해서 '가장 정확한 1개'만 가져오기
    for kw in keywords:
        # 각 키워드로 2개씩만 검색 (혹시 1등이 중복일까봐 예비로 2개)
        results = search_articles(kw) 
        
        for article in results:
            # 이미 담은 기사(URL 기준)가 아니면 담고 break (키워드당 1개만)
            if article['url'] not in seen_urls:
                # 키워드 정보를 뱃지처럼 제목 앞에 살짝 추가해주면 더 좋음
                article['keyword_label'] = kw 
                final_articles.append(article)
                seen_urls.add(article['url'])
                break # 1개 담았으면 다음 키워드로 이동

    # 3. 데이터 반환
    return {
        "keyword": ", ".join(keywords), # 화면 표시용 (예: 반도체, 부동산, AI)
        "articles": final_articles,
        "items": final_articles
    }


# ---------------------------------------------------------
# (기존 유지) OpenAI 응답 생성
# ---------------------------------------------------------
def get_completion(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful news curator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API 오류: {e}")
        return ""

# ---------------------------------------------------------
# 4. [Feature] DB 내부 연관 기사 추천 (find_connected_articles)
# ---------------------------------------------------------
def find_connected_articles(target_article):
    """
    현재 읽는 기사와 유사한 내 서재의 기사를 찾습니다.
    (벡터 유사도 기반)
    """
    # 임베딩이 없으면 추천 불가
    if not target_article.embedding:
        return []

    # 내 서재의 다른 기사들 가져오기 (저장된 것만)
    user_articles = Article.objects.filter(
        user=target_article.user, 
        status='saved'
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
                "similarity": round(float(similarity), 2)
            })
    
    # 유사도 높은 순 정렬 후 상위 3개 반환
    recommendations.sort(key=lambda x: x['similarity'], reverse=True)
    return recommendations[:3]

# ---------------------------------------------------------
# 5. [Feature] 과거 기사 복기 (review_past_knowledge)
# ---------------------------------------------------------
def review_past_knowledge(user):
    """
    [Upgrade] 단순 회상이 아니라, 3가지 모드(퀴즈/토론/행동) 중 하나로 
    지적 자극을 주는 고도화된 복기 로직
    """
    now = timezone.now()
    threshold_time = now - timedelta(days=1) 

    # 1. 대상 기사 선정 (SAVED 상태, 24시간 지난 것)
    candidates = Article.objects.filter(
        user=user, 
        created_at__lte=threshold_time, 
        status=Article.Status.SAVED
    )
    
    # (Fallback) 없으면 전체 SAVED 기사 중 선택
    if not candidates.exists():
        candidates = Article.objects.filter(user=user, status=Article.Status.SAVED)

    if not candidates.exists():
        return {"message": "아직 서재가 비어있네요. 흥미로운 기사를 저장해보세요!"}

    target = random.choice(list(candidates))

    # 2. [핵심] 3가지 페르소나 중 랜덤 선택
    modes = ["quiz", "debate", "action"]
    selected_mode = random.choice(modes)
    
    logger.debug(f"🎲 선택된 복기 모드: {selected_mode}")

    # 3. 모드별 프롬프트 분기
    if selected_mode == "quiz":
        # 기억력 테스트 모드
        system_role = "너는 날카로운 퀴즈 출제자야."
        instruction = f"""
        사용자가 과거에 읽은 이 기사의 핵심 내용에 대해 'OX 퀴즈' 혹은 '짧은 객관식 퀴즈'를 하나만 내줘.
        정답은 알려주지 말고, 사용자가 스스로 생각하게 만들어.
        문체: 도전적이고 위트 있게.
        """
        
    elif selected_mode == "debate":
        # 비판적 사고 모드 (악마의 대변인)
        system_role = "너는 비판적 사고를 돕는 토론 파트너야."
        instruction = f"""
        이 기사의 핵심 주장을 파악하고, 그에 대한 '반대 의견'이나 '생각해볼 만한 딜레마'를 질문으로 던져줘.
        사용자가 이 주제를 다각도로 보게 만드는 것이 목표야.
        문체: 진지하고 철학적으로.
        """
        
    else: # action
        # 실천 유도 모드
        system_role = "너는 성장을 돕는 라이프 코치야."
        instruction = f"""
        이 기사의 내용을 실제 삶이나 업무에 적용할 수 있는 '구체적인 질문'을 던져줘.
        예: "이 내용을 바탕으로 이번 주에 시도해본 것이 있나요?"
        문체: 부드럽고 격려하는 어조로.
        """

    # 4. LLM 호출
    try:
        full_prompt = f"""
        [기사 정보]
        제목: {target.title}
        요약: {target.summary}
        
        [지시사항]
        {instruction}
        
        조건: 
        1. 질문은 딱 한 문장~두 문장으로 짧게.
        2. 기사 내용을 모르면 답할 수 없게 구체적으로.
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.8, # 창의성을 위해 온도를 약간 높임
        )
        comment = response.choices[0].message.content
        
        # 모드에 따른 이모지 추가
        prefix = {"quiz": "🧩 [퀴즈] ", "debate": "⚖️ [생각] ", "action": "🚀 [실천] "}
        comment = prefix[selected_mode] + comment

    except Exception as e:
        logger.error(f"복기 생성 실패: {e}")
        comment = "이 기사의 내용, 기억나시나요?"
    
    return {"article": target, "comment": comment}