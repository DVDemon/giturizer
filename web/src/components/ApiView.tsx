import { RedocStandalone } from "redoc";
import { useState } from "react";

import type { ApiSpec } from "../types";

function asArray(value: unknown): any[] {
  return Array.isArray(value) ? value : [];
}

export function ApiView({ specs }: { specs: ApiSpec[] }) {
  const [active, setActive] = useState(0);

  if (specs.length === 0) {
    return <p className="muted">API-контракты не найдены.</p>;
  }
  const spec = specs[Math.min(active, specs.length - 1)];

  return (
    <div>
      <div className="tabs-inline">
        {specs.map((item, index) => (
          <button
            key={`${item.kind}-${item.name}`}
            className={index === active ? "chip active" : "chip"}
            onClick={() => setActive(index)}
          >
            {item.kind}: {item.name}
          </button>
        ))}
      </div>
      {spec.kind === "openapi" ? (
        <div className="redoc-wrap">
          <RedocStandalone
            spec={spec.spec}
            options={{
              hideDownloadButton: true,
              disableSearch: true,
              nativeScrollbars: true,
              theme: { colors: { primary: { main: "#facc15" } } },
            }}
          />
        </div>
      ) : (
        <SpecTable spec={spec} />
      )}
    </div>
  );
}

function SpecTable({ spec }: { spec: ApiSpec }) {
  if (spec.kind === "grpc") {
    const services = asArray(spec.spec.services);
    return (
      <table className="table">
        <thead>
          <tr>
            <th>Сервис</th>
            <th>RPC</th>
            <th>Запрос</th>
            <th>Ответ</th>
          </tr>
        </thead>
        <tbody>
          {services.flatMap((service) =>
            asArray(service.rpcs).map((rpc) => (
              <tr key={`${service.name}-${rpc.name}`}>
                <td>{service.name}</td>
                <td>{rpc.name}</td>
                <td>{rpc.request}</td>
                <td>{rpc.response}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    );
  }

  if (spec.kind === "graphql") {
    const types = asArray(spec.spec.types);
    const operations = asArray(spec.spec.operations);
    return (
      <div className="grid-2">
        <div>
          <h3>Типы</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Вид</th>
                <th>Имя</th>
              </tr>
            </thead>
            <tbody>
              {types.map((type) => (
                <tr key={`${type.kind}-${type.name}`}>
                  <td>{type.kind}</td>
                  <td>{type.name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h3>Операции</h3>
          <ul className="list">
            {operations.map((operation) => (
              <li key={operation.operation}>
                <strong>{operation.operation}</strong>: {asArray(operation.fields).join(", ")}
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  if (spec.kind === "annotations") {
    const endpoints = asArray(spec.spec.endpoints);
    return (
      <table className="table">
        <thead>
          <tr>
            <th>Метод</th>
            <th>Путь</th>
          </tr>
        </thead>
        <tbody>
          {endpoints.map((endpoint, index) => (
            <tr key={`${endpoint.method}-${endpoint.path}-${index}`}>
              <td>{endpoint.method}</td>
              <td>{endpoint.path}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  return <pre className="raw">{JSON.stringify(spec.spec, null, 2)}</pre>;
}
