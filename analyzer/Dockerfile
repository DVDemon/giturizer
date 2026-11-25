FROM python:3.12-slim

ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

ARG ARCHGUARD_VERSION=2.3.0
ARG ARCHGUARD_SHA256=71c1b496e40a0fbffbad07e51203cc65eefe3fd9a2975f8faddd266c6f37b522
ENV ARCHGUARD_VERSION=${ARCHGUARD_VERSION}

WORKDIR /app

# Инструменты анализа: doxygen (C++), Java + ArchGuard scanner (Java/Kotlin/C#/TS/Python/Golang).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        doxygen \
        default-jre-headless \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/archguard/analysers \
    && curl -fsSL -o /opt/archguard/scanner_cli.jar \
        "https://github.com/archguard/archguard/releases/download/v${ARCHGUARD_VERSION}/scanner_cli-${ARCHGUARD_VERSION}-all.jar" \
    && echo "${ARCHGUARD_SHA256}  /opt/archguard/scanner_cli.jar" | sha256sum -c - \
    && for jar in lang_java lang_python lang_typescript feat_apicalls feat_datamap idl_protobuf idl_thrift; do \
         curl -fsSL -o "/opt/archguard/analysers/${jar}-${ARCHGUARD_VERSION}-all.jar" \
           "https://github.com/archguard/archguard/releases/download/v${ARCHGUARD_VERSION}/${jar}-${ARCHGUARD_VERSION}-all.jar"; \
       done

COPY backend/pyproject.toml ./
COPY backend/src ./src
RUN pip install ".[syntax]"

CMD ["celery", "-A", "archdiscovery.analyzer.celery_app.celery_app", "worker", "-Q", "analyzers", "--loglevel=INFO"]
