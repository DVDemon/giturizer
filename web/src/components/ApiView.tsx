import { useEffect, useMemo, useRef, useState } from "react";

import { buildCatalog, kindLabel } from "../apiCatalog";
import type { CatalogOperation } from "../apiCatalog";
import { pageNumbers } from "../format";
import type { ApiSpec } from "../types";

const PAGE_SIZE = 50;

function MethodBadge({ method }: { method: string }) {
  return (
    <span className={`method method-${method.toLowerCase()}`}>{method}</span>
  );
}

function SchemaDetails({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="api-schema">
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function OperationDetail({
  operation,
  onClose,
}: {
  operation: CatalogOperation;
  onClose: () => void;
}) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    ref.current?.scrollTo({ top: 0 });
  }, [operation.id]);

  const contentTypes = (value: unknown): string => {
    if (!value || typeof value !== "object") {
      return "";
    }
    return Object.keys(value as Record<string, unknown>).join(", ");
  };

  return (
    <aside className="api-detail panel" ref={ref}>
      <div className="api-detail-head">
        <MethodBadge method={operation.method} />
        <button className="icon-button" title="Закрыть" onClick={onClose}>
          ×
        </button>
      </div>
      <h3 className="api-detail-path">{operation.path}</h3>
      {operation.summary && <p className="api-detail-summary">{operation.summary}</p>}
      {operation.description && (
        <p className="muted">{operation.description}</p>
      )}

      <div className="api-meta">
        <div>
          <span>Сервис</span>
          <strong>{operation.service}</strong>
        </div>
        <div>
          <span>Источник</span>
          <strong>{kindLabel(operation.kind)}</strong>
        </div>
        {operation.framework && (
          <div>
            <span>Фреймворк</span>
            <strong>{operation.framework}</strong>
          </div>
        )}
        {operation.operationId && (
          <div>
            <span>operationId</span>
            <code>{operation.operationId}</code>
          </div>
        )}
        <div className="api-meta-wide">
          <span>Файл</span>
          <code>{operation.source}</code>
        </div>
        {operation.tags.length > 0 && (
          <div className="api-meta-wide">
            <span>Теги</span>
            <div className="api-tags">
              {operation.tags.map((tag) => (
                <span className="tag" key={tag}>
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {operation.parameters.length > 0 && (
        <section className="api-section">
          <h4>Параметры</h4>
          <table className="table api-params">
            <thead>
              <tr>
                <th>Имя</th>
                <th>Где</th>
                <th>Обяз.</th>
                <th>Схема</th>
              </tr>
            </thead>
            <tbody>
              {operation.parameters.map((parameter) => (
                <tr key={`${parameter.name}-${parameter.location}`}>
                  <td>{parameter.name}</td>
                  <td>{parameter.location}</td>
                  <td>{parameter.required ? "да" : "—"}</td>
                  <td>
                    <code>
                      {parameter.schema ? JSON.stringify(parameter.schema) : "—"}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {operation.requestBody != null && (
        <section className="api-section">
          <h4>Тело запроса</h4>
          <p className="muted">
            content-type: {contentTypes((operation.requestBody as Record<string, unknown>).content) || "—"}
          </p>
          <SchemaDetails title="Схема запроса" value={operation.requestBody} />
        </section>
      )}

      {operation.responses.length > 0 && (
        <section className="api-section">
          <h4>Ответы</h4>
          <table className="table api-params">
            <thead>
              <tr>
                <th>Код</th>
                <th>Описание</th>
                <th>Content-Type</th>
              </tr>
            </thead>
            <tbody>
              {operation.responses.map((response) => (
                <tr key={response.status}>
                  <td>
                    <code>{response.status}</code>
                  </td>
                  <td>{response.description || "—"}</td>
                  <td>{contentTypes(response.content) || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {operation.responses.map((response) =>
            response.content ? (
              <SchemaDetails
                key={`schema-${response.status}`}
                title={`Схема ответа ${response.status}`}
                value={response.content}
              />
            ) : null,
          )}
        </section>
      )}

      {(operation.request || operation.response) && (
        <section className="api-section">
          <h4>Контракт</h4>
          <div className="api-meta">
            <div>
              <span>Запрос</span>
              <code>{operation.request ?? "—"}</code>
            </div>
            <div>
              <span>Ответ</span>
              <code>{operation.response ?? "—"}</code>
            </div>
          </div>
        </section>
      )}

      {operation.fields && operation.fields.length > 0 && (
        <section className="api-section">
          <h4>Поля</h4>
          <p className="api-fields">{operation.fields.join(", ")}</p>
        </section>
      )}

      {operation.parameters.length === 0 &&
        operation.requestBody == null &&
        operation.responses.length === 0 &&
        !operation.request &&
        !operation.fields?.length && (
          <p className="muted">
            Для annotation-контракта доступны метод, путь и файл-источник;
            схемы запроса/ответа в исходниках не найдены.
          </p>
        )}
    </aside>
  );
}

export function ApiView({ specs }: { specs: ApiSpec[] }) {
  const catalog = useMemo(() => buildCatalog(specs), [specs]);
  const [query, setQuery] = useState("");
  const [service, setService] = useState("");
  const [method, setMethod] = useState("");
  const [kind, setKind] = useState("");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const methods = useMemo(
    () => [...new Set(catalog.operations.map((item) => item.method))].sort(),
    [catalog],
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return catalog.operations.filter((item) => {
      if (service && item.service !== service) {
        return false;
      }
      if (method && item.method !== method) {
        return false;
      }
      if (kind && item.kind !== kind) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${item.method} ${item.path} ${item.summary} ${item.operationId} ${item.service} ${item.tags.join(" ")}`
        .toLowerCase()
        .includes(needle);
    });
  }, [catalog, query, service, method, kind]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const selected =
    catalog.operations.find((item) => item.id === selectedId) ?? null;

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  useEffect(() => {
    const opId = new URLSearchParams(window.location.search).get("op");
    if (!opId) {
      return;
    }
    const index = catalog.operations.findIndex((item) => item.id === opId);
    if (index >= 0) {
      setSelectedId(opId);
      setPage(Math.floor(index / PAGE_SIZE) + 1);
    }
  }, [catalog]);

  function syncUrl(operation: CatalogOperation | null) {
    const url = new URL(window.location.href);
    if (operation) {
      url.searchParams.set("api", String(operation.specIndex));
      url.searchParams.set("op", operation.id);
    } else {
      url.searchParams.delete("api");
      url.searchParams.delete("op");
    }
    window.history.replaceState(
      null,
      "",
      `${url.pathname}${url.search}${url.hash}`,
    );
  }

  function select(operation: CatalogOperation) {
    setSelectedId(operation.id);
    syncUrl(operation);
  }

  function close() {
    setSelectedId(null);
    syncUrl(null);
  }

  function resetPage() {
    setPage(1);
  }

  if (catalog.operations.length === 0) {
    return <p className="muted">API-контракты не найдены.</p>;
  }

  return (
    <div className="api-page">
      <p className="muted api-stats">
        {catalog.operations.length} endpoint · {catalog.services.length} сервисов ·{" "}
        {specs.length} источников
      </p>

      <div className="toolbar api-toolbar">
        <input
          className="input search"
          placeholder="Поиск по path, summary, operationId…"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            resetPage();
          }}
        />
        <select
          className="input select"
          value={service}
          onChange={(event) => {
            setService(event.target.value);
            resetPage();
          }}
        >
          <option value="">Все сервисы</option>
          {catalog.services.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          className="input select"
          value={method}
          onChange={(event) => {
            setMethod(event.target.value);
            resetPage();
          }}
        >
          <option value="">Все методы</option>
          {methods.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          className="input select"
          value={kind}
          onChange={(event) => {
            setKind(event.target.value);
            resetPage();
          }}
        >
          <option value="">Все источники</option>
          {catalog.kinds.map((item) => (
            <option key={item} value={item}>
              {kindLabel(item)}
            </option>
          ))}
        </select>
        <span className="muted api-counter">
          {filtered.length} из {catalog.operations.length}
        </span>
      </div>

      <div className="api-layout">
        <div className="api-list">
          <table className="table api-table">
            <thead>
              <tr>
                <th>Метод</th>
                <th>Endpoint</th>
                <th>Сервис</th>
                <th>Источник</th>
              </tr>
            </thead>
            <tbody>
              {pageItems.map((operation) => (
                <tr
                  key={operation.id}
                  className={
                    operation.id === selectedId
                      ? "api-row selected"
                      : "api-row"
                  }
                  onClick={() => select(operation)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      select(operation);
                    }
                  }}
                  tabIndex={0}
                  role="button"
                >
                  <td>
                    <MethodBadge method={operation.method} />
                  </td>
                  <td>
                    <div className="api-path">{operation.path}</div>
                    {operation.summary && (
                      <div className="api-summary">{operation.summary}</div>
                    )}
                  </td>
                  <td>
                    <span className="api-service">{operation.service}</span>
                  </td>
                  <td>
                    <span className="tag">{kindLabel(operation.kind)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {filtered.length === 0 && (
            <p className="muted api-empty">Ничего не найдено.</p>
          )}

          <div className="pagination">
            <span className="muted">
              {filtered.length > 0
                ? `Показано ${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, filtered.length)} из ${filtered.length}`
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
        </div>

        {selected ? (
          <OperationDetail operation={selected} onClose={close} />
        ) : (
          <aside className="api-detail api-detail-empty panel">
            <p className="muted">
              Выберите endpoint слева, чтобы увидеть параметры, схемы запроса и
              ответов.
            </p>
          </aside>
        )}
      </div>
    </div>
  );
}
