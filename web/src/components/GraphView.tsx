import cytoscape from "cytoscape";
import { useEffect, useRef, useState } from "react";

import { api } from "../api";
import type { Dependency } from "../types";

interface GraphViewProps {
  runId: string;
  workspace: Record<string, unknown>;
}

function asArray(value: unknown): any[] {
  return Array.isArray(value) ? value : [];
}

export function GraphView({ runId, workspace }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [dependencies, setDependencies] = useState<Dependency[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    const model = (workspace as { model?: Record<string, unknown> }).model ?? {};
    const nodes: cytoscape.ElementDefinition[] = [];
    const edges: cytoscape.ElementDefinition[] = [];

    for (const system of asArray(model.softwareSystems)) {
      nodes.push({
        data: { id: system.id, label: system.name, kind: "system" },
      });
      for (const container of asArray(system.containers)) {
        nodes.push({
          data: { id: container.id, label: container.name, kind: "container" },
        });
        edges.push({
          data: {
            id: `parent-${system.id}-${container.id}`,
            source: system.id,
            target: container.id,
            label: "",
          },
        });
        for (const component of asArray(container.components)) {
          nodes.push({
            data: {
              id: component.id,
              label: component.name,
              kind: "component",
            },
          });
          edges.push({
            data: {
              id: `parent-${container.id}-${component.id}`,
              source: container.id,
              target: component.id,
              label: "",
            },
          });
        }
      }
    }

    for (const relationship of asArray(model.relationships)) {
      edges.push({
        data: {
          id: `rel-${relationship.id}`,
          source: relationship.sourceId,
          target: relationship.destinationId,
          label: relationship.description ?? "",
        },
      });
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...nodes, ...edges],
      style: [
        {
          selector: 'node[kind="system"]',
          style: {
            "background-color": "#facc15",
            color: "#0f172a",
            label: "data(label)",
            "font-size": 12,
            "font-weight": 600,
            shape: "round-rectangle",
            width: 120,
            height: 42,
            "text-valign": "center",
            "text-halign": "center",
          },
        },
        {
          selector: 'node[kind="container"]',
          style: {
            "background-color": "#38bdf8",
            color: "#0f172a",
            label: "data(label)",
            "font-size": 11,
            shape: "round-rectangle",
            width: 110,
            height: 36,
            "text-valign": "center",
          },
        },
        {
          selector: 'node[kind="component"]',
          style: {
            "background-color": "#a78bfa",
            color: "#0f172a",
            label: "data(label)",
            "font-size": 10,
            shape: "ellipse",
            width: 80,
            height: 34,
            "text-valign": "center",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.2,
            "line-color": "#64748b",
            "target-arrow-color": "#64748b",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "font-size": 9,
            color: "#94a3b8",
            label: "data(label)",
            "text-background-color": "#0f172a",
            "text-background-opacity": 0.8,
            "text-background-padding": "2px",
          },
        },
      ],
      layout: { name: "cose", animate: false, padding: 40 },
      wheelSensitivity: 0.2,
    });

    cy.on("tap", "node", (event) => {
      setSelected(String(event.target.data("label")));
    });

    return () => {
      cy.destroy();
    };
  }, [workspace]);

  useEffect(() => {
    if (!selected) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const elements = await api.graphElements(runId);
        const match = elements.find((item) => item.name === selected);
        if (!match) {
          setDependencies([]);
          return;
        }
        const deps = await api.dependencies(runId, match.id);
        if (!cancelled) {
          setDependencies(deps);
          setError(null);
        }
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : String(cause));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selected, runId]);

  return (
    <div className="graph-layout">
      <div ref={containerRef} className="graph-canvas" />
      <aside className="graph-side">
        <h3>Зависимости</h3>
        {!selected && <p className="muted">Кликните по узлу графа.</p>}
        {selected && <p className="muted">Элемент: {selected}</p>}
        {error && <p className="error">{error}</p>}
        {selected && !error && dependencies.length === 0 && (
          <p className="muted">Нет исходящих зависимостей.</p>
        )}
        {dependencies.length > 0 && (
          <ul className="deps">
            {dependencies.map((dependency) => (
              <li key={dependency.id}>
                <span className={`dot dot-${dependency.type}`} />
                {dependency.name}
                <span className="muted"> · шаг {dependency.distance}</span>
              </li>
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}
