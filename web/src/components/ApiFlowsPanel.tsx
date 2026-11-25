import type { ApiFlow } from "../types";

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function basename(path: string): string {
  return path.split("/").pop() ?? path;
}

export function ApiFlowsPanel({ flows }: { flows: ApiFlow[] }) {
  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>API-потоки</h2>
            <p className="muted">
              Входная операция → цепочка вызовов → внешний HTTP-клиент. Это
              кандидаты P2: внешняя операция и URL будут уточнены в P3.
            </p>
          </div>
          <span className="badge">{flows.length}</span>
        </div>
        <div className="table-wrap">
          <table className="table flow-table">
            <thead>
              <tr>
                <th>Входная операция</th>
                <th>Цепочка вызовов</th>
                <th>Внешний вызов</th>
                <th>URL</th>
                <th>Confidence</th>
                <th>Источник</th>
              </tr>
            </thead>
            <tbody>
              {flows.map((flow, index) => (
                <tr key={`${flow.input.operation}-${flow.output.file}-${flow.output.line}-${index}`}>
                  <td>
                    <strong>{flow.input.operation}</strong>
                    <div className="flow-meta">
                      {flow.input.handler.symbol}
                      <br />
                      <span title={flow.input.handler.file}>
                        {basename(flow.input.handler.file)}:{flow.input.handler.line}
                      </span>
                    </div>
                  </td>
                  <td>
                    <div className="flow-path">
                      {(flow.path.length > 0
                        ? flow.path.map((step) => step.symbol)
                        : [flow.input.handler.symbol]
                      ).join(" → ")}
                    </div>
                    <div className="flow-meta">
                      {flow.path.map((step) => (
                        <div key={`${step.file}:${step.line}`} title={step.file}>
                          {basename(step.file)}:{step.line}
                        </div>
                      ))}
                    </div>
                  </td>
                  <td>
                    <code>{flow.output.callee}</code>
                    <div className="flow-meta">{flow.output.kind}</div>
                  </td>
                  <td>
                    {flow.output.urls.length > 0 ? (
                      flow.output.urls.map((url) => <div key={url} className="flow-url">{url}</div>)
                    ) : (
                      <span className="muted">URL не разрешён</span>
                    )}
                  </td>
                  <td>
                    {percent(flow.confidence)}
                    <div className="flow-meta">{flow.status}</div>
                  </td>
                  <td>
                    <span title={flow.output.file}>
                      {basename(flow.output.file)}:{flow.output.line}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
