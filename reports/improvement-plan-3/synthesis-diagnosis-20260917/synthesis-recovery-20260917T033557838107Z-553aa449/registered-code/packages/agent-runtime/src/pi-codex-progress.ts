const STAGES = ["request_validated", "runtime_initializing", "auth_ready", "resources_ready",
  "session_ready", "prompt_started", "request_prepared", "request_dispatched", "http_response",
  "stream_open", "first_response_event", "thinking_started", "tool_arguments_started", "result_tool_started", "result_tool_invoked",
  "agent_ended", "completed", "failed", "terminated"] as const;
type Stage = typeof STAGES[number];

/** Fixed vocabulary, once per stage: never serialize model content or credentials. */
export function createProgress(write: (line: string) => void, now = () => performance.now()) {
  const start = now();
  const seen = new Set<Stage>();
  return (stage: Stage, status?: number) => {
    if (!STAGES.includes(stage) || seen.has(stage)) return;
    seen.add(stage);
    write(JSON.stringify({ version: "pi-progress-v1", stage,
      elapsed_ms: Math.max(0, Math.round(now() - start)),
      ...(stage === "http_response" && Number.isInteger(status) && status! >= 100 && status! <= 599
        ? { http_status: status } : {}) }) + "\n");
  };
}
