"""Веб-интерфейс агента «Краткое резюме страницы» (Flask)."""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, jsonify, render_template, request

from agent import summarize_url
from fetcher import FetchError
from llm_client import LLMError
from logger import setup_logger

logger = setup_logger("agent.web")

app = Flask(__name__)


@app.get("/")
def index() -> str:
    """Главная страница с формой."""
    return render_template("index.html")


@app.post("/api/summarize")
def api_summarize() -> tuple:
    """API: принимает {"url": ...}, возвращает {"summary": ...} или {"error": ...}."""
    data = request.get_json(silent=True) or {}
    url = str(data.get("url") or "").strip()
    if not url:
        return jsonify(error="Введите URL страницы."), 400

    try:
        summary = summarize_url(url)
    except ValueError as exc:
        return jsonify(error=f"Ошибка ввода: {exc}"), 400
    except (FetchError, LLMError) as exc:
        logger.error("Ошибка обработки %s: %s", url, exc)
        return jsonify(error=str(exc)), 502

    return jsonify(summary=summary)


def main() -> None:
    """Запуск веб-сервера (HOST/PORT из env, по умолчанию 127.0.0.1:5000)."""
    import os
    import threading
    import webbrowser

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    url = f"http://127.0.0.1:{port}"
    print(f"Агент «Краткое резюме страницы»: http://{host}:{port}")
    print("Не закрывайте это окно. Остановка сервера — Ctrl+C.")
    if os.getenv("NO_BROWSER") != "1" and host in ("127.0.0.1", "localhost"):
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
