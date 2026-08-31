import { Temporal } from "@js-temporal/polyfill";
import {
  contentHash,
  marketTimeToInstant,
  UsEquityExchangeCalendar,
  type MarketBar
} from "@spy-predictor/domain";
import { InMemoryMarketDataProvider } from "./provider";

const TARGET_RETURNS = [
  -0.0032, -0.0018, -0.0006, 0.0001, 0.0007, 0.0014, 0.0028, -0.0024,
  0.0004, 0.0019, -0.0012, 0
];

function makeBar(
  symbol: string,
  eventTime: string,
  price: number,
  previousPrice: number,
  volume: number,
  datasetVersion: string
): MarketBar {
  const payload = { symbol, eventTime, price, previousPrice, volume, datasetVersion };
  return {
    symbol,
    eventTime,
    open: previousPrice,
    high: Math.max(price, previousPrice) * 1.0001,
    low: Math.min(price, previousPrice) * 0.9999,
    close: price,
    volume,
    source: "synthetic-foundation",
    sourceTimestamp: eventTime,
    firstSeenAt: eventTime,
    effectiveTimestamp: eventTime,
    ingestionTimestamp: eventTime,
    version: datasetVersion,
    hash: contentHash(payload)
  };
}

export function syntheticTradingDates(count: number): string[] {
  const dates: string[] = [];
  let cursor = Temporal.PlainDate.from("2024-01-02");
  const calendar = new UsEquityExchangeCalendar();
  while (dates.length < count) {
    if (calendar.session(cursor.toString())) dates.push(cursor.toString());
    cursor = cursor.add({ days: 1 });
  }
  return dates;
}

export function createSyntheticMarketProvider(tradingDays: number): {
  provider: InMemoryMarketDataProvider;
  dates: string[];
} {
  const datasetVersion = "synthetic-spy-v1";
  const dates = syntheticTradingDates(tradingDays);
  const bars: MarketBar[] = [];
  let priorClose = 475;

  dates.forEach((date, dayIndex) => {
    const gap = (((dayIndex * 7) % 11) - 5) * 0.00035;
    const premarket = priorClose * (1 + gap);
    const premarketTime = marketTimeToInstant(date, "09:29:00");
    bars.push(
      makeBar("SPY", premarketTime, premarket, priorClose, 50_000, datasetVersion)
    );

    const targetReturn = TARGET_RETURNS[dayIndex % TARGET_RETURNS.length] ?? 0;
    const startPrice = premarket * (1 + (((dayIndex % 3) - 1) * 0.00005));
    let previous = startPrice;
    for (let minute = 0; minute <= 29; minute += 1) {
      const progress = minute / 29;
      const wave = Math.sin(progress * Math.PI * 2) * 0.00018;
      const price = startPrice * Math.exp(targetReturn * progress + wave);
      const minuteText = String(31 + minute).padStart(2, "0");
      const hour = Number(minuteText) >= 60 ? "10" : "09";
      const minuteWithinHour = String(Number(minuteText) % 60).padStart(2, "0");
      const eventTime = marketTimeToInstant(
        date,
        `${hour}:${minuteWithinHour}:00`
      );
      bars.push(
        makeBar(
          "SPY",
          eventTime,
          price,
          previous,
          80_000 + minute * 1_000,
          datasetVersion
        )
      );
      previous = price;
    }

    const afternoonMove = (((dayIndex * 5) % 9) - 4) * 0.0005;
    priorClose = previous * (1 + afternoonMove);
    const closeTime = marketTimeToInstant(date, "16:00:00");
    bars.push(
      makeBar("SPY", closeTime, priorClose, previous, 1_000_000, datasetVersion)
    );
  });

  return {
    provider: new InMemoryMarketDataProvider(
      bars,
      "synthetic-foundation",
      datasetVersion
    ),
    dates
  };
}
