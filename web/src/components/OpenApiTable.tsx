const METHODS = ["get", "post", "put", "delete", "patch", "head", "options"];

export function OpenApiTable({ spec }: { spec: Record<string, unknown> }) {
  const paths = (spec.paths ?? {}) as Record<string, Record<string, unknown>>;
  const rows: Array<[string, string, string]> = [];

  for (const [path, operations] of Object.entries(paths)) {
    if (!operations || typeof operations !== "object") {
      continue;
    }
    for (const method of METHODS) {
      const operation = operations[method] as Record<string, unknown> | undefined;
      if (!operation) {
        continue;
      }
      rows.push([
        method.toUpperCase(),
        path,
        String(operation.summary ?? operation.operationId ?? ""),
      ]);
    }
  }

  if (rows.length === 0) {
    return <p className="muted">В спецификации нет операций.</p>;
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Метод</th>
          <th>Путь</th>
          <th>Описание</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([method, path, summary]) => (
          <tr key={`${method}-${path}`}>
            <td>{method}</td>
            <td className="mono">{path}</td>
            <td className="muted">{summary}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
