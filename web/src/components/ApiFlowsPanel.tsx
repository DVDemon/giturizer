import { useEffect, useMemo, useState } from "react";

import { pageNumbers } from "../format";
import type { ApiFlow } from "../types";

type SortKey = "operation" | "chains" | "systems";
type SortDirection = "asc" | "desc";

const PAGE_SIZES = [10, 20, 50];

function basename(path: string): string {
  return path.split("/").pop() ?? path;
}

function kindLabel(kind: string): string {
  const labels: Record<string, string> = {
    http: "HTTP",
    postgresql: "PostgreSQL",
    redis: "Redis",
    s3: "S3",
    rabbitmq: "RabbitMQ",
    kafka: "Kafka",
    neo4j: "Neo4j",
    mongodb: "MongoDB",
    elasticsearch: "Elasticsearch",
    database: "База данных",
    mysql: "MySQL",
  };
  return labels[kind] ?? kind;
}

function systemKey(flow: ApiFlow): string {
  const url = flow.output.urls[0];
  if (url) {
    try {
      const parsed = new URL(url);
      if (parsed.host) {
        return `${flow.output.kind}:${parsed.host}`;
      }
    } catch {
      // Относительный URL/DSN — системы считаем по типу.
    }
  }
  return flow.output.kind;
}

function systemLabel(key: string): string {
  const [kind, host] = key.split(":", 2);
  return host ? `${kindLabel(kind)} · ${host}` : kindLabel(kind);
}

function flowText(flow: ApiFlow): string {
  return [
    flow.input.operation,
    flow.input.handler.symbol,
    flow.input.handler.file,
    flow.output.callee,
    flow.output.kind,
    ...flow.output.urls,
    ...(flow.output.targets ?? []),
    ...flow.path.map((step) => step.symbol),
  ]
    .join(" ")
    .toLowerCase();
}

interface FlowGroup {
  operation: string;
  handler: ApiFlow["input"]["handler"];
  chains: ApiFlow[];
  systems: Set<string>;
}

function groupFlows(flows: ApiFlow[]): FlowGroup[] {
  const groups = new Map<string, FlowGroup>();
  for (const flow of flows) {
    const group = groups.get(flow.input.operation) ?? {
      operation: flow.input.operation,
      handler: flow.input.handler,
      chains: [],
      systems: new Set<string>(),
    };
    group.chains.push(flow);
    group.systems.add(systemKey(flow));
    groups.set(flow.input.operation, group);
  }
  return [...groups.values()];
}

