# backend/news/warmup.py
"""
서버가 요청을 받기 전에 무거운 것들을 미리 불러온다.

gunicorn 설정(backend/gunicorn.conf.py)의 post_worker_init 훅에서 부른다.
미리 불러오지 않으면 재시작 후 첫 사용자가 그 시간을 기다려야 한다(2026-11-12 측정 17초).

- URL 설정: 뷰 모듈을 import하면서 spaCy 한/영 모델(nlp_utils)도 같이 올라간다
- 로컬 임베딩 모델(약 1GB): 저장·읽기 로그 처리에 쓰인다

runserver(개발)와 테스트에서는 부르지 않는다. 코드를 고칠 때마다 다시 불러오면 느리기 때문이다.
"""
import time


def preload_models():
    """불러온 항목과 걸린 시간(초)을 돌려준다."""
    timings = {}

    start = time.monotonic()
    from django.urls import get_resolver
    get_resolver().url_patterns  # URLconf → 뷰 → nlp_utils(spaCy) import
    timings['urls+spacy'] = round(time.monotonic() - start, 1)

    start = time.monotonic()
    from .ai_service import get_local_model
    get_local_model()
    timings['embedding_model'] = round(time.monotonic() - start, 1)

    return timings
