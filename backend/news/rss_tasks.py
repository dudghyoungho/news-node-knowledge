import feedparser
import time
import random
import requests
from datetime import datetime
from django.contrib.auth import get_user_model
from .models import Article
from .rss_config import RSS_FEEDS
# [기존] 크롤러 헤더 가져오기
from .crawler import extract_article, get_headers
# [신규] AI 분류 함수 임포트
from .ai_service import classify_news

User = get_user_model()

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
            # 1. RSS XML 다운로드
            response = requests.get(
                feed_config['url'], 
                headers=get_headers(), 
                timeout=20 
            )
            
            if response.status_code != 200:
                print(f"   -> Error: Status Code {response.status_code}")
                continue
                
            # 2. 파싱
            feed = feedparser.parse(response.content)
            
        except Exception as e:
            print(f"   -> Network Error: {e}")
            continue

        if not feed.entries:
            print(f"   -> Empty Feed (No items found)")
            if b"<!DOCTYPE html" in response.content[:50]:
                 print("   -> 🚨 Blocked (HTML response received)")
            continue

        # URL 파라미터 보존 로직 (기존 유지)
        rss_entries_map = {}
        for entry in feed.entries:
            if not hasattr(entry, 'link'): continue
            target_link = entry.link
            rss_entries_map[target_link] = entry

        # Bulk Check (기존 유지)
        target_urls = list(rss_entries_map.keys())
        existing_urls = set(
            Article.objects.filter(url__in=target_urls)
                           .values_list('url', flat=True)
        )

        # =========================================================
        # 크롤링 및 AI 분류 저장
        # =========================================================
        for clean_url, entry in rss_entries_map.items():
            
            if clean_url in existing_urls:
                title_preview = getattr(entry, 'title', 'No Title')[:20]
                # print(f"   - Skipped (Exists): {title_preview}...") # 로그 너무 길면 주석 처리
                continue

            title = getattr(entry, 'title', 'No Title')
            print(f"   + Crawling: {title[:30]}...")
            
            # 본문 추출 시도
            data = extract_article(clean_url)

            if not data:
                print("     -> Failed (No Content or Filtered)")
                continue

            # -------------------------------------------------------------
            # [핵심 수정] 정공법: AI에게 정밀 카테고리 분류 요청
            # -------------------------------------------------------------
            try:
                # RSS 설정에 있는 region 정보를 넘겨줘야 한국어/영어 카테고리를 정확히 구분함
                # 예: 'Economy' -> AI 분류 -> '주식/투자' or 'Real Estate'
                refined_category = classify_news(data['content'], region=feed_config['region'])
                
                # 로그로 확인 (기존 RSS 대분류 -> AI 세분류)
                print(f"     -> [AI Classify] {feed_config.get('category_base')} ➡️  {refined_category}")
                
            except Exception as e:
                print(f"     -> [AI Error] 분류 실패, 기본값 사용: {e}")
                refined_category = feed_config['category_base']

            # 저장
            try:
                Article.objects.create(
                    user=system_user,
                    region=feed_config['region'],
                    url=clean_url,
                    source=Article.Source.RSS_CRAWLED,
                    title=data['title'],
                    content=data['content'],
                    thumbnail_url=data['thumbnail_url'],
                    
                    # [변경] RSS Config의 기본값이 아니라, AI가 정해준 정밀 카테고리로 저장
                    category=refined_category, 
                    
                    status=Article.Status.PENDING
                )
                total_count += 1
                
                # AI 호출 및 사이트 부하 고려 딜레이 (1~2초)
                time.sleep(random.uniform(1.0, 2.0))
                
            except Exception as e:
                if "unique" in str(e).lower():
                    print("     -> Skipped (Duplicate in DB)")
                else:
                    print(f"     -> DB Error: {e}")

    print(f"\n✅ Collection Finished. {total_count} articles added.")