import { useMemo, useState } from "react";

import { downloadCsv } from "../api";
import type { Technology } from "../types";

export function TechTable({
  technologies,
  runId,
}: {
  technologies: Technology[];
  runId: string;
}) {
  const [filter, setFilter] = useState("");

  const filtered = useMemo(
    () =>
      technologies.filter((item) =>
        `${item.name} ${item.kind} ${item.evidence}`
          .toLowerCase()
          .includes(filter.toLowerCase()),
      ),
    [technologies, filter],
  );

  const exportCsv = () =>
    downloadCsv(`technologies-${runId.slice(0, 8)}.csv`, [
      ["name", "kind", "version", "evidence"],
      ...technologies.map((item) => [
        item.name,
        item.kind,
        item.version ?? "",
        item.evidence,
      ]),
    ]);

  return (
    <div>
      <div className="toolbar">
        <input
          className="input"
          placeholder="Фильтр по технологии…"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />
        <button className="button ghost" onClick={exportCsv}>
          CSV
        </button>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Технология</th>
            <th>Тип</th>
            <th>Версия</th>
            <th>Основание</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((item) => (
            <tr key={`${item.kind}-${item.name}`}>
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
      {filtered.length === 0 && <p className="muted">Ничего не найдено.</p>}
    </div>
  );
}
