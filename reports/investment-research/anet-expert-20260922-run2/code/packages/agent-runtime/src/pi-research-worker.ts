#!/usr/bin/env node
/** A separate protocol: one action selection, then return control to Python.
 * Python authorizes each intentional model turn and executes every research tool.
 * There are no built-in tools, extensions, project instructions, or auto retries.
 */
import { createAgentSession, defineTool, DefaultResourceLoader, getAgentDir,
  ModelRuntime, SessionManager, SettingsManager, VERSION } from "@earendil-works/pi-coding-agent";
import { constrainedSamplingSchema, parseCodexModel } from "./pi-codex-contract";
import { ActionBoundary, RESEARCH_PROTOCOL, RESEARCH_TOOLS, requireResearchRequest } from "./pi-research-contract";

async function main(): Promise<void> {
  const [major = 0, minor = 0] = process.versions.node.split(".").map(Number);
  if (major < 22 || (major === 22 && minor < 19)) throw new Error("Node >=22.19 required");
  const runtime = await ModelRuntime.create({ allowModelNetwork: false });
  if (process.argv.includes("--preflight")) {
    process.stdout.write(JSON.stringify({ schema_version: RESEARCH_PROTOCOL, pi_version: VERSION,
      oauth_configured: runtime.hasConfiguredAuth("openai-codex") && runtime.isUsingOAuth("openai-codex"),
      models: (await runtime.getAvailable("openai-codex")).map(m => m.id),
      tools: RESEARCH_TOOLS, builtins: false, paid_model_calls: 0 }) + "\n");
    return;
  }
  const chunks: Buffer[] = [];
  let bytes = 0;
  for await (const chunk of process.stdin) {
    bytes += Buffer.byteLength(chunk);
    if (bytes > 2_000_000) throw new Error("Request byte ceiling exceeded");
    chunks.push(Buffer.from(chunk));
  }
  const request = requireResearchRequest(JSON.parse(Buffer.concat(chunks).toString("utf8")));
  if (!runtime.hasConfiguredAuth("openai-codex") || !runtime.isUsingOAuth("openai-codex")) {
    throw new Error("Configured Pi OAuth is required");
  }
  const catalog = runtime.getModel("openai-codex", parseCodexModel(request.runtime.model));
  if (!catalog) throw new Error("Configured model is unavailable");
  const settings = SettingsManager.inMemory({ transport: "sse", compaction: { enabled: false },
    retry: { enabled: false, provider: { maxRetries: 0 } }, enableAnalytics: false,
    enableInstallTelemetry: false }, { projectTrusted: true });
  const loader = new DefaultResourceLoader({ cwd: process.cwd(), agentDir: getAgentDir(),
    settingsManager: settings, noExtensions: true, noSkills: true, noPromptTemplates: true,
    noThemes: true, noContextFiles: true, systemPrompt: request.instructions });
  await loader.reload();
  const boundary = new ActionBoundary();
  const permittedTools = Object.keys(request.tool_schemas);
  const customTools = permittedTools.map(name => defineTool({
    name, label: name, description: `Select ${name}. Python executes it and returns its result on the next authorized turn.`,
    parameters: constrainedSamplingSchema(request.tool_schemas[name]) as any,
    constrainedSampling: { type: "json_schema" as const, strict: "require" as const },
    async execute(_id, params) {
      boundary.select(name, params);
      return { content: [{ type: "text" as const, text: "Action returned to controller." }],
        details: { deferred_to_controller: true }, terminate: true };
    }
  }));
  const { session } = await createAgentSession({ cwd: process.cwd(), agentDir: getAgentDir(),
    modelRuntime: runtime, model: { ...catalog, maxTokens: Math.min(catalog.maxTokens, request.runtime.max_output_tokens) },
    thinkingLevel: request.runtime.reasoning_effort, noTools: "builtin", tools: permittedTools,
    customTools, resourceLoader: loader, settingsManager: settings,
    sessionManager: SessionManager.inMemory(process.cwd()) });
  const stream = session.agent.streamFunction;
  session.agent.streamFunction = (model, context, options) => {
    boundary.admitModelCall();
    return stream(model, context, { ...options, maxRetries: 0,
      // Pi 0.85.1 otherwise sends parallel_tool_calls=true. Require exactly one
      // selection, with Python authorizing any later model/tool turn.
      onPayload: async (payload, selectedModel) => {
        const updated = await options?.onPayload?.(payload, selectedModel);
        const body = updated ?? payload;
        if (!body || typeof body !== "object" || Array.isArray(body)) throw new Error("Invalid provider payload");
        return { ...body, parallel_tool_calls: false, tool_choice: "required" };
      } });
  };
  const timeout = setTimeout(() => { void session.abort(); }, request.runtime.timeout_seconds * 1000);
  const started = performance.now();
  let receipt: Record<string, unknown> | null = null;
  const unsubscribe = session.subscribe(event => {
    if (event.type === "message_end" && event.message.role === "assistant") {
      const usage = event.message.usage;
      const prices = catalog.cost;
      const knownPrice = Object.values(prices).some(price => typeof price === "number" && price > 0);
      // The SDK may emit a synthetic zero-usage error after our guard refuses
      // an unapproved continuation. It must not erase the paid turn's receipt.
      if (receipt && usage.totalTokens <= 0) {
        receipt = { ...receipt, blocked_model_calls: boundary.blockedCalls,
          worker_terminal_reason: event.message.stopReason };
        return;
      }
      receipt = { input_tokens: usage.totalTokens > 0 ? usage.input + usage.cacheRead + usage.cacheWrite : null,
        output_tokens: usage.totalTokens > 0 ? usage.output : null,
        catalog_cost_usd: knownPrice && usage.totalTokens > 0 ? usage.cost.total : null,
        model: request.runtime.model, response_model: event.message.responseModel ?? event.message.model,
        pi_version: VERSION, stop_reason: event.message.stopReason, latency_ms: Math.round(performance.now() - started),
        provider_output_token_limit_enforced: false, model_calls: boundary.calls,
        blocked_model_calls: boundary.blockedCalls };
    }
  });
  try {
    await session.prompt(JSON.stringify(request.context), { expandPromptTemplates: false, source: "rpc" });
    if (!boundary.action || boundary.rejected) throw new Error("No single valid action selected");
    process.stdout.write(JSON.stringify({ schema_version: RESEARCH_PROTOCOL, action: boundary.action, receipt }) + "\n");
  } catch {
    // Return any measured usage even when action selection/streaming fails.
    process.stdout.write(JSON.stringify({ schema_version: RESEARCH_PROTOCOL, action: null, receipt,
      error: "WORKER_TURN_FAILED", boundary: { selected_tool: boundary.action?.tool ?? null,
        duplicate_action: boundary.rejected, blocked_model_calls: boundary.blockedCalls } }) + "\n");
  } finally {
    clearTimeout(timeout);
    unsubscribe();
    session.dispose();
  }
}

main().catch(() => {
  process.stderr.write("pi-research-worker: initialization or protocol failure\n");
  process.exitCode = 1;
});
