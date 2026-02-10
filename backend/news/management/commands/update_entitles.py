import time
from django.core.management.base import BaseCommand
from news.models import Article
from news.nlp_utils import extract_entities

class Command(BaseCommand):
    help = '기존 기사들의 NER(개체명) 데이터를 추출하여 업데이트합니다.'

    def handle(self, *args, **options):
        # 1. 대상 선정: entities 필드가 비어있는 기사만 조회
        # (PostgreSQL의 경우 JSONField 빈 값은 보통 {} 입니다)
        articles = Article.objects.filter(entities__exact={})
        total_count = articles.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ 업데이트할 기사가 없습니다."))
            return

        self.stdout.write(self.style.WARNING(f"🚀 총 {total_count}개의 기사 업데이트 시작..."))

        success_count = 0
        
        # 2. [메모리 최적화] iterator() 사용
        # objects.all()로 가져오면 2GB 램이 터질 수 있습니다.
        # chunk_size만큼 끊어서 가져옵니다.
        for i, article in enumerate(articles.iterator(chunk_size=100)):
            if not article.content:
                continue

            try:
                # NER 추출 실행
                entities = extract_entities(article.content, region=article.region)
                
                # 업데이트 및 저장
                article.entities = entities
                
                # [DB 최적화] update_fields 사용
                # 전체 필드를 다시 쓰지 않고 entities 필드만 업데이트하여 빠릅니다.
                article.save(update_fields=['entities'])
                
                success_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error ID {article.id}: {e}"))

            # 진행 상황 표시 (10개마다)
            if (i + 1) % 10 == 0:
                self.stdout.write(f"   -> {i + 1}/{total_count} 완료...")

            # CPU 과부하 방지 (약간의 텀)
            # time.sleep(0.05) 

        self.stdout.write(self.style.SUCCESS(f"✅ 업데이트 완료! (성공: {success_count}/{total_count})"))