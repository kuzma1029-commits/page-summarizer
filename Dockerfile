FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=5000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY config.py logger.py fetcher.py llm_client.py prompts.py agent.py app.py ./
COPY templates ./templates

EXPOSE 5000

CMD ["python", "app.py"]
