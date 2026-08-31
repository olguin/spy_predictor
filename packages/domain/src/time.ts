import { Temporal } from "@js-temporal/polyfill";
import type { Instant } from "./types";

export const MARKET_TIMEZONE = "America/New_York" as const;

export function marketTimeToInstant(date: string, time: string): Instant {
  const plainDate = Temporal.PlainDate.from(date);
  const plainTime = Temporal.PlainTime.from(time);
  return plainDate
    .toZonedDateTime({ timeZone: MARKET_TIMEZONE, plainTime })
    .toInstant()
    .toString();
}

export function compareInstants(left: Instant, right: Instant): number {
  return Temporal.Instant.compare(
    Temporal.Instant.from(left),
    Temporal.Instant.from(right)
  );
}

export function assertAtOrBefore(
  requested: Instant,
  cutoff: Instant,
  description = "requested timestamp"
): void {
  if (compareInstants(requested, cutoff) > 0) {
    throw new PointInTimeViolation(
      `${description} ${requested} is after cutoff ${cutoff}`
    );
  }
}

export class PointInTimeViolation extends Error {
  override name = "PointInTimeViolation";
}
