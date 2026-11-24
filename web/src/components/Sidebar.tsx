import { useState } from "react";

import type { CreateProjectPayload } from "../api";
import type { Project, Run } from "../types";
import { StatusBadge } from "./StatusBadge";

interface SidebarProps {
  projects: Project[];
  selectedProjectId: string | null;
  onSelectProject: (projectId: string) => void;
  onCreateProject: (payload: CreateProjectPayload) => Promise<void>;
  onDeleteProject: (projectId: string) => Promise<void>;
  runs: Run[];
  activeRunId: string | null;
  onSelectRun: (runId: string) => void;
  onStartRun: () => void;
  busy: boolean;
}

export function Sidebar({
  projects,
  selectedProjectId,
  onSelectProject,
  onCreateProject,
  onDeleteProject,
  runs,
  activeRunId,
  onSelectRun,
  onStartRun,
  busy,
}: SidebarProps) {
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [token, setToken] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || !url.trim()) {
      return;
    }
    setSubmitting(true);
    try {
      await onCreateProject({
        name: name.trim(),
        repo_url: url.trim(),
        default_branch: branch.trim() || undefined,
        token: token.trim() || undefined,
      });
      setName("");
      setUrl("");
      setToken("");
      setShowForm(false);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <h2>Проекты</h2>
        <button
          className="button ghost small"
          onClick={() => setShowForm((value) => !value)}
        >
          {showForm ? "Скрыть" : "+ URL"}
        </button>
      </div>

      {showForm && (
        <form className="form" onSubmit={submit}>
          <input
            className="input"
            placeholder="Имя проекта"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <input
            className="input"
            placeholder="https://github.com/owner/repo или GitLab"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
          <input
            className="input"
            placeholder="Ветка (авто, если пусто)"
            value={branch}
            onChange={(event) => setBranch(event.target.value)}
          />
          <input
            className="input"
            placeholder="Токен (только для приватных)"
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
          />
          <p className="muted">
            Публичные репозитории GitHub и GitLab клонируются без токена.
          </p>
          <button className="button" disabled={submitting}>
            {submitting ? "Создаём…" : "Создать проект"}
          </button>
        </form>
      )}

      <ul className="project-list">
        {projects.map((project) => (
          <li key={project.id}>
            <button
              className={
                project.id === selectedProjectId
                  ? "project-item active"
                  : "project-item"
              }
              onClick={() => onSelectProject(project.id)}
            >
              <span>{project.name}</span>
              <small>
                {project.provider} · {project.default_branch ?? "авто"}
              </small>
            </button>
            <button
              className="icon-button"
              title="Удалить проект"
              onClick={() => {
                if (confirm(`Удалить проект «${project.name}»?`)) {
                  void onDeleteProject(project.id);
                }
              }}
            >
              ×
            </button>
          </li>
        ))}
        {projects.length === 0 && <li className="muted">Проектов пока нет.</li>}
      </ul>

      {selectedProjectId && (
        <div className="runs">
          <div className="sidebar-head">
            <h2>Запуски</h2>
            <button
              className="button small"
              onClick={onStartRun}
              disabled={busy}
            >
              {busy ? "…" : "Анализ"}
            </button>
          </div>
          <ul className="run-list">
            {runs.map((run) => (
              <li key={run.id}>
                <button
                  className={
                    run.id === activeRunId ? "run-item active" : "run-item"
                  }
                  onClick={() => onSelectRun(run.id)}
                >
                  <StatusBadge status={run.status} />
                  <small>{new Date(run.created_at).toLocaleString("ru-RU")}</small>
                </button>
              </li>
            ))}
            {runs.length === 0 && <li className="muted">Запусков нет.</li>}
          </ul>
        </div>
      )}
    </aside>
  );
}
