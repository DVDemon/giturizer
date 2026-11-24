import { useEffect, useState } from "react";

import { api } from "./api";
import { ProjectsPage } from "./components/ProjectsPage";
import { ScanPage } from "./components/ScanPage";

type Page = "projects" | "scan";

function parseHash(): { page: Page; projectId: string | null } {
  const hash = window.location.hash.replace(/^#/, "");
  if (hash === "scan") {
    return { page: "scan", projectId: null };
  }
  if (hash.startsWith("scan/")) {
    const projectId = decodeURIComponent(hash.slice(5));
    return { page: "scan", projectId: projectId || null };
  }
  return { page: "projects", projectId: null };
}

export default function App() {
  const initial = parseHash();
  const [page, setPage] = useState<Page>(initial.page);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    initial.projectId,
  );
  const [health, setHealth] = useState("…");

  useEffect(() => {
    void api
      .health()
      .then((value) => setHealth(value.status))
      .catch(() => setHealth("недоступен"));
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      const route = parseHash();
      setPage(route.page);
      if (route.projectId) {
        setSelectedProjectId(route.projectId);
      }
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  function openProject(projectId: string) {
    setSelectedProjectId(projectId);
    setPage("scan");
    window.location.hash = `scan/${encodeURIComponent(projectId)}`;
  }

  function showProjects() {
    setPage("projects");
    window.location.hash = "projects";
  }

  function showScan() {
    setPage("scan");
    window.location.hash = selectedProjectId
      ? `scan/${encodeURIComponent(selectedProjectId)}`
      : "scan";
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            A
          </span>
          <div>
            <h1>ArchDiscovery</h1>
            <p className="subtitle">
              Архитектура из кода GitHub/GitLab · Structurizr + Neo4j
            </p>
          </div>
        </div>
        <nav className="main-nav">
          <button
            className={page === "projects" ? "nav-tab active" : "nav-tab"}
            onClick={showProjects}
          >
            Проекты
          </button>
          <button
            className={page === "scan" ? "nav-tab active" : "nav-tab"}
            onClick={showScan}
          >
            Сканирование
          </button>
        </nav>
        <span className={`health ${health === "ok" ? "ok" : "bad"}`}>
          API: {health}
        </span>
      </header>

      <main className="content content-wide">
        {page === "projects" ? (
          <ProjectsPage onOpenProject={openProject} />
        ) : selectedProjectId ? (
          <ScanPage projectId={selectedProjectId} onBack={showProjects} />
        ) : (
          <div className="page">
            <div className="panel">
              <p className="muted">
                Выберите проект на вкладке «Проекты», чтобы увидеть детали
                сканирования.
              </p>
              <button className="button" onClick={showProjects}>
                К проектам
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
