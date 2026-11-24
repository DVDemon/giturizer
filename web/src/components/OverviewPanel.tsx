import { downloadCsv, downloadJson, structurizrDownloadUrl } from "../api";
import type { Run, RunResults } from "../types";
import { StatusBadge } from "./StatusBadge";

export function OverviewPanel({
  run,
  results,
  runId,
}: {
  run: Run;
  results: RunResults | null;
  runId: string;
}) {
  const warnings =
    results?.artifacts.find((artifact) => artifact.kind === "pipeline_warnings")
      ?.content.warnings ?? [];

  const openapi = results?.api_specs.find((spec) => spec.kind === "openapi");

  return (
    <div className="stack">
      <section className="panel">
        <h3>Запуск</h3>
        <div className="kv-grid">
          <span>Статус</span>
          <span>
            <StatusBadge status={run.status} />
          </span>
          <span>Commit</span>
          <span className="mono">{run.commit_sha ?? "—"}</span>
          <span>Создан</span>
          <span>{formatDate(run.created_at)}</span>
          <span>Начат</span>
          <span>{formatDate(run.started_at)}</span>
          <span>Завершён</span>
          <span>{formatDate(run.finished_at)}</span>
          <span>Длительность</span>
          <span>{duration(run.started_at, run.finished_at)}</span>
        </div>
        {run.error && <p className="error">{run.error}</p>}
      </section>

      {results && (
        <div className="cards">
          <Metric label="Технологий" value={results.technologies.length} />
          <Metric label="API-контрактов" value={results.api_specs.length} />
          <Metric
            label="Compose-сервисов"
            value={results.deployment?.summary.compose_services ?? 0}
          />
          <Metric
            label="Kubernetes"
            value={results.deployment?.summary.kubernetes_resources ?? 0}
          />
          <Metric
            label="Dockerfile"
            value={results.deployment?.summary.dockerfiles ?? 0}
          />
          <Metric label="Артефактов" value={results.artifacts.length} />
        </div>
      )}

      {(warnings as string[]).length > 0 && (
        <section className="panel">
          <h3>Предупреждения</h3>
          <ul className="list">
            {(warnings as string[]).map((warning) => (
              <li key={warning} className="error">
                {warning}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="panel">
        <h3>Экспорт</h3>
        <div className="toolbar">
          <a className="button" href={structurizrDownloadUrl(runId, "dsl")} download>
            workspace.dsl
          </a>
          <a className="button" href={structurizrDownloadUrl(runId, "json")} download>
            workspace.json
          </a>
          {openapi && (
            <button
              className="button ghost"
              onClick={() =>
                downloadJson(`openapi-${runId.slice(0, 8)}.json`, openapi.spec)
              }
            >
              OpenAPI
            </button>
          )}
          {results && (
            <button
              className="button ghost"
              onClick={() =>
                downloadCsv(`technologies-${runId.slice(0, 8)}.csv`, [
                  ["name", "kind", "version", "evidence"],
                  ...results.technologies.map((item) => [
                    item.name,
                    item.kind,
                    item.version ?? "",
                    item.evidence,
                  ]),
                ])
              }
            >
              Технологии CSV
            </button>
          )}
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span className="metric-value">{value}</span>
      <span className="metric-label">{label}</span>
    </div>
  );
}

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }
  return new Date(value).toLocaleString("ru-RU");
}

function duration(start: string | null, end: string | null): string {
  if (!start || !end) {
    return "—";
  }
  const milliseconds = new Date(end).getTime() - new Date(start).getTime();
  if (milliseconds < 1000) {
    return `${milliseconds} мс`;
  }
  const seconds = Math.round(milliseconds / 1000);
  if (seconds < 60) {
    return `${seconds} с`;
  }
  const minutes = Math.floor(seconds / 60);
  return `${minutes} мин ${seconds % 60} с`;
}
