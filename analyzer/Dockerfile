FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# P0: стаб — только пакет приложения.
# P2: здесь будут установлены инструменты анализа (ArchGuard, doxygen, pyan, dependency-cruiser).
COPY backend/pyproject.toml ./
COPY backend/src ./src
RUN pip install .

CMD ["celery", "-A", "archdiscovery.analyzer.celery_app.celery_app", "worker", "-Q", "analyzers", "--loglevel=INFO"]
