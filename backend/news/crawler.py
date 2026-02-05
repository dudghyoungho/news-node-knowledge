import requests
import trafilatura
import random
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# [차단 방지] User-Agent 로테이션 (RSS 대량 수집 시 필수)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }

def extract_article(url):
    """
    URL을 받아 기사 제목, 본문, 썸네일을 추출하는 메인 함수.
    """
    if "naver.com" in url:
        return _extract_naver_specific(url)
    
    return _extract_general(url)


def _extract_general(url):
    """
    호주 뉴스, 글로벌 사이트 및 Google News 대응 범용 추출기
    """
    try:
        # 1. Trafilatura로 1차 시도 (가장 깔끔함)
        downloaded = trafilatura.fetch_url(url)
        
        # 2. 실패 시 requests로 2차 시도 (헤더 변경 + 리다이렉트 허용)
        # Google News 링크는 리다이렉트가 필수이므로 requests가 유리할 때가 있음
        if downloaded is None:
            try:
                # allow_redirects=True: 구글 뉴스 단축 URL 등을 따라가서 원본을 가져옴
                response = requests.get(url, headers=get_headers(), timeout=15, allow_redirects=True)
                if response.status_code == 200:
                    downloaded = response.text
                else:
                    print(f"   [Fail] Status {response.status_code} for {url}")
                    return None
            except Exception as e:
                print(f"   [Request Error] {e}")
                return None

        # 3. 본문 및 메타데이터 추출
        result = trafilatura.extract(
            downloaded, 
            include_comments=False,
            include_tables=False,
            output_format='json',
            with_metadata=True
        )
        
        if not result:
            return None

        data = json.loads(result)

        title = data.get('title') or "No Title"
        content = data.get('text') or ""
        image_url = data.get('image')

        # 4. 이미지 추출 보강 (BS4)
        # Trafilatura가 이미지를 놓치는 경우가 있어 og:image를 2차로 확인
        if not image_url:
            soup = BeautifulSoup(downloaded, 'html.parser')
            og_img = soup.select_one('meta[property="og:image"]')
            if og_img:
                image_url = og_img.get('content')
            else:
                # 트위터 카드 이미지 시도
                tw_img = soup.select_one('meta[name="twitter:image"]')
                if tw_img:
                    image_url = tw_img.get('content')

        # 5. [안전장치] 데이터 정제 및 필터링
        
        # A. 내용이 너무 짧으면 버림 (300자 미만은 뉴스 가치 없음 / 에러 페이지일 확률 높음)
        if len(content) < 300:
            # print(f"   [Skip] Too short ({len(content)} chars)")
            return None

        # B. 이미지 URL 절대경로 변환 (/img/logo.png -> https://site.com/img/logo.png)
        if image_url and not image_url.startswith('http'):
            image_url = urljoin(url, image_url)

        # C. DB 에러 방지: 이미지 URL이 1000자를 넘으면 버림 (Guardian 해시 URL 등)
        if image_url and len(image_url) > 990:
            image_url = None

        return {
            "title": title[:500], # 제목 길이 안전장치
            "content": content,
            "thumbnail_url": image_url
        }

    except Exception as e:
        print(f"   [Crawl Error] {e}")
        return None


def _extract_naver_specific(url):
    """
    네이버 전용 크롤러 (기존 로직 유지 + 안전장치 추가)
    """
    try:
        # 네이버도 랜덤 헤더 적용
        response = requests.get(url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        title_meta = soup.select_one('meta[property="og:title"]')
        title = title_meta.get('content', '제목 없음') if title_meta else (soup.title.string if soup.title else "제목 없음")

        image_meta = soup.select_one('meta[property="og:image"]')
        image_url = image_meta.get('content') if image_meta else None

        # [안전장치] 이미지 길이 체크
        if image_url and len(image_url) > 990:
            image_url = None

        content_element = soup.select_one('#dic_area') or \
                  soup.select_one('#newsEndContents') or \
                  soup.select_one('div._article_content') or \
                  soup.select_one('[class*="NewsEndContents_article"]') or \
                  soup.select_one('#newsct_article')

        if not content_element:
            return None

        garbage_selectors = ['.img_desc', '.end_photo_org', '.byline', '.link_news', '.reporter_area', 'script', 'style', '.banner_area']
        for selector in garbage_selectors:
            for tag in content_element.select(selector):
                tag.decompose()
            
        content = content_element.get_text(separator='\n', strip=True)
        
        # 네이버 뉴스도 너무 짧으면 버림
        if len(content) < 100:
            return None

        return {
            "title": title[:500],
            "content": content,
            "thumbnail_url": image_url
        }
    except Exception as e:
        print(f"   [Naver Error] {e}")
        return None