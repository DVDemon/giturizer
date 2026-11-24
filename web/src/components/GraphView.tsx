import cytoscape from "cytoscape";
import { MultiGraph } from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
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

function protocolColor(protocol: string): string {
  const value = protocol.toLowerCase();
  if (value.includes("postgres") || value.includes("mongo") || value.includes("sql")) {
    return "#00c2ab";
  }
  if (value.includes("resp") || value.includes("redis") || value.includes("valkey")) {
    return "#1e8e4e";
  }
  if (value.includes("grpc")) {
    return "#6432c8";
  }
  if (value.includes("graphql")) {
    return "#ec008c";
  }
  if (value.includes("http")) {
    return "#538efb";
  }
  if (value.includes("include")) {
    return "#8a8f96";
  }
  return "#4e535b";
}

interface EdgeDetails {
  detail: string;
  color: string;
  style: string;
}

function relationDetails(properties: Record<string, unknown>): EdgeDetails {
  const protocol = String(properties.protocol ?? "");
  const transport = String(properties.transport ?? "");
  const port = String(properties.port ?? "");
  if (!protocol) {
    return { detail: "", color: "#d8dce3", style: "solid" };
  }
  if (protocol === "include") {
    return { detail: "include", color: "#8a8f96", style: "dashed" };
  }
  const transportLabel = transport ? `${transport}${port ? `:${port}` : ""}` : "";
  return {
    detail: [protocol, transportLabel].filter(Boolean).join(" · "),
    color: protocolColor(protocol),
    style: "solid",
  };
}

function nodeSize(kind: string): number {
  return kind === "system" ? 60 : kind === "container" ? 45 : 30;
}

function forceSettings(order: number) {
  const inferred = forceAtlas2.inferSettings(order);
  return {
    ...inferred,
    barnesHutOptimize: true,
    barnesHutTheta: 0.8,
    adjustSizes: true,
    scalingRatio: 12,
    gravity: 0.6,
    strongGravityMode: false,
    linLogMode: true,
    outboundAttractionDistribution: true,
    edgeWeightInfluence: 0.7,
    slowDown: 2,
  };
}

