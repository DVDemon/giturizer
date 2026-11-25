# План анализа React-фронтенда

- **Статус:** Phase 1 — реализован, Phase 2 — следующий этап
- **Дата:** 2026-11-25
- **Связанные документы:** [api-flow-analysis.md](api-flow-analysis.md), [api-flow-resolution.md](../api-flow-resolution.md)

## 1. Зачем нужен фронтенд

Backend-анализ видит handler → внешний вызов, но не видит:

- какие API реально вызывает UI;
- gateway-префиксы и маршрутизацию;
- страницы, действия и последовательности вызовов;
- endpoint’ы, которые есть только в клиентском коде/contracts.

Фронтенд **не заменяет** backend-анализ: он не даёт БД, Redis, RabbitMQ,
Neo4j и внутренние вызовы сервисов. Он дополняет API-каталог и UI-сценарии.

## 2. Целевая модель

```json
{
  "frontends": [
    {
      "root": "services/prospect-frontend",
      "name": "prospect-frontend",
      "framework": "react"
    }
  ],
  "api_calls": [
    {
      "file": "src/api/user/index.ts",
      "line": 12,
      "method": "GET",
      "url_template": "/user/api/v1/user/{}/info",
      "normalized_path": "/api/v1/user/{}/info",
      "service": "fdm-auth",
      "source": "Api.get",
      "confidence": 0.85
    }
  ],
  "stats": {
    "frontends": 1,
    "files": 120,
    "api_calls": 269
  },
  "errors": []
}
```

## 3. Фазы

### Phase 1. Frontend API index

- определить React-пакеты по `package.json`;
- найти `src/api/**`;
- извлечь `Api.get/post/put/patch/delete`, `axios.*`, `fetch`;
- разобрать URL-шаблоны и `${...}`;
- резолвить константы `GATEWAY_*`/`PREFIX_*` из `const.ts`;
- нормализовать путь, query и path-параметры;
- определить сервис по gateway-префиксу;
- сохранить artifact `frontend` и endpoint `/api/runs/{id}/frontend`.

**Не входит:** React Router, hooks, component graph, UI journeys.

Phase 1 реализован: artifact `frontend`, `GET /api/runs/{id}/frontend`.

Результат на `services/prospect-frontend` BeeAtlas:

```text
frontends: 1
files:     2271
api_calls: 294
```

Сервисы: product 42, cx 36, capability 32, techradar 26, staging 23,
document 21, solution-checker 18, architect-graph 15, auth 14, bpm 11,
project 11, notifications 10, ff 8, ai-chat 6, dashboard-service 4.
Динамические `fetch(path)` (Self Architecture) дают 0 вызовов — это ограничение Phase 1.

### Phase 2. React Router и страницы

- `createBrowserRouter`, `<Route>`, `useRoutes`;
- page/component → hook → API call;
- пользовательские действия и последовательности;
- `ui_flows`.

### Phase 3. Сопоставление с backend

- gateway path → service-local operation;
- frontend call → backend `api_flows`;
- `source: frontend|backend`, confidence;
- отчёт о расхождениях.

### Phase 4. UI и покрытие

- вкладка «Frontend API»;
- фильтры по сервису/странице;
- golden-тест BeeAtlas docs → endpoints.

## 4. Приёмка Phase 1

- React-пакет определяется по `package.json`;
- `Api.get/post/...` и `axios`/`fetch` извлекаются с source line;
- `GATEWAY_*` и `PREFIX_*` резолвятся;
- путь нормализуется (`${id}` → `{}`, query удаляется);
- сервис определяется по префиксу;
- mock/test/generated не учитываются;
- artifact `frontend` и endpoint `/frontend` доступны;
- тесты на React API-модуль.

## 5. Ограничения

- динамические URL/feature flags;
- gateway называет сервис не так, как backend-каталог;
- mock-данные;
- никаких БД/очередей/Neo4j из фронтенда.
