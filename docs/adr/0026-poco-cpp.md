# ADR-0026: C++/POCO в API-flow

- **Статус:** Принято
- **Дата:** 2026-11-25

## Контекст

Нужно поддержать C++-сервис на POCO: HTTP-server через
`Poco::Net::HTTPRequestHandler`, PostgreSQL через `Poco::Data`,
Redis через `redis++`, RabbitMQ через `AmqpClient`.

Обычного include/CMake-анализа недостаточно: routes задаются вручную в
`dispatch()` сравнениями `method` и `segments`.

## Решение

- `analyzer/syntax` поддерживает C++ (`.cpp/.cc/.cxx/.hpp/.hh/.h`).
- POCO-route detection:
  - класс наследует `Poco::Net::HTTPRequestHandler`;
  - анализируются `dispatch`/`handleRequest`;
  - условия `method == "POST"` и `segments.size()/segments[i]`;
  - helper-вызов в теле условия становится handler’ом;
  - `segments[i]` без литерала → `{}`.
- Call graph использует типы C++ полей/параметров (`PostgresStore& store_`,
  `RedisCache& cache_`, `RabbitMQProducer& producer_`).
- Классификация: `PostgresStore` → PostgreSQL, `RedisCache` → Redis,
  `RabbitMQProducer`/`AmqpClient` → RabbitMQ, POCO HTTP client → HTTP.
- Doxygen остаётся для C++ include/class fallback, но POCO routes даёт
  Tree-sitter.

## Пример

```cpp
if (method == "POST" && segments.size() == 1 && segments[0] == "users") {
    createUser(request, response);
    return;
}
```

→ `POST /users`, handler `createUser`, затем
`createUser → store_.createUser` (`postgresql`),
`cache_.set` (`redis`), `producer_.publish` (`rabbitmq`).

## Последствия

- (+) C++ POCO-сервисы видны в `/handlers`, `/outbound-calls`, `api_flows`.
- (+) Работает на architecture_homework_06: 10 routes, 35 внешних вызовов
  (19 PostgreSQL, 11 Redis, 5 RabbitMQ).
- (−) Правило специализировано для POCO `dispatch`-паттерна.
- (−) Нет полноценного C++ type checker; типы выводятся эвристически.
- (−) Poco HTTP-клиентские вызовы требуют отдельных маркеров.
