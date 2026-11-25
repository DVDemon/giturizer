# План: анализ API-потоков (input API → external API)

- **Статус:** P0/P1 завершены; P2 — следующий этап
- **Дата:** 2026-11-25
- **Связанные ADR:** [0007](../adr/0007-api-sources.md), [0018](../adr/0018-api-catalog.md), [0021](../adr/0021-json-report.md)

## 1. Цель и границы

Нужен массив связей:

```json
[
  {
    "input": {
      "api": "orders-service",
      "operation": "POST /orders/{id}/pay",
      "handler": {
        "file": "services/orders/.../OrderController.java",
        "line": 42,
        "symbol": "OrderController.pay"
      }
    },
    "output": {
      "api": "billing-service",
      "operation": "POST /api/v1/invoices",
      "client": {
        "file": "services/orders/.../OrderController.java",
        "line": 57,
        "symbol": "BillingClient.createInvoice"
      },
      "url_template": "http://billing/api/v1/invoices"
    },
    "evidence": [
      {"kind": "route", "file": "...", "line": 42, "value": "@PostMapping(\"/{id}/pay\")"},
      {"kind": "call", "file": "...", "line": 57, "value": "billing.createInvoice"},
      {"kind": "url", "file": "...", "line": 57, "value": "http://billing/api/v1/invoices"},
      {"kind": "spec_match", "value": "OpenAPI billing-service POST /api/v1/invoices"}
    ],
    "confidence": 0.82,
    "status": "resolved"
  }
]
```

Статусы: `resolved`, `partial`, `unresolved`.

**Входит:**

- обнаружение кода, реализующего API;
- построение call graph от handler к outbound-вызовам;
- определение HTTP/gRPC/GraphQL-клиента и URL;
- сопоставление с каталогом внешних API;
- источник информации и confidence.

**Не входит:**

- runtime-трафик/APM;
- гарантированное разрешение динамических URL и DI;
- замена ArchGuard для семантики Java/Kotlin/C#/TS/Python/Golang.

## 2. Ключевое решение: Tree-sitter — парсер, не анализатор

Tree-sitter используется как **syntax index**:

- AST + queries по языкам;
- imports/includes, классы, методы, аннотации/декораторы, вызовы, строковые литералы;
- точные `file:line` для evidence.

Семантику (разрешение имён, типов, реализаций интерфейсов, URL) строим отдельным слоем. ArchGuard остаётся семантическим анализатором Java/Kotlin/C#/TS/Python/Golang; Doxygen — временный fallback для C++ до parity.

## 3. Как определяется код с API

Это отдельный, обязательный этап. «Код с API» — не любой файл, где встречается слово `api`, и не OpenAPI-спека. Это **route registration + handler**, зарегистрированный фреймворком.

### 3.1. Алгоритм

1. **Syntax index** по каждому файлу: модуль, imports, классы, методы/функции, аннотации/декораторы, строки, ranges.
2. **Поиск route-паттернов** для языка/фреймворка (таблица ниже).
3. **Сборка полного пути**:
   - class-level prefix (`@RequestMapping("/orders")`, `@Controller("orders")`, `router = APIRouter(prefix="/orders")`);
   - method-level path (`@PostMapping("/{id}/pay")`, `@Post(":id/pay")`, `@app.post("/orders/{id}/pay")`);
   - нормализация: HTTP-метод + путь, параметры `{id}`/`:id` → `{}`, убрать trailing slash.
4. **Привязка handler**:
   - symbol (класс/функция), файл, строка;
   - фреймворк, язык, теги;
   - `implementation: code | spec-only | generated | unknown`.
5. **Сверка с уже извлечёнными API**:
   - OpenAPI/annotations/ArchGuard;
   - при совпадении `METHOD + normalized path` — объединить;
   - при конфликте — сохранить оба и понизить confidence.
6. **Исключения**:
   - `test/`, `tests/`, `fixtures/`, `generated/`, `vendor/`, `node_modules/`, `target/`, `build/`;
   - клиентские стабы и DTO не считать handler’ами;
   - deprecated/скрытые routes — флаг, не исключение.
7. **Специальные источники**:
   - gRPC: `.proto` `service/rpc` → реализация сервиса (по имени/пакету);
   - GraphQL: schema + resolver map;
   - OpenAPI без кода — `spec-only`, поток не строится.

