# ArchDiscovery

Сервис анализа архитектуры: по URL GitLab-проекта выгружает код, восстанавливает архитектуру
(связи, API, технологии, deployment) и отдаёт результат в формате Structurizr (DSL + JSON).

- Архитектура: [docs/architecture.md](docs/architecture.md)
- Решения (ADR): [docs/adr/README.md](docs/adr/README.md)
- План разработки: [docs/plan/development-plan.md](docs/plan/development-plan.md)
- План тестирования: [docs/plan/test-plan.md](docs/plan/test-plan.md)

## Статус

Фаза **P1 (Ядро домена и API)**: проекты и запуски, постановка анализа в очередь Celery,
stub-пайплайн `queued → running → done`, шифрование GitLab-токена. Перед этим — P0 (каркас,
`docker-compose`, CI, Alembic).

### API

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/health` | health-check |
| POST | `/api/projects` | создать проект (URL GitLab, ветка, токен) |
| GET | `/api/projects` | список проектов |
| GET | `/api/projects/{id}` | проект |
| DELETE | `/api/projects/{id}` | удалить проект (каскадно удаляет запуски) |
| POST | `/api/projects/{id}/runs` | запустить анализ (`202`, `status=queued`) |
| GET | `/api/runs/{id}` | статус запуска |
| GET | `/api/projects/{id}/runs` | запуски проекта |

## Быстрый старт

```bash
cp .env.example .env      # при конфликте портов поменяйте API_PORT/WEB_PORT
make up                   # docker compose up -d --build
```

- API: http://localhost:8000/health (или `API_PORT` из `.env`)
- UI: http://localhost:8080 (или `WEB_PORT`)
- Neo4j Browser: http://localhost:7474

Остановка:

```bash
make down
```

## Локальная разработка

```bash
make venv        # .venv + backend[dev]
make test        # pytest
make lint        # ruff + black --check
make typecheck   # mypy
```

## Контейнеры (docker-compose)

| Сервис | Назначение |
|--------|------------|
| `api` | FastAPI, REST API, health-check |
| `worker` | Celery-воркер очереди `pipeline` (оркестрация) |
| `analyzer` | Celery-воркер очереди `analyzers` (инструменты анализа) |
| `web` | React/TS SPA (заглушка на P0) |
| `postgres` | PostgreSQL 16 — метаданные и артефакты |
| `neo4j` | Neo4j 5 — граф архитектуры |
| `redis` | Redis 7 — брокер очередей |

`worker` и `analyzer` используют общий volume `data` (`/data`): клон репозитория доступен
анализатору по тому же пути.
