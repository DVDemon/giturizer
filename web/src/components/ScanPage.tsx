import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import { formatDate, formatDuration, stageLabel, statusLabel } from "../format";
import type { C4Model, Project, Run, RunReport, RunResults } from "../types";
import { ApiFlowsPanel } from "./ApiFlowsPanel";
import { ApiView } from "./ApiView";
import { C4View } from "./C4View";
import { DeploymentView } from "./DeploymentView";
import { OverviewPanel } from "./OverviewPanel";
import { StatusBadge } from "./StatusBadge";
import { TechTable } from "./TechTable";

type Tab = "overview" | "c4" | "api" | "flows" | "tech" | "deployment";

function initialTab(): Tab {
  return new URLSearchParams(window.location.search).has("op") ? "api" : "overview";
}

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "overview", label: "Обзор" },
  { id: "c4", label: "C4" },
  { id: "api", label: "API" },
  { id: "flows", label: "API-потоки" },
  { id: "tech", label: "Технологии" },
  { id: "deployment", label: "Deployment" },
];

function c4ServiceCount(model: C4Model | null): number {
  if (!model) {
    return 0;
  }
  return model.softwareSystems.reduce((total, system) => {
    const containers = system.containers ?? [];
    return total + (containers.length > 0 ? containers.length : 1);
  }, 0);
}

function hasApiData(report: RunReport | null, results: RunResults | null): boolean {
  return Boolean(results?.api_specs.length || report?.api.length);
}

function hasDeploymentData(
  report: RunReport | null,
  results: RunResults | null,
): boolean {
  if (report?.deployment.some((item) => item.services.length > 0)) {
    return true;
  }
  const deployment = results?.deployment;
  if (!deployment) {
    return false;
  }
  return Boolean(
    deployment.compose.length ||
      deployment.dockerfiles.length ||
      deployment.kubernetes.length ||
      deployment.helm.length ||
      deployment.argocd.length ||
      deployment.gitlab_ci.length,
  );
}

interface Props {
  projectId: string;
  onBack: () => void;
}

function message(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause);
}

