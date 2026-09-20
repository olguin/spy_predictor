import { afterEach, beforeEach, expect, it, vi } from "vitest";

const fake = vi.hoisted(() => ({
  stderr: [] as string[], stdout: [] as string[], listeners: [] as ((event: any) => void)[],
  tool: undefined as any, settings: undefined as any, session: undefined as any,
  streams: 0, repeat: false, reject: false, disposed: false,
  schema: {} as any, result: { ok: true } as any
}));
vi.mock("node:fs", () => ({ writeSync: (_fd: number, line: string) => fake.stderr.push(line) }));
vi.mock("@earendil-works/pi-coding-agent", () => ({
  VERSION: "0.85.1", getAgentDir: () => "/mock",
  defineTool: (tool: any) => { fake.tool = tool; return tool; },
  ModelRuntime: { create: async () => ({ hasConfiguredAuth: () => true, isUsingOAuth: () => true,
    getModel: () => ({ id: "gpt-6-astra", maxTokens: 128000 }) }) },
  SettingsManager: { inMemory: (settings: any) => { fake.settings = settings; return settings; } },
  SessionManager: { inMemory: () => ({}) },
  DefaultResourceLoader: class { async reload() {} },
  createAgentSession: async () => {
    const assistant = { role: "assistant", model: "gpt-6-astra", stopReason: "toolUse",
      usage: { input: 10, output: 2, reasoning: 0, cacheRead: 0, cacheWrite: 0,
        totalTokens: 12, cost: { total: 0 } } };
    fake.session = {
      thinkingLevel: "medium", messages: [assistant],
      agent: {
        onPayload: (payload: any) => payload,
        streamFunction: async (_model: any, _context: any, options: any) => {
          fake.streams++;
          expect(options.maxRetries).toBe(0);
          await fake.session.agent.onPayload({ confidential: "SECRET_PAYLOAD" }, {});
          await options.fetch("https://example.invalid", {});
          await fake.session.agent.onResponse({ status: 200, headers: { authorization: "SECRET_TOKEN" } }, {});
        }
      },
      subscribe: (listener: (event: any) => void) => {
        fake.listeners.push(listener);
        return () => { fake.listeners = fake.listeners.filter((item) => item !== listener); };
      },
      prompt: async () => {
        await fake.session.agent.streamFunction({}, {}, {});
        for (const event of [{ type: "message_start", message: assistant },
          { type: "message_update", assistantMessageEvent: { type: "toolcall_start", delta: "SECRET_PAYLOAD" } },
          { type: "tool_execution_start", toolName: "submit_result", args: { ok: true } }]) {
          fake.listeners.forEach((listener) => listener(event));
        }
        if (fake.reject) {
          fake.listeners.forEach((listener) => listener({ type: "message_end", message: assistant }));
          fake.listeners.forEach((listener) => listener({ type: "tool_execution_end", isError: true,
            result: { content: [{ type: "text", text: 'Validation failed for tool "submit_result": SECRET_PAYLOAD' }] } }));
          throw new Error("SECRET_PROVIDER_ERROR");
        }
        await fake.tool.execute("id", fake.result);
        if (fake.repeat) await fake.session.agent.streamFunction({}, {}, {});
        fake.listeners.forEach((listener) => listener({ type: "agent_end" }));
      },
      dispose: () => { fake.disposed = true; }
    };
    return { session: fake.session };
  }
}));

