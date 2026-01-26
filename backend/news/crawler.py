import requests
from bs4 import BeautifulSoup
import trafilatura # [NEW] 범용 기사 추출 라이브러리

def extract_article(url):
    """
    URL을 받아 기사 제목, 본문, 썸네일을 추출하는 메인 함수.
    네이버 뉴스는 전용 로직을, 그 외(호주 뉴스 등)는 범용 로직을 사용합니다.
    """
    # 1. 네이버 뉴스인지 확인
    if "naver.com" in url:
        return _extract_naver_specific(url)
    
    # 2. 그 외 글로벌/호주 뉴스 (범용 추출)
    return _extract_general(url)


def _extract_general(url):
    """
    호주 뉴스 및 글로벌 사이트용 범용 추출기 (Trafilatura 사용)
    """
    try:
        # 1. HTML 다운로드
        downloaded = trafilatura.fetch_url(url)
        
        if downloaded is None:
            # 403 Forbidden 등으로 막혔을 경우 requests로 재시도 (User-Agent 변경)
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            downloaded = response.text

        # 2. 본문 및 메타데이터 추출
        # include_images=True, include_comments=False
        result = trafilatura.extract(
            downloaded, 
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            output_format='json',
            with_metadata=True
        )
        
        if not result:
            print(f"Trafilatura 추출 실패: {url}")
            return None

        import json
        data = json.loads(result)

        # 3. 데이터 매핑
        title = data.get('title') or "No Title"
        content = data.get('text') or ""
        image_url = data.get('image') # Trafilatura가 찾은 메인이미지

        # Trafilatura가 이미지를 못 찾았을 경우 BS4로 og:image 시도 (백업)
        if not image_url:
            soup = BeautifulSoup(downloaded, 'html.parser')
            og_image = soup.select_one('meta[property="og:image"]')
            if og_image:
                image_url = og_image.get('content')

        return {
            "title": title,
            "content": content,
            "thumbnail_url": image_url
        }

    except Exception as e:
        print(f"범용 크롤링 에러: {e}")
        return None


def _extract_naver_specific(url):
    """
    기존에 작성한 네이버 전용 크롤러 (변경 없음)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        title_meta = soup.select_one('meta[property="og:title"]')
        title = title_meta.get('content', '제목 없음') if title_meta else (soup.title.string if soup.title else "제목 없음")

        image_meta = soup.select_one('meta[property="og:image"]')
        image_url = image_meta.get('content') if image_meta else None

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

        return {
            "title": title,
            "content": content,
            "thumbnail_url": image_url
        }
    except Exception as e:
        print(f"네이버 크롤링 에러: {e}")
        return None