export function ScanPage({ projectId, onBack }: Props) {
  const [project, setProject] = useState<Project | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [results, setResults] = useState<RunResults | null>(null);
  const [c4Model, setC4Model] = useState<C4Model | null>(null);
  const [report, setReport] = useState<RunReport | null>(null);
  const [tab, setTab] = useState<Tab>(() => initialTab());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [, setTick] = useState(0);

  const activeRun = useMemo(
    () => runs.find((run) => run.id === activeRunId) ?? null,
    [runs, activeRunId],
  );

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setProject(null);
    setRuns([]);
    setActiveRunId(null);
    setResults(null);
    setC4Model(null);
    setReport(null);
    setTab(initialTab());
    Promise.all([api.project(projectId), api.runs(projectId)])
      .then(([loadedProject, loadedRuns]) => {
        if (cancelled) {
          return;
        }
        setProject(loadedProject);
        setRuns(loadedRuns);
        setActiveRunId(loadedRuns[0]?.id ?? null);
      })
      .catch((cause) => {
        if (!cancelled) {
          setError(message(cause));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const activeRunStatus = activeRun?.status;
  const activeRunIdValue = activeRun?.id;

  useEffect(() => {
    if (
      !activeRunIdValue ||
      (activeRunStatus !== "queued" && activeRunStatus !== "running")
    ) {
      return;
    }
    const timer = setInterval(() => {
      void api
        .run(activeRunIdValue)
        .then((updated) =>
          setRuns((previous) =>
            previous.map((run) => (run.id === updated.id ? updated : run)),
          ),
        )
        .catch((cause) => setError(message(cause)));
    }, 2500);
    return () => clearInterval(timer);
  }, [activeRunIdValue, activeRunStatus]);

  useEffect(() => {
    if (!activeRunIdValue || activeRunStatus === "done" || activeRunStatus === "failed") {
      return;
    }
    const timer = setInterval(() => setTick((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [activeRunIdValue, activeRunStatus]);

  useEffect(() => {
    if (!activeRunIdValue || activeRunStatus !== "done") {
      setResults(null);
      setC4Model(null);
      setReport(null);
      return;
    }
    let cancelled = false;
    Promise.allSettled([
      api.results(activeRunIdValue),
      api.c4Model(activeRunIdValue),
      api.report(activeRunIdValue),
    ]).then(([resultsResult, c4Result, reportResult]) => {
      if (cancelled) {
        return;
      }
      setResults(resultsResult.status === "fulfilled" ? resultsResult.value : null);
      setC4Model(c4Result.status === "fulfilled" ? c4Result.value : null);
      setReport(reportResult.status === "fulfilled" ? reportResult.value : null);
    });
    return () => {
      cancelled = true;
    };
  }, [activeRunIdValue, activeRunStatus]);

  async function handleStart() {
    setBusy(true);
    setError(null);
    try {
      const run = await api.startRun(projectId);
      setRuns((previous) => [run, ...previous]);
      setActiveRunId(run.id);
      setTab("overview");
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }

  const visibleTabs = TABS.filter((item) => {
    if (item.id === "c4") {
      return c4ServiceCount(c4Model) > 1;
    }
    if (item.id === "api") {
      return hasApiData(report, results);
    }
    if (item.id === "deployment") {
      return hasDeploymentData(report, results);
    }
    if (item.id === "flows") {
      return Boolean(report?.api_flows.length);
    }
    return true;
  });
  const effectiveTab = visibleTabs.some((item) => item.id === tab)
    ? tab
    : "overview";
  const progress = Math.max(0, Math.min(100, activeRun?.progress ?? 0));

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <button className="back-link" onClick={onBack}>
            ← Все проекты
          </button>
          <h2>{project?.name ?? "Загрузка…"}</h2>
          {project && (
            <p className="meta-line">
              <span className={`provider-pill provider-${project.provider}`}>
                {project.provider}
              </span>
              <a href={project.repo_url} target="_blank" rel="noreferrer">
                {project.repo_url}
              </a>
              <span className="muted">
                ветка: {project.default_branch ?? "авто"}
              </span>
            </p>
          )}
        </div>
        <div className="page-actions">
          {runs.length > 1 && (
            <select
              className="input select"
              value={activeRunId ?? ""}
              onChange={(event) => setActiveRunId(event.target.value)}
            >
              {runs.map((run) => (
                <option key={run.id} value={run.id}>
                  {formatDate(run.created_at)} · {statusLabel(run.status)}
                </option>
              ))}
            </select>
          )}
          <button className="button" onClick={() => void handleStart()} disabled={busy}>
            {busy ? "Запуск…" : "Запустить анализ"}
          </button>
        </div>
      </div>

      {error && (
        <div className="alert error">
          {error}
          <button className="icon-button" onClick={() => setError(null)}>
            ×
          </button>
        </div>
      )}

      {!activeRun && project && (
        <div className="panel">
          <p className="muted">
            У проекта ещё нет запусков. Нажмите «Запустить анализ», чтобы построить
            архитектуру.
          </p>
        </div>
      )}

      {activeRun && (
        <>
          {activeRun.status !== "done" && (
          <section className="scan-card">
            <div className="scan-card-head">
              <StatusBadge status={activeRun.status} />
              <strong>{stageLabel(activeRun.stage)}</strong>
              <span className="muted">run {activeRun.id.slice(0, 8)}</span>
            </div>
            <div className="progress" aria-label={`Прогресс ${progress}%`}>
              <div
                className={
                  activeRun.status === "running" || activeRun.status === "queued"
                    ? "progress-bar live"
                    : "progress-bar"
                }
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="progress-caption">
              <span>{progress}%</span>
              <span>{formatDuration(activeRun)}</span>
            </div>
            {activeRun.progress_detail?.message && (
              <div className="progress-detail">
                <span>{activeRun.progress_detail.message}</span>
                {(activeRun.progress_detail.total ?? 0) > 0 && (
                  <strong>
                    {activeRun.progress_detail.current?.toLocaleString("ru-RU") ?? 0} /{" "}
                    {activeRun.progress_detail.total?.toLocaleString("ru-RU")} файлов
                  </strong>
                )}
              </div>
            )}
            <div className="scan-counters">
              <div className="counter">
                <strong>{activeRun.technologies_count}</strong>
                <span>Технологий</span>
              </div>
              <div className="counter">
                <strong>{activeRun.services_count}</strong>
                <span>Сервисов</span>
              </div>
              <div className="counter">
                <strong>{activeRun.api_count}</strong>
                <span>API-контрактов</span>
              </div>
              <div className="counter">
                <strong>{formatDuration(activeRun)}</strong>
                <span>Длительность</span>
              </div>
            </div>
            <div className="scan-facts">
              <span>Commit: {activeRun.commit_sha?.slice(0, 10) ?? "—"}</span>
              <span>Начат: {formatDate(activeRun.started_at)}</span>
              <span>Завершён: {formatDate(activeRun.finished_at)}</span>
            </div>
          </section>
          )}

          {activeRun.status === "done" && (
            <div className="scan-compact">
              <StatusBadge status={activeRun.status} />
              {project && (
                <a href={project.repo_url} target="_blank" rel="noreferrer">
                  {project.repo_url}
                </a>
              )}
            </div>
          )}

          {activeRun.status === "failed" && (
            <div className="alert error">
              Запуск завершился ошибкой: {activeRun.error}
            </div>
          )}

          {(activeRun.status === "queued" || activeRun.status === "running") && (
            <p className="muted">
              Этап и прогресс обновляются автоматически каждые 2.5 секунды.
            </p>
          )}

          {activeRun.status === "done" && (
            <>
              <nav className="tabs">
                {visibleTabs.map((item) => (
                  <button
                    key={item.id}
                    className={effectiveTab === item.id ? "tab active" : "tab"}
                    onClick={() => setTab(item.id)}
                  >
                    {item.label}
                  </button>
                ))}
              </nav>

              {!results ? (
                <p className="muted">Загрузка результатов…</p>
              ) : effectiveTab === "overview" ? (
                <OverviewPanel
                  run={activeRun}
                  results={results}
                  report={report}
                  runId={activeRun.id}
                />
              ) : effectiveTab === "c4" && !c4Model ? (
                <p className="muted">
                  Для этого запуска нет C4-модели — запустите анализ заново.
                </p>
              ) : effectiveTab === "c4" && c4Model ? (
                <C4View runId={activeRun.id} model={c4Model} />
              ) : effectiveTab === "api" ? (
                <ApiView specs={results.api_specs} />
              ) : effectiveTab === "flows" ? (
                <ApiFlowsPanel flows={report?.api_flows ?? []} />
              ) : effectiveTab === "tech" ? (
                <TechTable technologies={results.technologies} runId={activeRun.id} />
              ) : (
                <DeploymentView deployment={results.deployment} />
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