export function GraphView({ runId, workspace }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [dependencies, setDependencies] = useState<Dependency[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [layoutRun, setLayoutRun] = useState(0);

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
        grabbable: true,
      });
      for (const container of asArray(system.containers)) {
        nodes.push({
          data: { id: container.id, label: container.name, kind: "container" },
          grabbable: true,
        });
        edges.push({
          data: {
            id: `parent-${system.id}-${container.id}`,
            source: system.id,
            target: container.id,
            label: "",
            color: "#d8dce3",
          },
          classes: "parent",
        });
        for (const component of asArray(container.components)) {
          nodes.push({
            data: {
              id: component.id,
              label: component.name,
              kind: "component",
            },
            grabbable: true,
          });
          edges.push({
            data: {
              id: `parent-${container.id}-${component.id}`,
              source: container.id,
              target: component.id,
              label: "",
              color: "#d8dce3",
            },
            classes: "parent",
          });
        }
      }
    }

    for (const relationship of asArray(model.relationships)) {
      const properties = (relationship.properties ?? {}) as Record<string, unknown>;
      const { detail, color } = relationDetails(properties);
      const description = String(relationship.description ?? "");
      const isInclude = String(properties.protocol ?? "") === "include";
      edges.push({
        data: {
          id: `rel-${relationship.id}`,
          source: relationship.sourceId,
          target: relationship.destinationId,
          label: detail ? `${description}\n${detail}` : description,
          color,
        },
        classes: isInclude ? "include" : "network",
      });
    }

    const layoutGraph = new MultiGraph();
    const uniqueNodes = [
      ...new Map(nodes.map((node) => [String(node.data.id), node])).values(),
    ];
    uniqueNodes.sort((left, right) => {
      const kindOrder = (kind: unknown) =>
        kind === "system" ? 0 : kind === "container" ? 1 : 2;
      const byKind = kindOrder(left.data.kind) - kindOrder(right.data.kind);
      return byKind || String(left.data.label).localeCompare(String(right.data.label));
    });
    uniqueNodes.forEach((node, index) => {
      const kind = String(node.data.kind ?? "");
      const angle = index * 2.399963229728653 + layoutRun * 0.37;
      const radius = 120 + Math.sqrt(index + 1) * 45;
      layoutGraph.addNode(String(node.data.id), {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        size: nodeSize(kind),
      });
    });
    for (const edge of edges) {
      const source = String(edge.data.source ?? "");
      const target = String(edge.data.target ?? "");
      if (!layoutGraph.hasNode(source) || !layoutGraph.hasNode(target)) {
        continue;
      }
      layoutGraph.addEdgeWithKey(String(edge.data.id), source, target, {
        weight: edge.classes?.includes("parent") ? 0.7 : 1,
      });
    }
    if (layoutGraph.order > 1) {
      forceAtlas2.assign(layoutGraph, {
        iterations: Math.min(1000, Math.max(300, layoutGraph.order * 8)),
        settings: forceSettings(layoutGraph.order),

      });
    }
    const positions: Record<string, { x: number; y: number }> = {};
    layoutGraph.forEachNode((node, attributes) => {
      positions[node] = {
        x: Number(attributes.x) || 0,
        y: Number(attributes.y) || 0,
      };
    });

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...nodes, ...edges],
      style: [
        {
          selector: 'node[kind="system"]',
          style: {
            "background-color": "#ffc800",
            "border-color": "#000000",
            "border-width": 2,
            color: "#141414",
            label: "data(label)",
            "font-size": 13,
            "font-weight": 500,
            "font-family": "Beeline Sans, Golos Text, sans-serif",
            shape: "round-rectangle",
            width: 150,
            height: 50,
            "text-valign": "center",
            "text-halign": "center",
          },
        },
        {
          selector: 'node[kind="container"]',
          style: {
            "background-color": "#538efb",
            "border-color": "#0d63b3",
            "border-width": 1,
            color: "#ffffff",
            label: "data(label)",
            "font-size": 12,
            "font-weight": 500,
            "font-family": "Beeline Sans, Golos Text, sans-serif",
            shape: "round-rectangle",
            width: 132,
            height: 42,
            "text-valign": "center",
          },
        },
        {
          selector: 'node[kind="component"]',
          style: {
            "background-color": "#6432c8",
            "border-color": "#45326f",
            "border-width": 1,
            color: "#ffffff",
            label: "data(label)",
            "font-size": 11,
            "font-family": "Beeline Sans, Golos Text, sans-serif",
            shape: "ellipse",
            width: 100,
            height: 38,
            "text-valign": "center",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.4,
            "line-color": "data(color)",
            "target-arrow-color": "data(color)",
            "target-arrow-shape": "triangle",
            "line-style": "solid",
            "curve-style": "bezier",
            "font-size": 10,
            color: "#4e535b",
            "font-family": "Beeline Sans, Golos Text, sans-serif",
            label: "data(label)",
            "text-wrap": "wrap",
            "text-max-width": "170px",
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.95,
            "text-background-padding": "2px",
          },
        },
        {
          selector: "edge.parent",
          style: {
            width: 1,
            "target-arrow-shape": "none",
            "line-style": "solid",
          },
        },
        {
          selector: "edge.include",
          style: {
            "line-style": "dashed",
          },
        },
      ],
      layout: {
        name: "preset",
        positions,
        fit: true,
        padding: 40,
        animate: false,
      },
      wheelSensitivity: 0.2,
      autoungrabify: false,
      autounselectify: false,
    });

    cyRef.current = cy;

    const relayoutAround = (nodeId: string) => {
      const root = cy.getElementById(nodeId);
      if (root.empty()) {
        return;
      }
      const neighbourhood = root
        .closedNeighborhood()
        .nodes()
        .union(root.neighborhood().nodes().neighborhood().nodes());
      const graph = new MultiGraph();
      neighbourhood.forEach((node) => {
        const position = node.position();
        graph.addNode(node.id(), {
          x: position.x,
          y: position.y,
          size: nodeSize(String(node.data("kind") ?? "")),
          fixed: node.id() === nodeId,
        });
      });
      if (graph.order < 2) {
        return;
      }
      cy.edges().forEach((edge) => {
        const source = edge.source().id();
        const target = edge.target().id();
        if (graph.hasNode(source) && graph.hasNode(target)) {
          graph.addEdgeWithKey(edge.id(), source, target, {
            weight: edge.hasClass("parent") ? 0.7 : 1,
          });
        }
      });
      forceAtlas2.assign(graph, {
        iterations: 120,
        settings: forceSettings(graph.order),
      });
      graph.forEachNode((node, attributes) => {
        if (node === nodeId) {
          return;
        }
        const target = cy.getElementById(node);
        if (!target.empty()) {
          target.animate(
            {
              position: {
                x: Number(attributes.x) || 0,
                y: Number(attributes.y) || 0,
              },
            },
            { duration: 300 },
          );
        }
      });
    };

    cy.on("dragfree", "node", (event) => {
      relayoutAround(String(event.target.id()));
    });

    cy.ready(() => {
      cy.fit(undefined, 60);
      if (cy.zoom() > 1.4) {
        cy.zoom(1.4);
        cy.center();
      }
    });

    cy.on("tap", "node", (event) => {
      setSelected(String(event.target.data("label")));
    });

    return () => {
      cyRef.current = null;
      cy.destroy();
    };
  }, [workspace, layoutRun]);

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
      <div className="graph-main">
        <div className="graph-toolbar">
          <span className="graph-layout-badge">ForceAtlas2</span>
          <button
            className="button ghost small"
            onClick={() => cyRef.current?.fit(undefined, 60)}
          >
            Вписать
          </button>
          <button
            className="button ghost small"
            onClick={() => setLayoutRun((value) => value + 1)}
          >
            Пересчитать
          </button>
        </div>
        <p className="graph-hint muted">
          Перетаскивайте узлы: связанные пересчитываются после отпускания · колесо — масштаб
        </p>
        <div ref={containerRef} className="graph-canvas" />
      </div>
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
                {dependency.protocol ? (
                  <span className="muted">
                    {" · "}
                    {dependency.protocol}
                    {dependency.transport ? `/${dependency.transport}` : ""}
                    {dependency.port ? `:${dependency.port}` : ""}
                  </span>
                ) : null}
                <span className="muted"> · шаг {dependency.distance}</span>
              </li>
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}
