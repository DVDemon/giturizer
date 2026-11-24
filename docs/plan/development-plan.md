# План разработки приложения ArchDiscovery

План создания сервиса по [архитектуре](../architecture.md) и [ADR](../adr/README.md).

## Принципы

- **Вертикальные срезы**: каждая фаза заканчивается демонстрируемым состоянием через `docker compose up`.
- **Расширение по одному языку/инструменту**: сначала Node (проще всего), затем Python, C++, ArchGuard.
- **Definition of Done (DoD)** для каждой задачи: код + автотесты + документация (если меняется контракт) + `docker compose up` зелёный.
- **Совместимость контрактов**: API описывается Pydantic-схемами, Structurizr-вывод валидируется JSON Schema.

## Структура репозитория (целевая)

```text
giturizr/
├── docker-compose.yml
├── .gitlab-ci.yml
├── Makefile
├── .env.example
├── docs/                        # architecture.md, adr/, plan/
├── backend/                     # api + worker (общий код)
│   ├── pyproject.toml
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   ├── alembic/
│   └── src/archdiscovery/
│       ├── config.py
│       ├── logging.py
│       ├── db/                  # session, models (SQLAlchemy), migrations, graph (Neo4j)
│       ├── schemas/             # Pydantic
│       ├── api/                 # FastAPI app + routers
│       │   ├── main.py
│       │   └── routes/{projects,runs,results,artifacts}.py
│       ├── services/            # business logic: projects, runs, results
│       ├── queue/               # celery app, publisher
│       ├── gitlab/              # clone client
│       └── pipeline/
│           ├── orchestrator.py
│           ├── clone.py
│           ├── tech_detect.py
│           ├── analyzers/{base,archguard,cpp,python,node}.py
│           ├── api_extractors/{openapi,annotations,grpc,graphql}.py
│           ├── deployment/{dockerfile,compose,k8s,helm,argocd,gitlabci}.py
│           ├── model/           # внутренняя архитектурная модель + graph
│           ├── merge.py
│           ├── structurizr/{dsl,json}.py
│           └── persist.py
├── analyzer/                    # один долгоживущий образ со всеми инструментами
│   └── Dockerfile
└── web/                         # React + TS (Vite)
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── api/                 # client
        ├── pages/{ProjectList,ProjectDetail,RunDetail}.tsx
        └── components/
            ├── DependencyGraph.tsx   # Cytoscape.js
            ├── C4Diagram.tsx         # Mermaid
            ├── ApiViewer.tsx         # Swagger UI/Redoc
            ├── TechRegistry.tsx
            └── DeploymentView.tsx
```

## Фазы

Оценки — идеальные дни для одного инженера; допускают перекрытие.

### P0 — Bootstrap (2–3 дня)

| ID | Задача | Результат |
|----|--------|-----------|
| P0.1 | Каркас репозитория: `backend/`, `analyzers/`, `web/`, `docs/`, `Makefile` | Структура каталогов |
| P0.2 | `backend/pyproject.toml`: ruff, black, mypy, pytest(+cov), celery, sqlalchemy, alembic | Конфиг линтера/тестов |
| P0.3 | `docker-compose.yml`: `postgres`, `neo4j`, `redis`, общий volume `data`, стабы `api`/`worker`/`analyzer`/`web` | `docker compose up` поднимается |
| P0.4 | CI (`.gitlab-ci.yml`): lint → test | Зелёный пайплайн |
| P0.5 | Alembic init + первая пустая миграция | Готовность к моделям |

**DoD P0**: `docker compose up -d` → `GET /health` = 200, заглушка UI открывается, CI зелёный.

### P1 — Ядро домена и API (3–4 дня)

| ID | Задача | Результат |
|----|--------|-----------|
| P1.1 | ORM-модели + миграции: `projects`, `analysis_runs` (см. §8 архитектуры) | Схема БД |
| P1.2 | `POST/GET/DELETE /api/projects` | CRUD проектов |
| P1.3 | `POST /api/projects/{id}/runs`, `GET /api/runs/{id}` | Запуск + статус |
| P1.4 | Celery: app, `publish_run`, stub-задача (меняет status queued→done) | Очередь работает |
| P1.5 | Конфиг (pydantic-settings), структурное логирование, обработка ошибок | Базовая набо́рка |

**DoD P1**: создать проект → запустить анализ → stub завершается → статус отдаётся. М1.

### P2 — Пайплайн и анализаторы (5–6 дней)

