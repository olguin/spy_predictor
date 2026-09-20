import { expect, it } from "vitest";
import { createProgress, responseFailureStage } from "./pi-codex-progress";

it("classifies failures without returning reflected provider text", () => {
  expect(responseFailureStage("error", "socket closed SECRET_TOKEN")).toBe("transport_failed");
  expect(responseFailureStage("error", "SECRET_PAYLOAD")).toBe("response_failed");
  expect(responseFailureStage("length", "SECRET_PAYLOAD")).toBe("response_length_limit");
  expect(responseFailureStage("aborted", "SECRET_PAYLOAD")).toBe("response_aborted");
});

it("bounds progress and discards untrusted stages, status data, and payloads", () => {
  const lines: string[] = [];
  let clock = 10;
  const progress = createProgress((line) => lines.push(line), () => clock++);
  for (let i = 0; i < 10000; i++) progress("first_response_event");
  progress("secret payload" as never);
  progress("http_response", { headers: { authorization: "secret" } } as never);
  progress("failed");
  expect(lines.map((line) => JSON.parse(line).stage)).toEqual([
    "first_response_event", "http_response", "failed"]);
  expect(lines.join("")).not.toMatch(/secret|headers|payload|http_status/);
  expect(JSON.parse(lines[0]!).elapsed_ms).toBe(1);
});

it("records only a valid HTTP status beside fixed stage and elapsed time", () => {
  const lines: string[] = [];
  createProgress((line) => lines.push(line), () => 1)("http_response", 429);
  expect(JSON.parse(lines[0]!)).toEqual({ version: "pi-progress-v1",
    stage: "http_response", elapsed_ms: 0, http_status: 429 });
});
