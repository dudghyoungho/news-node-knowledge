import json
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

# [핵심 변경 1] DRF 전용 팩토리와 강제 인증 함수 임포트
from rest_framework.test import APIRequestFactory, force_authenticate

# 기존 뷰 임포트
from news.views.article_views import save_article 
from news.models import Article

class Command(BaseCommand):
    help = '기존 save_article 로직을 재사용하여 실제 기사를 크롤링하고 데모 데이터를 구축합니다.'

    def handle(self, *args, **options):
        User = get_user_model()
        username = 'demo_guest'
        
        # 1. 데모 유저 생성
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password('demo1234')
            user.save()
            self.stdout.write(self.style.SUCCESS(f"✅ 데모 유저 '{username}' 생성 완료"))

        # 2. 기존 데이터 삭제
        deleted_count, _ = Article.objects.filter(user=user).delete()
        self.stdout.write(f"🧹 기존 데이터 {deleted_count}개 삭제 완료.")

        # 3. URL 리스트
        target_urls = [
            # --- [Cluster 1] Tech & AI ---
            {"url": "https://openai.com/index/hello-gpt-4o/", "days_ago": 30},
            {"url": "https://nvidianews.nvidia.com/news/nvidia-blackwell-platform-arrives-to-power-a-new-era-of-computing", "days_ago": 60},
            {"url": "https://www.anthropic.com/news/claude-3-5-sonnet", "days_ago": 7},
            {"url": "https://ai.meta.com/blog/meta-llama-3-1/", "days_ago": 15},
            {"url": "https://www.apple.com/newsroom/2024/06/introducing-apple-intelligence-for-iphone-ipad-and-mac/", "days_ago": 10},
            
            # --- [Cluster 2] Economy & Policy ---
            {"url": "https://www.cnbc.com/2024/06/12/fed-meeting-june-2024-interest-rate-decision.html", "days_ago": 5},
            {"url": "https://www.reuters.com/technology/space/spacex-starship-rocket-survives-reentry-historic-test-flight-2024-06-06/", "days_ago": 20},
            {"url": "https://www.whitehouse.gov/briefing-room/statements-releases/2024/04/08/biden-harris-administration-announces-preliminary-terms-with-tsmc-under-the-chips-and-science-act/", "days_ago": 40},
            
            # --- [Bridge] Tech <-> Biz ---
            {"url": "https://news.samsung.com/global/samsung-electronics-starts-mass-production-of-industrys-first-12-stack-hbm3e-dram", "days_ago": 25},
            {"url": "https://group.softbank/en/news/press/20240216", "days_ago": 45}
        ]

        # [핵심 변경 2] 일반 RequestFactory 대신 APIRequestFactory 사용
        factory = APIRequestFactory()
        count = 0
        
        self.stdout.write("🚀 실제 크롤링 및 임베딩 생성을 시작합니다. (시간이 조금 걸립니다...)")

        for item in target_urls:
            url = item['url']
            days_ago = item['days_ago']

            try:
                self.stdout.write(f"🌐 처리 중: {url}")

                # [핵심 변경 3] JSON 데이터 생성 방식 변경 (json.dumps 불필요)
                # APIRequestFactory는 format='json'을 지원하여 자동으로 파싱해줍니다.
                request = factory.post(
                    '/api/news/save/', 
                    {'url': url}, 
                    format='json'
                )
                
                # [핵심 변경 4] 강제 인증 (CSRF 및 권한 우회)
                # 이 코드가 있어야 403 에러가 나지 않습니다.
                force_authenticate(request, user=user)

                # 뷰 실행
                response = save_article(request)

                if response.status_code in [200, 201]:
                    # 저장된 기사 찾아서 날짜 변경
                    saved_article = Article.objects.filter(user=user, url=url).first()
                    
                    if saved_article:
                        saved_article.created_at = timezone.now() - timedelta(days=days_ago)
                        saved_article.status = 'READ' if days_ago > 20 else 'SAVED'
                        saved_article.save(update_fields=['created_at', 'status'])
                        count += 1
                        self.stdout.write(f"  └─ ✅ 저장 성공! ({saved_article.title[:20]}...)")
                    else:
                        self.stdout.write(self.style.WARNING(f"⚠️ 저장 메시지는 왔으나 DB 조회 실패: {url}"))
                else:
                    self.stdout.write(self.style.ERROR(f"❌ 저장 실패 ({response.status_code}): {url}"))
                    # 디버깅을 위해 에러 메시지가 있다면 출력
                    if hasattr(response, 'data'):
                        print(f"     Reason: {response.data}")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"🔥 에러 발생 ({url}): {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"✅ 총 {count}개의 리얼 데이터 주입 완료!"))