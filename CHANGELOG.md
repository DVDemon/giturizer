# Changelog

## [Unreleased]

### Added

- Поддержка публичных репозиториев **GitHub** (наряду с GitLab): провайдер определяется по URL,
  токен не обязателен; ветка определяется автоматически (`main`, `master`, …) и запоминается.
  API принимает `repo_url` (старое `gitlab_url` поддерживается как alias), миграция 0005.
- Сборка образов поддерживает альтернативный PyPI-индекс через build-arg `PIP_INDEX_URL`.
- **ArchGuard scanner 2.3.0** в контейнере `analyzer` для Java/Kotlin/C#/TypeScript/Python/Golang
  (Java — `apicalls`/`datamap`); анализаторы предзагружены, ошибка языка не валит пайплайн.
- Клонирование **git submodules** (`--recurse-submodules --shallow-submodules`);
  отчёт ArchGuard показывает покрытие `services/<name>`.
- Fallback-скан JS/TS (файлы и локальные импорты) для модулей, не покрытых ArchGuard;
  покрытие submodules считается по ArchGuard + fallback.

### Changed

- Веб-интерфейс переведён на дизайн-систему Beeline (брендбук 2024):
  жёлтый `#FFC800` / чёрный `#141414` / белый, Beeline Sans + Golos Text,
  карточки с чёрной обводкой, кнопки-«пилюли», светлая тема графа и C4.
- Граф: иерархическая раскладка (breadthfirst), ограничение зума, брендовые цвета узлов.
- C4: SVG-метки Mermaid (без обрезки подписей), брендовая тема.
- Hash-навигация по вкладкам (`#graph`, `#c4`, …).
- Граф показывает протоколы транспортного и прикладного уровня (PostgreSQL/TCP:5432,
  MongoDB/TCP:27017, RESP/TCP:6379, HTTP/TCP:8080) с легендой и цветами по протоколу;
  протоколы пишутся в Structurizr (`technology`/`properties`) и Neo4j-рёбра.

## [1.0.0] — 2026-11-24

Первый релиз: восстановление архитектуры по исходному коду GitLab-репозитория.

### Added

- **Проекты и запуски**: создание по URL GitLab, асинхронный анализ через Celery, статусы,
  история запусков.
- **Клон репозитория** по access token, с редактированием токена в ошибках.
- **Детект технологий и версий**: образы compose, `FROM` Dockerfile, `package.json`,
  `requirements.txt`/`pyproject.toml`, `pom.xml` (+parent), `*.csproj`, Gradle/Maven
  (+wrapper), `go.mod`, CMake (`find_package`, minimum version, C++ standard),
  `.nvmrc`/`.python-version`/`.java-version`.
- **C++ анализатор** в выделенном контейнере: doxygen XML + include-граф, классы, фреймворки.
- **API-контракты**: OpenAPI/Swagger, gRPC (services/rpcs/streaming), GraphQL,
  аннотации Spring/JAX-RS, ASP.NET, FastAPI/Flask, Express.
- **Модель развёртывания**: compose, Dockerfile, Kubernetes, Helm (`Chart.yaml`/values/templates),
  ArgoCD, GitLab CI, со сводкой.
- **Structurizr**: `workspace.dsl` + `workspace.json` с валидацией JSON Schema и Structurizr CLI.
- **Граф в Neo4j**: идемпотентная запись, транзитивные зависимости через Cypher.
- **Веб-интерфейс**: проекты/запуски, граф (Cytoscape.js), C4 (Mermaid), API (Redoc/таблицы),
  технологии (CSV), deployment, экспорт.
- **Эксплуатация**: `docker-compose`, health-checks, Alembic-миграции, smoke-скрипт,
  runbook, ADR-реестр.

### Security

- GitLab-токены шифруются (Fernet), не возвращаются API, редактируются в логах.
- Контейнеры `api`/`worker`/`analyzer`/`web`: `no-new-privileges`, `cap_drop: ALL`;
  nginx unprivileged; Docker-сокет не используется.
- Клон репозитория удаляется после анализа (`KEEP_REPOS=true` — оставить).
