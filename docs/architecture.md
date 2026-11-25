# Сервис анализа архитектуры (ArchDiscovery)

Рабочее название: **ArchDiscovery**.

Сервис принимает на вход URL репозитория GitHub или GitLab (публичного или с токеном),
выгружает и анализирует его исходный код,
и восстанавливает архитектуру: связи между компонентами/сервисами, API, технологии и библиотеки,
а также модель развёртывания. Канонический результат — **единый JSON-отчёт**:
`technologies`, `api` (сервисы → методы) и `deployment` (способ → сервисы).

## 1. Цель и назначение

- Принять URL репозитория **GitHub** или **GitLab** (HTTP(S)); публичные — без токена,
  приватные — с access token. Ветка может быть указана или определена автоматически.
- Выполнить полный цикл статического анализа кода.
- Построить архитектурную модель (C4-ориентированную): системы/сервисы, контейнеры, компоненты,
  зависимости, вызовы API, обращения к БД.
- Извлечь модель развёртывания из IaC/конфигурации в репозитории (Dockerfile, docker-compose,
  Kubernetes, Helm, ArgoCD, GitLab CI).
- Сгенерировать спецификации API (OpenAPI, gRPC, GraphQL, аннотации фреймворков).
- Сформировать реестр технологий и библиотек.
- Отдать единый JSON-отчёт и визуализировать C4/API/технологии/deployment в вебе.

## 2. Ключевые архитектурные решения (кратко)

| # | Решение | Значение | Статус |
|---|---------|----------|--------|
| 1 | Бэкенд | Python + FastAPI | Принято |
| 2 | БД | PostgreSQL (метаданные/артефакты/JSON-отчёт/C4) | Принято |
| 3 | Веб-визуализация | Свой вьюер (Graphviz/Mermaid + API-каталог) | Принято |
| 4 | Модель выполнения | Асинхронная очередь (Redis + Celery) | Принято |
| 5 | Анализаторы | Долгоживущий контейнер `analyzer` + очередь задач | Принято |
| 6 | Источники развёртывания | Dockerfile/compose, k8s, Helm, ArgoCD, GitLab CI | Принято |
| 7 | Источники API | OpenAPI, gRPC/protobuf, GraphQL, аннотации фреймворков | Принято |
| 8 | Аутентификация | Одиночный пользователь / внутренний | Принято |
| 9 | Формат результата | единый JSON-отчёт (technologies/api/deployment) | Принято |
| 10 | Хранение графа | PostgreSQL JSONB (C4-модель) | Принято |
| 11 | Связь worker ↔ analyzer | Общая очередь + shared volume (без docker.sock) | Принято |
| 12 | Доступ к GitLab/GitHub | access token (опционально) | Принято |
| 13 | Провайдеры | GitHub (public) + GitLab, авто-ветка | Принято |
| 14 | Анализатор | Tree-sitter (Java/TS/Python/C++ POCO) + ArchGuard + C++ (doxygen), submodules | Принято |

Полный реестр — в [`docs/adr/README.md`](adr/README.md).

## 3. Системный контекст (C4: Context)

```mermaid
flowchart LR
    U[Пользователь / архитектор] --> W[ArchDiscovery]
    W --> G[GitHub / GitLab (источник кода)]
    W --> R[Реестры Docker-образов]
    W --> D[PostgreSQL + Redis]
    W --> A[Анализаторы: Tree-sitter, ArchGuard, doxygen, pyan, ...]
```

- **Пользователь** — архитектор/разработчик, вводит URL проекта, просматривает результаты.
- **GitHub / GitLab** — источник исходного кода. Публичные репозитории клонируются
  анонимно, приватные — по access token; провайдер определяется по URL.
- **Реестры образов** — необязательно: определения образов из Dockerfile/k8s/Helm.
- **PostgreSQL + Redis** — метаданные/артефакты/отчёт/C4 и очередь задач.

## 4. Контейнеры (C4: Containers)

