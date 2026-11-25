# Реестр архитектурных решений (ADR)

Реестр решений сервиса **ArchDiscovery**. Формат записи — облегчённый ADR
(Michael Nygard): Контекст / Решение / Альтернативы / Последствия.

Статусы: **Принято** — решение зафиксировано; **Предложено** — решение сформировано,
ожидает подтверждения; **Открыто** — развилка не закрыта.

| # | Решение | Статус |
|---|---------|--------|
| [0001](0001-backend-stack.md) | Бэкенд на Python + FastAPI | Принято |
| [0002](0002-database.md) | PostgreSQL (метаданные) + Neo4j (граф) | Уточнено ADR-0022 |
| [0003](0003-frontend-viewer.md) | Собственный веб-вьюер (уточнён ADR-0018/0020) | Принято |
| [0004](0004-execution-model.md) | Асинхронное выполнение через Redis + Celery | Принято |
| [0005](0005-analyzer-runners.md) | Анализаторы в долгоживущем контейнере `analyzer` + очередь | Принято |
| [0006](0006-deployment-sources.md) | Источники развёртывания: Dockerfile/compose, k8s, Helm, ArgoCD, GitLab CI | Принято |
| [0007](0007-api-sources.md) | Источники API: OpenAPI, gRPC/protobuf, GraphQL, аннотации фреймворков | Принято |
| [0008](0008-auth.md) | Одиночный пользователь / внутренний режим | Принято |
| [0009](0009-structurizr-output.md) | Вывод в Structurizr: DSL + JSON workspace | Заменено ADR-0021 |
| [0010](0010-graph-storage.md) | Хранение графа архитектуры в Neo4j | Заменено ADR-0022 |
| [0011](0011-worker-analyzer-interaction.md) | Взаимодействие worker ↔ analyzer: очередь + общий volume | Принято |
| [0012](0012-gitlab-access.md) | Доступ к GitLab: access token | Принято |
| [0013](0013-clone-retention.md) | Очистка клонов после анализа (`KEEP_REPOS`) | Принято |
| [0014](0014-container-hardening.md) | Минимальные привилегии контейнеров | Принято |
| [0015](0015-github-public.md) | Публичные GitHub-репозитории и авто-ветка | Принято |
| [0016](0016-archguard-scanner.md) | ArchGuard scanner в анализаторе + submodules | Принято |
| [0017](0017-projects-ux.md) | Два таба, пагинация проектов и прогресс сканирования | Принято |
| [0018](0018-api-catalog.md) | API-каталог вместо Redoc | Принято |
| [0019](0019-forceatlas2-graph.md) | ForceAtlas2 и перетаскиваемые узлы графа | Заменено: UI-граф убран |
| [0020](0020-graphviz-c4.md) | Graphviz C4 container diagram (по мотивам VARP) | Принято |
| [0021](0021-json-report.md) | Единый JSON-отчёт вместо Structurizr | Принято |
| [0022](0022-postgres-only.md) | PostgreSQL-only, без Neo4j | Принято |
| [0023](0023-tree-sitter-syntax.md) | Tree-sitter syntax-index для API-handler'ов | Принято |
| [0024](0024-outbound-callgraph.md) | Call graph handler → outbound API | Принято |
| [0025](0025-external-services-flow.md) | Не-HTTP внешние вызовы в API flow | Принято |

## Шаблон записи

```markdown
# ADR-NNNN: Название

- **Статус:** Принято / Предложено / Открыто
- **Дата:** YYYY-MM-DD

## Контекст
...

## Решение
...

## Альтернативы
...

## Последствия
...
```
