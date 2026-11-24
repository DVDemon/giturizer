import { useMemo, useState } from "react";

import { downloadCsv } from "../api";
import type { Technology } from "../types";

type SortKey = "name" | "kind" | "version";
type SortDirection = "asc" | "desc";

function compareVersions(left?: string | null, right?: string | null): number {
  if (!left && !right) {
    return 0;
  }
  if (!left) {
    return 1;
  }
  if (!right) {
    return -1;
  }
  return left.localeCompare(right, undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

export function TechTable({
  technologies,
  runId,
}: {
  technologies: Technology[];
  runId: string;
}) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({
    key: "name",
    direction: "asc",
  });

  const kinds = useMemo(
    () => Array.from(new Set(technologies.map((item) => item.kind))).sort(),
    [technologies],
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return technologies.filter((item) => {
      if (kind && item.kind !== kind) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${item.name} ${item.kind} ${item.version ?? ""} ${item.evidence}`
        .toLowerCase()
        .includes(needle);
    });
  }, [technologies, query, kind]);

  const sorted = useMemo(() => {
    return [...filtered].sort((left, right) => {
      let result: number;
      if (sort.key === "version") {
        const leftMissing = !left.version;
        const rightMissing = !right.version;
        if (leftMissing || rightMissing) {
          result = leftMissing === rightMissing ? 0 : leftMissing ? 1 : -1;
        } else {
          result = compareVersions(left.version, right.version);
        }
      } else {
        result = String(left[sort.key]).localeCompare(String(right[sort.key]), "ru", {
          numeric: true,
          sensitivity: "base",
        });
      }
      if (sort.key === "version" && (!left.version || !right.version)) {
        return result;
      }
      return sort.direction === "asc" ? result : -result;
    });
  }, [filtered, sort]);

  function toggleSort(key: SortKey) {
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" },
    );
  }

  function reset() {
    setQuery("");
    setKind("");
    setSort({ key: "name", direction: "asc" });
  }

  function exportCsv() {
    downloadCsv(`technologies-${runId.slice(0, 8)}.csv`, [
      ["name", "kind", "version", "evidence"],
      ...sorted.map((item) => [
        item.name,
        item.kind,
        item.version ?? "",
        item.evidence,
      ]),
    ]);
  }

  function SortHeader({ column, label }: { column: SortKey; label: string }) {
    const active = sort.key === column;
    return (
      <th aria-sort={active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}>
        <button className="sort-button" onClick={() => toggleSort(column)}>
          {label}
          <span className={active ? "sort-arrow active" : "sort-arrow"}>
            {active ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}
          </span>
        </button>
      </th>
    );
  }

  const hasFilters = query.trim() !== "" || kind !== "";

  return (
    <div>
      <div className="toolbar tech-toolbar">
        <input
          className="input search"
          placeholder="Поиск по технологии, версии, основанию…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select
          className="input select"
          value={kind}
          onChange={(event) => setKind(event.target.value)}
        >
          <option value="">Все типы</option>
          {kinds.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <button className="button ghost" onClick={reset} disabled={!hasFilters && sort.key === "name" && sort.direction === "asc"}>
          Сбросить
        </button>
        <button className="button ghost" onClick={exportCsv}>
          CSV
        </button>
        <span className="muted tech-counter">
          {sorted.length} из {technologies.length}
        </span>
      </div>

      <table className="table tech-table">
        <thead>
          <tr>
            <SortHeader column="name" label="Технология" />
            <SortHeader column="kind" label="Тип" />
            <SortHeader column="version" label="Версия" />
            <th>Основание</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((item, index) => (
            <tr key={`${item.kind}-${item.name}-${item.version ?? ""}-${index}`}>
              <td>{item.name}</td>
              <td>
                <span className="tag">{item.kind}</span>
              </td>
              <td>{item.version ?? "—"}</td>
              <td className="muted">{item.evidence}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {sorted.length === 0 && <p className="muted">Ничего не найдено.</p>}
    </div>
  );
}
