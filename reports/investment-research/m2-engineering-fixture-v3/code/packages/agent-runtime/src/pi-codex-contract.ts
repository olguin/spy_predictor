export interface PiAdapterRequest {
  role: string;
  input_hash: string;
  instructions: string;
  packet: Record<string, unknown>;
  prior_results: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  runtime: {
    model: string;
    max_output_tokens: number;
    tools: unknown[];
    attempts: number;
    reasoning_effort?: string;
    transport?: "sse" | "websocket" | "websocket-cached" | "auto";
  };
}

export interface PiUsageReceipt {
  runtime: "pi-coding-agent";
  pi_version: string;
  provider: "openai-codex";
  requested_model: string;
  response_model: string;
  thinking_level: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  reasoning_tokens: number | null;
  cache_read_tokens: number;
  cache_write_tokens: number;
  total_tokens: number;
  catalog_cost_estimate_usd: number;
  stop_reason: string;
  requested_transport: string;
  requested_max_output_tokens: number;
  provider_output_token_limit_enforced: false;
  numeric_enum_transport: "exact_decimal_strings_v1";
}

export function requireAdapterRequest(value: unknown): PiAdapterRequest {
  if (!isRecord(value)) {
    throw new Error("Adapter request must be a JSON object");
  }
  for (const key of ["packet", "prior_results", "output_schema", "runtime"] as const) {
    if (!isRecord(value[key])) {
      throw new Error(`Adapter request.${key} must be an object`);
    }
  }
  for (const key of ["role", "input_hash", "instructions"] as const) {
    if (typeof value[key] !== "string" || value[key].length === 0) {
      throw new Error(`Adapter request.${key} must be a nonempty string`);
    }
  }
  const runtime = value.runtime;
  if (!isRecord(runtime)) {
    throw new Error("Adapter request.runtime must be an object");
  }
  if (typeof runtime.model !== "string" || runtime.model.length === 0) {
    throw new Error("Adapter request.runtime.model must be a nonempty string");
  }
  if (!Number.isInteger(runtime.max_output_tokens) ||
      (runtime.max_output_tokens as number) < 1 ||
      (runtime.max_output_tokens as number) > 20_000) {
    throw new Error("Adapter request.runtime.max_output_tokens must be an integer from 1 to 20000");
  }
  if (!Array.isArray(runtime.tools) || runtime.tools.length !== 0) {
    throw new Error("Pi Codex research stages require runtime.tools=[]");
  }
  if (runtime.attempts !== 1) {
    throw new Error("Pi Codex research stages require runtime.attempts=1");
  }
  if (runtime.reasoning_effort !== undefined &&
      !["minimal", "low", "medium", "high", "xhigh", "max"].includes(String(runtime.reasoning_effort))) {
    throw new Error("Unsupported runtime.reasoning_effort");
  }
  if (runtime.transport !== undefined && !["sse", "websocket", "websocket-cached", "auto"].includes(String(runtime.transport))) {
    throw new Error("Unsupported runtime.transport");
  }
  return value as unknown as PiAdapterRequest;
}

export function parseCodexModel(value: string): string {
  const trimmed = value.trim();
  const slash = trimmed.indexOf("/");
  if (slash === -1) return trimmed;
  const provider = trimmed.slice(0, slash);
  const model = trimmed.slice(slash + 1);
  if (provider !== "openai-codex" || model.length === 0) {
    throw new Error("Model must belong to the openai-codex provider");
  }
  return model;
}

export function canonicalCodexModel(value: string): string {
  return `openai-codex/${parseCodexModel(value)}`;
}

