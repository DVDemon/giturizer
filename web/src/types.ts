export type RunStatus = "queued" | "running" | "done" | "failed";

export interface Project {
  id: string;
  name: string;
  repo_url: string;
  provider: "github" | "gitlab" | "other";
  default_branch: string | null;
  created_at: string;
  last_scan_at?: string | null;
}

export interface PagedProjects {
  items: Project[];
  total: number;
  page: number;
  per_page: number;
}

export interface Run {
  id: string;
  project_id: string;
  status: RunStatus;
  stage: string | null;
  progress: number;
  technologies_count: number;
  services_count: number;
  api_count: number;
  commit_sha: string | null;
  config: Record<string, unknown>;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Technology {
  name: string;
  kind: string;
  evidence: string;
  version?: string | null;
}

export interface ApiSpec {
  kind: string;
  name: string;
  spec: Record<string, unknown>;
}

export interface Artifact {
  kind: string;
  path: string;
  content: Record<string, unknown>;
}

export interface DeploymentSummary {
  compose_files: number;
  compose_services: number;
  dockerfiles: number;
  kubernetes_resources: number;
  helm_charts: number;
  argocd_apps: number;
  gitlab_ci_files: number;
}

export interface DeploymentModel {
  compose: Array<{
    file: string;
    services: Array<{
      name: string;
      image: string | null;
      build_context: string | null;
      dockerfile: string | null;
      ports: string[];
      depends_on: string[];
    }>;
    edges: Array<{ from: string; to: string; type: string }>;
  }>;
  dockerfiles: Array<{
    file: string;
    base_images: string[];
    exposed_ports: string[];
    commands: string[];
  }>;
  kubernetes: Array<Record<string, unknown>>;
  helm: Array<Record<string, unknown>>;
  argocd: Array<Record<string, unknown>>;
  gitlab_ci: Array<Record<string, unknown>>;
  summary: DeploymentSummary;
}

export interface RunResults {
  run: Run;
  technologies: Technology[];
  api_specs: ApiSpec[];
  deployment: DeploymentModel | null;
  artifacts: Artifact[];
}

export interface StructurizrArtifact {
  dsl: string;
  workspace: Record<string, unknown>;
}

export interface GraphElement {
  id: string;
  name: string;
  type: string;
  technology: string | null;
}

export interface Dependency {
  id: string;
  name: string;
  type: string;
  distance: number;
  protocol?: string | null;
  transport?: string | null;
  port?: string | null;
}
