import {
  marketTimeToInstant,
  type DirectionLabel,
  type MarketSnapshot,
  type MarketTarget,
  type TargetDefinition
} from "@spy-predictor/domain";
import type { HistoricalMarketDataProvider } from "@spy-predictor/data-providers";

export class TargetGenerator {
  constructor(private readonly provider: HistoricalMarketDataProvider) {}

  async generate(
    date: string,
    snapshot: MarketSnapshot,
    definition: TargetDefinition
  ): Promise<MarketTarget> {
    const startTime = marketTimeToInstant(date, definition.targetStart);
    const endTime = marketTimeToInstant(date, definition.targetEnd);
    const bars = await this.provider.queryBars({
      symbol: definition.instrument,
      start: startTime,
      end: endTime
    });
    if (bars.length < 2) {
      throw new Error(`Insufficient target bars for ${date}`);
    }
    const first = bars[0]!;
    const last = bars.at(-1)!;
    const targetReturn = Math.log(last.close / first.close);
    const realizedVariance = bars.slice(1).reduce((sum, bar, index) => {
      const previous = bars[index]!;
      const minuteReturn = Math.log(bar.close / previous.close);
      return sum + minuteReturn * minuteReturn;
    }, 0);
    const high = Math.max(...bars.map((bar) => bar.high));
    const low = Math.min(...bars.map((bar) => bar.low));
    let directionLabel: DirectionLabel = "NEUTRAL";
    if (targetReturn > definition.neutralThreshold) directionLabel = "UP";
    if (targetReturn < -definition.neutralThreshold) directionLabel = "DOWN";

    return {
      snapshotId: snapshot.id,
      targetDefinitionId: definition.id,
      startTime,
      endTime,
      startPrice: first.close,
      endPrice: last.close,
      return: targetReturn,
      directionLabel,
      realizedVolatility: Math.sqrt(realizedVariance),
      absoluteReturn: Math.abs(targetReturn),
      highLowRange: Math.log(high / low)
    };
  }
}