function ChainTable({ flows }: { flows: ApiFlow[] }) {
  return (
    <div className="table-wrap">
      <table className="table flow-chain-table">
        <thead>
          <tr>
            <th>Цепочка вызовов</th>
            <th>Внешний вызов</th>
            <th>Endpoint / target</th>
            <th>Confidence</th>
            <th>Источник</th>
          </tr>
        </thead>
        <tbody>
          {flows.map((flow, index) => (
            <tr key={`${flow.output.file}-${flow.output.line}-${index}`}>
              <td>
                <div className="flow-path">
                  {flow.path.map((step) => step.symbol).join(" → ")}
                </div>
                <div className="flow-meta">
                  {flow.path.map((step) => (
                    <div key={`${step.file}:${step.line}`} title={step.file}>
                      {basename(step.file)}:{step.line}
                    </div>
                  ))}
                </div>
              </td>
              <td>
                <code>{flow.output.callee}</code>
                <div className="flow-meta">{kindLabel(flow.output.kind)}</div>
              </td>
              <td>
                {[...flow.output.urls, ...(flow.output.targets ?? [])]
                  .filter((value, position, values) => values.indexOf(value) === position)
                  .slice(0, 4)
                  .map((value) => (
                    <div key={value} className="flow-url">
                      {value}
                    </div>
                  ))}
                {flow.output.urls.length === 0 &&
                  (flow.output.targets ?? []).length === 0 && (
                    <span className="muted">target не разрешён</span>
                  )}
              </td>
              <td>
                {Math.round(flow.confidence * 100)}%
                <div className="flow-meta">{flow.status}</div>
              </td>
              <td>
                <span title={flow.output.file}>
                  {basename(flow.output.file)}:{flow.output.line}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ApiFlowsPanel({ flows }: { flows: ApiFlow[] }) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({
    key: "operation",
    direction: "asc",
  });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selectedOperation, setSelectedOperation] = useState<string | null>(null);

  const groups = useMemo(() => groupFlows(flows), [flows]);
  const kinds = useMemo(
    () => [...new Set(flows.map((flow) => flow.output.kind))].sort(),
    [flows],
  );

  const filteredGroups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return groups
      .map((group) => {
        const chains = group.chains.filter((flow) => {
          if (kind && flow.output.kind !== kind) {
            return false;
          }
          return !needle || flowText(flow).includes(needle);
        });
        return {
          ...group,
          chains,
          systems: new Set(chains.map(systemKey)),
        };
      })
      .filter((group) => group.chains.length > 0);
  }, [groups, kind, query]);

  const sortedGroups = useMemo(() => {
    return [...filteredGroups].sort((left, right) => {
      let result: number;
      if (sort.key === "chains") {
        result = left.chains.length - right.chains.length;
      } else if (sort.key === "systems") {
        result = left.systems.size - right.systems.size;
      } else {
        result = left.operation.localeCompare(right.operation, "ru", {
          numeric: true,
          sensitivity: "base",
        });
      }
      return sort.direction === "asc" ? result : -result;
    });
  }, [filteredGroups, sort]);

  const totalPages = Math.max(1, Math.ceil(sortedGroups.length / pageSize));
  const pageGroups = sortedGroups.slice((page - 1) * pageSize, page * pageSize);

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  const selectedChains = useMemo(
    () =>
      selectedOperation
        ? flows.filter((flow) => flow.input.operation === selectedOperation)
        : [],
    [flows, selectedOperation],
  );

  function toggleSort(key: SortKey) {
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" },
    );
    setPage(1);
  }

  function SortHeader({ column, label }: { column: SortKey; label: string }) {
    const active = sort.key === column;
    return (
      <th
        aria-sort={
          active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"
        }
      >
        <button className="sort-button" onClick={() => toggleSort(column)}>
          {label}
          <span className={active ? "sort-arrow active" : "sort-arrow"}>
            {active ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}
          </span>
        </button>
      </th>
    );
  }

  if (selectedOperation) {
    const operationChains = selectedChains;
    const systems = new Set(operationChains.map(systemKey));
    const handler = operationChains[0]?.input.handler;
    return (
      <div className="stack">
        <nav className="breadcrumbs" aria-label="Хлебные крошки">
          <button className="crumb-link" onClick={() => setSelectedOperation(null)}>
            API-потоки
          </button>
          <span className="crumb-sep">/</span>
          <span>{selectedOperation}</span>
        </nav>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>{selectedOperation}</h2>
              {handler && (
                <p className="muted">
                  {handler.symbol} · {basename(handler.file)}:{handler.line}
                </p>
              )}
            </div>
            <div className="flow-detail-stats">
              <span className="badge">{operationChains.length} цепочек</span>
              <span className="badge">{systems.size} систем</span>
            </div>
          </div>
          <ChainTable flows={operationChains} />
        </section>
      </div>
    );
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>API-потоки</h2>
            <p className="muted">
              Сгруппировано по входной операции. Нажмите на строку, чтобы открыть
              цепочки вызовов: HTTP, PostgreSQL, Redis, S3, RabbitMQ, Kafka и др.
            </p>
          </div>
          <span className="badge">{groups.length}</span>
        </div>

        <div className="toolbar flow-toolbar">
          <input
            className="input search"
            placeholder="Поиск по операции, handler, вызову, URL…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
          <select
            className="input select"
            value={kind}
            onChange={(event) => {
              setKind(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Все внешние системы</option>
            {kinds.map((item) => (
              <option key={item} value={item}>
                {kindLabel(item)}
              </option>
            ))}
          </select>
          <select
            className="input select"
            value={pageSize}
            onChange={(event) => {
              setPageSize(Number(event.target.value));
              setPage(1);
            }}
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size} на странице
              </option>
            ))}
          </select>
          <span className="muted api-counter">
            {filteredGroups.length} операций ·{" "}
            {filteredGroups.reduce((sum, group) => sum + group.chains.length, 0)} цепочек
          </span>
        </div>

        <div className="table-wrap">
          <table className="table flow-group-table">
            <thead>
              <tr>
                <SortHeader column="operation" label="Входная операция" />
                <SortHeader column="chains" label="Цепочек вызовов" />
                <SortHeader column="systems" label="Систем" />
              </tr>
            </thead>
            <tbody>
              {pageGroups.map((group) => (
                <tr
                  key={group.operation}
                  className="flow-group-row"
                  tabIndex={0}
                  role="button"
                  onClick={() => setSelectedOperation(group.operation)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedOperation(group.operation);
                    }
                  }}
                >
                  <td>
                    <strong>{group.operation}</strong>
                    <div className="flow-meta">
                      {group.handler.symbol} ·{" "}
                      <span title={group.handler.file}>
                        {basename(group.handler.file)}:{group.handler.line}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className="flow-count">{group.chains.length}</span>
                  </td>
                  <td>
                    <span className="flow-count">{group.systems.size}</span>
                    <div className="flow-meta">
                      {[...group.systems].slice(0, 3).map(systemLabel).join(", ")}
                      {group.systems.size > 3 ? " +" : ""}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {sortedGroups.length === 0 && (
          <p className="muted flow-empty">Ничего не найдено.</p>
        )}

        <div className="pagination">
          <span className="muted">
            {sortedGroups.length > 0
              ? `Показано ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, sortedGroups.length)} из ${sortedGroups.length}`
              : "Нет операций"}
          </span>
          <div className="pagination-controls">
            <button
              className="button ghost small"
              disabled={page <= 1}
              onClick={() => setPage((value) => Math.max(1, value - 1))}
            >
              ←
            </button>
            {pageNumbers(page, totalPages).map((value, index) =>
              value === "…" ? (
                <span key={`gap-${index}`} className="muted">
                  …
                </span>
              ) : (
                <button
                  key={value}
                  className={value === page ? "button small" : "button ghost small"}
                  onClick={() => setPage(value)}
                >
                  {value}
                </button>
              ),
            )}
            <button
              className="button ghost small"
              disabled={page >= totalPages}
              onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
            >
              →
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
