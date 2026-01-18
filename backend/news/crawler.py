import requests
from bs4 import BeautifulSoup

def fetch_naver_news(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    }

    try:
        # 1. 페이지 요청 (모바일 주소도 대응하기 위해 User-Agent를 모바일로 설정)
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 2. 제목 추출 (안전한 방식)
        title_meta = soup.select_one('meta[property="og:title"]')
        if title_meta:
            title = title_meta.get('content', '제목 없음')
        else:
            title = soup.title.string if soup.title else "제목 없음"

        # 3. 썸네일 추출 (오류 발생 지점 - 안전하게 수정)
        image_meta = soup.select_one('meta[property="og:image"]')
        image_url = image_meta.get('content') if image_meta else None

        # 4. 본문 추출 (스포츠/일반/모바일 통합 타겟팅)
        # 네이버 스포츠 모바일은 .NewsEndContents 또는 #newsEndContents를 사용함
        content_element = soup.select_one('#dic_area') or \
                  soup.select_one('#newsEndContents') or \
                  soup.select_one('div._article_content') or \
                  soup.select_one('[class*="NewsEndContents_article"]') or \
                  soup.select_one('#newsct_article')

        if not content_element:
            print(f"본문 추출 실패 URL: {url}")
            return None

        # 불필요한 태그 제거 (광고, 추천 등)
        garbage_selectors = [
            '.img_desc', '.end_photo_org', '.byline', '.link_news', 
            '.reporter_area', 'script', 'style', '.banner_area'
        ]
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
        print(f"크롤링 상세 에러 발생: {e}")
        return None