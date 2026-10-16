"""Обёртка над OpenAI-совместимым API (ProxyAPI) с повторами."""

from __future__ import annotations

import openai
from openai import OpenAI
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import get_settings
from logger import setup_logger
from prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

MAX_CONTENT_CHARS = 15_000
MIN_CONTENT_CHARS = 50

logger = setup_logger("agent.llm")


class LLMError(Exception):
    """Ошибка обращения к модели."""


def _truncate(text: str, limit: int = MAX_CONTENT_CHARS) -> str:
    """Обрезает текст до limit символов с пометкой об обрезке."""
    if len(text) <= limit:
        return text
    logger.info(
        "Текст обрезан: %d -> %d символов", len(text), limit
    )
    return text[:limit] + "\n...[текст обрезан]"


def summarize_text(text: str) -> str:
    """Формирует краткое резюме (3–5 предложений) для переданного текста.

    Args:
        text: Исходный текст страницы.

    Returns:
        Резюме длиной 3–5 предложений или служебная строка-заглушка.

    Raises:
        LLMError: если после всех повторов ответ от модели не получен.
    """
    content = (text or "").strip()
    if len(content) < MIN_CONTENT_CHARS:
        logger.info("Недостаточно текста для анализа (%d символов)", len(content))
        return "Недостаточно текста для анализа."

    settings = get_settings()
    content = _truncate(content)

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=settings.request_timeout,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(content=content)},
    ]

    retryable_errors = (
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.RateLimitError,
    )

    retrying = Retrying(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(
            multiplier=1,
            min=settings.retry_min_wait,
            max=settings.retry_max_wait,
        ),
        retry=retry_if_exception_type(retryable_errors),
        reraise=True,
        before_sleep=lambda state: logger.warning(
            "Повторная попытка %d после ошибки: %s",
            state.attempt_number,
            state.outcome.exception() if state.outcome else "неизвестно",
        ),
    )

    def _call() -> str:
        logger.debug(
            "Параметры запроса: model=%s, messages=%d, temperature=0.3",
            settings.model,
            len(messages),
        )
        logger.info("Запрос к модели %s", settings.model)
        response = client.chat.completions.create(
            model=settings.model,
            messages=messages,
            temperature=0.3,
        )
        return (response.choices[0].message.content or "").strip()

    try:
        summary = retrying(_call)
    except retryable_errors as exc:
        logger.error("Ошибка API после %d попыток: %s", settings.max_retries, exc)
        raise LLMError(f"Не удалось получить ответ от модели: {exc}") from exc
    except openai.OpenAIError as exc:
        logger.error("Ошибка API: %s", exc)
        raise LLMError(f"Не удалось получить ответ от модели: {exc}") from exc

    logger.info("Резюме получено (длина: %d символов)", len(summary))
    return summary
