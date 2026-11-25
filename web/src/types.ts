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

export interface C4Component {
  id: string;
  name: string;
}

export interface C4Container {
  id: string;
  name: string;
  technology?: string;
  components?: C4Component[];
}

export interface C4System {
  id: string;
  name: string;
  technology?: string;
  containers?: C4Container[];
}

export interface C4Relationship {
  sourceId: string;
  destinationId: string;
  description?: string;
}

export interface C4Model {
  softwareSystems: C4System[];
  relationships: C4Relationship[];
}

export interface ReportTechnology {
  name: string;
  type: string;
  version: string | null;
  description: string;
}

export interface ReportMethod {
  operation: string;
  description: string;
  technology: string;
}

export interface ReportApiService {
  service: string;
  methods: ReportMethod[];
}

export interface ReportDeploymentService {
  name: string;
  image: string | null;
  image_version: string | null;
  ports: string[];
  dependencies: string[];
}

export interface ReportDeployment {
  method: string;
  services: ReportDeploymentService[];
}

export interface RunReport {
  technologies: ReportTechnology[];
  api: ReportApiService[];
  deployment: ReportDeployment[];
}
