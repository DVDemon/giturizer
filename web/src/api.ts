import type {
  Dependency,
  GraphElement,
  Project,
  Run,
  RunResults,
  StructurizrArtifact,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export interface CreateProjectPayload {
  name: string;
  gitlab_url: string;
  default_branch?: string;
  token?: string;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  projects: () => request<Project[]>("/api/projects"),
  createProject: (payload: CreateProjectPayload) =>
    request<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteProject: (projectId: string) =>
    request<void>(`/api/projects/${projectId}`, { method: "DELETE" }),

  runs: (projectId: string) =>
    request<Run[]>(`/api/projects/${projectId}/runs`),
  startRun: (projectId: string) =>
    request<Run>(`/api/projects/${projectId}/runs`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  run: (runId: string) => request<Run>(`/api/runs/${runId}`),

  results: (runId: string) =>
    request<RunResults>(`/api/runs/${runId}/results`),
  structurizr: (runId: string) =>
    request<StructurizrArtifact>(`/api/runs/${runId}/structurizr`),

  graphElements: (runId: string) =>
    request<GraphElement[]>(`/api/runs/${runId}/graph/elements`),
  dependencies: (runId: string, elementId: string, depth = 3) =>
    request<Dependency[]>(
      `/api/runs/${runId}/graph/dependencies?element_id=${encodeURIComponent(elementId)}&depth=${depth}`,
    ),
};

export function structurizrDownloadUrl(runId: string, format: "dsl" | "json") {
  return `/api/runs/${runId}/structurizr.${format}`;
}

export function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  downloadBlob(filename, blob);
}

export function downloadCsv(filename: string, rows: string[][]) {
  const content = rows
    .map((row) =>
      row
        .map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`)
        .join(","),
    )
    .join("\n");
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  downloadBlob(filename, blob);
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
