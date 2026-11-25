# План тестирования ArchDiscovery

Тестовая стратегия по [архитектуре](../architecture.md) и [плану разработки](development-plan.md).

## 1. Стратегия

Тестовая пирамида с упором на детерминизм и изоляцию анализаторов:

```text
        ┌─────────────┐
        │   E2E       │  Docker Compose + Playwright (мало, дорого)
        ├─────────────┤
        │ Contract    │  схемы API / JSON-отчёт
        ├─────────────┤
        │ Integration │  Postgres/Redis (testcontainers), очередь
        ├─────────────┤
        │ Component   │  пайплайн-шаги на фикстурных репо
        ├─────────────┤
        │ Unit        │  чистая логика: парсеры, merge, генераторы
        └─────────────┘
```

Принципы:

- **Детерминизм**: unit/component не ходят в сеть; GitHub/GitLab мокается; внешние анализаторы — за маркером.
- **Golden-файлы** для JSON-отчёта и парсеров (snapshot-тестирование с явным обновлением).
- **Каждый анализатор — за абстракцией**: подмена реального раннера на фейк в тестах.
- **Отказ изолируется**: тест «сбой одного анализатора → остальные этапы проходят».

## 2. Инструменты

| Слой | Инструменты |
|------|-------------|
| Бэкенд | `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx.AsyncClient`/`TestClient`, `respx`, `freezegun`, `hypothesis` (для парсеров) |
| Интеграция | `testcontainers-python` (postgres, redis), `celery` eager mode, `fakeredis` |
| Контракты | `jsonschema` (JSON-отчёт), `schemathesis` (опц.) |
| Анализаторы | `pytest`-обёртки + реальные образы (маркер `@pytest.mark.docker`) |
| Веб | `vitest`, `@testing-library/react`, `msw`, `Playwright` |
| Качество | `ruff`, `black`, `mypy` (backend); `eslint`, `tsc` (web) |

## 3. Уровни тестирования

### 3.1 Unit

Быстрые, без БД/сети. Покрывают:

- `tech_detect` — маппинг манифестов → языки/фреймворки.
- `merge` — склейка, дедупликация, стабильность ID (ID не «прыгают» между прогонами).
- `graph` — внутренний C4-снапшот PostgreSQL (без Neo4j).
- `report.json` — golden-снапшот единого отчёта.
- `deployment/*` — парсеры YAML/Dockerfile/GitLab CI на фикстурах.
- `api_extractors/*` — нормализация OpenAPI/gRPC/GraphQL/аннотаций.
- `gitlab` — обработка URL/токена, редакция секретов в логах.

**Цель покрытия**: ≥80% строк в `pipeline/`, `services/`; ≥70% в `api/`.

### 3.2 Component (пайплайн-шаги)

Каждый шаг гоняется на фикстурном репозитории без БД:

```text
tests/fixtures/repos/<name>/   →   запуск шага   →   ожидаемый JSON
```

Проверяется: структура результата, привязка к контейнеру, изоляция ошибок, лимиты по времени.

### 3.3 Integration

- Миграции + CRUD через `testcontainers` (PostgreSQL).
- Celery: постановка задачи + смена статусов (eager/`fakeredis`).
- `respx` — мок GitHub/GitLab HTTP; локальный git-репозиторий как фикстура.
- PostgreSQL: JSON-отчёт/C4-снапшоты, консистентность данных,
  идемпотентность повторной записи, согласованность с PostgreSQL после сбоя.
- Контейнер `analyzer` (маркер `@pytest.mark.docker`): задача из очереди `analyzers` → инструмент
  отрабатывает фикстуру в общем volume → JSON-артефакт появляется на месте.

### 3.4 Contract

- Валидация всех ответов API по Pydantic-схемам (и `schemathesis` при наличии OpenAPI нашего API).
- Валидация структуры `report.json` (три массива: technologies/api/deployment).
- Валидация извлечённого `openapi.json` по OpenAPI 3.x schema.

### 3.5 E2E

Через `docker compose up` + Playwright:

1. Открыть UI → создать проект с URL фикстуры.
2. Дождаться статуса `done`.
3. Увидеть C4-диаграмму, API-каталог, реестр технологий, deployment и JSON-дерево.
4. Скачать JSON-отчёт — структура и массивы валидны.

GitLab-источник подменяется лёгким `git-http` контейнером с фикстурным репо (или мок-сервером).

### 3.6 Производительность

- Крупный фикстурный монорепо (несколько языков, много файлов).
- Бюджеты: клон+детект < 60 с; полный анализ среднего репо < 10 мин.
- Пропускная способность очереди: N воркеров обрабатывают M задач без взаимоблокировок.

### 3.7 Безопасность