### 3.2. Паттерны по языкам

| Язык / фреймворк | Признак API-кода | Путь |
|---|---|---|
| Java Spring | `@RestController`, `@Controller` + `@RequestMapping` | class + `@GetMapping/@PostMapping/...` |
| Java JAX-RS | `@Path` | class + method `@GET/@POST/...` |
| Kotlin Spring | те же аннотации | class + method |
| Python FastAPI | `@app.get/post/...`, `@router.*` | decorator path + `APIRouter(prefix=...)` |
| Python Flask | `@app.route(..., methods=[...])` | route rule |
| Python Django/DRF | `urlpatterns`, `path()`, `@api_view` | URLconf + view |
| TypeScript NestJS | `@Controller`, `@Get/@Post/...` | class prefix + method |
| TypeScript Express/Fastify | `app.get/post`, `router.get/post`, `fastify.route` | registration path |
| C# ASP.NET | `[ApiController]`, `[Route]`, `[HttpGet]` | class + method |
| C# Minimal API | `MapGet/MapPost` | endpoint mapping |
| Go net/http | `HandleFunc`, `http.Handle` | pattern |
| Go gin/echo | `r.GET/POST` | route |
| C++ userver | handler registration | компонент/route |
| gRPC | `.proto` service/rpc | service implementation |
| GraphQL | schema/resolvers | resolver map |

### 3.3. Confidence детекции API-кода

| Условие | Confidence |
|---|---|
| Явная аннотация/декоратор + handler + совпал OpenAPI | 0.95 |
| Явная аннотация/декоратор, OpenAPI нет | 0.85 |
| Route registration в коде, путь динамический | 0.6 |
| Только OpenAPI/спека, handler не найден | `spec-only`, 0.4 |
| Эвристика по имени/строке | ≤0.4, только как кандидат |

## 4. Как определяются внешние API-вызовы

Для каждого handler:

1. Обойти call graph вглубь (по умолчанию 5–7, настраиваемо).
2. Найти вызовы HTTP/gRPC/GraphQL-клиентов:
   - Java: RestTemplate, WebClient, Feign, OkHttp, Apache HttpClient;
   - Python: requests, httpx, aiohttp, urllib;
   - TS/JS: fetch, axios, got, NestJS HttpService;
   - C#: HttpClient, Refit;
   - Go: net/http, resty;
   - C++: userver HttpClient, curl, cpr, Boost.Beast;
   - gRPC stubs, GraphQL clients.
3. Извлечь URL/операцию:
   - строковый литерал;
   - конкатенация/шаблон;
   - константа;
   - `@FeignClient(name/url)` + path;
   - конфиг (`application.yml`, env, `servers` OpenAPI);
   - service discovery/K8s DNS.
4. Сопоставить с **каталогом API** (все операции проекта + внешние OpenAPI):
   - `METHOD + normalized path`;
   - path-параметры нормализуются;
   - при неоднозначности — несколько кандидатов/`partial`.
5. Записать evidence: route, call, URL, spec match, source line.

Если URL/операция не разрешены — `unresolved` с `api` из имени Feign/service и `operation: null`. Не угадывать.

## 5. Call graph

- **Tree-sitter** строит syntax index и вызовы.
- **Resolver** (языкозависимый):
  - локальные функции/методы;
  - imports/includes;
  - поля/типы, где возможно;
  - реализации интерфейсов — только при явной связи (иначе несколько кандидатов).
- Java/Kotlin: ArchGuard + JavaParser-подобный resolver.
- C++: сначала Doxygen XML как fallback, затем Tree-sitter + Clang при необходимости.
- Ограничения: DI, reflection, dynamic dispatch, macros, runtime config — помечаются `partial/unresolved`.

## 6. Архитектура изменений

### Backend / analyzer

Новые модули:

```text
backend/src/archdiscovery/analyzer/syntax/
  index.py          # tree-sitter parse + queries
  languages.py      # грамматики, версии
  routes.py         # route/handler detection
  clients.py        # HTTP/gRPC/GraphQL client calls
  resolver.py       # call graph / scope resolution
  models.py         # SyntaxFile, RouteHandler, CallSite
backend/src/archdiscovery/pipeline/api_flow/
  build.py          # handler -> outbound calls
  match.py          # URL/operation -> API catalog
  models.py         # ApiFlowEdge, Evidence, Confidence
```

