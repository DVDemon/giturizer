import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "./api";
import type { CreateProjectPayload } from "./api";
import { ApiView } from "./components/ApiView";
import { C4View } from "./components/C4View";
import { DeploymentView } from "./components/DeploymentView";
import { GraphView } from "./components/GraphView";
import { OverviewPanel } from "./components/OverviewPanel";
import { Sidebar } from "./components/Sidebar";
import { TechTable } from "./components/TechTable";
import type { Project, Run, RunResults, StructurizrArtifact } from "./types";

type Tab = "overview" | "graph" | "c4" | "api" | "tech" | "deployment";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "overview", label: "Обзор" },
  { id: "graph", label: "Граф" },
  { id: "c4", label: "C4" },
  { id: "api", label: "API" },
  { id: "tech", label: "Технологии" },
  { id: "deployment", label: "Deployment" },
];

function message(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause);
}

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [results, setResults] = useState<RunResults | null>(null);
  const [structurizr, setStructurizr] = useState<StructurizrArtifact | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState("…");
  const [busy, setBusy] = useState(false);

  const activeRun = useMemo(
    () => runs.find((run) => run.id === activeRunId) ?? null,
    [runs, activeRunId],
  );

  const loadProjects = useCallback(async () => {
    const items = await api.projects();
    setProjects(items);
    setSelectedProjectId((current) => {
      if (current && items.some((item) => item.id === current)) {
        return current;
      }
      return items[0]?.id ?? null;
    });
  }, []);

  useEffect(() => {
    void loadProjects().catch((cause) => setError(message(cause)));
    void api
      .health()
      .then((value) => setHealth(value.status))
      .catch(() => setHealth("недоступен"));
  }, [loadProjects]);

  useEffect(() => {
    if (!selectedProjectId) {
      setRuns([]);
      setActiveRunId(null);
      return;
    }
    let cancelled = false;
    api
      .runs(selectedProjectId)
      .then((items) => {
        if (cancelled) {
          return;
        }
        setRuns(items);
        setActiveRunId((current) =>
          current && items.some((item) => item.id === current)
            ? current
            : (items[0]?.id ?? null),
        );
      })
      .catch((cause) => {
        if (!cancelled) {
          setError(message(cause));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedProjectId]);

  const activeRunStatus = activeRun?.status;
  const activeRunIdValue = activeRun?.id;

  useEffect(() => {
    if (!activeRunIdValue || activeRunStatus !== "done") {
      setResults(null);
      setStructurizr(null);
      return;
    }
    let cancelled = false;
    Promise.all([api.results(activeRunIdValue), api.structurizr(activeRunIdValue)])
      .then(([runResults, artifact]) => {
        if (cancelled) {
          return;
        }
        setResults(runResults);
        setStructurizr(artifact);
      })
      .catch((cause) => {
        if (!cancelled) {
          setError(message(cause));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeRunIdValue, activeRunStatus]);

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

  async function handleCreate(payload: CreateProjectPayload) {
    const project = await api.createProject(payload);
    await loadProjects();
    setSelectedProjectId(project.id);
  }

  async function handleDelete(projectId: string) {
    await api.deleteProject(projectId);
    if (selectedProjectId === projectId) {
      setSelectedProjectId(null);
    }
    await loadProjects();
  }

  async function handleStartRun() {
    if (!selectedProjectId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const run = await api.startRun(selectedProjectId);
      setRuns((previous) => [run, ...previous]);
      setActiveRunId(run.id);
      setTab("overview");
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }

  const project = projects.find((item) => item.id === selectedProjectId) ?? null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>ArchDiscovery</h1>
          <p className="subtitle">
            Архитектура из исходного кода · Structurizr + Neo4j
          </p>
        </div>
        <span className={`health ${health === "ok" ? "ok" : "bad"}`}>
          API: {health}
        </span>
      </header>

      <div className="layout">
        <Sidebar
          projects={projects}
          selectedProjectId={selectedProjectId}
          onSelectProject={setSelectedProjectId}
          onCreateProject={handleCreate}
          onDeleteProject={handleDelete}
          runs={runs}
          activeRunId={activeRunId}
          onSelectRun={setActiveRunId}
          onStartRun={handleStartRun}
          busy={busy}
        />

        <main className="content">
          {error && (
            <div className="alert error">
              {error}
              <button className="icon-button" onClick={() => setError(null)}>
                ×
              </button>
            </div>
          )}

          {!project && <p className="muted">Создайте проект по URL GitLab.</p>}

          {project && !activeRun && (
            <p className="muted">
              Запустите анализ проекта «{project.name}».
            </p>
          )}

          {activeRun && (
            <>
              <div className="content-head">
                <h2>{project?.name}</h2>
                <span className="muted">run {activeRun.id.slice(0, 8)}</span>
              </div>
              <nav className="tabs">
                {TABS.map((item) => (
                  <button
                    key={item.id}
                    className={tab === item.id ? "tab active" : "tab"}
                    onClick={() => setTab(item.id)}
                  >
                    {item.label}
                  </button>
                ))}
              </nav>

              {activeRunStatus === "queued" || activeRunStatus === "running" ? (
                <p className="muted">
                  Анализ выполняется… статус обновляется автоматически.
                </p>
              ) : activeRunStatus === "failed" ? (
                <div className="alert error">
                  Запуск завершился ошибкой: {activeRun.error}
                </div>
              ) : tab === "overview" ? (
                <OverviewPanel
                  run={activeRun}
                  results={results}
                  runId={activeRun.id}
                />
              ) : !results || !structurizr ? (
                <p className="muted">Загружаем результаты…</p>
              ) : tab === "graph" ? (
                <GraphView
                  runId={activeRun.id}
                  workspace={structurizr.workspace}
                />
              ) : tab === "c4" ? (
                <C4View workspace={structurizr.workspace} />
              ) : tab === "api" ? (
                <ApiView specs={results.api_specs} />
              ) : tab === "tech" ? (
                <TechTable
                  technologies={results.technologies}
                  runId={activeRun.id}
                />
              ) : (
                <DeploymentView deployment={results.deployment} />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