```mermaid
flowchart TB
    subgraph compose[Архитектура внутри docker-compose]
        WEB[web — SPA (React/TS)] --> API[api — FastAPI]
        API --> PG[(postgres)]
        API --> RD[(redis)]
        API -->|задача| RD
        RD --> WK[worker — Celery, очередь pipeline]
        RD --> AN[analyzer — Celery, очередь analyzers]
        WK --> PG
        WK -->|clone| VOL[(volume data: repos / artifacts)]
        AN -->|read/write| VOL
        WK --> GIT[GitHub/GitLab clone]
    end
```

| Контейнер | Технология | Назначение |
|-----------|------------|------------|
| `web` | React + TypeScript (Vite), unprivileged nginx | SPA: ввод URL, список проектов/запусков, визуализация |
| `api` | Python + FastAPI + Graphviz | REST API, CRUD проектов/запусков, постановка задач, отдача результатов, C4 SVG (`fdp`) |
| `worker` | Python + Celery | Оркестрирует пайплайн (клон, детект, merge, persist), ставит задачи анализа в очередь |
| `analyzer` | Python + Celery + Java 21 + Tree-sitter + инструменты анализа | Долгоживущий воркер очереди `analyzers`: Tree-sitter syntax-index, ArchGuard scanner, doxygen, pyan |
| `postgres` | PostgreSQL 16 | Метаданные + JSON-отчёты + внутренняя C4-модель |
| `redis` | Redis 7 | Брокер очереди + кэш статусов |

> Примечание: анализаторы работают в долгоживущем контейнере `analyzer` и вызываются через очередь
> (`analyzers`). Клон репозитория и результаты передаются через общий volume `/data/repos` и
> `/data/artifacts`; Docker-сокет не используется (см. [ADR-0005](adr/0005-analyzer-runners.md),
> [ADR-0011](adr/0011-worker-analyzer-interaction.md)).

## 5. Компоненты бэкенда (C4: Components, контур `api` + `worker` + `analyzer`)

```mermaid
flowchart LR
    subgraph api
        A1[ProjectController] --> A2[ProjectService]
        A2 --> A3[RunService]
        A3 --> A4[TaskQueuePublisher]
        A5[ResultController] --> A6[ResultService]
    end
    subgraph worker
        W1[Pipeline Orchestrator]
        W2[TechDetector]
        W3[AnalyzerDispatcher]
        W4[ApiExtractor]
        W5[DeploymentExtractor]
        W6[ModelMerger]
        W7[C4ModelBuilder]
        W8[ReportBuilder]
        W9[Persister]
    end
    subgraph analyzer
        N1[Analyzer Consumer] --> N2[Tool Runners]
    end
    A4 -->|publish| RD[(redis)]
    RD --> W1
    W1 --> W2 --> W3 --> W4 --> W5 --> W6 --> W7 --> W8 --> W9
    W3 -->|задачи analyzers| RD
    RD --> N1
```

### 5.1 Пайплайн анализа (этапы)

1. **Ingest** — принимает URL GitHub/GitLab + параметры (токен, ветка, include/exclude), создаёт
   `Project` и `AnalysisRun(status=queued)`.
2. **Clone** — worker клонирует репозиторий в общий volume `/data/repos/<run_id>` (shallow, по ветке,
   с `--recurse-submodules --shallow-submodules`; если ветка не задана — определяется
   `git ls-remote --symref ... HEAD`, иначе `main`);
   путь доступен контейнеру `analyzer`.
3. **Tech detection** — определяет языки и фреймворки по манифестам
   (`pom.xml`, `build.gradle`, `*.csproj`, `CMakeLists.txt`, `requirements.txt`/`pyproject.toml`,
   `package.json`). Формирует первичный реестр технологий.
