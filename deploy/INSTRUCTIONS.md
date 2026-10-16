# Инструкция по развёртыванию на VPS (kvm.ihor-hosting.ru)

Образ: `argonpower/gpt-secretary-bot:latest`
Приложение: веб-агент «Краткое резюме страницы» (порт 80 → контейнер 5000).

## Место на сервере (2,3 GB свободно) — хватит

| Компонент | Примерный объём |
|---|---|
| Docker Engine + compose | ~600 MB |
| Образ (python:3.12-slim + пакеты) | ~350 MB |
| Сборочный кэш (после очистки удаляется) | ~200 MB |
| Система (логи, `.env`) | ~50 MB |
| **Итого** | **~1,2 GB** |

После сборки рекомендуется: `docker builder prune -f`.

## Что нужно от владельца сервера

1. **SSH-доступ**: IP-адрес сервера, логин `root`, пароль (или ключ).
2. **Аккаунт Docker Hub** (логин `argonpower`) и **Personal Access Token**
   (Docker Hub → Account Settings → Personal access tokens → Generate).
   Нужен, чтобы пушить/тянуть образ `argonpower/gpt-secretary-bot`.
3. **Файл `.env`** с ключом ProxyAPI — кладётся на сервер вручную
   (в образ и git он НЕ входит).
4. Открытый порт **80** (для сайта) — обычно уже открыт на VPS.

## Шаг 0. Проверка места

```bash
df -h /
```

Если свободно < 1,5 GB — сначала освободите место.

## Шаг 1. Установка Docker (если ещё нет)

```bash
apt update && apt install -y docker.io docker-compose-v2
docker --version && docker compose version
```

## Шаг 2. Файлы проекта на сервер

Вариант А — с локальной машины (из папки проекта):

```powershell
scp Dockerfile docker-compose.yml .dockerignore requirements.txt config.py logger.py fetcher.py llm_client.py prompts.py agent.py app.py root@<IP>:/root/
scp -r templates root@<IP>:/root/
scp deploy/update.sh root@<IP>:/root/update.sh
```

Вариант Б — через git (если репозиторий в GitHub/GitLab):

```bash
cd /root && git clone <URL_репозитория> page-summarizer && cd page-summarizer
```

## Шаг 3. Окружение (секреты)

```bash
cd /root/page-summarizer
cp .env.example .env
nano .env    # вписать реальный OPENAI_API_KEY и параметры
chmod 600 .env
```

Содержимое `.env` (пример):

```
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
MODEL_NAME=gpt-4o-mini
```

## Шаг 4. Сборка и запуск (сделать один раз)

```bash
cd /root/page-summarizer
docker compose up -d --build
docker builder prune -f          # очистка кэша сборки (экономит ~200 MB)
docker ps                        # должен быть page-summarizer, Up, health: healthy
curl -I http://127.0.0.1:80      # HTTP 200
```

Контейнер уже имеет `restart: always` — перезапускается сам после падения и после перезагрузки сервера.

## Шаг 5. Push образа в Docker Hub (для автообновлений)

```bash
docker login -u argonpower          # пароль = Personal Access Token
docker push argonpower/gpt-secretary-bot:latest
```

После этого на других серверах/при обновлениях образ тянется из Hub,
а не собирается заново.

## Шаг 6. Ежечасное бесшовное обновление

```bash
chmod +x /root/update.sh
(crontab -l; echo "0 * * * * /root/update.sh") | crontab -
crontab -l     # проверить строку: 0 * * * * /root/update.sh
```

Скрипт `/root/update.sh` каждый час:
1. Сверяет локальный образ с `argonpower/gpt-secretary-bot:latest` в Hub.
2. Если есть новая версия — `docker compose up -d --no-deps` (пересоздание за секунды).
3. Пишет результат в `/root/update.log`, чистит старые образы.

Ручная проверка: `bash /root/update.sh && tail /root/update.log`.

## Шаг 7. Финальная проверка

```bash
docker ps                                  # Running + healthy
docker logs page-summarizer --tail 20
curl -s -X POST http://127.0.0.1/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'       # должен вернуть {"summary": ...}
```

Сайт: `http://<IP-сервера>/`

## Распространённые проблемы

| Проблема | Решение |
|---|---|
| Не открывается снаружи | Проверить `ufw allow 80` / файрвол панели хостинга |
| `port is already allocated` | Сменить `"80:5000"` на `"8080:5000"` в docker-compose.yml |
| Ошибка «OPENAI_API_KEY не найден» | Проверить `.env` рядом с docker-compose.yml |
| Мало места | `docker system prune -af` (удалит всё неиспользуемое) |
