"""CLI entrypoint: агент «Краткое резюме страницы»."""

from __future__ import annotations

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from logger import setup_logger

try:
    from fetcher import FetchError, fetch_page_text
    from llm_client import LLMError, summarize_text
except ImportError as exc:
    print(
        f"Отсутствует зависимость: {exc.name}.\n"
        "Активируйте виртуальное окружение и установите пакеты:\n"
        "  .venv\\Scripts\\activate        (Windows)\n"
        "  source .venv/bin/activate      (Linux/macOS)\n"
        "  pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(3) from exc

logger = setup_logger("agent")


def summarize_url(url: str) -> str:
    """Оркестратор: загрузка страницы -> резюме.

    Args:
        url: URL страницы.

    Returns:
        Резюме в 3–5 предложениях.

    Raises:
        ValueError: невалидный URL.
        FetchError: ошибка загрузки страницы.
        LLMError: ошибка обращения к модели.
    """
    logger.info("Начинаю обработку: %s", url)
    text = fetch_page_text(url)
    summary = summarize_text(text)
    logger.info("Обработка завершена: %s", url)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    """Создаёт CLI-парсер."""
    parser = argparse.ArgumentParser(
        prog="agent.py",
        description='Агент "Краткое резюме страницы": 3–5 предложений по URL.',
    )
    parser.add_argument("url", help="URL страницы (http/https)")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Подробные (DEBUG) логи",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Точка входа: разбор аргументов, пайплайн, вывод результата.

    Returns:
        0 — успех, 1 — ошибка загрузки/модели, 2 — ошибка ввода.
    """
    args = _build_parser().parse_args(argv)

    if args.verbose:
        setup_logger("agent", level=10)
        setup_logger("agent.fetcher", level=10)
        setup_logger("agent.llm", level=10)

    try:
        summary = summarize_url(args.url)
    except ValueError as exc:
        print(f"Ошибка ввода: {exc}", file=sys.stderr)
        return 2
    except (FetchError, LLMError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