4. **Language analysis** — по обнаруженным языкам `worker` последовательно ставит задачи в очередь
   `analyzers`; контейнер `analyzer` выполняет соответствующие инструменты над клоном:
   - Java / TypeScript / Python / C++ POCO → **Tree-sitter syntax-index** (endpoint → handler, call graph, outbound calls, source ranges);
     подробно: [api-flow-resolution.md](api-flow-resolution.md);
   - Java / Kotlin / C# / TS/JS / Python / Go → **ArchGuard scanner** (Java-фичи apicalls/datamap:
     services map, API, database map; классы и модули). Анализаторы предзагружены в образ,
     каждый язык запускается независимо: ошибка языка фиксируется и не валит остальные;
     непокрытые JS/TS-модули добираются fallback-сканом файлов и импортов.
   - C++ → **doxygen** (call/include графы) + **cpp-dependencies** (`#include` в `.dot`).
   - Python → **pyan** (call graph) + **pyreverse** (UML классов/пакетов).
   - Node/TS → **dependency-cruiser** (граф модулей, правила) + **madge** (визуальный граф).

   Задачи выполняются по одной; `worker` дожидается результата каждой и забирает артефакт из
   `/data/artifacts/<run_id>`.
5. **API extraction** — извлекает и нормализует API-контракты (см. §6).
6. **Deployment extraction** — извлекает модель развёртывания (см. §7).
7. **Merge** — сводит результаты в единую внутреннюю модель архитектуры (граф элементов и связей
   в терминах C4 + deployment nodes + API + реестр технологий).
8. **Report generation** — собирает единый JSON (`technologies`, `api`, `deployment`)
   из артефактов анализа; внутренняя C4-модель генерируется для вкладки C4.
9. **Persist** — пишет метаданные/отчёт/C4-модель в PostgreSQL
   (`MERGE` по `element_id`), артефакты и обновляет статус.
10. **Serve** — API отдаёт JSON-отчёт и данные вкладок; веб рендерит.

## 6. Извлечение API

Источники (по [ADR-0007](adr/0007-api-sources.md)):

