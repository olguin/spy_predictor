import { describe, expect, it } from "vitest";
import {
  PointInTimeViolation,
  contentHash,
  marketTimeToInstant,
  type MarketBar
} from "@spy-predictor/domain";
import {
  InMemoryMarketDataProvider,
  PointInTimeMarketDataProvider
} from "./provider";

function bar(eventTime: string, firstSeenAt = eventTime): MarketBar {
  return {
    symbol: "SPY",
    eventTime,
    open: 100,
    high: 101,
    low: 99,
    close: 100,
    volume: 10,
    source: "test",
    sourceTimestamp: eventTime,
    firstSeenAt,
    effectiveTimestamp: eventTime,
    ingestionTimestamp: firstSeenAt,
    version: "v1",
    hash: contentHash({ eventTime, firstSeenAt })
  };
}

describe("point-in-time provider", () => {
  const cutoff = marketTimeToInstant("2024-01-10", "09:29:00");

  it("rejects a query extending beyond the cutoff", async () => {
    const guarded = new PointInTimeMarketDataProvider(
      new InMemoryMarketDataProvider([]),
      cutoff
    );
    await expect(
      guarded.queryBars({
        symbol: "SPY",
        start: cutoff,
        end: marketTimeToInstant("2024-01-10", "09:31:00")
      })
    ).rejects.toBeInstanceOf(PointInTimeViolation);
  });

  it("rejects records that were first seen after the cutoff", async () => {
    const eventTime = marketTimeToInstant("2024-01-10", "09:28:00");
    const leaked = bar(
      eventTime,
      marketTimeToInstant("2024-01-10", "09:30:00")
    );
    const guarded = new PointInTimeMarketDataProvider(
      new InMemoryMarketDataProvider([leaked]),
      cutoff
    );
    await expect(
      guarded.queryBars({ symbol: "SPY", start: eventTime, end: cutoff })
    ).rejects.toBeInstanceOf(PointInTimeViolation);
  });
});
