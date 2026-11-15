# Dockerfile

# 버전 고정 (2026-11-08 동작 확인). 바꿀 때는 constraints.txt도 다시 만들 것
FROM python:3.11.18-slim-trixie

# 파이썬 출력 버퍼링 비활성화 (로그 즉시 출력)
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt constraints.txt /app/

# 1) torch는 CPU판을 먼저 설치 (PyPI 기본은 CUDA판이라 이미지가 10GB 넘게 커짐)
# 2) 나머지는 requirements.txt + constraints.txt(하위 의존성까지 전체 고정)
RUN pip install pip==26.3 && \
    pip install torch==2.15.0+cpu --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r requirements.txt -c constraints.txt

# spaCy 모델도 버전 고정 (spacy 3.8.x 호환)
RUN python -m spacy download en_core_web_sm-3.8.0 --direct
RUN python -m spacy download ko_core_news_sm-3.8.0 --direct

# 소스 코드 복사
COPY . /app/

# [수정] 기본 실행 명령을 Gunicorn으로 변경 (안전장치)
# 실제 실행은 docker-compose command가 덮어쓰지만, 이미지는 프로덕션용으로 맞춤
CMD ["gunicorn", "-c", "backend/gunicorn.conf.py"]