# ADR-0019: ForceAtlas2 и перетаскиваемые узлы графа

- **Статус:** Заменено (UI-граф и Neo4j удалены)
- **Дата:** 2026-11-24

## Контекст

Граф архитектуры использовал `breadthfirst` и не давал свободно исследовать
связи. Нужна ForceAtlas2-раскладка и перетаскивание узлов.

## Исследование компонентов

Проверены популярные варианты (npm, скачивания за месяц):

- [`graphology-layout-forceatlas2`](https://www.npmjs.com/package/graphology-layout-forceatlas2)
  — ForceAtlas2 для [`graphology`](https://www.npmjs.com/package/graphology), ~2.5 млн/мес;
  стандартная связка с [`sigma`](https://www.npmjs.com/package/sigma) (~3 млн/мес).
- [`cytoscape-fcose`](https://www.npmjs.com/package/cytoscape-fcose) и
  [`cytoscape-cola`](https://www.npmjs.com/package/cytoscape-cola) — force-directed
  раскладки для Cytoscape, но **не ForceAtlas2**.
- [`react-force-graph-2d`](https://www.npmjs.com/package/react-force-graph-2d) —
  d3-force, draggable, но не ForceAtlas2.
- Отдельного поддерживаемого `cytoscape-forceatlas2` в npm не найдено.

## Решение

- Позиции считает **`graphology-layout-forceatlas2`** на `MultiGraph`, построенном
  из тех же узлов/рёбер (parent-связи слабее, weight 0.7; relationship — 1).
- Cytoscape остаётся рендерером: раскладка `preset` с полученными координатами,
  поэтому сохраняются стили, подписи, клики и drill-down.
- Узлы **grabbable** (`autoungrabify: false`, `grabbable: true`), курсор `grab`.
- После `dragfree` пересчитываются **связанные узлы** (2-hop neighborhood):
  перемещаемый узел фиксируется, остальные пересчитываются ForceAtlas2 и
  анимируются. Легенда технологий над графом убрана.
- Начальные позиции — детерминированная спираль; кнопка «Пересчитать» меняет seed,
  «Вписать» возвращает весь граф в видимую область.
- Параметры: `adjustSizes`, `scalingRatio: 12`, `gravity: 0.6`, `linLogMode`,
  `barnesHutOptimize`, 300–1000 итераций в зависимости от числа узлов.

## Альтернативы

- Перейти на Sigma.js — больше возможностей для больших графов, но полный
  rewrite рендера, подписей, кликов и side panel.
- fCoSE/Cola — проще, но это не ForceAtlas2.
- React Force Graph — не ForceAtlas2.

## Последствия

- (+) Органичная ForceAtlas2-раскладка, узлы можно двигать и исследовать.
- (+) Текущие стили и drill-down сохранены.
- (+) Зависимости небольшие (graphology + layout), без смены рендера.
- (−) При 86 узлах и крупных подписях начальный fit мелкий; помогает зум и «Вписать».
- (−) ForceAtlas2 считается синхронно при открытии графа (для сотен узлов — доли секунды).


> Уточнение 2026-11-25: интерактивный граф убран из карточек систем, graph-API удалён,
> Neo4j также удалён (ADR-0022); данные C4 остаются в PostgreSQL.
