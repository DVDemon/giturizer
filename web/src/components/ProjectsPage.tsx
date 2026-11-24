import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import type { CreateProjectPayload } from "../api";
import { formatDate, pageNumbers } from "../format";
import type { PagedProjects } from "../types";

const PAGE_SIZES = [10, 20, 50, 100];
const SORT_OPTIONS = [
  { value: "last_scan_at:desc", label: "Сканирование ↓" },
  { value: "last_scan_at:asc", label: "Сканирование ↑" },
  { value: "name:asc", label: "Имя А→Я" },
  { value: "name:desc", label: "Имя Я→А" },
  { value: "created_at:desc", label: "Дата создания ↓" },
  { value: "repo_url:asc", label: "URL А→Я" },
];

const EMPTY_FORM = { name: "", repo_url: "", branch: "", token: "" };

interface Props {
  onOpenProject: (projectId: string) => void;
}

function message(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause);
}

export function ProjectsPage({ onOpenProject }: Props) {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [provider, setProvider] = useState("");
  const [sortValue, setSortValue] = useState("last_scan_at:desc");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [data, setData] = useState<PagedProjects | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sort, order] = sortValue.split(":");
      const result = await api.projects({
        search: search || undefined,
        provider: provider || undefined,
        sort,
        order,
        page,
        per_page: perPage,
      });
      setData(result);
      if (result.items.length === 0 && page > 1) {
        setPage((value) => Math.max(1, value - 1));
      }
    } catch (cause) {
      setError(message(cause));
    } finally {
      setLoading(false);
    }
  }, [search, provider, sortValue, page, perPage]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const payload: CreateProjectPayload = {
        name: form.name.trim(),
        repo_url: form.repo_url.trim(),
        default_branch: form.branch.trim() || undefined,
        token: form.token.trim() || undefined,
      };
      const project = await api.createProject(payload);
      setForm(EMPTY_FORM);
      setShowCreate(false);
      await load();
      onOpenProject(project.id);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(projectId: string, name: string) {
    if (!window.confirm(`Удалить проект «${name}» и все его запуски?`)) {
      return;
    }
    setBusyId(projectId);
    setError(null);
    try {
      await api.deleteProject(projectId);
      await load();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusyId(null);
    }
  }

  async function handleStart(projectId: string) {
    setBusyId(projectId);
    setError(null);
    try {
      await api.startRun(projectId);
      onOpenProject(projectId);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusyId(null);
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;
  const from = data && data.total > 0 ? (data.page - 1) * data.per_page + 1 : 0;
  const to = data ? Math.min(data.page * data.per_page, data.total) : 0;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>Проекты</h2>
          <p className="muted">
            {data ? `${data.total} проектов` : "Загрузка…"}
          </p>
        </div>
        <button className="button" onClick={() => setShowCreate((value) => !value)}>
          {showCreate ? "Скрыть форму" : "+ Новый проект"}
        </button>
      </div>

      {error && (
        <div className="alert error">
          {error}
          <button className="icon-button" onClick={() => setError(null)}>
            ×
          </button>
        </div>
      )}

      {showCreate && (
        <form className="panel create-panel" onSubmit={handleCreate}>
          <h3>Новый проект</h3>
          <div className="create-grid">
            <input
              className="input"
              placeholder="Имя проекта"
              required
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
            <input
              className="input"
              placeholder="https://github.com/owner/repo или GitLab"
              required
              value={form.repo_url}
              onChange={(event) => setForm({ ...form, repo_url: event.target.value })}
            />
            <input
              className="input"
              placeholder="Ветка (авто, если пусто)"
              value={form.branch}
              onChange={(event) => setForm({ ...form, branch: event.target.value })}
            />
            <input
              className="input"
              type="password"
              placeholder="Токен (только для приватных)"
              value={form.token}
              onChange={(event) => setForm({ ...form, token: event.target.value })}
            />
          </div>
          <p className="muted">
            Публичные репозитории GitHub и GitLab клонируются без токена.
          </p>
          <button className="button" type="submit" disabled={submitting}>
            {submitting ? "Создание…" : "Создать проект"}
          </button>
        </form>
      )}

      <div className="toolbar">
        <input
          className="input search"
          placeholder="Поиск по имени или URL"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
        />
        <select
          className="input select"
          value={provider}
          onChange={(event) => {
            setProvider(event.target.value);
            setPage(1);
          }}
        >
          <option value="">Все провайдеры</option>
          <option value="github">GitHub</option>
          <option value="gitlab">GitLab</option>
          <option value="other">Другие</option>
        </select>
        <select
          className="input select"
          value={sortValue}
          onChange={(event) => {
            setSortValue(event.target.value);
            setPage(1);
          }}
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          className="input select"
          value={perPage}
          onChange={(event) => {
            setPerPage(Number(event.target.value));
            setPage(1);
          }}
        >
          {PAGE_SIZES.map((size) => (
            <option key={size} value={size}>
              {size} на странице
            </option>
          ))}
        </select>
      </div>

      <div className={loading ? "table-wrap loading" : "table-wrap"}>
        <table className="projects-table">
          <thead>
            <tr>
              <th>Проект</th>
              <th>URL</th>
              <th>Последнее сканирование</th>
              <th aria-label="Действия" />
            </tr>
          </thead>
          <tbody>
            {(data?.items ?? []).map((project) => (
              <tr
                key={project.id}
                className="project-row"
                onClick={() => onOpenProject(project.id)}
              >
                <td>
                  <button
                    className="project-name"
                    onClick={(event) => {
                      event.stopPropagation();
                      onOpenProject(project.id);
                    }}
                  >
                    {project.name}
                  </button>
                  <div className="project-sub">
                    <span className={`provider-pill provider-${project.provider}`}>
                      {project.provider}
                    </span>
                    <span className="muted">
                      {project.default_branch ?? "ветка авто"}
                    </span>
                  </div>
                </td>
                <td>
                  <span className="url-cell" title={project.repo_url}>
                    {project.repo_url}
                  </span>
                </td>
                <td>{formatDate(project.last_scan_at)}</td>
                <td className="row-actions">
                  <button
                    className="button small"
                    disabled={busyId === project.id}
                    onClick={(event) => {
                      event.stopPropagation();
                      void handleStart(project.id);
                    }}
                  >
                    Анализ
                  </button>
                  <button
                    className="icon-button"
                    title="Удалить проект"
                    disabled={busyId === project.id}
                    onClick={(event) => {
                      event.stopPropagation();
                      void handleDelete(project.id, project.name);
                    }}
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr>
                <td colSpan={4} className="empty-state">
                  Ничего не найдено. Измените фильтры или создайте проект.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <span className="muted">
          {data && data.total > 0
            ? `Показано ${from}–${to} из ${data.total}`
            : "Нет проектов"}
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
  );
}
