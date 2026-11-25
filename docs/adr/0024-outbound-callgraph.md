# ADR-0024: Call graph handler → outbound API

- **Статус:** Принято
- **Дата:** 2026-11-25

> Подробный алгоритм: [api-flow-resolution.md](../api-flow-resolution.md).

## Контекст

P1 даёт `endpoint → handler`, но не отвечает, какие внешние HTTP-вызовы делает
код handler'а. Нужны промежуточные данные до сопоставления с внешним API (P3).

## Решение

- Строится call graph по Tree-sitter syntax-index для Java/TS/Python.
- Разрешаются:
  - вызовы `this.foo()`/`self.foo()` в текущем классе;
  - однозначные методы по имени;
  - Feign-интерфейсы и клиентские методы как terminal;
  - прямые HTTP-клиенты: RestTemplate/WebClient, axios/fetch, requests/httpx/aiohttp.
- Типы receiver'ов выводятся из аннотаций параметров/полей:
  Python (`service: ProjectService`), Java-полей, TS constructor params.
  Поэтому `service.create()` разрешается в конкретный `ProjectService.create`,
  даже если методов `create` несколько.
- При неизвестном receiver граф **не размножается** по всем одноимённым методам;
  вызов остаётся неразрешённым до P3.
- BFS: глобальный `visited` на handler, глубина ≤6, ≤50 outbound на handler.
- Результат: `syntax.outbound_calls` и `GET /api/runs/{id}/outbound-calls`.
  Это **partial**-кандидаты без URL/операции внешнего API.
- URL, конфиги, Feign path и сопоставление с API-каталогом — P3.

## Альтернативы

- Перебирать все пути call graph — взрывной рост (проверено на BeeAtlas).
- Разрешать все одноимённые методы — тысячи ложных связей.
- Сразу делать P3 — без call graph нельзя отделить handler от клиента.

## Последствия

- (+) 540 handler'ов BeeAtlas → 100 outbound-кандидатов без зависания.
- (+) Есть source path handler → service → client.
- (+) Ограничения защищают от комбинаторного взрыва.
- (−) Часть вызовов с неизвестным receiver не разрешается.
- (−) Нет URL из конфигов и external operation — до P3.