Изменения существующих:

- `analyzer/cpp.py` — Doxygen fallback или замена на syntax index после parity.
- `pipeline/annotations_extract.py` — добавить `handler: {file,line,symbol}` к endpoints.
- `pipeline/report.py` — не ломать текущий контракт; потоки отдельно.
- `services/pipeline.py` — новый этап `api_flow` после API extraction + report, с progress/счётчиком.
- `services/report.py` — при необходимости API для потоков.

### Хранение

Рекомендуется JSONB на запуск:

```text
architecture_snapshots.api_flows jsonb  -- миграция 0008
```

Альтернатива для фильтрации/агрегации — нормализованная таблица:

```text
api_flows(run_id, input_api, input_operation, output_api, output_operation,
          evidence jsonb, confidence, status)
```

Начать с JSONB; нормализовать при появлении запросов.

### API

Новый endpoint:

```text
GET /api/runs/{id}/api-flows
```

Отдаёт массив из §1. Текущий `/report` не расширять без версионирования контракта.

### UI

Новая вкладка **«API-потоки»**:

- таблица: входная операция → внешняя операция, confidence, source;
- фильтры по API/статусу/confidence;
- раскрытие evidence;
- вкладка скрыта, если потоков нет (как C4/API/Deployment).

## 7. Этапы

| Этап | Работы | Результат | Оценка |
|---|---|---|---|
| P0 | Spike Tree-sitter vs Doxygen; схема `ApiFlowEdge` | **Завершён** — [отчёт](api-flow-poc.md) | 2–3 дня |
| P1 | Syntax index + route/handler detection (Java/TS/Python) | **Завершён** — artifact `syntax`, `/handlers` | 1–2 недели |
| P2 | Call graph/resolver + client calls для Java/TS/Python | handler → outbound calls | 2–3 недели |
| P3 | URL resolution + match с API-каталогом + confidence | `api_flows` | 1–2 недели |
| P4 | JSONB/API/UI, тесты, фича-флаг | UI + endpoint | 1 неделя |
| P5 | C#/Go/C++/Kotlin, стабилизация, удаление Doxygen после parity | multi-language | 2–4 недели |

Приоритет: Java (Spring/Feign) → TypeScript (Nest/axios) → Python (FastAPI/requests) → C#/Go → C++.

P1 реализован: artifact `syntax`, `GET /api/runs/{id}/handlers`, ADR-0023.

## 8. Тестирование и приёмка

Фикстуры:

- Spring: controller + service + Feign/RestTemplate + config URL;
- FastAPI: router prefix + decorator + httpx;
- NestJS: controller + HttpService/axios;
- Express: router + fetch/axios;
- ASP.NET: attributes + HttpClient;
- gRPC: proto + stub;
- C++: handler → client → URL literal;
- negative: DB/Redis calls, test routes, generated clients, unresolved URL.

Проверки:

- `METHOD + normalized path` совпадает с endpoint;
- source file/line указывает на route и call;
- confidence/status соответствуют правилам;
- нет ложных срабатываний на тестах/сгенерированном коде;
- call graph без циклов, ограничение глубины;
- API-контракт `api-flows` стабилен;
- UI скрывает вкладку без данных.

## 9. Риски

| Риск | Митигация |
|---|---|
| Tree-sitter не даёт семантику | resolver слой, ArchGuard для Java |
| DI/прокси/reflection | `partial/unresolved`, runtime APM как дополнение |
| URL в конфиге | парсинг конфигов + сопоставление по path, confidence |
| C++ макросы/preprocessor | Doxygen/Clang fallback, не обещать полный охват |
| Качество грамматик | pin версии, тесты на фикстурах |
| Ложные API-вызовы | фильтр HTTP-клиентов, исключение БД/кэшей, evidence |
| Производительность | syntax index один проход, call graph с depth cap |
| «Любой язык» | поддерживаемые грамматики и правила, остальные — `unresolved` |

## 10. Критерии готовности

- На тестовом репозитории (Java/TS/Python) строится `api_flows` с input/output/evidence.
- Для C++ есть parity с Doxygen по классам/includes до удаления Doxygen.
- Все неразрешённые случаи явно помечены, без ложных `resolved`.
- Вкладка/эндпоинт скрываются без данных.
- Документация и ADR обновлены; миграция и тесты зелёные.