let priorSignals: Record<string, Function[]>;
let priorExitCode: typeof process.exitCode;
beforeEach(() => {
  vi.resetModules();
  Object.assign(fake, { stderr: [], stdout: [], listeners: [], streams: 0, repeat: false, reject: false, disposed: false });
  fake.schema = {};
  fake.result = { ok: true };
  priorSignals = Object.fromEntries((["SIGTERM", "SIGINT"] as const).map((s) => [s, process.listeners(s)]));
  priorExitCode = process.exitCode;
  vi.stubGlobal("fetch", vi.fn(async () => new Response("")));
  vi.spyOn(process.stdin, Symbol.asyncIterator).mockImplementation(async function* () {
    yield Buffer.from(JSON.stringify({ role: "synthesis", input_hash: "fixture", instructions: "fixture",
      packet: {}, prior_results: {}, output_schema: fake.schema, runtime: { model: "openai-codex/gpt-6-astra",
        attempts: 1, tools: [], max_output_tokens: 5000, reasoning_effort: "medium", transport: "sse" } }));
    return undefined;
  });
  vi.spyOn(process.stdout, "write").mockImplementation((chunk: any) => { fake.stdout.push(String(chunk)); return true; });
});
afterEach(() => {
  for (const signal of ["SIGTERM", "SIGINT"] as const) {
    for (const listener of process.listeners(signal)) {
      if (!priorSignals[signal]!.includes(listener)) process.removeListener(signal, listener);
    }
  }
  process.exitCode = priorExitCode;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("wires credential-free progress through dispatch, HTTP, stream and result while preserving stdout", async () => {
  await import("./pi-codex-adapter");
  await vi.waitFor(() => expect(fake.disposed).toBe(true));
  expect(fake.streams).toBe(1);
  expect(fake.settings.retry).toEqual({ enabled: false, provider: { maxRetries: 0 } });
  expect(fake.stderr.join("")).not.toContain("SECRET");
  expect(fake.stderr.map((line) => JSON.parse(line).stage)).toContain("stream_open");
  expect(fake.stderr.map((line) => JSON.parse(line).stage)).toContain("result_tool_invoked");
  const envelope = JSON.parse(fake.stdout.find((line) => line.includes('"receipt"'))!);
  expect(envelope.result).toEqual({ ok: true });
  expect(envelope.receipt.provider_output_token_limit_enforced).toBe(false);
  expect(fake.listeners).toHaveLength(0);
});

it("rejects a second model turn before provider dispatch and records failure", async () => {
  fake.repeat = true;
  await import("./pi-codex-adapter");
  await vi.waitFor(() => expect(fake.stderr.some((line) => JSON.parse(line).stage === "failed")).toBe(true));
  expect(fake.streams).toBe(1);
  expect(fake.stdout.some((line) => line.includes('"receipt"'))).toBe(false);
  expect(fake.disposed).toBe(true);
  expect(fake.listeners).toHaveLength(0);
});

it("retains completed response usage and rejected candidate without logging provider errors", async () => {
  fake.reject = true;
  await import("./pi-codex-adapter");
  await vi.waitFor(() => expect(fake.stderr.some((line) => JSON.parse(line).stage === "failed")).toBe(true));
  expect(fake.stderr.map((line) => JSON.parse(line).stage)).toContain("tool_validation_failed");
  expect(fake.stderr.join("") + fake.stdout.join("")).not.toContain("SECRET");
  const envelope = JSON.parse(fake.stdout.find((line) => line.includes('"failure"'))!);
  expect(envelope.failure).toBe("RESULT_NOT_ACCEPTED");
  expect(envelope.result).toEqual({ ok: true });
  expect(envelope.receipt.total_tokens).toBe(12);
  expect(fake.streams).toBe(1);
});

it("uses string choices on the tool wire and returns the exact frozen v4 number with provenance", async () => {
  const frozen = 0.48819133259310843;
  fake.schema = { type: "object", properties: { probability: { enum: [frozen] } } };
  fake.result = { probability: "0.48819133259310843" };
  await import("./pi-codex-adapter");
  await vi.waitFor(() => expect(fake.disposed).toBe(true));
  expect(fake.tool.parameters.properties.probability).toEqual({ type: "string", enum: ["0.48819133259310843"] });
  const envelope = JSON.parse(fake.stdout.find((line) => line.includes('"receipt"'))!);
  expect(envelope.result.probability).toBe(frozen);
  expect(envelope.numeric_enum_restorations).toEqual([{ path: "/probability",
    submitted: "0.48819133259310843", frozen_value: frozen }]);
  expect(envelope.receipt.numeric_enum_transport).toBe("exact_decimal_strings_v1");
});
