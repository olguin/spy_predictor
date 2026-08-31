export interface AgentDefinition {
  id: string;
  version: string;
  role: string;
}

export interface AgentExecutionContext {
  snapshotId: string;
  payload: Readonly<Record<string, unknown>>;
}

export interface OutputSchema<T> {
  parse(value: unknown): T;
}

export interface AgentExecutionOptions {
  model: string;
  reasoningEffort?: string;
  temperature?: number;
  maxInputTokens?: number;
  maxOutputTokens?: number;
  timeoutMs?: number;
  seed?: number;
  allowedTools: string[];
  cachePolicy: "use" | "refresh" | "bypass";
}

export interface AgentExecutionResult<T> {
  output: T;
  runtime: string;
  cached: boolean;
  latencyMs: number;
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
}

export interface AgentRuntime {
  execute<T>(
    definition: AgentDefinition,
    context: AgentExecutionContext,
    schema: OutputSchema<T>,
    options: AgentExecutionOptions
  ): Promise<AgentExecutionResult<T>>;
}

export class MockAgentRuntime implements AgentRuntime {
  constructor(
    private readonly responder: (
      definition: AgentDefinition,
      context: AgentExecutionContext
    ) => unknown
  ) {}

  async execute<T>(
    definition: AgentDefinition,
    context: AgentExecutionContext,
    schema: OutputSchema<T>,
    _options: AgentExecutionOptions
  ): Promise<AgentExecutionResult<T>> {
    const started = performance.now();
    const output = schema.parse(this.responder(definition, context));
    return {
      output,
      runtime: "mock",
      cached: false,
      latencyMs: performance.now() - started,
      inputTokens: 0,
      outputTokens: 0,
      costUsd: 0
    };
  }
}
