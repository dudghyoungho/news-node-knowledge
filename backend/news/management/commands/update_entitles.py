import time
from django.core.management.base import BaseCommand
from django.db.models import Q
from news.models import Article
from news.nlp_utils import extract_entities

class Command(BaseCommand):
    help = '기존 기사들의 NER(개체명) 데이터를 추출하여 업데이트합니다. (실패했던 기사 재시도 포함)'

    def handle(self, *args, **options):
        # 1. 대상 선정: 비어있거나, 이전에 '개체명 없음'으로 잘못 판정된 기사 모두 포함
        articles = Article.objects.filter(
            Q(entities__isnull=True) | 
            Q(entities={}) | 
            Q(entities=[]) | 
            Q(entities="") |
            Q(entities={"_status": "no_entities_found"}) # [핵심 추가] 이전에 실패했던 기사들도 다시 불러옵니다!
        )
        total_count = articles.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ 업데이트할 기사가 없습니다."))
            return

        self.stdout.write(self.style.WARNING(f"🚀 총 {total_count}개의 기사 업데이트 시작..."))

        success_count = 0
        skipped_count = 0 # 본문이 없어서 스킵된 개수 추적
        
        # 2. [메모리 최적화] iterator() 사용
        for i, article in enumerate(articles.iterator(chunk_size=100)):
            # 본문이 없는 경우, 상태를 기록하여 무한 재시도 방지
            if not article.content:
                article.entities = {"_status": "no_content"} # 빈 값 대신 상태를 명시
                article.save(update_fields=['entities'])
                skipped_count += 1
                continue

            try:
                # NER 추출 실행 (이제 한국어/영어 모두 정상 작동합니다)
                entities = extract_entities(article.content, region=article.region)
                
                # 추출 결과가 여전히 비어있을 경우 (진짜 개체명이 없는 기사)
                if not entities:  
                    entities = {"_status": "no_entities_found"}
                
                # 업데이트 및 저장
                article.entities = entities
                article.save(update_fields=['entities'])
                
                success_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error ID {article.id}: {e}"))

            # 진행 상황 표시 (100개마다 출력하여 콘솔 부하 줄임)
            if (i + 1) % 100 == 0:
                self.stdout.write(f"   -> {i + 1}/{total_count} 완료...")

        self.stdout.write(self.style.SUCCESS(
            f"✅ 작업 완료! (추출 성공: {success_count}건 / 본문 없음 스킵: {skipped_count}건)"
        ))