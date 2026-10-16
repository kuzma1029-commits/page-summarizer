"""Настройка логирования: stdout + файл с ротацией."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logger(
    name: str = "agent",
    log_file: str = "logs/agent.log",
    level: int | None = None,
) -> logging.Logger:
    """Создаёт логгер, пишущий в stdout и в файл (ротация 1MB x3).

    Args:
        name: Имя логгера.
        log_file: Путь к файлу логов (создаётся каталог, если нужно).
        level: Уровень логирования; если None — INFO, либо DEBUG при DEBUG=1.

    Returns:
        Настроенный логгер.
    """
    if level is None:
        level = logging.DEBUG if os.getenv("DEBUG") == "1" else logging.INFO

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        for handler in logger.handlers:
            handler.setLevel(level)
        return logger

    formatter = logging.Formatter(LOG_FORMAT)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_path = Path(log_file)
    if not file_path.is_absolute():
        file_path = BASE_DIR / file_path
    file_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        file_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
