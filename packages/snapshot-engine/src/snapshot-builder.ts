import { Temporal } from "@js-temporal/polyfill";
import {
  contentHash,
  compareInstants,
  marketTimeToInstant,
  type MarketSnapshot,
  type SourceManifestEntry,
  type TargetDefinition
} from "@spy-predictor/domain";
import {
  PointInTimeMarketDataProvider,
  type HistoricalMarketDataProvider
} from "@spy-predictor/data-providers";

export const SNAPSHOT_SCHEMA_VERSION = "market-snapshot-v1";
export const FEATURE_VERSION = "foundation-features-v1";

export class SnapshotBuilder {
  constructor(private readonly provider: HistoricalMarketDataProvider) {}

  async build(date: string, target: TargetDefinition): Promise<MarketSnapshot> {
    const predictionTime = marketTimeToInstant(date, target.predictionTime);
    const guarded = new PointInTimeMarketDataProvider(
      this.provider,
      predictionTime
    );
    const lookbackStart = Temporal.Instant.from(predictionTime)
      .subtract({ hours: 24 * 7 })
      .toString();
    const bars = await guarded.queryBars({
      symbol: target.instrument,
      start: lookbackStart,
      end: predictionTime
    });
    if (bars.length < 2) {
      throw new Error(`Insufficient point-in-time bars for ${date}`);
    }

    const currentSessionStart = marketTimeToInstant(date, "00:00:00");
    const previousBars = bars.filter(
      (bar) => compareInstants(bar.eventTime, currentSessionStart) < 0
    );
    const currentBars = bars.filter(
      (bar) => compareInstants(bar.eventTime, currentSessionStart) >= 0
    );
    const previousCloseBar = previousBars.at(-1);
    const latestBar = currentBars.at(-1);
    if (!previousCloseBar || !latestBar) {
      throw new Error(`Missing previous close or current bar for ${date}`);
    }

    const sourceManifest: SourceManifestEntry[] = [
      {
        source: this.provider.source,
        datasetVersion: this.provider.datasetVersion,
        recordCount: bars.length,
        earliestFirstSeenAt: bars[0]!.firstSeenAt,
        latestFirstSeenAt: bars.at(-1)!.firstSeenAt,
        contentHash: contentHash(bars.map((bar) => bar.hash))
      }
    ];
    const overnightReturn = Math.log(latestBar.close / previousCloseBar.close);
    const snapshotBody = {
      schemaVersion: SNAPSHOT_SCHEMA_VERSION,
      predictionTime,
      dataCutoff: predictionTime,
      instruments: [
        {
          symbol: target.instrument,
          asOf: latestBar.eventTime,
          latestPrice: latestBar.close,
          previousClose: previousCloseBar.close,
          overnightReturn
        }
      ],
      technicalFeatures: {
        overnightReturn,
        absoluteOvernightReturn: Math.abs(overnightReturn)
      },
      sourceManifest,
      dataQuality: {
        marketDataComplete: true,
        newsAvailable: false,
        macroAvailable: false,
        optionsAvailable: false,
        staleSources: [],
        qualityScore: 0.4
      }
    };
    const hash = contentHash(snapshotBody);
    return {
      id: `snap_${hash.slice(0, 20)}`,
      ...snapshotBody,
      hash
    };
  }
}
