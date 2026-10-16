# page_summarizer — агент «Краткое резюме страницы»

Агент, который загружает содержимое страницы по URL и возвращает краткое
резюме в **3–5 предложениях**.

## Требования

- Python >= 3.10
- Ключ [ProxyAPI](https://api.proxyapi.ru) (OpenAI-совместимый API)

## Установка

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Настройка

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Вставьте в `.env` свой ключ:

```
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
MODEL_NAME=gpt-4o-mini
```

`.env` в `.gitignore` и не попадает в репозиторий.

## Использование

### CLI

```bash
python agent.py https://example.com
python agent.py https://ru.wikipedia.org/wiki/Искусственный_интеллект
python agent.py <url> --verbose   # DEBUG-логи
```

### Веб-интерфейс

```bash
python app.py
```

Откройте http://127.0.0.1:5000 — введите URL и нажмите «Резюмировать».
Интерфейс: `templates/index.html`; API: `POST /api/summarize` `{"url": "..."}` → `{"summary": "..."}`.

### Пример вывода

```
Искусственный интеллект — это область компьютерных наук, занимающаяся
созданием систем, способных выполнять задачи, традиционно требующие
человеческого интеллекта. Ключевыми направлениями являются машинное
обучение, обработка естественного языка и компьютерное зрение. ...
```

## Архитектура

| Модуль | Назначение |
|---|---|
| `config.py` | Загрузка `.env`, валидация ключа, `Settings` (model, timeout, retry) |
| `logger.py` | Логирование в stdout и `logs/agent.log` (ротация 1MB × 3) |
| `fetcher.py` | Загрузка текста: Jina Reader (`https://r.jina.ai/<url>`), fallback — прямой GET + парсинг HTML |
| `prompts.py` | `SYSTEM_PROMPT` и шаблон `USER_PROMPT_TEMPLATE` |
| `llm_client.py` | Клиент ProxyAPI + повторы (tenacity), обрезка текста до 15 000 символов |
| `agent.py` | CLI (`argparse`) и пайплайн `summarize_url` |
| `app.py` | Веб-интерфейс (Flask, порт 5000) |
| `templates/index.html` | Страница с формой URL и выводом резюме |
| `Dockerfile`, `docker-compose.yml` | Контейнеризация (образ `argonpower/gpt-secretary-bot`) |
| `deploy/update.sh` | Ежечасное автообновление контейнера на сервере |
| `deploy/INSTRUCTIONS.md` | Пошаговая инструкция развёртывания на VPS |

## Развёртывание (Docker)

```bash
docker compose up -d --build     # сборка и запуск (порт 80)
```

Подробная инструкция для сервера — `deploy/INSTRUCTIONS.md`.

## Обработка ошибок

| Ситуация | Поведение | Код выхода |
|---|---|---|
| Невалидный URL (не http…) | `Ошибка ввода: …` в stderr | 2 |
| Нет `OPENAI_API_KEY` | `ValueError: OPENAI_API_KEY не найден…` | 2 |
| Jina недоступна (таймаут/статус) | warning в логе + автоматический fallback: прямой GET и парсинг HTML | — |
| Таймаут / ошибка соединения (оба способа) | `Ошибка: … (Jina: …)` в stderr | 1 |
| HTTP-статус != 200 (оба способа, напр. 404) | `Ошибка: HTTP 404 при загрузке …` в stderr | 1 |
| 429 / таймаут / обрыв API | повторы (exp. backoff, до 3), затем `LLMError` | 1 |

Все события пишутся в `logs/agent.log`.

## Лицензия

MIT (учебный проект)
