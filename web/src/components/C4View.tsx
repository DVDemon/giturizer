import mermaid from "mermaid";
import { useEffect, useMemo, useState } from "react";

let counter = 0;

function quote(value: unknown): string {
  return String(value ?? "").replaceAll('"', "&quot;");
}

function asArray(value: unknown): any[] {
  return Array.isArray(value) ? value : [];
}

function buildMermaid(workspace: Record<string, unknown>): string {
  const model = (workspace as { model?: Record<string, unknown> }).model ?? {};
  const lines = ["flowchart LR"];
  const nodeIds = new Map<string, string>();

  for (const system of asArray(model.softwareSystems)) {
    const systemId = `s${system.id}`;
    nodeIds.set(system.id, systemId);
    const containers = asArray(system.containers);
    if (containers.length > 0) {
      lines.push(`  subgraph ${systemId}["${quote(system.name)}"]`);
      for (const container of containers) {
        const containerId = `c${container.id}`;
        nodeIds.set(container.id, containerId);
        const technology = container.technology
          ? `<br/>${quote(container.technology)}`
          : "";
        lines.push(`    ${containerId}["${quote(container.name)}${technology}"]`);
        for (const component of asArray(container.components)) {
          const componentId = `k${component.id}`;
          nodeIds.set(component.id, componentId);
          lines.push(`    ${componentId}["${quote(component.name)}"]`);
          lines.push(`    ${containerId} -.-> ${componentId}`);
        }
      }
      lines.push("  end");
    } else {
      const technology = system.technology
        ? `<br/>${quote(system.technology)}`
        : "";
      lines.push(`  ${systemId}["${quote(system.name)}${technology}"]`);
    }
  }

  for (const relationship of asArray(model.relationships)) {
    const source = nodeIds.get(relationship.sourceId);
    const target = nodeIds.get(relationship.destinationId);
    if (!source || !target) {
      continue;
    }
    lines.push(`  ${source} -->|${quote(relationship.description)}| ${target}`);
  }

  return lines.join("\n");
}

export function C4View({
  workspace,
  runId,
}: {
  workspace: Record<string, unknown>;
  runId: string;
}) {
  const [svg, setSvg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"graphviz" | "mermaid">("graphviz");
  const [graphvizError, setGraphvizError] = useState(false);
  const [zoom, setZoom] = useState(100);
  const code = useMemo(() => buildMermaid(workspace), [workspace]);

  useEffect(() => {
    setGraphvizError(false);
  }, [runId]);

  useEffect(() => {
    if (mode !== "mermaid") {
      return;
    }
    let cancelled = false;
    mermaid.initialize({
      startOnLoad: false,
      theme: "base",
      securityLevel: "loose",
      flowchart: { htmlLabels: false },
      themeVariables: {
        fontFamily: '"Beeline Sans", "Golos Text", sans-serif',
        primaryColor: "#ffc800",
        primaryTextColor: "#141414",
        primaryBorderColor: "#000000",
        lineColor: "#141414",
        secondaryColor: "#f1f2f6",
        tertiaryColor: "#ffffff",
        clusterBkg: "#f1f2f6",
        clusterBorder: "#d8dce3",
        edgeLabelBackground: "#ffffff",
        textColor: "#141414",
      },
    });
    const id = `c4-${counter++}`;
    mermaid
      .render(id, code)
      .then((result) => {
        if (!cancelled) {
          setSvg(result.svg);
          setError(null);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : String(cause));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [code, mode]);

  const graphvizUrl = `/api/runs/${runId}/c4.svg`;

  return (
    <div>
      <div className="toolbar c4-toolbar">
        <button
          className={mode === "graphviz" ? "chip active" : "chip"}
          onClick={() => setMode("graphviz")}
        >
          Graphviz
        </button>
        <button
          className={mode === "mermaid" ? "chip active" : "chip"}
          onClick={() => setMode("mermaid")}
        >
          Mermaid
        </button>
        <select
          className="input select"
          value={zoom}
          onChange={(event) => setZoom(Number(event.target.value))}
          aria-label="Масштаб C4"
        >
          <option value={100}>100%</option>
          <option value={150}>150%</option>
          <option value={200}>200%</option>
        </select>
        <a className="button ghost small" href={graphvizUrl} download>
          Скачать SVG
        </a>
      </div>

      {mode === "graphviz" &&
        (graphvizError ? (
          <div className="alert warning">
            Graphviz-рендер недоступен.{" "}
            <button className="button ghost small" onClick={() => setMode("mermaid")}>
              Открыть Mermaid
            </button>
          </div>
        ) : (
          <div className="c4-graphviz">
            <img
              src={graphvizUrl}
              alt="C4 container diagram"
              style={{ width: `${zoom}%` }}
              onError={() => setGraphvizError(true)}
            />
          </div>
        ))}

      {mode === "mermaid" &&
        (error ? (
          <p className="error">Mermaid: {error}</p>
        ) : (
          <div className="c4" dangerouslySetInnerHTML={{ __html: svg }} />
        ))}
    </div>
  );
}
