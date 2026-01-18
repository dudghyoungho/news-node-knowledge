# Makefile
.PHONY: init up down shell migrate makemigrations

# 1. 초기 세팅 (이미지 빌드 + 장고 프로젝트 생성)
init:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	docker-compose build
	docker-compose run --rm web django-admin startproject config backend

# 2. 서버 실행
up:
	docker-compose up

# 3. 서버 중지 (볼륨 삭제 X)
down:
	docker-compose down

# 4. 컨테이너 내부 쉘 접속 (디버깅용)
shell:
	docker-compose exec web /bin/bash

# 5. 마이그레이션 적용
migrate:
	docker-compose exec web python backend/manage.py migrate

# 6. 마이그레이션 파일 생성
makemigrations:
	docker-compose exec web python backend/manage.py makemigrations

# 7. 슈퍼유저 생성
superuser:
	docker-compose exec web python backend/manage.py createsuperuser

