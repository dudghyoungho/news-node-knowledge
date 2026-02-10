import feedparser
import time
import random
import requests
import logging
from datetime import datetime
from django.utils import timezone
from time import mktime
from django.contrib.auth import get_user_model

from .models import Article
from .rss_config import RSS_FEEDS
from .nlp_utils import extract_entities

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

        for entry in feed.entries:
            if not hasattr(entry, 'link'): continue
            
            raw_link = entry.link
            title = getattr(entry, 'title', 'No Title')
            
            # 1. URL 디코딩
            target_url = get_final_url(raw_link)

            # 2. 중복 방어
            if Article.objects.filter(url=target_url).exists():
                continue

            yesterday = timezone.now() - timezone.timedelta(days=7)
            if Article.objects.filter(title=title, created_at__gte=yesterday).exists():
                # print(f"   - Skipped (Title Exists): {title[:20]}...")
                continue
            
            print(f"   + New Found: {title[:30]}...")

            # 3. 본문 크롤링
            data = extract_article(target_url)

            if not data or not data['content']:
                print("     -> Failed (No Content)")
                continue

            # 4. AI 카테고리 분류
            final_category = feed_config.get('category_base', 'General')
            final_type = 'FACT'

            try:
                ai_result = classify_news(data['content'], region=feed_config['region'])
                if isinstance(ai_result, dict):
                    final_category = ai_result.get('category', final_category)
                    final_type = ai_result.get('type', 'FACT')
                else:
                    final_category = str(ai_result)
            except Exception as e:
                print(f"     -> [AI Error] Using default: {e}")

            # 4-2. 날짜 파싱
            published_at = timezone.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    dt = datetime.fromtimestamp(mktime(entry.published_parsed))
                    published_at = timezone.make_aware(dt)
                except Exception as e:
                    pass

            # =========================================================
            # [핵심 수정] 4-3. NER 개체 추출 (nlp_utils 활용)
            # =========================================================
            try:
                # 본문 내용을 바탕으로 인물/조직 추출
                extracted_entities = extract_entities(data['content'], region=feed_config['region'])
                # 디버깅용 출력 (필요 시 주석 해제)
                # print(f"     -> NER: {extracted_entities}")
            except Exception as e:
                print(f"     -> [NER Error] {e}")
                extracted_entities = {}

            # =========================================================
            # [핵심 수정] 5. DB 저장 (entities 필드 추가)
            # =========================================================
            try:
                Article.objects.create(
                    user=system_user,
                    region=feed_config['region'],
                    url=target_url, 
                    source=Article.Source.RSS_CRAWLED,
                    title=data['title'],
                    content=data['content'], 
                    summary=data['content'][:500],
                    thumbnail_url=data.get('thumbnail_url', ''),
                    
                    category=final_category, 
                    article_type=final_type,
                    created_at=published_at,
                    status=Article.Status.PENDING,
                    
                    # [New] 여기가 핵심입니다: 추출한 개체명을 DB에 저장
                    entities=extracted_entities 
                )
                total_count += 1
                
                time.sleep(random.uniform(1.0, 2.0))
                
            except Exception as e:
                if "unique" in str(e).lower():
                    print("     -> Skipped (Duplicate during save)")
                else:
                    print(f"     -> DB Save Error: {e}")

    print(f"\n✅ Collection Finished. {total_count} articles added.")