# backend/news/rss_tasks.py

import feedparser
import time
import random
import requests
from datetime import datetime
from django.contrib.auth import get_user_model
from .models import Article
from .rss_config import RSS_FEEDS
# [수정] crawler에서 헤더 생성 함수 가져오기 (일관성 유지)
from .crawler import extract_article, get_headers 

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
            # crawler.py와 동일한 헤더(User-Agent)를 사용하여 차단 회피
            response = requests.get(
                feed_config['url'], 
                headers=get_headers(), 
                timeout=20 # 타임아웃 넉넉하게 (해외 사이트 고려)
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

        # =========================================================
        # [로직 변경] URL 파라미터 보존 (Trust Original Link)
        # =========================================================
        # 이제 다양한 소스(Reddit, Donga, MK 등)를 다루므로,
        # ? 뒤를 함부로 자르면 링크가 깨지거나(404) 중복으로 오인될 수 있습니다.
        # RSS가 주는 링크를 그대로 믿는 것이 가장 안전합니다.
        
        rss_entries_map = {}
        for entry in feed.entries:
            # 링크가 없는 항목 방어
            if not hasattr(entry, 'link'):
                continue

            # 원본 링크 그대로 사용
            target_link = entry.link
            
            # [선택] 명백한 추적 코드는 제거하고 싶다면 아래처럼 보수적으로 처리
            # (하지만 RSS 링크는 보통 Clean하므로 그대로 두는 것을 추천)
            # if "utm_source" in target_link:
            #     target_link = target_link.split('?utm_source')[0]

            rss_entries_map[target_link] = entry

        # =========================================================
        # Bulk Check (DB 조회 최적화)
        # =========================================================
        target_urls = list(rss_entries_map.keys())
        
        # 이미 DB에 있는 URL들을 한 번에 조회
        existing_urls = set(
            Article.objects.filter(url__in=target_urls)
                           .values_list('url', flat=True)
        )

        # =========================================================
        # 크롤링 및 저장
        # =========================================================
        for clean_url, entry in rss_entries_map.items():
            
            if clean_url in existing_urls:
                # 제목 출력 시 길이 제한 안전장치
                title_preview = getattr(entry, 'title', 'No Title')[:20]
                print(f"   - Skipped (Exists): {title_preview}...")
                continue

            title = getattr(entry, 'title', 'No Title')
            print(f"   + Crawling: {title[:30]}...")
            
            # 본문 추출 시도
            data = extract_article(clean_url)

            if not data:
                print("     -> Failed (No Content or Filtered)")
                continue

            try:
                Article.objects.create(
                    user=system_user,
                    region=feed_config['region'],
                    url=clean_url,
                    source=Article.Source.RSS_CRAWLED,
                    title=data['title'],
                    content=data['content'],
                    thumbnail_url=data['thumbnail_url'],
                    category=feed_config['category_base'],
                    status=Article.Status.PENDING
                )
                total_count += 1
                
                # 사이트 부하 방지를 위한 랜덤 딜레이
                time.sleep(random.uniform(1.0, 2.0))
                
            except Exception as e:
                # 유니크 제약조건 등 DB 에러 방어
                if "unique" in str(e).lower():
                    print("     -> Skipped (Duplicate in DB)")
                else:
                    print(f"     -> DB Error: {e}")

    print(f"\n✅ Collection Finished. {total_count} articles added.")