export function constrainedSamplingSchema(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(constrainedSamplingSchema);
  if (!isRecord(value)) return value;
  const unsupported = new Set([
    "allOf", "uniqueItems", "pattern", "format", "minLength", "maxLength",
    "minItems", "maxItems", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"
  ]);
  const normalized = Object.fromEntries(Object.entries(value)
    .filter(([key]) => !unsupported.has(key))
    .map(([key, child]) => {
      // Pi rejects boolean *schemas*. Preserve ordinary boolean keywords and
      // enum/const values. Sampling may propose null in an impossible position;
      // the unchanged Python schema rejects it. Empty arrays remain representable.
      if (key === "items" && typeof child === "boolean") {
        return [key, { type: "null" }];
      }
      if ((key === "properties" || key === "$defs" || key === "definitions") && isRecord(child)) {
        return [key, Object.fromEntries(Object.entries(child).map(([name, schema]) =>
          [name, typeof schema === "boolean" ? { type: "null" } : constrainedSamplingSchema(schema)]))];
      }
      if (key === "const" || key === "enum" || key === "default" || key === "examples") {
        return [key, child];
      }
      return [key, constrainedSamplingSchema(child)];
    }));
  if (!("type" in normalized)) {
    const candidates = "const" in normalized
      ? [normalized.const]
      : Array.isArray(normalized.enum) ? normalized.enum : [];
    const types = new Set(candidates.map((candidate) =>
      candidate === null ? "null" :
        typeof candidate === "number" && Number.isInteger(candidate) ? "integer" :
          typeof candidate));
    if (types.size === 1 && ["string", "number", "integer", "boolean", "null"].includes([...types][0] ?? "")) {
      normalized.type = [...types][0];
    }
  }
  return normalized;
}

function decimalEnum(schema: Record<string, unknown>): number[] | undefined {
  const values = schema.enum;
  return Array.isArray(values) && values.length > 0
    && values.every((value) => typeof value === "number" && Number.isFinite(value))
    && values.some((value) => !Number.isInteger(value)) ? values as number[] : undefined;
}

/** Decimal enum literals travel as exact strings; Python still receives v4 numbers. */
export function resultToolSchema(schema: Record<string, unknown>): Record<string, unknown> {
  function project(value: unknown): unknown {
    if (Array.isArray(value)) return value.map(project);
    if (!isRecord(value)) return value;
    const values = decimalEnum(value);
    if (values) return { ...value, type: "string", enum: values.map(String) };
    return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, project(child)]));
  }
  return project(constrainedSamplingSchema(schema)) as Record<string, unknown>;
}

export interface NumericEnumRestoration { path: string; submitted: string; frozen_value: number }

export function restoreNumericEnums(result: unknown, schema: Record<string, unknown>): {
  result: Record<string, unknown>; restorations: NumericEnumRestoration[]
} {
  const restorations: NumericEnumRestoration[] = [];
  function restore(value: unknown, shape: unknown, path: string): unknown {
    if (!isRecord(shape)) return value;
    const values = decimalEnum(shape);
    if (values) {
      // No float parsing, epsilon, nearest-value search, or probability recomputation.
      const index = typeof value === "string" ? values.findIndex((number) => String(number) === value) : -1;
      if (index < 0) throw new Error("Decimal enum must exactly match a frozen transport string");
      const frozen = values[index]!;
      restorations.push({ path, submitted: value as string, frozen_value: frozen });
      return frozen;
    }
    if (Array.isArray(value)) return value.map((child, i) => restore(child, shape.items, `${path}/${i}`));
    if (isRecord(value) && isRecord(shape.properties)) {
      const properties = shape.properties;
      return Object.fromEntries(Object.entries(value).map(([key, child]) =>
        [key, restore(child, properties[key], `${path}/${key.replace(/~/g, "~0").replace(/\//g, "~1")}`)]));
    }
    return value;
  }
  const restored = restore(result, schema, "");
  if (!isRecord(restored)) throw new Error("Result must be an object");
  return { result: restored, restorations };
}

export function parseExactJsonObject(text: string): Record<string, unknown> {
  const trimmed = text.trim();
  if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) {
    throw new Error("Model response must contain only one JSON object");
  }
  const value: unknown = JSON.parse(trimmed);
  if (!isRecord(value)) {
    throw new Error("Model response must be a JSON object");
  }
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
