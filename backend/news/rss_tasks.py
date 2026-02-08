import feedparser
import time
import random
import requests
import logging
from datetime import datetime
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Article
from .rss_config import RSS_FEEDS

# [기존] 크롤러 및 AI 분류
from .crawler import extract_article, get_headers
from .ai_service import classify_news

# [신규] 구글 뉴스 디코더 (pip install googlenewsdecoder 필요)
from googlenewsdecoder import gnewsdecoder

User = get_user_model()
logger = logging.getLogger(__name__)

# =========================================================
# 1. 구글 뉴스 디코딩 헬퍼 함수
# =========================================================
def get_final_url(url):
    """
    URL이 news.google.com 도메인이면 디코딩을 시도하여 원본 URL을 반환.
    아니면 원래 URL 반환.
    """
    if "news.google.com" in url:
        try:
            # interval: 1초 대기 (구글 차단 방지용 필수)
            decoded = gnewsdecoder(url, interval=1)
            if decoded.get("status"):
                real_url = decoded["decoded_url"]
                # print(f"     🔍 Decoded Google Link: {real_url[:60]}...")
                return real_url
            else:
                print(f"     ⚠️ Decoding failed: {decoded.get('message')}")
        except Exception as e:
            print(f"     ⚠️ Google Decoder Error: {e}")
    
    # 구글 뉴스가 아니거나 실패하면 원래 URL 반환
    return url

# =========================================================
# 2. 메인 수집기
# =========================================================
def run_rss_collector():
    print(f"[{datetime.now()}] RSS Collecting Started...")
    
    system_user = User.objects.filter(is_superuser=True).first()
    if not system_user:
        print("❌ System admin user not found. Create superuser first.")
        return

    total_count = 0

    for feed_config in RSS_FEEDS:
        print(f"\n📡 Parsing Feed: {feed_config['name']} ...")
        
        try:
            # RSS 다운로드
            response = requests.get(
                feed_config['url'], 
                headers=get_headers(), 
                timeout=20 
            )
            
            if response.status_code != 200:
                print(f"   -> Error: Status Code {response.status_code}")
                continue
                
            feed = feedparser.parse(response.content)
            
        except Exception as e:
            print(f"   -> Network Error: {e}")
            continue

        if not feed.entries:
            print(f"   -> Empty Feed")
            continue

        # =========================================================
        # [핵심 수정] 항목별 순차 처리 (디코딩 및 중복 체크)
        # =========================================================
        for entry in feed.entries:
            if not hasattr(entry, 'link'): continue
            
            raw_link = entry.link
            
            # 1. URL 디코딩 (구글 뉴스 대응)
            # 이 과정이 있어야 '진짜 URL'로 중복 체크와 크롤링이 가능함
            target_url = get_final_url(raw_link)

            # 2. 중복 체크 (DB에 이미 있는 원본 URL인지 확인)
            # Bulk Check 방식을 제거하고 개별 체크로 변경 (디코딩된 URL 기준이어야 하므로)
            if Article.objects.filter(url=target_url).exists():
                # title_preview = getattr(entry, 'title', 'No Title')[:20]
                # print(f"   - Skipped (Exists): {title_preview}...") 
                continue

            title = getattr(entry, 'title', 'No Title')
            print(f"   + New Found: {title[:30]}...")

            # 3. 본문 크롤링 (Crawling)
            # 반드시 디코딩된 target_url을 넘겨야 함
            data = extract_article(target_url)

            if not data or not data['content']:
                print("     -> Failed (No Content)")
                continue

            # 4. AI 카테고리 분류 (Classification)
            refined_category = feed_config['category_base'] # 기본값
            try:
                # RSS 설정의 region 정보를 넘겨 정밀 분류
                refined_category = classify_news(data['content'], region=feed_config['region'])
                print(f"     -> [AI Classify] {feed_config.get('category_base')} ➡️  {refined_category}")
            except Exception as e:
                print(f"     -> [AI Error] Using default: {e}")

            # 5. DB 저장 (Save)
            # 임베딩은 여기서 하지 않고, ai_service.py의 별도 로직이나 Signal이 처리한다고 가정
            try:
                Article.objects.create(
                    user=system_user,
                    region=feed_config['region'],
                    url=target_url, # [중요] 원본 URL 저장
                    source=Article.Source.RSS_CRAWLED,
                    title=data['title'],
                    content=data['content'], 
                    summary=data['content'][:500], # 요약 필드 (일단 앞부분)
                    thumbnail_url=data.get('thumbnail_url', ''),
                    
                    category=refined_category, # AI가 분류한 카테고리
                    article_type='FACT', # 기본값
                    
                    status=Article.Status.PENDING
                )
                total_count += 1
                
                # 디코딩 및 크롤링 부하 조절 (랜덤 딜레이)
                time.sleep(random.uniform(1.0, 2.0))
                
            except Exception as e:
                if "unique" in str(e).lower():
                    print("     -> Skipped (Duplicate during save)")
                else:
                    print(f"     -> DB Save Error: {e}")

    print(f"\n✅ Collection Finished. {total_count} articles added.")