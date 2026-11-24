# ADR-0006: Источники развёртывания

- **Статус:** Принято
- **Дата:** 2026-11-23

## Контекст

Модель развёртывания в Structurizr (`deploymentNodes`, `deploymentRelationships`) нужно извлекать из
IaC/конфигурации, которая лежит в анализируемом репозитории.

## Решение

Извлекать deployment-модель из всех заявленных источников:

1. **Dockerfile / docker-compose** — образы, контейнеры, порты, volumes, env, сети.
2. **Kubernetes** (Deployment/Service/Ingress/StatefulSet) — поды, сервисы, экспозиция, реплики.
3. **Helm-чарты** (`Chart.yaml`, `values.yaml`, `templates/`) — параметризованные k8s-ресурсы.
4. **ArgoCD** (`Application`/`AppProject`) — связка репозитория ↔ кластер/namespace.
5. **GitLab CI** (`.gitlab-ci.yml`) — стадии, job'ы, окружения, образы раннеров.

Результат маппится в `deploymentNodes` (Deployment Node → Container Instance) и связи
«контейнер/сервис → deployment node».

## Альтернативы

- Только Dockerfile + k8s (сужение объёма) — меньше работы, но неполная картина для ArgoCD/GitLab CI.
- Парсить только один источник — отклонено, пользователь запросил все пять.

## Последствия

- Более полная deployment-модель, но нужны отдельные парсеры под каждый формат
  (YAML-парсер с учётом Helm-шаблонов и k8s-схем).
- Рост сложности: Helm-шаблоны и GitLab CI требуют рендера/интерпретации, а не простого YAML-read.
