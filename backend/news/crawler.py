import requests
from bs4 import BeautifulSoup

def fetch_naver_news(url):
    """
    네이버 뉴스 URL을 받아 제목, 썸네일, 본문을 추출
    """
    # 1. 헤더 설정
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() # 404, 500 에러 시 예외 발생
        
        # 2. HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')

        # 3. 데이터 추출
        # (1) 제목 (meta 태그 활용이 가장 정확함)
        title = soup.select_one('meta[property="og:title"]')['content']
        
        # (2) 썸네일 이미지
        image_meta = soup.select_one('meta[property="og:image"]')
        image_url = image_meta['content'] if image_meta else None

        # (3) 본문 (핵심!)
        # 네이버 뉴스는 보통 'dic_area' 또는 'newsct_article' ID를 사용함
        content_element = soup.select_one('#dic_area') or soup.select_one('#newsct_article')
        
        if not content_element:
            return None # 본문 구조가 다르면 수집 불가 처리

        # 불필요한 태그 제거 (이미지 설명, 기자 정보 등)
        for tag in content_element.select('.img_desc, .end_photo_org, .byline'):
            tag.decompose()
            
        # 텍스트만 깔끔하게 정리
        content = content_element.get_text(separator='\n', strip=True)

        return {
            "title": title,
            "content": content,
            "thumbnail_url": image_url
        }

    except Exception as e:
        print(f"크롤링 에러 발생: {e}")
        return None

# ---- 테스트 코드 (이 파일만 실행했을 때 작동) ----
if __name__ == "__main__":
    # 테스트할 네이버 뉴스 기사 URL
    test_url = "https://n.news.naver.com/mnews/article/092/0002318356" # 예시 URL
    
    print(f"크롤링 시작: {test_url}")
    result = fetch_naver_news(test_url)
    
    if result:
        print("\n--- [성공] ---")
        print(f"제목: {result['title']}")
        print(f"이미지: {result['thumbnail_url']}")
        print(f"본문(앞 100자): {result['content'][:100]}...")
    else:
        print("\n--- [실패] ---")