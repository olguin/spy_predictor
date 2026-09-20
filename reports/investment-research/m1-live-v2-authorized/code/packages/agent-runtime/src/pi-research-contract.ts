export const RESEARCH_PROTOCOL = "pi-research-worker-v2" as const;
export const RESEARCH_TOOLS = ["discover_sources", "read_source", "inspect_evidence", "calculate", "ask_specialist", "submit_findings", "route_question"] as const;

export interface ResearchRequest {
  schema_version: typeof RESEARCH_PROTOCOL;
  task_id: string;
  instructions: string;
  context: Record<string, unknown>;
  tool_schemas: Record<string, Record<string, unknown>>;
  runtime: { model: string; reasoning_effort: "minimal" | "low" | "medium" | "high" | "xhigh" | "max";
    max_output_tokens: number; timeout_seconds: number };
}

export function requireResearchRequest(value: unknown): ResearchRequest {
  if (!value || typeof value !== "object") throw new Error("Invalid research request");
  const request = value as ResearchRequest;
  if (request.schema_version !== RESEARCH_PROTOCOL || typeof request.task_id !== "string" ||
      typeof request.instructions !== "string" || !request.instructions || !request.context ||
      typeof request.context !== "object" || !request.runtime || !request.tool_schemas) {
    throw new Error("Invalid research protocol envelope");
  }
  const keys = Object.keys(request.tool_schemas).sort();
  if (!keys.includes("submit_findings") || keys.some(key => !RESEARCH_TOOLS.includes(key as typeof RESEARCH_TOOLS[number]))) {
    throw new Error("Research tool allowlist mismatch");
  }
  if (typeof request.runtime.model !== "string" || !request.runtime.model.startsWith("openai-codex/") ||
      !Number.isInteger(request.runtime.max_output_tokens) || request.runtime.max_output_tokens < 256 ||
      request.runtime.max_output_tokens > 20_000 || !Number.isInteger(request.runtime.timeout_seconds) ||
      request.runtime.timeout_seconds < 1 || request.runtime.timeout_seconds > 600 ||
      !["minimal", "low", "medium", "high", "xhigh", "max"].includes(request.runtime.reasoning_effort)) {
    throw new Error("Invalid frozen research runtime");
  }
  return request;
}

export class ActionBoundary {
  calls = 0;
  rejected = false;
  action: { tool: string; arguments: unknown } | null = null;
  admitModelCall(): void {
    if (++this.calls > 1) throw new Error("One controller-authorized model turn per worker invocation");
  }
  select(tool: string, args: unknown): void {
    if (!RESEARCH_TOOLS.includes(tool as typeof RESEARCH_TOOLS[number])) throw new Error("Tool not permitted");
    if (this.action) {
      this.rejected = true;
      throw new Error("Exactly one action may cross the controller boundary");
    }
    this.action = { tool, arguments: args };
  }
}
