#!/usr/bin/env bash
# 백업 파일이 실제로 복원되는지 검사한다.
#
# 운영 DB는 건드리지 않는다. 같은 DB 이미지로 임시 컨테이너를 띄워 거기에 복원하고,
# 주요 테이블의 행 수를 운영 DB와 나란히 보여 준 뒤 임시 컨테이너를 지운다.
#
# 사용: scripts/verify_backup.sh [백업 파일]     (생략하면 가장 최근 자동 백업)
# 환경변수: BACKUP_DIR(기본 ~/backups), COMPOSE_FILE(기본 docker-compose.prod.yml)
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

file="${1:-$(ls -1t "$BACKUP_DIR"/news_db_*.dump 2>/dev/null | head -1 || true)}"
if [ -z "$file" ] || [ ! -s "$file" ]; then
    echo "검사할 백업 파일이 없습니다: ${file:-$BACKUP_DIR/news_db_*.dump}" >&2
    exit 1
fi

# 운영과 같은 이미지(digest 고정)를 쓴다
image="$(docker compose -f "$COMPOSE_FILE" config --images | grep pgvector | head -1)"
name="news-restore-test-$$"

echo "백업 파일 : $file ($(du -h "$file" | cut -f1))"
echo "DB 이미지 : $image"

# 포트를 열지 않는 임시 컨테이너. 비밀번호는 이 검사에서만 쓰는 임의 값
docker run -d --rm --name "$name" \
    -e POSTGRES_PASSWORD="restore-test-$$" -e POSTGRES_DB=restore_test \
    "$image" > /dev/null
trap 'docker rm -f "$name" > /dev/null 2>&1 || true' EXIT

for _ in $(seq 1 60); do
    # 초기화 중 임시 서버가 잠깐 떴다 내려가므로, 실제 DB 접속까지 확인한다
    docker exec "$name" psql -U postgres -d restore_test -c 'select 1' > /dev/null 2>&1 && break
    sleep 1
done

# 소유자·권한 정보는 빼고 복원한다 (임시 컨테이너에는 운영 DB 계정이 없음)
docker exec -i "$name" pg_restore -U postgres -d restore_test \
    --no-owner --no-acl --exit-on-error < "$file"

query="select 'auth_user' as t, count(*) from auth_user
union all select 'news_article', count(*) from news_article
union all select 'news_useractionlog', count(*) from news_useractionlog
union all select 'news_userprofile', count(*) from news_userprofile
union all select 'django_migrations', count(*) from django_migrations"

echo
echo "== 복원한 백업"
docker exec "$name" psql -U postgres -d restore_test -At -F ' : ' -c "$query"
echo
echo "== 지금 운영 DB (백업 이후 늘어난 만큼 더 많을 수 있음)"
docker compose -f "$COMPOSE_FILE" exec -T db \
    sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F " : " -c "$1"' _ "$query"
echo
echo "복원 성공"
