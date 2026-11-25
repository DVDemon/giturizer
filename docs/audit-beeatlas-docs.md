# Аудит анализа BeeAtlas по документации

- **Дата:** 2026-11-25
- **Документация:** `documentation.zip`, git `8a90769` («переодическое обновление под main ветку репозиториев»)
- **Анализ:** последний успешный запуск BeeAtlas + локальная проверка исправлений
- **Репозиторий:** `tech-beeline/beeatlas-fdm-infrastructure`

## 1. Что сравнивали

Из документации извлечены:

- 1 335 markdown-файлов;
- **653 endpoint** из 20 каталогов `*/api/*.md` (включая вложенные `api/rest/...`);
- описания сервисов, интеграций, API и deployment.

С анализом сравнивались:

- сервисы и endpoint’ы (`/report.api`);
- внешние интеграции и API-flow;
- технологии и deployment.

## 2. Итог по API

| Метрика | Значение |
|---|---:|
| endpoint’ов в документации | 653 |
| endpoint’ов в анализе | 571 (с дублями алиасов) |
| сопоставлено по методу и пути | 524 |
| не найдено в анализе | 129 |

Основные расхождения:

| Сервис | Docs | Analysis | Не найдено | Причина |
|---|---:|---:|---:|---|
| `dashboard` | 60 | 0 | 60 | сервиса нет в анализируемом монорепо |
| `dashboard-service` | 41 | 0 | 41 | сервиса нет в анализируемом монорепо |
| `staging-service` | 47 | 34 | 13 | часть endpoint’ов отсутствует в текущей main-ветке |
| `cx-backend` | 56 | 47 | 12 | references/v3 endpoints отсутствуют в коде |
| `structurizr-backend` | 46 | 47 | 2 | `ff/adr02`, `ff/pg01` описаны, но кода нет |
| `fdm-search` | 11 | 12 | 1 | расхождение версии docs/кода |

Остальные сервисы (ai-chat, architect-graph, capability, document, fdm-auth, fdm-bpm, gateway, notifications, pack-loader, products, ff-manager, project, solution-checker, techradar) покрыты по endpoint’ам — missing = 0 после нормализации путей.

### 2.1. Что было исправлено

- Spring-аннотации с `path = "..."` и `produces = ...`:
  - были потеряны NFR endpoints (`GET /api/v1/nfr/{id}`, `GET /api/v2/nfr/{id}`);
  - генерировались ложные пути вида `/application/json`;
  - добавлен тест.
- `@RequestMapping` class-level с `path = ...`.
- Neo4j добавлен в классификацию внешних вызовов.

### 2.2. Что ещё требует исправления

1. **Дубли сервисов по алиасам**:
   `capability-backend` + `capability-service`, `cx-backend` + `cx-service`,
   `fdm-auth` + `fdm-auth-service`, `fdm-products` + `products-service`,
   `structurizr-backend` + `structurizr_backend`, `techradar-backend` + `techradar-service`.
   OpenAPI-теги и имена каталогов исходников дают разные имена.
2. **Gateway-префиксы**:
   в отчёт попадают `/arch-graph/...`, `/cx/...`, `/product/...`, `/user/...`,
   хотя документация использует service-local paths.
3. **FastAPI `APIRouter(prefix=...)`**:
   `ai-chat` в report API имеет `/session`, документация — `/api/v1/session`.
4. **Infra endpoints**:
   `/`, `/health`, `/actuator/prometheus`, `/versions` попадают в API, но
   документация их исключает.
5. **Нет канонического сопоставления** service name между compose/OpenAPI/annotations.

## 3. Технологии и deployment

- В анализе **192 технологии**, включая Java/Spring, Python/FastAPI, PostgreSQL,
  Redis, RabbitMQ/Kafka, Neo4j, S3/MinIO, frontend-библиотеки.
- Docker Compose: **85 сервисов**, Dockerfile: **26**.
- Документация описывает 20 сервисных каталогов; compose включает их плюс
  инфраструктурные контейнеры. Явных противоречий по стеку не найдено.
- `dashboard`/`dashboard-service` отсутствуют в исходниках, поэтому их
  технологии и deployment не могут быть получены из этого репозитория.

## 4. API-flow и интеграции

Локальный прогон после исправлений:

```text
handlers:        540
outbound calls:  3197
database:        2568
http:             344
postgresql:       220
redis:             37
rabbitmq:          11
s3:                 7
mongodb:            4
kafka:              4
neo4j:              2
```

Что подтверждается документацией:

- `architect-graph-service` использует Neo4j и Redis — после исправления
  Neo4j-вызовы появились;
- `document-service` использует S3 — 7 вызовов;
- `structurizr-backend` использует Kafka/Redis/PostgreSQL — все три типа есть;
- `events-history`, `fdm-bpm`, `capability` — RabbitMQ-вызовы есть.

Что требует внимания:

1. **ai-chat n8n**:
   handler `create_session` вызывает импортированную функцию под alias
   `create_session_with_n8n`, затем `call_chat_workflow` → `httpx.Client.post`.
   Call graph не разрешает Python import aliases, поэтому HTTP-вызов n8n
   в `api_flows` не попадает. Это реальный пропуск.
2. **RabbitMQ/Kafka consumers**:
   документация часто упоминает `@RabbitListener`/Kafka consumers. Это
   **входящие** сообщения, а API-flow считает исходящие вызовы handler’ов;
   их отсутствие в `api_flows` ожидаемо.
3. **Слишком много `database`**:
   2 568 кандидатов — эвристика `Repository`/`SQLAlchemy`/generic-методов.
   Нужна проверка false-positive, особенно для staging/products.
4. **Нет URL/operation match**:
   это P3; текущие записи остаются `partial`.

## 5. Вывод

Анализ в целом правильно определяет сервисы, стек и большинство API.
Критичные пробелы:

- `dashboard`/`dashboard-service` не анализируются (нет исходников в репозитории);
- часть endpoint’ов docs новее кода (staging, cx, structurizr);
- есть дубли сервисов и gateway-префиксы в API;
- FastAPI router prefixes и Python import aliases теряются;
- external API-flow для ai-chat/n8n не строится.

Приоритет исправлений:

1. канонизация service names и нормализация gateway-префиксов;
2. FastAPI prefix + Python import alias resolution;
3. фильтрация infra endpoints;
4. golden-тест `docs → expected operations` для BeeAtlas;
5. снижение false-positive `database` в API flow.
