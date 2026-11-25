# P0 PoC: Tree-sitter vs Doxygen для API-потоков

- **Статус:** Завершён
- **Дата:** 2026-11-25
- **План:** [api-flow-analysis.md](api-flow-analysis.md)
- **Код PoC:** [poc/api-flow](../../poc/api-flow)

## 1. Что проверяли

P0 отвечает на вопросы:

1. Может ли Tree-sitter быть общим syntax-index для C++, Java, TypeScript, Python?
2. Достаточно ли Doxygen для тех же данных?
3. Как детектировать route/handler и outbound-вызов по AST?
4. Какая схема `ApiFlowEdge` нужна для P1?

Фикстуры:

- `fixtures/cpp/order.cpp` — вызов `client.post("http://billing/api/v1/invoices")`;
- `fixtures/java/OrderController.java` — Spring controller + Feign client;
- `fixtures/typescript/orders.controller.ts` — NestJS controller + axios;
- `fixtures/python/orders.py` — FastAPI router + httpx.

## 2. Tree-sitter: результаты

Команда:

```bash
cd poc/api-flow
pip install -r requirements.txt
python syntax_index.py fixtures > syntax-index.json
```

Получено:

| Фикстура | Routes | Outbound call | URL |
|---|---|---|---|
| C++ | — (route-паттерн C++ не задан) | `client.post` / `createOrder` | `http://billing/api/v1/invoices` |
| Java | `POST /orders/{}/pay`, handler `pay` | `createInvoice` / `pay` | `http://billing/api/v1/invoices` |
| TypeScript | `POST /orders/{}/pay`, handler `pay` | `axios.post` / `pay` | `http://billing/api/v1/invoices` |
| Python | `POST /orders/{}/pay`, handler `pay` | `httpx.AsyncClient().post` / `pay` | `http://billing/api/v1/invoices` |

Кандидаты потоков (`api_flow_candidates`): 3 (Java/TS/Python), все `partial`, confidence `0.6`, потому что внешний API-каталог в PoC не подключён.

Ключевые наблюдения:

- Аннотации/декораторы **стоят до объявления** функции/класса, поэтому простой обход «текущая функция» даёт неверного владельца. Понадобилось связывать аннотацию с ближайшим owner по диапазонам байт.
- Feign-интерфейс с `@PostMapping("/api/v1/invoices")` выглядит как route, но это **клиентский контракт**, а не входной API. В PoC исключён по `@FeignClient`.
- Class-level prefix + method path склеиваются в `POST /orders/{}/pay`; path-параметры нормализуются в `{}`.
- Импорты/`#include` извлекаются, но сами по себе не дают операции/URL — только контекст.

## 3. Doxygen: сравнение

### C++ (успешно)

Doxygen XML с `REFERENCES_RELATION=YES`, `REFERENCED_BY_RELATION=YES`, `XML_PROGRAMLISTING=YES`, `HAVE_DOT=NO`:

- `<referencedby>createOrder</referencedby>` у `callExternal`;
- `<references>callExternal</references>` внутри `createOrder`;
- URL-литерал в `<programlisting>` с номером строки.

То есть для прямых C++-вызовов Doxygen даёт call chain и URL — сопоставимо с Tree-sitter, но без собственного AST-слоя.

### Java (ограниченно)

На аналогичной фикстуре Doxygen:

- разобрал `@PostMapping("/orders")` и URL в program listing;
- **не дал** `<references>`/`<referencedby>` для `billing.post` (при `HAVE_DOT=NO`);
- не разрешает Feign/Spring DI, прокси и конфиг URL.

Даже с Graphviz и `CALL_GRAPH=YES` остаются runtime-прокси и выбор реализации.

### TypeScript / Python

Doxygen не является практичным парсером для этих языков; сравнение не проводилось. Tree-sitter разобрал оба.

## 4. Include/import

| Вопрос | Include/import |
|---|---|
| Найти файлы, использующие HTTP-клиент | да, как кандидаты |
| Определить входную операцию | нет |
| Определить внешнюю операцию | нет |
| Построить цепочку handler → client | нет, нужен call graph |

Include/import используем как фильтр/подсказку, не как источник `ApiFlowEdge`.

## 5. Схема `ApiFlowEdge`

Схема зафиксирована в [poc/api-flow/api_flow_edge.schema.json](../../poc/api-flow/api_flow_edge.schema.json):

- `input`: service, operation, handler{file,line,symbol};
- `output`: api, operation, url_template, client{file,line,symbol};
- `evidence[]`: route/call/url/spec_match с source;
- `confidence`: 0..1;
- `status`: `resolved | partial | unresolved`.

Валидация PoC: 3/3 кандидата прошли JSON Schema.

## 6. Решение P0

1. **Tree-sitter принимается как syntax-index**, но не как замена семантическому анализу.
2. **Doxygen остаётся fallback для C++** до parity; для Java/TS/Python он не используется.
3. **ArchGuard остаётся** семантическим анализатором Java/Kotlin/C#/TS/Python/Golang.
4. Route/handler detection — отдельный слой; `@FeignClient`/client stubs исключаются из входных API.
5. `ApiFlowEdge` схема принимается как draft для P1.
6. Перед P1 нужно добавить:
   - нормализацию route-паттернов C++ (userver/gRPC);
   - фильтр HTTP-клиентов без URL;
   - production-резолв Feign/конфигов;
   - подключение внешнего API-каталога для `output.operation`.

## 7. Ограничения PoC

- Route-детекция в PoC упрощённая (regex по тексту аннотаций/декораторов).
- Только прямые вызовы в handler, без межфайлового call graph.
- Нет разрешения URL из конфигов/service discovery.
- C++ route не реализован (нет выбранного фреймворка).
- `service` — временно из имени файла.
- Нет сравнения на реальном репозитории (следующий шаг P1).
