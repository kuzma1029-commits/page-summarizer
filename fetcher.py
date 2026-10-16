"""Загрузка текста страницы: Jina Reader + fallback на прямой парсинг HTML."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from logger import setup_logger

JINA_PREFIX = "https://r.jina.ai/"

# Кэш доменов, заблокированных Jina: домен -> unix-время окончания блокировки.
# Заблокированный домен не запрашиваем повторно, чтобы не ждать таймаут.
_JINA_BLOCKS: dict[str, float] = {}
JINA_BLOCK_TTL = 1800.0  # если точное время окончания распознать не удалось
TOTAL_FETCH_TIMEOUT = 60.0  # общий лимит времени на загрузку (Jina + fallback)

SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head"}
BLOCK_TAGS = {
    "p", "div", "br", "li", "ul", "ol", "table", "tr", "td", "th",
    "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
    "header", "footer", "blockquote", "pre", "figcaption",
}

logger = setup_logger("agent.fetcher")


class FetchError(Exception):
    """Ошибка загрузки страницы."""


class _HTMLTextExtractor(HTMLParser):
    """Извлекает видимый текст из HTML (без script/style)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        elif tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data)

    def get_text(self) -> str:
        """Возвращает собранный текст с нормализованными переносами."""
        raw = " ".join(self._chunks)
        lines = [line.strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def html_to_text(html: str) -> str:
    """Преобразует HTML в чистый текст.

    Args:
        html: HTML-разметка.

    Returns:
        Извлечённый текст.
    """
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    extractor.close()
    return extractor.get_text()


def _error_detail(body: str) -> str:
    """Достаёт читаемое описание ошибки из JSON-ответа Jina Reader.

    Args:
        body: Тело ответа.

    Returns:
        Строка вида "Name: message" (обрезанная) или пустая строка.
    """
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(payload, dict):
        return ""
    name = str(payload.get("name") or "").strip()
    message = str(payload.get("message") or "").strip()
    if not name and not message:
        return ""
    detail = f"{name}: {message}" if name and message else (name or message)
    return detail[:300]


def _validate_url(url: str) -> str:
    """Проверяет и нормализует URL.

    Raises:
        ValueError: URL пустой или без http/https.
    """
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("URL пустой. Пример: python agent.py https://example.com")
    if not cleaned.lower().startswith(("http://", "https://")):
        raise ValueError(
            f"Невалидный URL: {cleaned!r}. Ожидается адрес, начинающийся с http:// или https://"
        )
    return cleaned


def _jina_block_until(detail: str) -> float:
    """Возвращает unix-время окончания блокировки Jina из текста ошибки.

    Args:
        detail: Описание ошибки от Jina (содержит "blocked until ...").

    Returns:
        Unix-время окончания блокировки; при нераспознанном формате — now+TTL.
    """
    match = re.search(r"blocked until (.+?)(?:\s+due|\s*$)", detail)
    if match:
        raw = match.group(1).strip()
        for fmt in ("%a %b %d %Y %H:%M:%S GMT%z", "%a %b %d %Y %H:%M:%S GMT+0000"):
            try:
                return datetime.strptime(raw, fmt).timestamp()
            except ValueError:
                continue
    return time.time() + JINA_BLOCK_TTL


def _jina_blocked(url: str) -> str | None:
    """Проверяет кэш блокировок Jina для домена URL.

    Returns:
        Сообщение об ошибке, если домен ещё заблокирован, иначе None.
    """
    domain = urlparse(url).netloc.lower()
    until = _JINA_BLOCKS.get(domain)
    if until and time.time() < until:
        left = int(until - time.time())
        return (
            f"Jina: домен {domain} временно заблокирован "
            f"(ещё ~{left} c), пробую прямую загрузку"
        )
    return None


def _fetch_via_jina(url: str, timeout: float) -> str:
    """Загружает текст страницы через Jina Reader.

    Raises:
        FetchError: таймаут, HTTP-статус != 200, ошибка соединения
            или известная блокировка домена.
    """
    cached = _jina_blocked(url)
    if cached:
        raise FetchError(cached)

    target = f"{JINA_PREFIX}{url}"
    logger.debug("Целевой URL Jina: %s", target)
    logger.info("Загрузка через Jina: %s", url)

    try:
        with httpx.Client(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            follow_redirects=True,
            headers={"User-Agent": "page-summarizer/1.0"},
        ) as client:
            response = client.get(target)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise FetchError(f"Jina: таймаут при загрузке {url}") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = _error_detail(exc.response.text or "")
        if "AbuseAlleviationError" in detail:
            _JINA_BLOCKS[urlparse(url).netloc.lower()] = _jina_block_until(detail)
        message = f"Jina: HTTP {status} при загрузке {url}"
        if detail:
            message = f"{message} — {detail}"
        raise FetchError(message) from exc
    except httpx.RequestError as exc:
        raise FetchError(f"Jina: ошибка соединения при загрузке {url}") from exc

    text = (response.text or "").strip()
    if not text:
        raise FetchError(f"Jina: пустой ответ при загрузке {url}")
    return response.text


def _fetch_direct(url: str, timeout: float) -> str:
    """Загружает страницу напрямую и извлекает текст из HTML.

    Raises:
        FetchError: таймаут, HTTP-статус != 200 или ошибка соединения.
    """
    logger.info("Fallback: прямая загрузка %s", url)

    try:
        with httpx.Client(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 12.0)),
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36 page-summarizer/1.0"
                )
            },
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise FetchError(f"Таймаут при загрузке {url}") from exc
    except httpx.HTTPStatusError as exc:
        raise FetchError(
            f"HTTP {exc.response.status_code} при загрузке {url}"
        ) from exc
    except httpx.RequestError as exc:
        raise FetchError(f"Ошибка соединения при загрузке {url}") from exc

    content_type = response.headers.get("content-type", "").lower()
    body = response.text or ""
    if "html" in content_type:
        text = html_to_text(body)
    else:
        text = body.strip()

    if not text:
        raise FetchError(f"Пустой ответ при загрузке {url}")
    return text


