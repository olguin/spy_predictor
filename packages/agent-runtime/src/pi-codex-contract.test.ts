import { describe, expect, it } from "vitest";
import {
  canonicalCodexModel,
  constrainedSamplingSchema,
  resultToolSchema,
  restoreNumericEnums,
  parseCodexModel,
  parseExactJsonObject,
  requireAdapterRequest
} from "./pi-codex-contract";

function request() {
  return {
    role: "technical",
    input_hash: "abc",
    instructions: "Use only the packet",
    packet: {},
    prior_results: {},
    output_schema: {},
    runtime: {
      model: "openai-codex/gpt-5.6-terra",
      max_output_tokens: 5000,
      tools: [],
      attempts: 1,
      reasoning_effort: "medium"
    }
  };
}

describe("Pi Codex adapter contract", () => {
  it("accepts a bounded, tool-free request", () => {
    expect(requireAdapterRequest(request()).runtime.model).toBe("openai-codex/gpt-5.6-terra");
  });

  it("rejects tools, retries, and excessive output", () => {
    expect(() => requireAdapterRequest({ ...request(), runtime: { ...request().runtime, tools: ["read"] } })).toThrow(/tools/);
    expect(() => requireAdapterRequest({ ...request(), runtime: { ...request().runtime, attempts: 2 } })).toThrow(/attempts/);
    expect(() => requireAdapterRequest({ ...request(), runtime: { ...request().runtime, max_output_tokens: 20_001 } })).toThrow(/max_output/);
    expect(requireAdapterRequest({ ...request(), runtime: { ...request().runtime, transport: "sse" } }).runtime.transport).toBe("sse");
    expect(() => requireAdapterRequest({ ...request(), runtime: { ...request().runtime, transport: "unbounded-retry" } })).toThrow(/transport/);
  });

  it("only permits the Codex provider and exact JSON output", () => {
    expect(parseCodexModel("openai-codex/gpt-5.6-sol")).toBe("gpt-5.6-sol");
    expect(canonicalCodexModel("gpt-5.6-sol")).toBe("openai-codex/gpt-5.6-sol");
    expect(canonicalCodexModel("openai-codex/gpt-5.6-sol")).toBe("openai-codex/gpt-5.6-sol");
    expect(() => parseCodexModel("openai/gpt-5.6-sol")).toThrow(/openai-codex/);
    expect(parseExactJsonObject('{"ok":true}')).toEqual({ ok: true });
    expect(() => parseExactJsonObject('```json\n{"ok":true}\n```')).toThrow(/only one JSON/);
  });

  it("removes unsupported allOf only from the provider sampling schema", () => {
    const source = {
      type: "object",
      properties: {
        row: { type: "object", allOf: [{ if: {} }] },
        role: { const: "technical", pattern: "^technical$" },
        ids: { type: "array", uniqueItems: true, minItems: 1, items: { type: "string" } }
      },
      allOf: []
    };
    expect(constrainedSamplingSchema(source)).toEqual({
      type: "object", properties: {
        row: { type: "object" }, role: { const: "technical", type: "string" },
        ids: { type: "array", items: { type: "string" } }
      }
    });
    expect(source).toHaveProperty("allOf");
  });

  it("can sample empty evidence arrays without changing boolean data or the final schema", () => {
    const source = { type: "object", additionalProperties: false, properties: {
      evidence: { type: "array", items: false },
      unavailable: false,
      flag: { const: false },
      choices: { type: "boolean", enum: [true, false] }
    }};
    expect(constrainedSamplingSchema(source)).toEqual({
      type: "object", additionalProperties: false, properties: {
        evidence: { type: "array", items: { type: "null" } },
        unavailable: { type: "null" },
        flag: { const: false, type: "boolean" },
        choices: { type: "boolean", enum: [true, false] }
      }
    });
    expect(source.properties.evidence.items).toBe(false);
    expect(source.properties.unavailable).toBe(false);
  });

  it("round-trips exact decimal enum strings without relaxing the numerical contract", () => {
    const frozen = 0.48819133259310843;
    const schema = { type: "object", properties: { rows: { type: "array", items: {
      type: "object", properties: { probability: { enum: [frozen, 0.44889345827485483] },
        days: { enum: [5, 21, 63] } } } } } };
    const original = structuredClone(schema);
    const projected = resultToolSchema(schema) as any;
    expect(projected.properties.rows.items.properties.probability).toEqual({ type: "string",
      enum: ["0.48819133259310843", "0.44889345827485483"] });
    expect(projected.properties.rows.items.properties.days.enum).toEqual([5, 21, 63]);
    const transport = { rows: [{ probability: "0.48819133259310843", days: 5 }] };
    const restored = restoreNumericEnums(transport, schema);
    expect(restored.result).toEqual({ rows: [{ probability: frozen, days: 5 }] });
    expect(restored.restorations).toEqual([{ path: "/rows/0/probability",
      submitted: "0.48819133259310843", frozen_value: frozen }]);
    expect(transport.rows[0]!.probability).toBe("0.48819133259310843");
    expect(schema).toEqual(original);
    for (const value of ["0.4881913325931084", 0.4881913325931084, frozen, "0.49", "5e-1"]) {
      expect(() => restoreNumericEnums({ rows: [{ probability: value }] }, schema)).toThrow(/exactly match/);
    }
  });
});
