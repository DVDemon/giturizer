# ADR-0023: Tree-sitter как syntax-index для API-handler'ов

- **Статус:** Принято
- **Дата:** 2026-11-25

## Контекст

После P0 ([api-flow-poc](../plan/api-flow-poc.md)) нужно production-решение для
определения кода, реализующего API: route + handler + источник.

Doxygen хорошо работает для C++ call graph, но ограничен для Java-фреймворков,
не подходит для TS/Python и не связывает аннотации с handler'ами.

## Решение

- Tree-sitter используется как **syntax-index** для Java, TypeScript и Python.
- Детектируются:
  - Spring/JAX-RS (`@RestController`, `@RequestMapping`, `@GetMapping`, ...);
  - NestJS (`@Controller`, `@Get/@Post/...`), Express/Fastify (`app.get/...`);
  - FastAPI (`@router.post`, `APIRouter(prefix=...)`), Flask (`@app.route`).
- Class-level prefix + method path нормализуются; path-параметры → `{}`.
- `@FeignClient`/клиентские интерфейсы исключаются из входных API.
- Результат — artifact `syntax` (`syntax.json`) и
  `GET /api/runs/{id}/handlers`.
- Tree-sitter не строит call graph и не разрешает DI/URL; это этапы P2/P3.
- ArchGuard остаётся семантическим анализатором; Doxygen — fallback для C++.
- Зависимости Tree-sitter устанавливаются только в образ `analyzer` (extra `syntax`);
  API/worker их не получают.

## Альтернативы

- Doxygen для всех языков — не подходит для TS/Python и Java-прокси.
- Только ArchGuard — не даёт точных source ranges и route-нормализации.
- Regex — хрупко; Tree-sitter даёт AST и устойчивость.

## Последствия

- (+) Единый AST-слой для Java/TS/Python, точные `file:line`.
- (+) Artifact пригоден для P2 call graph.
- (+) API/worker не утяжеляются.
- (−) Нужны отдельные route-правила на фреймворк.
- (−) DI/URL/конфиги остаются нерешёнными до P2/P3.
- (−) Грамматики нужно версионировать и тестировать.
