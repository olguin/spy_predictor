import { describe, expect, it } from "vitest";
import { ActionBoundary, RESEARCH_PROTOCOL, RESEARCH_TOOLS, requireResearchRequest } from "./pi-research-contract";

const request = () => ({ schema_version: RESEARCH_PROTOCOL, task_id: "task-1", instructions: "Research",
  context: {}, tool_schemas: Object.fromEntries(RESEARCH_TOOLS.map(t => [t, {}])),
  runtime: { model: "openai-codex/gpt-5.6-terra", reasoning_effort: "medium", max_output_tokens: 3000, timeout_seconds: 60 } });

describe("research controller boundary", () => {
  it("accepts only the separate protocol and exact tool allowlist", () => {
    expect(requireResearchRequest(request()).task_id).toBe("task-1");
    expect(() => requireResearchRequest({ ...request(), schema_version: "legacy" })).toThrow();
    expect(() => requireResearchRequest({ ...request(), tool_schemas: { ...request().tool_schemas, shell: {} } })).toThrow();
  });
  it("does not select another model provider or accept unbounded requests", () => {
    for (const runtime of [{ ...request().runtime, model: "other/model" },
      { ...request().runtime, max_output_tokens: 0 }, { ...request().runtime, timeout_seconds: Infinity }]) {
      expect(() => requireResearchRequest({ ...request(), runtime })).toThrow();
    }
  });
  it("rejects a second model call or duplicate tool action", () => {
    const boundary = new ActionBoundary();
    boundary.admitModelCall();
    expect(() => boundary.admitModelCall()).toThrow();
    boundary.select("read_source", { source_id: "issuer" });
    expect(() => boundary.select("submit_findings", {})).toThrow();
    expect(() => new ActionBoundary().select("shell", {})).toThrow();
  });
});
