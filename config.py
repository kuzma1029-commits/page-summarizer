"""Настройки проекта: загрузка .env, валидация ключа, константы."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """Неизменяемый набор настроек агента."""

    openai_api_key: str
    openai_base_url: str = "https://api.proxyapi.ru/openai/v1"
    model: str = "gpt-4o-mini"
    request_timeout: float = 30.0
    max_retries: int = 3
    retry_min_wait: float = 1.0
    retry_max_wait: float = 10.0


def get_settings() -> Settings:
    """Возвращает (и кэширует) настройки из переменных окружения.

    Raises:
        ValueError: если OPENAI_API_KEY отсутствует или пуст.
    """
    global _SETTINGS
    if _SETTINGS is not None:
        return _SETTINGS

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY не найден: скопируйте .env.example в .env "
            "и вставьте ключ ProxyAPI."
        )

    _SETTINGS = Settings(
        openai_api_key=api_key,
        openai_base_url=os.getenv(
            "OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1"
        ).strip(),
        model=(
            os.getenv("MODEL_NAME")
            or os.getenv("MODEL")
            or "gpt-4o-mini"
        ).strip(),
        request_timeout=float(os.getenv("REQUEST_TIMEOUT", "30.0")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        retry_min_wait=float(os.getenv("RETRY_MIN_WAIT", "1.0")),
        retry_max_wait=float(os.getenv("RETRY_MAX_WAIT", "10.0")),
    )
    return _SETTINGS


_SETTINGS: Settings | None = None


def __getattr__(name: str) -> Settings:
    """Ленивый синглтон: ``from config import settings``."""
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
