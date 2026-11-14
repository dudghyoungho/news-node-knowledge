#!/usr/bin/env bash
# DB 백업: pg_dump(custom 형식, 압축됨) → $BACKUP_DIR/news_db_YYYY-MM-DD_HHMMSS.dump
#
# 서버 cron에서 매일 실행한다 (등록 방법: docs/LIGHTSAIL_RUNBOOK.md 또는 아래 예시).
#   30 18 * * * /home/ubuntu/news-node-knowledge/scripts/backup_db.sh >> /home/ubuntu/backups/backup.log 2>&1
#
# 환경변수 (모두 선택)
#   BACKUP_DIR    저장 폴더          기본: ~/backups
#   KEEP_DAYS     보관 일수          기본: 14
#   COMPOSE_FILE  compose 파일       기본: docker-compose.prod.yml
#
# 실패하면(덤프 실패, 빈 파일, 깨진 파일) 0이 아닌 코드로 끝나고 파일을 남기지 않는다.
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

stamp="$(date +%F_%H%M%S)"
final="$BACKUP_DIR/news_db_${stamp}.dump"
partial="${final}.partial"
trap 'rm -f "$partial"' EXIT   # 중간에 실패하면 덜 만든 파일을 지운다

log() { echo "[$(date '+%F %T')] $*"; }

log "백업 시작 → $final"

# 비밀번호·DB 이름은 컨테이너 안의 환경변수를 쓴다 (스크립트에 적지 않음)
docker compose -f "$COMPOSE_FILE" exec -T db \
    sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$partial"

# 빈 파일 검사: 2026-11-08 수동 백업이 0바이트로 남았던 일을 반복하지 않기 위해
if [ ! -s "$partial" ]; then
    log "실패: 덤프 파일이 비어 있음"
    exit 1
fi

# 파일이 읽히는지 검사: 목차를 읽지 못하면 깨진 덤프
if ! docker compose -f "$COMPOSE_FILE" exec -T db pg_restore --list < "$partial" > /dev/null; then
    log "실패: 덤프 파일을 읽을 수 없음"
    exit 1
fi

mv "$partial" "$final"
chmod 600 "$final"
log "완료: $(du -h "$final" | cut -f1)"

# 보관 기간이 지난 자동 백업 삭제 (이 스크립트가 만든 이름 형식만 대상)
deleted="$(find "$BACKUP_DIR" -maxdepth 1 -name 'news_db_????-??-??_??????.dump' -mtime +"$KEEP_DAYS" -print -delete | wc -l | tr -d ' ')"
log "보관 기간(${KEEP_DAYS}일) 지난 백업 ${deleted}개 삭제"
