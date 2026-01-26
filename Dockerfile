# Dockerfile

FROM python:3.11-slim

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

COPY requirements.txt /app/

# [수정] gunicorn 명시적 설치 (requirements.txt에 있어도 안전장치로 추가)
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install gunicorn trafilatura

# 소스 코드 복사
COPY . /app/

# [수정] 기본 실행 명령을 Gunicorn으로 변경 (안전장치)
# 실제 실행은 docker-compose command가 덮어쓰지만, 이미지는 프로덕션용으로 맞춤
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--chdir", "backend", "config.wsgi:application"]