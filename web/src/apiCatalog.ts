import type { ApiSpec } from "./types";

const HTTP_METHODS = ["get", "post", "put", "delete", "patch", "head", "options"];

export interface CatalogParameter {
  name: string;
  location: string;
  required: boolean;
  description: string;
  schema: unknown;
}

export interface CatalogResponse {
  status: string;
  description: string;
  content: unknown;
}

export interface CatalogOperation {
  id: string;
  specIndex: number;
  kind: string;
  service: string;
  source: string;
  framework?: string;
  method: string;
  path: string;
  summary: string;
  description: string;
  operationId: string;
  tags: string[];
  parameters: CatalogParameter[];
  requestBody: unknown;
  responses: CatalogResponse[];
  request?: string;
  response?: string;
  fields?: string[];
}

export interface ApiCatalog {
  operations: CatalogOperation[];
  services: string[];
  kinds: string[];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export function serviceFromSource(source: string): string {
  const match = source.match(/services\/([^/]+)/);
  if (match) {
    return match[1];
  }
  const parts = source.split("/").filter(Boolean);
  return parts.length > 1 ? parts[parts.length - 2] : "other";
}

export function kindLabel(kind: string): string {
  return {
    openapi: "OpenAPI",
    annotations: "Annotations",
    grpc: "gRPC",
    graphql: "GraphQL",
  }[kind] ?? kind;
}

function normalizeParameters(value: unknown): CatalogParameter[] {
  return asArray(value).flatMap((raw) => {
    const item = asRecord(raw);
    if (!item || typeof item.name !== "string") {
      return [];
    }
    return [
      {
        name: item.name,
        location: String(item.in ?? ""),
        required: Boolean(item.required),
        description: String(item.description ?? ""),
        schema: item.schema ?? null,
      },
    ];
  });
}

function normalizeResponses(value: unknown): CatalogResponse[] {
  const responses = asRecord(value);
  if (!responses) {
    return [];
  }
  return Object.entries(responses).map(([status, raw]) => {
    const item = asRecord(raw);
    return {
      status,
      description: String(item?.description ?? ""),
      content: item?.content ?? null,
    };
  });
}

export function buildCatalog(specs: ApiSpec[]): ApiCatalog {
  const operations: CatalogOperation[] = [];

  specs.forEach((spec, specIndex) => {
    const raw = asRecord(spec.spec) ?? {};
    const base = {
      specIndex,
      kind: spec.kind,
      source: spec.name,
    };

    if (spec.kind === "openapi") {
      const paths = asRecord(raw.paths) ?? {};
      for (const [path, rawItem] of Object.entries(paths)) {
        const pathItem = asRecord(rawItem);
        if (!pathItem) {
          continue;
        }
        for (const method of HTTP_METHODS) {
          const operation = asRecord(pathItem[method]);
          if (!operation) {
            continue;
          }
          const tags = asArray(operation.tags)
            .filter((tag): tag is string => typeof tag === "string")
            .slice(0, 10);
          operations.push({
            ...base,
            id: `${specIndex}:${method.toUpperCase()}:${path}`,
            service: tags[0] ?? serviceFromSource(spec.name),
            method: method.toUpperCase(),
            path,
            summary: String(operation.summary ?? ""),
            description: String(operation.description ?? ""),
            operationId: String(operation.operationId ?? ""),
            tags,
            parameters: normalizeParameters([
              ...asArray(pathItem.parameters),
              ...asArray(operation.parameters),
            ]),
            requestBody: operation.requestBody ?? null,
            responses: normalizeResponses(operation.responses),
          });
        }
      }
    } else if (spec.kind === "annotations") {
      const service = String(raw.service || serviceFromSource(spec.name));
      const source = String(raw.file ?? spec.name);
      const framework = raw.framework ? String(raw.framework) : undefined;
      for (const endpoint of asArray(raw.endpoints)) {
        const item = asRecord(endpoint);
        if (!item || typeof item.path !== "string") {
          continue;
        }
        const method = String(item.method ?? "GET").toUpperCase();
        operations.push({
          ...base,
          source,
          framework,
          id: `${specIndex}:${method}:${item.path}`,
          service,
          method,
          path: item.path,
          summary: "",
          description: "",
          operationId: "",
          tags: [],
          parameters: [],
          requestBody: null,
          responses: [],
        });
      }
    } else if (spec.kind === "grpc") {
      for (const rawService of asArray(raw.services)) {
        const service = asRecord(rawService);
        if (!service || typeof service.name !== "string") {
          continue;
        }
        for (const rawRpc of asArray(service.rpcs)) {
          const rpc = asRecord(rawRpc);
          if (!rpc || typeof rpc.name !== "string") {
            continue;
          }
          operations.push({
            ...base,
            id: `${specIndex}:RPC:${service.name}/${rpc.name}`,
            service: service.name,
            method: "RPC",
            path: `${service.name}/${rpc.name}`,
            summary: rpc.name,
            description: "",
            operationId: rpc.name,
            tags: [],
            parameters: [],
            requestBody: null,
            responses: [],
            request: rpc.request ? String(rpc.request) : undefined,
            response: rpc.response ? String(rpc.response) : undefined,
          });
        }
      }
    } else if (spec.kind === "graphql") {
      for (const rawOperation of asArray(raw.operations)) {
        const operation = asRecord(rawOperation);
        if (!operation || typeof operation.operation !== "string") {
          continue;
        }
        const fields = asArray(operation.fields)
          .filter((field): field is string => typeof field === "string");
        operations.push({
          ...base,
          id: `${specIndex}:GRAPHQL:${operation.operation}`,
          service: serviceFromSource(spec.name),
          method: "GRAPHQL",
          path: operation.operation,
          summary: fields.join(", "),
          description: "",
          operationId: operation.operation,
          tags: [],
          parameters: [],
          requestBody: null,
          responses: [],
          fields,
        });
      }
    }
  });

  operations.sort(
    (left, right) =>
      left.service.localeCompare(right.service, "ru") ||
      left.path.localeCompare(right.path, "ru", { numeric: true }) ||
      left.method.localeCompare(right.method),
  );

  return {
    operations,
    services: [...new Set(operations.map((item) => item.service))].sort((a, b) =>
      a.localeCompare(b, "ru"),
    ),
    kinds: [...new Set(operations.map((item) => item.kind))].sort(),
  };
}