- Токен GitLab не появляется в логах, БД (в открытом виде), артефактах.
- Анализаторы запускаются non-root, сеть по возможности `none`.
- Path traversal / zip-slip в именах из клонированного репо.
- Изоляция shared volume: analyzer видит только `/data/repos/<run_id>`; path traversal из
  репозитория не выходит за каталог запуска.

## 4. Фикстуры и golden-репозитории

`backend/tests/fixtures/repos/`:

| Фикстура | Покрывает |
|----------|-----------|
| `spring-service/` | Java, аннотации, OpenAPI, Dockerfile, k8s |
| `dotnet-service/` | C#, ASP.NET-контроллеры, csproj |
| `cpp-library/` | C++, CMake, doxygen/cpp-dependencies |
| `python-service/` | FastAPI + аннотации, requirements, Dockerfile |
| `node-service/` | express-роуты, package.json, dependency-cruiser |
| `monorepo-mixed/` | Java+Node+Python в одном репо |
| `deploy-kit/` | Helm, ArgoCD, `.gitlab-ci.yml`, compose |
| `api-specs/` | openapi.yaml, `*.proto`, `*.graphql` |

**Golden-файлы** (`tests/golden/`): эталонный `report.json` и нормализованные данные; обновление — только осознанно (`UPDATE_GOLDEN=1`).

## 5. Матрица «модуль → типы тестов»

| Модуль | Unit | Component | Integration | Contract | E2E | Perf | Security |
|--------|:----:|:---------:|:-----------:|:--------:|:---:|:----:|:--------:|
| projects/runs API | ✅ | — | ✅ | ✅ | ✅ | — | — |
| queue (celery) | ✅ | — | ✅ | — | ✅ | ✅ | — |
| gitlab clone | ✅ | — | ✅ | — | ✅ | — | ✅ |
| tech_detect | ✅ | ✅ | — | — | — | — | — |
| analyzer (queue) | — | ✅ | ✅(docker) | — | ✅ | ✅ | ✅ |
| api_extractors | ✅ | ✅ | — | ✅ | ✅ | — | — |
| deployment/* | ✅ | ✅ | — | — | ✅ | — | — |
| merge/model | ✅ | ✅ | — | ✅ | — | — | — |
| report/c4 | ✅ | ✅ | ✅ | — | ✅ | ✅ | — |
| report gen | ✅ | ✅ | — | ✅ | ✅ | — | — |
| persist/artifacts | ✅ | — | ✅ | ✅ | ✅ | — | ✅ |
| web UI | ✅ | — | — | — | ✅ | — | — |

## 6. CI-пайплайн

```text
lint (ruff, black, mypy, eslint, tsc)
  → unit (pytest, vitest)
  → integration (services: postgres, redis; testcontainers)
  → build (образы api/worker/web/analyzers)
  → e2e (ручной job: docker compose + scripts/smoke.sh)
  → coverage gate (--cov-fail-under=75) + артефакты
```

- Параллельные стадии: `lint`, `unit` запускаются одновременно.
- Docker-тесты — отдельный job с маркером, может быть опциональным на слабом CI.
- Coverage: публикуем отчёт; gate на изменённые строки (diff cover) рекомендуется после MVP.

## 7. Гейты качества (Definition of Done для тестов)

- Новая функциональность поставляется с unit- (и, где уместно, component-) тестами.
- Изменение контракта (API, JSON-отчёт) — с обновлением contract/golden-тестов.
- `docker compose up` в CI проходит e2e smoke.
- Нет секретов в логах (тест-security).
- Порог покрытия не падает.

## 8. Приёмочный чек-лист (ручной, перед релизом)

- [ ] Публичные GitHub и GitLab репозитории анализируются без токена; приватные — с токеном.
- [ ] UI: пагинация 10/20/50/100, поиск/фильтр/сортировка проектов, прогресс и этапы запуска.
- [ ] API-каталог: поиск/фильтры по сервису/методу/источнику, пагинация, deep link операции.
- [ ] C4: Graphviz SVG, переключение на Mermaid, масштаб, скачивание; подписи протоколов/транспорта; скрытие при одном прямоугольнике.
- [ ] API/Deployment вкладки скрываются при отсутствии данных.
- [ ] Tree-sitter: Spring/NestJS/FastAPI route + handler, Feign исключён, тесты/source ranges.
- [ ] P2 call graph: handler → service → HTTP-клиент, лимиты глубины/outbound, без `fetchone`-ложных срабатываний.
- [ ] Все 5 языков дают хотя бы базовый результат.
- [ ] Deployment-модель извлекается из всех 5 источников.
- [ ] API извлекается из всех 4 групп источников.
- [ ] JSON-отчёт содержит technologies/api/deployment и скачивается.
- [ ] C4-снапшот и JSON-отчёт согласованы в PostgreSQL.
- [ ] Веб показывает C4, API, технологии, deployment; граф доступен через API.
- [ ] Сбой одного анализатора не роняет весь запуск.
- [ ] Токен не утекает в логи/артефакты.
