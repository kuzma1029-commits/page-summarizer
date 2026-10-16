#!/bin/bash
# Ежечасное бесшовное обновление контейнера argonpower/gpt-secretary-bot:latest
# Поместить в /root/update.sh, дать chmod +x, добавить в cron: 0 * * * * /root/update.sh
set -u

IMAGE="aiandy075/page-summarizer:latest"
APP_DIR="/root/page-summarizer"
LOG="/root/update.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') | $*" >> "$LOG"; }

log "=== Проверка обновлений ==="

if [ ! -f "$APP_DIR/docker-compose.yml" ]; then
  log "ОШИБКА: нет $APP_DIR/docker-compose.yml"
  exit 1
fi

cd "$APP_DIR" || exit 1

# Локальный ID текущего образа
OLD_ID=$(docker inspect -f '{{.Image}}' page-summarizer 2>/dev/null || echo "none")

# Тянем свежий манифест из Docker Hub
docker pull -q "$IMAGE" >/dev/null 2>&1
NEW_ID=$(docker inspect -f '{{.Id}}' "$IMAGE" 2>/dev/null || echo "none")

if [ "$OLD_ID" = "$NEW_ID" ]; then
  log "Обновлений нет (image: ${NEW_ID:0:12})"
  exit 0
fi

log "Найдено обновление: ${OLD_ID:0:12} -> ${NEW_ID:0:12}. Пересоздаю контейнер..."
docker compose up -d --no-deps web >> "$LOG" 2>&1

if [ "$(docker inspect -f '{{.State.Running}}' page-summarizer 2>/dev/null)" = "true" ]; then
  log "Обновление завершено, контейнер работает."
else
  log "ОШИБКА: контейнер не запустился после обновления!"
  exit 1
fi

# Чистка старых образов (оставляем только используемые)
docker image prune -f >> "$LOG" 2>&1
log "Очистка старых образов выполнена."
