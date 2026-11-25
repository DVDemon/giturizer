# ADR-0025: Не-HTTP внешние вызовы в API flow

- **Статус:** Принято
- **Дата:** 2026-11-25

## Контекст

API flow учитывал только HTTP-клиентов. Реальные handler'ы обращаются к
PostgreSQL, Redis, S3, RabbitMQ, Kafka, MongoDB, Elasticsearch — это такие же
внешние зависимости и они должны попадать в `api_flows`.

## Решение

Call graph классифицирует terminal-вызовы по технологии:

- `postgresql` — JDBC/JdbcTemplate/psycopg/asyncpg/R2DBC;
- `database` — Spring Data/Repository, SQLAlchemy/DataSource;
- `redis` — RedisTemplate/Jedis/Lettuce/ioredis;
- `s3` — AWS SDK/MinIO/boto3;
- `rabbitmq` — RabbitTemplate/pika/amqplib;
- `kafka` — KafkaTemplate/kafka-python/kafkajs;
- `mongodb`, `elasticsearch`, `mysql`.

Классификация учитывает:

- callee и target-класс;
- imports исходного/целевого файла;
- типовые методы (`execute`, `query`, `send`, `publish`, `get/set`, ...).

Результат:

```json
{
  "output": {
    "callee": "redis_client.get",
    "kind": "redis",
    "urls": [],
    "targets": ["order:42"]
  },
  "confidence": 0.65,
  "status": "partial"
}
```

`kind` отображается в UI; для HTTP остаётся `http`, добавляются `targets`.
Сопоставление с конкретным внешним API/очередью/БД — P3.

## Последствия

- (+) DB/cache/object storage/messaging видны в API flow и JSON.
- (+) UI различает HTTP, PostgreSQL, Redis, S3, RabbitMQ, Kafka.
- (−) Классификация эвристическая; `database` может означать любой SQL-репозиторий.
- (−) DSN/host/queue/bucket из конфигов пока не разрешаются.
- (−) Возможны ложные срабатывания на именах переменных/импортах.
