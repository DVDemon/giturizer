# Runbook: эксплуатация ArchDiscovery

## 1. Сервисы и порты

| Сервис | Порт на хосте | Назначение |
|--------|---------------|------------|
| `web` | `${WEB_PORT:-8080}` → 8080 | SPA (unprivileged nginx) |
| `api` | `${API_PORT:-8000}` → 8000 | FastAPI |
| `neo4j` | `${NEO4J_HTTP_PORT:-7474}`, `${NEO4J_BOLT_PORT:-7687}` | Neo4j Browser / Bolt |
| `postgres`, `redis` | не публикуются | внутренняя сеть compose |

`worker` и `analyzer` не публикуют порты; `analyzer` использует общий volume `data`.

## 2. Переменные окружения

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `API_PORT` / `WEB_PORT` | 8000 / 8080 | порты на хосте |
| `POSTGRES_USER/PASSWORD/DB` | archdiscovery | PostgreSQL |
| `DATABASE_URL` | `postgresql+psycopg://...@postgres:5432/...` | подключение к БД |
| `NEO4J_USER/NEO4J_PASSWORD` | neo4j / archdiscovery | Neo4j |
| `NEO4J_URL` | `bolt://neo4j:7687` | Bolt-эндпоинт |
| `REDIS_URL` | `redis://redis:6379/0` | брокер Celery |
| `DATA_DIR` | `/data` | клоны и артефакты |
| `TOKEN_ENCRYPTION_KEY` | dev-значение | ключ шифрования токенов GitHub/GitLab |
| `CLONE_TIMEOUT` | 1200 | таймаут `git clone` (с submodules), сек |
| `ANALYZER_TIMEOUT` | 3600 | таймаут задачи анализатора (ArchGuard по языкам), сек |
| `KEEP_REPOS` | `false` | оставлять клон после анализа (для отладки) |

## 3. Запуск, обновление, миграции

```bash
cp .env.example .env        # при необходимости поправьте порты/пароли/ключ
make up                     # docker compose up -d --build
docker compose exec api alembic upgrade head   # применить миграции
docker compose exec api alembic current        # проверить версию схемы
```

Обновление версии:

```bash
git pull
docker compose build
docker compose up -d
docker compose exec api alembic upgrade head
```

Остановка: `make down` (с удалением volume — `docker compose down -v`, осторожно: удаляет БД).

Если PyPI недоступен в вашей сети, сборка поддерживает альтернативный индекс:

```bash
docker compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

## 4. Проверки

```bash
curl -fsS http://localhost:8000/health
make smoke                                  # по PROJECT_ID из окружения
API_URL=http://localhost:8000 GITLAB_URL=https://gitlab.com/group/repo \
  GITLAB_BRANCH=main GITLAB_TOKEN=glpat-... bash scripts/smoke.sh
```

Смоук: создаёт проект (или использует `PROJECT_ID`), запускает анализ, ждёт `done`,
проверяет `structurizr`, `results`, `graph` и скачивание DSL.

## 5. Логи и очередь

```bash
docker compose logs -f api
docker compose logs -f worker analyzer
docker compose exec worker celery -A archdiscovery.queue.celery_app.celery_app inspect ping
docker compose exec analyzer celery -A archdiscovery.analyzer.celery_app.celery_app inspect ping
docker compose exec redis redis-cli llen pipeline
docker compose exec redis redis-cli llen analyzers
```

Масштабирование воркеров: `docker compose up -d --scale worker=2` (учтите общий volume и нагрузку на БД).

## 6. Данные и ретеншн

Volumes: `pgdata` (PostgreSQL), `neo4jdata` (граф), `data` (клоны + артефакты).

- По умолчанию **клон удаляется после завершения анализа** (`KEEP_REPOS=false`).
- Артефакты (`/data/artifacts/<run_id>/`) сохраняются; удаление проекта каскадно удаляет записи
  БД, но файлы на volume не чистятся автоматически.

Очистка старых артефактов (пример, старше 7 дней):

```bash
docker run --rm -v archdiscovery_data:/data alpine \
  sh -c 'find /data/artifacts -mindepth 1 -maxdepth 1 -type d -mtime +7 -exec rm -rf {} +'
```

## 7. Бэкап и восстановление

```bash
# PostgreSQL
docker compose exec -T postgres pg_dump -U archdiscovery archdiscovery > backup.sql
cat backup.sql | docker compose exec -T postgres psql -U archdiscovery archdiscovery

# Neo4j (офлайн-дамп; остановите neo4j перед дампом)
docker compose stop neo4j
docker compose run --rm neo4j neo4j-admin database dump neo4j --to-path=/data/backup
docker compose up -d neo4j

# Артефакты (volume)
docker run --rm -v archdiscovery_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/artifacts.tar.gz -C /data artifacts
```

## 8. Безопасность

- Токены GitHub/GitLab хранятся **зашифрованными** (Fernet). Ключ — `TOKEN_ENCRYPTION_KEY`;
  при дефолтном ключе сервис пишет предупреждение в лог. Смена ключа делает старые токены
  нечитаемыми — пересоздайте проекты.
- Ошибки `git clone` **редактируются**: токен заменяется на `***`.
- Токен не возвращается API (`ProjectRead` не содержит поля token).
- Контейнеры `api`, `worker`, `analyzer`, `web`: `no-new-privileges`, `cap_drop: ALL`;
  nginx — unprivileged-образ (порт 8080, без root).
- Docker-сокет не монтируется; анализаторы запускаются внутри выделенного контейнера.
- Наружу публикуются только `api`, `web`, `neo4j`. Для внешнего доступа ставьте reverse proxy с TLS
  и ограничением по сети/VPN.

## 9. Траблшутинг

| Симптом | Что проверить |
|---------|----------------|
| `clone` 401/403 | токен жив и имеет доступ (`read_repository`/`Contents: read`); для публичных GitHub/GitLab токен не нужен |
| `Remote branch ... not found` | ветка не указана/неверна — оставьте пустой (авто) или укажите реальную |
| `status=failed` + ошибка | `GET /api/runs/{id}` → `error`; логи `worker` |
| C++-анализатор упал | артефакт `pipeline_warnings` в `/results`; логи `analyzer`; doxygen в образе |
| ArchGuard по языку упал | блок `errors` в артефакте `archguard`; Java/Python продолжают работать (TS-парсер 2.3.0 падает на части синтаксиса) |
| Submodules не склонированы | `git clone --recurse-submodules` требует доступ к URL подмодулей; проверьте `.gitmodules` и токен |
| Neo4j недоступен | запуск завершится `done` с warning `neo4j: ...`; graph-эндпоинты вернут 503 |
| graph-эндпоинт 503 | `docker compose ps neo4j`, креды `NEO4J_*` |
| Порт занят | измените `API_PORT`/`WEB_PORT` в `.env` |
| Очередь растёт | масштабируйте `worker`/`analyzer`, проверьте Redis |
| Мало места | очистка артефактов (см. §6), `docker system prune` |

## 10. Удаление проекта

```bash
curl -X DELETE http://localhost:8000/api/projects/<id>
```

Каскадно удаляются запуски, результаты, API-спеки, deployment-модели и снапшоты.
Файлы артефактов на volume удаляются вручную (см. §6).
