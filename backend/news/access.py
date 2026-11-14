# backend/news/access.py
"""
사용자가 볼 수 있는 기사 범위.

- 내가 저장한 기사 (source=USER, user=나)
- RSS로 수집한 공용 기사 (source=RSS, 관리자 소유)

다른 사용자가 저장한 기사는 개인 서재이므로 조회·추천·Bridge 후보 어디에도 쓰지 않는다.
기사를 id나 url로 찾거나 후보군을 만들 때는 Article.objects 대신 이 함수를 쓴다.
"""
from django.db.models import Q

from .models import Article


def visible_articles(user):
    return Article.objects.filter(Q(user=user) | Q(source=Article.Source.RSS_CRAWLED))


# 데모 계정: 랜딩 "View Live Demo"와 확장의 데모 로그인이 공유하는 계정
DEMO_USERNAME = 'demo_guest'


def is_demo_user(user):
    return bool(user) and getattr(user, 'username', None) == DEMO_USERNAME
