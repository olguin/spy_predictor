const STAGES = ["request_validated", "runtime_initializing", "auth_ready", "resources_ready",
  "session_ready", "prompt_started", "request_prepared", "request_dispatched", "http_response",
  "stream_open", "first_response_event", "thinking_started", "tool_arguments_started", "result_tool_started", "result_tool_invoked",
  "tool_validation_failed", "tool_failed", "response_failed", "transport_failed",
  "response_aborted", "response_length_limit", "agent_ended", "completed", "failed", "terminated"] as const;
type Stage = typeof STAGES[number];

/** Map runtime failures to fixed categories without retaining reflected error text. */
export function responseFailureStage(stopReason: string, error: unknown): Stage {
  if (stopReason === "aborted") return "response_aborted";
  if (stopReason === "length") return "response_length_limit";
  const message = typeof error === "string" ? error : error instanceof Error ? error.message : "";
  return /fetch failed|socket|connection|network|ECONN|EPIPE|timed? ?out|terminated|stream.*(closed|ended|error)/i.test(message)
    ? "transport_failed" : "response_failed";
}

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
