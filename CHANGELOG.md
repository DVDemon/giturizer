# Changelog

## [Unreleased]

### Added

- **React frontend API index (Phase 1)**: artifact `frontend`,
  `GET /api/runs/{id}/frontend`; Tree-sitter извлекает `Api.*`/`axios`/`fetch`,
  gateway-константы, method/path/service/source line.
- **Детальный прогресс анализа**: `analysis_runs.progress_detail` (этап,
  обработано/всего файлов) обновляется Tree-sitter-анализатором и показывается
  в карточке сканирования; миграция 0008.
- **API-потоки: группировка и навигация** — группировка по входной операции,
  фильтры/сортировка/пагинация, количество цепочек и внешних систем,
  детальный экран с хлебными крошками.
- **C++/POCO в API flow**: Tree-sitter routes из `dispatch()`
  (`HTTPRequestHandler`), PostgreSQL/Redis/RabbitMQ через типы POCO-компонентов.
- **UI/JSON: API-потоки** — массив `api_flows` в `/report` и отдельная вкладка
  «API-потоки»; вкладка скрывается без данных.
- **API flow: не-HTTP внешние вызовы** — PostgreSQL, Redis, S3, RabbitMQ, Kafka,
  MongoDB, Elasticsearch, SQL-репозитории; `output.kind`/`targets` в UI и JSON.
- **P2: call graph handler → outbound HTTP-кандидат** для Java/TS/Python:
  Spring/Feign/RestTemplate, Nest/axios/fetch, FastAPI/httpx/requests;
  artifact `syntax.outbound_calls`, `GET /api/runs/{id}/outbound-calls`.
- **P1: Tree-sitter syntax-index** для Java/TypeScript/Python: endpoint → handler,
  artifact `syntax`, `GET /api/runs/{id}/handlers`; Spring/NestJS/Express/FastAPI/Flask.
  Зависимости ставятся только в образ `analyzer` (extra `syntax`).
- **C4 container diagram через Graphviz**: DOT из внутренней C4-модели, engine `fdp`,
  endpoint `/api/runs/{id}/c4.svg`, переключатель Graphviz/Mermaid и масштаб в UI.
  Внешние системы фильтруются по связям с контейнерами и дедуплицируются по имени.
- **Единый JSON-отчёт** (`/api/runs/{id}/report`): `technologies`, `api`
  (сервисы → методы), `deployment` (способ → сервисы: образ/версия/порты/зависимости).
  Хранится в `architecture_snapshots.report` (миграция 0007), для старых запусков
  собирается лениво.
- **Обзор**: после завершения анализа верхняя плашка скрывается, остаются URL и
  статус; в «Обзоре» — статистика запуска, JSON-дерево и скачивание отчёта.
- **API-каталог**: все операции из OpenAPI/annotations/gRPC/GraphQL в одной таблице
  с поиском, фильтрами по сервису/методу/источнику, пагинацией и панелью деталей
  (параметры, body, ответы, схемы). Deep link через `?api=&op=`, Redoc удалён.
- **UI: два таба** — «Проекты» (таблица с поиском, фильтром провайдера,
  сортировкой и пагинацией 10/20/50/100, дата последнего сканирования) и
  «Сканирование» (статус, этап, прогресс, длительность, счётчики технологий/
  сервисов/API, deep link `#scan/<id>`).
- **Прогресс пайплайна в БД/API**: `stage`, `progress`, `technologies_count`,
  `services_count`, `api_count` (миграция 0006 с backfill исторических запусков).
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

### Added

- C4: на связях показываются прикладной протокол и транспорт (`HTTP · TCP:8080`).
- Вкладки C4/API/Deployment скрываются, если для них нет данных.

### Changed

- Публичный вывод Structurizr (`workspace.dsl`/`workspace.json`) и API `/structurizr*`
  удалены; Structurizr-модель остаётся только внутренней для C4.

### Removed

- **Neo4j удалён полностью** (ADR-0022): сервис/том/драйвер/`NEO4J_*` настройки и
  `graph_writer`; единственный источник данных — PostgreSQL.
- Интерактивный граф (вкладка «Граф», ForceAtlas2, Cytoscape/graphology) убран
  из карточек систем; публичные `/graph/*` API удалены, Neo4j остаётся внутренним.
- Удалены лишние API: `/structurizr`, `/structurizr.dsl`, `/structurizr.json`,
  `/graph/elements`, `/graph/dependencies`.

### Fixed

- Spring `@*Mapping(path=...)`/`produces`: потерянные NFR/import/export endpoints
  и ложные `/application/json` пути; C++/Neo4j теперь классифицируется.
- Конфликт hash-роутинга приложения и Redoc-ссылок (`#tag/...`) устранён:
  навигация API идёт через query-параметры приложения.
- UI не показывает Java-стек TypeScript-парсера ArchGuard: осталось только
  понятное жёлтое предупреждение и fallback-покрытие JS/TS.
- Таблица технологий: поиск по имени/версии/основанию, фильтр по типу,
  сортировка по колонкам (имя/тип/версия, версии — natural sort) и CSV
  по отфильтрованной выборке.
- Таблица проектов: фиксированные колонки и заголовок «Действия», URL с
  ellipsis, дата в одну строку; на экранах ≤860px — карточная раскладка
  без горизонтального скролла и обрезанных кнопок. Кнопки действий вынесены
  во вложенный блок, поэтому hover/выделение не обрываются перед правой колонкой.

### Changed

- `GET /api/projects` теперь возвращает конверт `{items,total,page,per_page}`
  с серверной пагинацией/фильтрацией/сортировкой и `last_scan_at`.
- Сайдбар заменён на два верхних таба; удалённые проекты и запуски больше не
  выгружаются целиком.
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