def fetch_page_text(url: str) -> str:
    """Загружает страницу по URL и возвращает её текст.

    Сначала пробует Jina Reader (markdown); при любой ошибке —
    прямой GET с извлечением текста из HTML.

    Args:
        url: Полный URL страницы (http/https).

    Returns:
        Текст страницы.

    Raises:
        ValueError: URL пустой или не начинается с http.
        FetchError: оба способа загрузки не сработали.
    """
    cleaned = _validate_url(url)
    deadline = time.monotonic() + TOTAL_FETCH_TIMEOUT
    reserve = 35.0  # время под прямую загрузку (она быстрая и надёжная)
    jina_budget = 12.0  # Jina часто виснет до таймаута — держим коротко

    def remaining() -> float:
        return deadline - time.monotonic()

    jina_error: FetchError | None = None
    if remaining() > reserve + 5:
        try:
            text = _fetch_via_jina(cleaned, jina_budget)
            logger.info("Jina: загрузка завершена (%d символов)", len(text))
            return text
        except FetchError as exc:
            jina_error = exc
            logger.warning("%s — пробую прямую загрузку", exc)
    else:
        jina_error = FetchError("Jina: не осталось времени на попытку")

    if remaining() <= 1:
        raise FetchError(
            f"Превышен общий лимит загрузки ({int(TOTAL_FETCH_TIMEOUT)} с) "
            f"при загрузке {cleaned} ({jina_error})"
        )

    try:
        text = _fetch_direct(cleaned, remaining())
    except FetchError as direct_error:
        raise FetchError(f"{direct_error} ({jina_error})") from direct_error

    logger.info("Fallback: загрузка завершена (%d символов)", len(text))
    return text