| Источник | Как извлекается | Нормализация |
|----------|-----------------|--------------|
| OpenAPI / Swagger | Парсинг `openapi.yaml/json`, Swagger-аннотации | OpenAPI 3.x как канон |
| gRPC / protobuf | Парсинг `*.proto` | RPC-сервисы → OpenAPI-подобная модель / protobuf-схема |
| GraphQL | Парсинг `*.graphql`/`*.gql` | Introspection-подобная схема |
| Аннотации фреймворков | Spring/JAX-RS (Java), ASP.NET (C#), FastAPI (Python), express-роуты (Node) | Endpoints (метод, путь, params, модель) |

Канонический формат хранения — OpenAPI 3.x (JSON) + метаданные (владелец-контейнер/сервис,
файл-источник, фреймворк). Для gRPC/GraphQL дополнительно сохраняется нативная схема.

## 7. Извлечение развёртывания (deployment)

Источники (по [ADR-0006](adr/0006-deployment-sources.md)):

| Источник | Что извлекается |
|----------|-----------------|
| `Dockerfile` / `docker-compose.yml` | образы, контейнеры, порты, volumes, env, сети |
| Kubernetes (Deployment/Service/Ingress/StatefulSet) | поды, сервисы, экспозиция, реплики, labels/selectors |
| Helm-чарты (`Chart.yaml`, `values.yaml`, `templates/`) | параметризованные k8s-ресурсы |
| ArgoCD (`Application`/`AppProject`) | связка git-репозитория ↔ кластер/namespace, sync policy |
| GitLab CI (`.gitlab-ci.yml`) | стадии, job'ы, окружения, образы раннеров |

Результат — `deploymentNodes` (Deployment Node → Container Instance) и `deploymentRelationships`
в терминах C4/deployment, плюс связи «контейнер → deployment node».

## 8. Модель данных (PostgreSQL)

```text
projects(id, name, repo_url, provider, default_branch, token_encrypted, created_at)
analysis_runs(id, project_id, status, stage, progress, technologies_count,
services_count, api_count, commit_sha, config jsonb, error text,
              started_at, finished_at)
architecture_snapshots(id, project_id, run_id, dsl text, workspace jsonb,
                       report jsonb, generated_at)  -- dsl/workspace — внутренние для C4
api_specs(id, project_id, run_id, kind, name, spec jsonb)      -- openapi|grpc|graphql|annotations
tech_registry(id, project_id, run_id, technologies jsonb)      -- языки, фреймворки, библиотеки, версии
deployment_models(id, project_id, run_id, model jsonb)         -- nodes + relationships
artifacts(id, run_id, kind, path, content bytea/text)          -- syntax.json, cpp, archguard, raw outputs
```

- **Граф архитектуры** (elements + relationships) хранится внутри `architecture_snapshots.workspace`
  (JSONB) и используется для C4; отдельного графового хранилища нет ([ADR-0022](adr/0022-postgres-only.md)).
- `architecture_snapshots.report` — единый публичный JSON-отчёт (`technologies`, `api`,
`deployment`, `api_flows`); `dsl`/`workspace` —
  внутренние данные для C4 и наружу не отдаются.

## 9. Единый JSON-отчёт

Публичный результат запуска — один JSON с тремя массивами:

```json
{
  "technologies": [
    {"name": "Spring Boot", "type": "framework", "version": "3.3.0", "description": "pom.xml"}
  ],
  "api": [
    {
      "service": "products-service",
      "methods": [
        {"operation": "GET /products", "description": "Список продуктов", "technology": "OpenAPI"}
      ]
    }
  ],
  "deployment": [
    {
      "method": "Docker Compose",
      "services": [
        {"name": "api", "image": "nginx", "image_version": "1.25",
         "ports": ["8080:80"], "dependencies": ["db"]}
      ]
    }
  ]
}
```

- **Технологии** берутся из реестра (`name`, `kind` → `type`, `version`, `evidence` → `description`).
- **API** группируется по сервисам; методы собираются из OpenAPI, annotations, gRPC и GraphQL.
- **Deployment** группируется по способу (Docker Compose, Dockerfile, Kubernetes, Helm, ArgoCD,
  GitLab CI); образ и версия разделяются, порты и зависимости сохраняются.
- Отчёт хранится в `architecture_snapshots.report`; для старых запусков собирается лениво
  и кешируется. API: `GET /api/runs/{id}/report` (и `?download=true`).
- Внутренняя C4-модель (DSL/workspace) наружу не отдаётся; для вкладки C4 используется
  минимальный `/c4.model` и SVG `/c4.svg`. Решение — [ADR-0021](adr/0021-json-report.md).

Связи несут **протоколы транспортного и прикладного уровня** (`transport`, `protocol`, `port`):
они определяются по образу/порту целевого сервиса и попадают в C4-подписи.
Базовые правила:

| Цель | Прикладной | Транспорт | Порт |
|------|-----------|-----------|------|
| `postgres[:tag]` | PostgreSQL | TCP | 5432 |
| `mongo[:tag]` | MongoDB | TCP | 27017 |
| `redis` / `valkey` | RESP | TCP | 6379 |
| `nginx` / `swagger-ui` | HTTP | TCP | 80 |
| собираемый сервис без образа | HTTP | TCP | из `ports` |
| C++ include-граф | include (compile-time) | — | — |

## 10. Визуализация (веб)

Свой вьюер ([ADR-0003](adr/0003-frontend-viewer.md)):

- **C4**: **Graphviz** (`fdp`) — container view в SVG с кластерами систем и внешними
  зависимостями, плюс переключатель на **Mermaid**. На связях отображаются прикладной
  протокол и транспорт (`HTTP · TCP:8080`); вкладка скрывается, если на диаграмме
  остаётся один прямоугольник.
- **API-каталог** — единый поиск/фильтры по всем операциям (OpenAPI/annotations/gRPC/GraphQL),
  панель деталей и deep links без конфликта с hash-роутингом; вкладка скрывается,
  если API не найдены.
- Вкладка **Deployment** скрывается, если нет данных о развёртывании.
- **Обзор** — компактная плашка (URL + статус), статистика запуска и раскрывающееся
  JSON-дерево отчёта с кнопкой скачивания.
- Граф архитектуры остаётся в PostgreSQL (C4-снапшот); публичные graph-API удалены.
- **C4 SVG** — `GET /api/runs/{id}/c4.svg`: DOT из внутренней C4-модели, Graphviz `fdp`,
  кластеры систем, связанные внешние системы; кешируется и встраивается в UI.
- Экспорт: JSON-отчёт (`/report?download=true`), API-каталог CSV, реестр технологий, C4 SVG.

## 11. Развёртывание (docker-compose)

Сервисы (см. §4): `web`, `api`, `worker`, `analyzer`, `postgres`, `redis`.

```yaml
# фрагмент docker-compose.yml (полная версия — в корне репозитория)
services:
  postgres:  { image: postgres:16, volumes: [pgdata:/var/lib/postgresql/data] }
  redis:     { image: redis:7-alpine }
  api:       { build: { context: ./backend,  dockerfile: Dockerfile.api },
               ports: ["${API_PORT:-8000}:8000"] }
  worker:    { build: { context: ./backend,  dockerfile: Dockerfile.worker },
               volumes: [data:/data] }
  analyzer:  { build: { context: .,          dockerfile: analyzer/Dockerfile },
               volumes: [data:/data] }
  web:       { build: ./web, ports: ["${WEB_PORT:-8080}:8080"] }
volumes: { data: {}, pgdata: {} }
```

Запуск: `docker compose up -d` → `web` на `:8080`, `api` на `:8000`.

## 12. Нефункциональные требования и границы

- **Изоляция**: анализаторы работают в выделенном контейнере `analyzer`; сбой одного инструмента не
  валит пайплайн (ошибки уровня инструмента ловятся и помечаются, остальные этапы продолжаются).
- **Масштаб**: количество проектов/запусков лимитируется очередью Celery; воркеры горизонтально
  масштабируются.
- **UI**: два таба — «Проекты» (серверная пагинация/фильтры/сортировка) и
  «Сканирование» (стадия, прогресс, счётчики, живые обновления).
- **Безопасность**: access token (GitLab/GitHub) хранится зашифрованно (Fernet/KMS), ошибки клонирования
  редактируются; Docker-сокет не используется; контейнеры `api`/`worker`/`analyzer`/`web` —
  `no-new-privileges` + `cap_drop: ALL`, nginx unprivileged; наружу публикуются только
  `api`/`web` (см. [ADR-0014](adr/0014-container-hardening.md)).
- **Ретеншн**: клон удаляется после запуска по умолчанию (`KEEP_REPOS=true` — оставить);
  артефакты хранятся в `/data/artifacts/<run_id>` (см. [ADR-0013](adr/0013-clone-retention.md)).
- **Границы v1**: монорепо поддерживается (несколько манифестов/языков в одном репо), но
  кросс-репозиторные зависимости и runtime-трафик (APM) не покрываются.

## 13. Открытые вопросы и roadmap

Пошаговый план реализации и стратегия тестирования — в
[`docs/plan/development-plan.md`](plan/development-plan.md) и
[`docs/plan/test-plan.md`](plan/test-plan.md).

- Покрытие C++ вне POCO слабое (doxygen/cpp-dependencies дают include/call-графы);
  для POCO routes/внешние вызовы теперь даёт Tree-sitter (ADR-0026).
- Поддержка монорепо с несколькими deployables и маппинг «код ↔ сервис» требует уточнения.
- Граф архитектуры хранится в PostgreSQL как C4-снапшот (см. [ADR-0022](adr/0022-postgres-only.md));
  публичные graph-API и UI-граф удалены.
- Мультиарендность и GitLab/GitHub OAuth — отложены до v2 ([ADR-0008](adr/0008-auth.md)).