| ID | Задача | Результат |
|----|--------|-----------|
| P2.1 | `gitlab.clone` (токен/SSH по ADR-0012), shallow, cleanup | Клон репозитория |
| P2.2 | `tech_detect` по манифестам (pom/gradle/csproj/CMake/requirements/pyproject/package.json) | Реестр стеков |
| P2.3 | Образ `analyzer` (все инструменты) + Celery-воркер очереди `analyzers`: приём задачи, запуск CLI над клоном, запись JSON, timeout, изоляция ошибок | Контейнер анализатора |
| P2.4 | Node-адаптер (dependency-cruiser) — **первый вертикальный срез** | Граф модулей |
| P2.5 | Python-адаптер (pyan + pyreverse) | Call/class графы |
| P2.6 | C++ адаптер (doxygen + cpp-dependencies) | Include/call графы |
| P2.7 | ArchGuard-адаптер (Java/Kotlin/C#, TS/JS) | Сервисы/API/DB-карта |
| P2.8 | `orchestrator`: связывание этапов, последовательная постановка задач в очередь `analyzers`, персист результатов, статусы | Пайплайн целиком |
| P2.9 | Общий volume: клон в `/data/repos/<run_id>`, права, очистка по TTL/ретеншну | Shared storage |

**DoD P2**: на фикстурных репозиториях каждый анализатор даёт нормализованные данные в БД; сбой одного не валит остальные. М2.

### P3 — Извлечение API (3–4 дня)

| ID | Задача | Результат |
|----|--------|-----------|
| P3.1 | OpenAPI/Swagger: файлы + аннотации | OpenAPI 3.x |
| P3.2 | Аннотации фреймворков: Spring/JAX-RS, ASP.NET, FastAPI, express | Endpoints |
| P3.3 | gRPC/protobuf: `.proto` → модель | RPC-сервисы |
| P3.4 | GraphQL: схемы | Схема |
| P3.5 | Нормализация в канон OpenAPI 3.x + метаданные (владелец, файл, фреймворк) | `api_specs` |

**DoD P3**: на фикстурах получается валидный `openapi.json`, привязанный к сервису/контейнеру.

### P4 — Модель развёртывания (3–4 дня)

| ID | Задача | Результат |
|----|--------|-----------|
| P4.1 | Dockerfile + docker-compose | Контейнеры/порты/env |
| P4.2 | Kubernetes (Deployment/Service/Ingress/StatefulSet) | Поды/сервисы |
| P4.3 | Helm (Chart.yaml/values/templates — подмножество) | Рендер k8s |
| P4.4 | ArgoCD (Application/AppProject) | Репозиторий↔кластер |
| P4.5 | GitLab CI (`.gitlab-ci.yml`) | Стадии/окружения |
| P4.6 | Сведение в deployment-модель | `deploymentNodes` + связи |

**DoD P4**: на deploy-фикстурах модель развёртывания извлекается и сохраняется.

### P5 — Merge + Structurizr (3–4 дня)

| ID | Задача | Результат |
|----|--------|-----------|
| P5.1 | Внутренняя модель: `ArchitectureModel` (elements, relationships, deployment) | Модель |
| P5.2 | `merge`: склейка, дедупликация, стабильные ID | Граф |
| P5.3 | Генератор DSL | `workspace.dsl` |
| P5.4 | Генератор JSON workspace | `workspace.json` |
| P5.5 | Валидация по Structurizr JSON Schema + golden-тесты | Гарантия формата |
| P5.6 | Persist артефактов + эндпоинты скачивания | `artifacts` |
| P5.7 | Neo4j: клиент, схема узлов/рёбер, идемпотентный `MERGE` графа, Cypher-запросы (транзитивные зависимости) | Граф в Neo4j |

**DoD P5**: валидные `workspace.dsl` + `workspace.json`, скачиваются; граф записан в Neo4j и отдаёт транзитивные зависимости; goldens стабильны. М3.

### P6 — Веб-визуализация (5–6 дней)

| ID | Задача | Результат |
|----|--------|-----------|
| P6.1 | Список проектов + форма создания (URL) | UI |
| P6.2 | Статус запуска + поллинг/прогресс | UI |
| P6.3 | Граф зависимостей (Cytoscape.js): фильтры, drill-down, подсветка транзитивных | UI |
| P6.4 | C4-диаграммы (Mermaid) | UI |
| P6.5 | Просмотр API (Swagger UI/Redoc) | UI |
| P6.6 | Таблица реестра технологий | UI |
| P6.7 | Просмотр deployment | UI |
| P6.8 | Экспорт: DSL/JSON/OpenAPI/CSV | UI |

**DoD P6**: сквозное демо — ввод URL → визуализация архитектуры. М4.

### P7 — Hardening и релиз (3–5 дней)

| ID | Задача | Результат |
|----|--------|-----------|
| P7.1 | Производительность на крупных репо; кэш клонирования | Ускорение |
| P7.2 | Безопасность: шифрование токена, отсутствие секретов в логах/артефактах, изоляция shared volume и прав на каталоги | Security review |
| P7.3 | E2E-прогон + chaos: timeout/сбой анализатора | E2E-набор |
| P7.4 | Документация: README, runbook, руководство пользователя | Docs |
| P7.5 | Ревью и актуализация ADR (все решения приняты; фиксировать отклонения) | Реестр |

**DoD P7**: релизный чек-лист пройден. М5.

## Оценка и вехи

| Фаза | Оценка (идеальные дни) |
|------|-------------------------|
| P0 | 2–3 |
| P1 | 3–4 |
| P2 | 5–6 |
| P3 | 3–4 |
| P4 | 3–4 |
| P5 | 4–5 |
| P6 | 5–6 |
| P7 | 3–5 |
| **Итого** | **≈29–40** |

## Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| ArchGuard меняет формат вывода | средняя | высокое | пиннинг версии, адаптер + golden-тесты |
| Helm-шаблоны сложно рендерить | высокая | среднее | подмножество (`helm template` в контейнере) |
| C++ даёт мало сервисной информации | высокая | среднее | честно помечать как «include/call-граф» |
| `analyzer` — единая точка отказа / «шумный сосед» | средняя | среднее | рестарт воркера, Celery retry, лимиты CPU/RAM, изоляция по каталогу `<run_id>` |
| Рост общего volume `data` (клоны/артефакты) | средняя | среднее | TTL/ретеншн, очистка после run, лимит размера |
| Рассинхрон двойной записи Postgres/Neo4j | средняя | высокое | идемпотентный `MERGE`, ре-импорт из JSONB-слепка, тест согласованности |
| Долгие анализы больших репо | средняя | среднее | таймауты, лимиты, прогресс-статусы |
