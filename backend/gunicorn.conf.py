# backend/gunicorn.conf.py — 운영 gunicorn 설정
# 실행: gunicorn -c backend/gunicorn.conf.py   (/app에서. compose와 Dockerfile이 이렇게 부른다)
#
# 왜 프로세스 1개 + 스레드 4개(gthread)인가
# - 요약은 스트리밍 응답이라 끝날 때까지 처리 단위 하나를 붙잡는다. 예전 설정(동기 워커 1개)에서는
#   누군가 요약하는 동안 다른 모든 요청이 기다렸다. 스레드 4개면 4개 요청을 동시에 처리한다.
# - 프로세스를 늘리면 임베딩 모델(약 1GB)이 프로세스마다 올라가 4GB 서버에 부담이 크다.
# - API 호출 제한 횟수를 프로세스 메모리(LocMem)에 적는다(news/throttles.py). 프로세스가
#   여러 개면 한도가 그 수만큼 늘어난다. 프로세스를 늘릴 때는 Redis 캐시로 먼저 옮긴다.
# - --preload(모델을 부모 프로세스에서 불러와 복제)는 프로세스가 1개라 이점이 없고,
#   torch를 불러온 뒤 fork하면 멈추는 문제가 있어 쓰지 않는다. 대신 아래 훅에서 불러온다.

chdir = "backend"
wsgi_app = "config.wsgi:application"
bind = "0.0.0.0:8000"

workers = 1
worker_class = "gthread"
threads = 4

# 긴 기사 요약 스트리밍과 첫 모델 로딩이 30초(기본값)를 넘을 수 있다
timeout = 120
graceful_timeout = 30

# 접속 로그(accesslog)는 켜지 않는다: Docker 로그에 크기 제한이 없어 디스크가 계속 찬다


def post_worker_init(worker):
    """워커가 요청을 받기 전에 모델을 미리 불러온다."""
    from news.warmup import preload_models

    try:
        timings = preload_models()
        worker.log.info("모델 미리 불러오기 완료: %s", timings)
    except Exception:
        # 미리 불러오기가 실패해도 서비스는 띄운다 (첫 요청 때 다시 시도됨)
        worker.log.exception("모델 미리 불러오기 실패")
