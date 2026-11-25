import { reportDownloadUrl } from "../api";
import type { Run, RunReport, RunResults } from "../types";
import { ReportTree } from "./ReportTree";
import { StatusBadge } from "./StatusBadge";

export function OverviewPanel({
  run,
  results,
  report,
  runId,
}: {
  run: Run;
  results: RunResults | null;
  report: RunReport | null;
  runId: string;
}) {
  const warnings =
    results?.artifacts.find((artifact) => artifact.kind === "pipeline_warnings")
      ?.content.warnings ?? [];

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

      <section className="panel">
        <div className="panel-head">
          <h3>JSON-отчёт</h3>
          <a className="button small" href={reportDownloadUrl(runId)} download>
            Скачать JSON
          </a>
        </div>
        {report ? (
          <ReportTree report={report} />
        ) : (
          <p className="muted">Отчёт ещё не сформирован.</p>
        )}
      </section>

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
