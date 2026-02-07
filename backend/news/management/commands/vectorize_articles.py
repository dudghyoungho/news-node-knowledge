import torch
from django.core.management.base import BaseCommand
from sentence_transformers import SentenceTransformer
from news.ai_service import get_local_model
from news.models import Article
import time

class Command(BaseCommand):
    help = '수집된 기사를 읽어서 PyTorch 모델로 벡터화하여 embedding_pytorch 필드에 저장합니다.'

    def handle(self, *args, **kwargs):
        # 1. AI 모델 로딩
        self.stdout.write("🏗️  AI 모델을 불러오는 중입니다... (paraphrase-multilingual-mpnet-base-v2)")
        # Lightsail 사양에 따라 처음 실행 시 모델 다운로드에 시간이 걸릴 수 있습니다.
        model = get_local_model()
        
        # 2. 새로운 필드(embedding_pytorch)가 비어있는 기사들만 필터링
        # 이전에 embedding이었던 부분을 embedding_pytorch__isnull로 변경했습니다.
        articles = Article.objects.filter(embedding_pytorch__isnull=True)
        total_count = articles.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ 모든 기사가 이미 PyTorch 벡터화 완료되었습니다."))
            return

        self.stdout.write(f"🚀 총 {total_count}개의 기사를 변환 시작합니다!")

        success_count = 0
        
        for article in articles:
            try:
                # AI에게 입력할 텍스트 구성
                summary = article.content[:200] if article.content else ""
                input_text = f"[{article.category}] {article.title}. {summary}"

                # 텍스트 -> 768차원 벡터 변환
                vector = model.encode(input_text)

                # [중요] 변경된 필드명 'embedding_pytorch'에 저장
                article.embedding_pytorch = vector.tolist()
                article.save()
                
                success_count += 1
                
                if success_count % 10 == 0:
                    self.stdout.write(f"   -> {success_count}/{total_count} 처리 완료...")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"⚠️ 에러 발생 (ID: {article.id}): {e}"))
                continue

        self.stdout.write(self.style.SUCCESS(f"🎉 변환 완료! 총 {success_count}개의 기사가 Item Tower(PyTorch)에 등록되었습니다."))