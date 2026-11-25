function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function label(value: unknown): string {
  if (value === null) {
    return "null";
  }
  if (typeof value === "string") {
    return value;
  }
  return String(value);
}

function TreeNode({
  name,
  value,
  depth,
}: {
  name: string;
  value: unknown;
  depth: number;
}) {
  const isArray = Array.isArray(value);
  const isObject = isRecord(value);

  if (isArray || isObject) {
    const entries = isArray
      ? value.map((item, index) => [String(index), item] as const)
      : Object.entries(value);
    return (
      <details className="tree-node" open={depth === 0}>
        <summary>
          <span className="tree-key">{name}</span>
          <span className="tree-count">
            {isArray ? `[${entries.length}]` : `{${entries.length}}`}
          </span>
        </summary>
        <div className="tree-children">
          {entries.map(([key, child]) => (
            <TreeNode
              key={key}
              name={key}
              value={child}
              depth={depth + 1}
            />
          ))}
        </div>
      </details>
    );
  }

  return (
    <div className="tree-leaf">
      <span className="tree-key">{name}</span>
      <span className="tree-value">{label(value)}</span>
    </div>
  );
}

export function ReportTree({ report }: { report: unknown }) {
  return (
    <div className="json-tree">
      <TreeNode name="report" value={report} depth={0} />
    </div>
  );
}
