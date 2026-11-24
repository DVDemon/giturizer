# ADR-0009: Вывод в Structurizr — DSL + JSON workspace

- **Статус:** Принято
- **Дата:** 2026-11-23

> Генерируются **оба** формата: `workspace.dsl` и `workspace.json`.

## Контекст

Канонический выход сервиса — архитектура в формате Structurizr. Structurizr поддерживает два
взаимозаменяемых представления одного workspace: DSL (текст) и JSON (машинный).

## Решение

Генерировать оба артефакта из внутренней модели:

1. **`workspace.dsl`** — Structurizr DSL, читаемый/редактируемый человеком.
2. **`workspace.json`** — Structurizr workspace JSON для импорта в Structurizr Lite/on-premises
   и клиентские библиотеки.

Маппинг: сервис → `softwareSystem`; контейнер (Dockerfile/k8s) → `container`; модуль/пакет →
`component`; вызов API → relationship с тегом `API`; обращение к БД → relationship с тегом `Database`;
источники §7 → `deploymentNodes` + `deploymentRelationships`.

## Альтернативы

- Только DSL — человеку удобно, но машинный импорт хуже.
- Только JSON — удобно инструментам, но не читается и не редактируется вручную.

## Последствия

- Полная совместимость с экосистемой Structurizr; возможность «допилить» модель вручную в DSL.
- Нужно поддерживать генератор и держать JSON-контракт согласованным с версией Structurizr.
