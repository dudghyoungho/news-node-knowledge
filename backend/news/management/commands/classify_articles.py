# backend/news/management/commands/classify_articles.py

from django.core.management.base import BaseCommand
from news.models import Article
from news.ai_service import classify_news
import time

class Command(BaseCommand):
    help = '기존 기사들의 article_type(FACT/INSIGHT 등)을 AI로 재분류합니다.'

    def handle(self, *args, **options):
        # article_type이 기본값이거나 비어있는 기사들만 타겟팅 (비용 절감)
        # 만약 전체를 다 다시 하고 싶다면 .all()로 변경
        target_articles = Article.objects.filter(article_type='FACT') 
        
        total = target_articles.count()
        print(f"🚀 총 {total}개의 기사를 재분류합니다...")

        for i, article in enumerate(target_articles):
            if not article.content:
                print(f"⚠️ [Skip] 본문 없음: {article.title}")
                continue
            
            try:
                # AI 호출
                result = classify_news(article.content, article.region)
                new_type = result.get('type', 'FACT')
                new_category = result.get('category', 'General')

                # DB 업데이트
                article.article_type = new_type
                article.category = new_category # 카테고리도 최신 로직으로 갱신
                article.save()

                print(f"[{i+1}/{total}] {new_type} | {article.title[:30]}...")
                
                # API Rate Limit 방지 (너무 빠르면 에러남)
                time.sleep(0.5) 

            except Exception as e:
                print(f"❌ Error on {article.id}: {e}")

        print("✅ 모든 기사 재분류 완료!")