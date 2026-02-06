# backend/news/management/commands/collect_rss.py

from django.core.management.base import BaseCommand
from news.rss_tasks import run_rss_collector

class Command(BaseCommand):
    help = 'RSS 피드에서 뉴스를 수집하여 Item Tower 후보군(Article)을 생성합니다.'

    def handle(self, *args, **options):
        # 1. 시작 메시지 출력 (Django 스타일)
        self.stdout.write(self.style.SUCCESS('RSS 수집기를 시작합니다...'))
        
        try:
            # 2. rss_tasks.py의 메인 함수 실행
            run_rss_collector()
            
            # 3. 완료 메시지
            self.stdout.write(self.style.SUCCESS('모든 RSS 수집 작업이 성공적으로 완료되었습니다.'))
            
        except ImportError:
            self.stdout.write(self.style.ERROR(
                "모듈을 찾을 수 없습니다. 'backend/news/rss_tasks.py' 파일이 존재하는지 확인해주세요."
            ))
        except Exception as e:
            # 예상치 못한 최상위 에러 처리
            self.stdout.write(self.style.ERROR(f'RSS 수집 중 치명적인 오류 발생: {str(e)}'))