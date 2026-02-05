# backend/news/tasks.py
import feedparser
import time
import random
from datetime import datetime
from django.contrib.auth import get_user_model
from .models import Article
from .rss_config import RSS_FEEDS
from .crawler import extract_article

User = get_user_model()

def run_rss_collector():
    print(f"[{datetime.now()}] RSS Collecting Started...")
    
    # 시스템 관리자 계정 (기사 소유주)
    system_user = User.objects.filter(is_superuser=True).first()
    if not system_user:
        print("❌ System admin user not found. Create superuser first.")
        return

    total_count = 0

    for feed_config in RSS_FEEDS:
        print(f"\n📡 Parsing Feed: {feed_config['name']} ...")
        
        # feedparser도 User-Agent를 설정할 수 있음
        feed = feedparser.parse(feed_config['url'], agent=random.choice(['Mozilla/5.0', 'Chrome/90.0']))
        
        # 최신 5개만 가져오기 (너무 과거 기사는 필요 없음)
        for entry in feed.entries[:5]:
            
            # 1. URL 정제 (UTM 파라미터 제거)
            clean_url = entry.link.split('?')[0]
            if "news.google.com" in clean_url: 
                # 구글 뉴스는 링크 자체가 중요하므로 자르지 않음 (리다이렉트용)
                clean_url = entry.link

            # 2. 중복 검사
            if Article.objects.filter(url=clean_url).exists():
                print(f"   - Skipped (Exists): {entry.title[:20]}...")
                continue

            # 3. 크롤링 (본문 확보)
            print(f"   + Crawling: {entry.title[:30]}...")
            data = extract_article(entry.link)

            if not data:
                print("     -> Failed (No Content)")
                continue

            # 4. 저장 (Item Tower의 재료)
            try:
                Article.objects.create(
                    user=system_user,
                    region=feed_config['region'],
                    url=clean_url,
                    title=data['title'],
                    content=data['content'],
                    thumbnail_url=data['thumbnail_url'],
                    category=feed_config['category_base'], # 1차 분류 (추후 AI로 정교화)
                    status=Article.Status.PENDING # 아직 임베딩 안 됨
                )
                total_count += 1
                
                # ★ [핵심] 차단 방지용 랜덤 휴식 (1.5초 ~ 3.5초)
                sleep_time = random.uniform(1.5, 3.5)
                time.sleep(sleep_time)
                
            except Exception as e:
                print(f"     -> DB Error: {e}")

    print(f"\n✅ Collection Finished. {total_count} articles added.")