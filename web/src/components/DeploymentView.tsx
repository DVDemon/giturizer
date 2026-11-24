import type { DeploymentModel } from "../types";

export function DeploymentView({
  deployment,
}: {
  deployment: DeploymentModel | null;
}) {
  if (!deployment) {
    return <p className="muted">Модель развёртывания не извлечена.</p>;
  }

  const summary = deployment.summary;

  return (
    <div className="stack">
      <div className="cards">
        <Metric label="Сервисов compose" value={summary.compose_services} />
        <Metric label="Dockerfile" value={summary.dockerfiles} />
        <Metric label="Kubernetes" value={summary.kubernetes_resources} />
        <Metric label="Helm-чартов" value={summary.helm_charts} />
        <Metric label="ArgoCD" value={summary.argocd_apps} />
        <Metric label="GitLab CI" value={summary.gitlab_ci_files} />
      </div>

      {deployment.compose.map((compose) => (
        <section key={compose.file} className="panel">
          <h3>Compose · {compose.file}</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Сервис</th>
                <th>Образ / сборка</th>
                <th>Порты</th>
                <th>Зависит от</th>
              </tr>
            </thead>
            <tbody>
              {compose.services.map((service) => (
                <tr key={service.name}>
                  <td>{service.name}</td>
                  <td>
                    {service.image ??
                      [service.build_context, service.dockerfile]
                        .filter(Boolean)
                        .join(" / ") ??
                      "—"}
                  </td>
                  <td>{service.ports.join(", ") || "—"}</td>
                  <td>{service.depends_on.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}

      {deployment.dockerfiles.length > 0 && (
        <section className="panel">
          <h3>Dockerfile</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Файл</th>
                <th>Базовые образы</th>
                <th>Порты</th>
              </tr>
            </thead>
            <tbody>
              {deployment.dockerfiles.map((dockerfile) => (
                <tr key={dockerfile.file}>
                  <td>{dockerfile.file}</td>
                  <td>{dockerfile.base_images.join(", ") || "—"}</td>
                  <td>{dockerfile.exposed_ports.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {deployment.kubernetes.length > 0 && (
        <section className="panel">
          <h3>Kubernetes</h3>
          <ul className="list">
            {deployment.kubernetes.map((resource, index) => (
              <li key={`${String(resource.kind)}-${String(resource.name)}-${index}`}>
                <strong>{String(resource.kind)}</strong> {String(resource.name ?? "")}
              </li>
            ))}
          </ul>
        </section>
      )}

      {deployment.helm.length > 0 && (
        <section className="panel">
          <h3>Helm</h3>
          <ul className="list">
            {deployment.helm.map((chart, index) => (
              <li key={`${String(chart.file)}-${index}`}>
                <strong>{String(chart.name ?? "")}</strong> {String(chart.version ?? "")}
              </li>
            ))}
          </ul>
        </section>
      )}

      {deployment.argocd.length > 0 && (
        <section className="panel">
          <h3>ArgoCD</h3>
          <ul className="list">
            {deployment.argocd.map((application, index) => (
              <li key={`${String(application.name)}-${index}`}>
                <strong>{String(application.name ?? "")}</strong>{" "}
                {String(application.repo_url ?? "")} / {String(application.path ?? "")}
              </li>
            ))}
          </ul>
        </section>
      )}

      {deployment.gitlab_ci.length > 0 && (
        <section className="panel">
          <h3>GitLab CI</h3>
          <ul className="list">
            {deployment.gitlab_ci.map((pipeline, index) => (
              <li key={`${String(pipeline.file)}-${index}`}>
                <strong>{String(pipeline.file)}</strong>: stages{" "}
                {(pipeline.stages as string[] | undefined)?.join(", ") ?? "—"}
              </li>
            ))}
          </ul>
        </section>
      )}
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
