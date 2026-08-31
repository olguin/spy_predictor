import { describe, expect, it } from "vitest";
import {
  UsEquityExchangeCalendar,
  canonicalJson,
  contentHash,
  marketTimeToInstant
} from "./index";

describe("deterministic domain primitives", () => {
  it("hashes objects independently of key insertion order", () => {
    expect(contentHash({ b: 2, a: 1 })).toBe(contentHash({ a: 1, b: 2 }));
    expect(canonicalJson({ b: 2, a: 1 })).toBe('{"a":1,"b":2}');
  });

  it("uses IANA daylight-saving rules for New York", () => {
    expect(marketTimeToInstant("2024-01-10", "09:29:00")).toBe(
      "2024-01-10T14:29:00Z"
    );
    expect(marketTimeToInstant("2024-06-10", "09:29:00")).toBe(
      "2024-06-10T13:29:00Z"
    );
  });
});

describe("US equity exchange calendar", () => {
  const calendar = new UsEquityExchangeCalendar();

  it("excludes holidays and models regular and early-close sessions", () => {
    expect(calendar.session("2024-07-04")).toBeNull();
    expect(calendar.session("2024-11-29")).toMatchObject({
      earlyClose: true,
      close: "2024-11-29T18:00:00Z"
    });
    expect(calendar.session("2024-11-27")).toMatchObject({ earlyClose: false });
  });

  it("uses DST-aware UTC session instants", () => {
    expect(calendar.session("2024-01-10")?.open).toBe("2024-01-10T14:30:00Z");
    expect(calendar.session("2024-06-10")?.open).toBe("2024-06-10T13:30:00Z");
  });
});
