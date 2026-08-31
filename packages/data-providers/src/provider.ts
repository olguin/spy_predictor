import {
  PointInTimeViolation,
  assertAtOrBefore,
  compareInstants,
  type Instant,
  type MarketBar
} from "@spy-predictor/domain";

export interface MarketSeriesQuery {
  symbol: string;
  start: Instant;
  end: Instant;
}

export interface HistoricalMarketDataProvider {
  readonly source: string;
  readonly datasetVersion: string;
  queryBars(query: MarketSeriesQuery): Promise<MarketBar[]>;
}

export class PointInTimeMarketDataProvider
  implements HistoricalMarketDataProvider
{
  readonly source: string;
  readonly datasetVersion: string;

  constructor(
    private readonly delegate: HistoricalMarketDataProvider,
    private readonly cutoff: Instant
  ) {
    this.source = delegate.source;
    this.datasetVersion = delegate.datasetVersion;
  }

  async queryBars(query: MarketSeriesQuery): Promise<MarketBar[]> {
    assertAtOrBefore(query.start, this.cutoff, "query start");
    assertAtOrBefore(query.end, this.cutoff, "query end");

    const bars = await this.delegate.queryBars(query);
    for (const bar of bars) {
      if (compareInstants(bar.firstSeenAt, this.cutoff) > 0) {
        throw new PointInTimeViolation(
          `Provider leaked ${bar.symbol} record first seen at ${bar.firstSeenAt} after cutoff ${this.cutoff}`
        );
      }
    }
    return bars;
  }
}

export class InMemoryMarketDataProvider
  implements HistoricalMarketDataProvider
{
  constructor(
    private readonly bars: readonly MarketBar[],
    readonly source = "in-memory",
    readonly datasetVersion = "in-memory-v1"
  ) {}

  async queryBars(query: MarketSeriesQuery): Promise<MarketBar[]> {
    return this.bars
      .filter(
        (bar) =>
          bar.symbol === query.symbol &&
          compareInstants(bar.eventTime, query.start) >= 0 &&
          compareInstants(bar.eventTime, query.end) <= 0
      )
      .sort((left, right) => compareInstants(left.eventTime, right.eventTime));
  }
}
