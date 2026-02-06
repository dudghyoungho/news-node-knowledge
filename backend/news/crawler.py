# backend/news/crawler.py
import requests
import trafilatura
import random
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# [차단 방지 1] 최신 브라우저 User-Agent로 교체 (2024~2025년 기준)
# 구형 UA를 쓰면 보안 솔루션이 "업데이트 안 된 수상한 봇"으로 간주할 수 있음
USER_AGENTS = [
    # Chrome (Windows)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    # Chrome (Mac)
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    # Firefox (Windows)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
    # Safari (Mac)
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    # Edge (Windows)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0'
]

def get_headers():
    """
    [차단 방지 2] 실제 브라우저처럼 보이게 하는 정교한 헤더 설정
    단순히 User-Agent만 보내는 게 아니라, Accept, Language 등을 같이 보내야 봇 탐지를 피함.
    """
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br", # 압축 전송 지원 (대역폭 절약)
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none", # 직접 주소창에 쳐서 들어온 것처럼 위장
        "Sec-Fetch-User": "?1",
        "Connection": "keep-alive"
        # Referer는 제거: RSS에서 직접 들어오는 경우 Referer가 없는 게 더 자연스러움
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
    [강화된 버전] 호주 뉴스, 글로벌 사이트 및 Hacker News 대응 범용 추출기
    """
    
    # 1. 파일 확장자 차단 (PDF 등 바이너리 파일 스킵)
    skip_extensions = ('.pdf', '.jpg', '.png', '.gif', '.mp4', '.avi', '.zip', '.exe', '.dmg', '.apk')
    if url.lower().endswith(skip_extensions):
        return None

    # 2. 소스코드 저장소 제외
    if "github.com" in url or "gitlab.com" in url:
        return None

    # 3. [블랙리스트] 뉴스레터 가입 페이지 등 제외
    blacklist_keywords = [
        "Sign up for", 
        "newsletter", 
        "Subscribe to",
        "Morning Mail",
        "Afternoon Update",
        "Log In", # 로그인 페이지 제외
        "Register"
    ]
    
    if any(bad_word.lower() in url.lower() for bad_word in blacklist_keywords):
        return None
    
    try:
        downloaded = None
        
        # 4. Requests로 안전하게 다운로드
        try:
            response = requests.get(
                url, 
                headers=get_headers(), 
                # (접속 5초, 다운로드 15초) -> 해외 사이트 느림 고려하여 약간 늘림
                timeout=(5, 15), 
                allow_redirects=True,
                stream=True 
            )
            
            # HTML 형식이 아니면 중단
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                response.close()
                return None

            if response.status_code == 200:
                # 10MB 제한
                if len(response.content) > 10 * 1024 * 1024: 
                    response.close()
                    return None
                    
                response.encoding = response.apparent_encoding
                downloaded = response.text
            else:
                # 403 Forbidden 등 에러 시
                return None

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            return None
        except Exception:
            return None

        # 5. Trafilatura 추출 (본문 파싱)
        if downloaded:
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

            # 6. 이미지 추출 보강 (Trafilatura 실패 시 BS4 사용)
            if not image_url:
                soup = BeautifulSoup(downloaded, 'html.parser')
                og_img = soup.select_one('meta[property="og:image"]')
                if og_img:
                    image_url = og_img.get('content')
                else:
                    tw_img = soup.select_one('meta[name="twitter:image"]')
                    if tw_img:
                        image_url = tw_img.get('content')

            # 7. 데이터 품질 체크
            
            # [블랙리스트 2차] 제목에 광고성 문구 있으면 제외
            if any(bad_word in title for bad_word in blacklist_keywords):
                return None

            # [길이 완화] 400자 -> 250자
            # 영문 기사는 짧고 굵은 경우가 많고(Reddit 요약 등), 
            # 400자로 하면 Insight 있는 짧은 칼럼을 놓칠 수 있음.
            if len(content) < 250:
                return None

            # 이미지 URL 절대경로 변환
            if image_url and not image_url.startswith('http'):
                image_url = urljoin(url, image_url)

            # URL 길이 제한
            if image_url and len(image_url) > 990:
                image_url = None

            return {
                "title": title[:500],
                "content": content,
                "thumbnail_url": image_url
            }

        return None

    except Exception:
        return None


def _extract_naver_specific(url):
    """
    네이버 전용 크롤러 (기존 로직 유지)
    """
    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        title_meta = soup.select_one('meta[property="og:title"]')
        title = title_meta.get('content', '제목 없음') if title_meta else (soup.title.string if soup.title else "제목 없음")

        image_meta = soup.select_one('meta[property="og:image"]')
        image_url = image_meta.get('content') if image_meta else None

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
        
        if len(content) < 100:
            return None

        return {
            "title": title[:500],
            "content": content,
            "thumbnail_url": image_url
        }
    except Exception:
        return None