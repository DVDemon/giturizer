FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# P2: инструменты анализа. Дальше — pyan/pyreverse (Python), dependency-cruiser/madge (Node).
RUN apt-get update \
    && apt-get install -y --no-install-recommends doxygen ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./
COPY backend/src ./src
RUN pip install .

CMD ["celery", "-A", "archdiscovery.analyzer.celery_app.celery_app", "worker", "-Q", "analyzers", "--loglevel=INFO"]
