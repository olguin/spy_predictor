import { Temporal } from "@js-temporal/polyfill";
import { marketTimeToInstant, MARKET_TIMEZONE } from "./time";
import type { Instant } from "./types";

export interface ExchangeSession {
  date: string;
  open: Instant;
  close: Instant;
  timezone: typeof MARKET_TIMEZONE;
  earlyClose: boolean;
}

export interface ExchangeCalendar {
  session(date: string): ExchangeSession | null;
  tradingDates(start: string, end: string): string[];
}

function nthWeekday(year: number, month: number, weekday: number, nth: number) {
  let date = Temporal.PlainDate.from({ year, month, day: 1 });
  date = date.add({ days: (weekday - date.dayOfWeek + 7) % 7 + (nth - 1) * 7 });
  return date;
}

function lastWeekday(year: number, month: number, weekday: number) {
  let date = Temporal.PlainDate.from({ year, month, day: 1 })
    .add({ months: 1 })
    .subtract({ days: 1 });
  return date.subtract({ days: (date.dayOfWeek - weekday + 7) % 7 });
}

function observed(date: Temporal.PlainDate): Temporal.PlainDate {
  if (date.dayOfWeek === 6) return date.subtract({ days: 1 });
  if (date.dayOfWeek === 7) return date.add({ days: 1 });
  return date;
}

function easterSunday(year: number): Temporal.PlainDate {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return Temporal.PlainDate.from({ year, month, day });
}

function holidaysForYear(year: number): Set<string> {
  const dates = [
    observed(Temporal.PlainDate.from({ year, month: 1, day: 1 })),
    nthWeekday(year, 1, 1, 3),
    nthWeekday(year, 2, 1, 3),
    easterSunday(year).subtract({ days: 2 }),
    lastWeekday(year, 5, 1),
    ...(year >= 2022
      ? [observed(Temporal.PlainDate.from({ year, month: 6, day: 19 }))]
      : []),
    observed(Temporal.PlainDate.from({ year, month: 7, day: 4 })),
    nthWeekday(year, 9, 1, 1),
    nthWeekday(year, 11, 4, 4),
    observed(Temporal.PlainDate.from({ year, month: 12, day: 25 }))
  ];
  return new Set(dates.map((date) => date.toString()));
}

function previousWeekday(date: Temporal.PlainDate): Temporal.PlainDate {
  let candidate = date.subtract({ days: 1 });
  while (candidate.dayOfWeek > 5) candidate = candidate.subtract({ days: 1 });
  return candidate;
}

function earlyClosesForYear(year: number): Set<string> {
  const thanksgiving = nthWeekday(year, 11, 4, 4);
  const independenceObserved = observed(
    Temporal.PlainDate.from({ year, month: 7, day: 4 })
  );
  const christmasEve = Temporal.PlainDate.from({ year, month: 12, day: 24 });
  const dates = [thanksgiving.add({ days: 1 }), previousWeekday(independenceObserved)];
  if (christmasEve.dayOfWeek <= 5) dates.push(christmasEve);
  return new Set(dates.map((date) => date.toString()));
}

export class UsEquityExchangeCalendar implements ExchangeCalendar {
  constructor(private readonly extraClosures = new Set<string>()) {}

  session(dateText: string): ExchangeSession | null {
    const date = Temporal.PlainDate.from(dateText);
    const holidayDates = new Set(
      [date.year - 1, date.year, date.year + 1].flatMap((year) => [
        ...holidaysForYear(year)
      ])
    );
    if (
      date.dayOfWeek > 5 ||
      holidayDates.has(dateText) ||
      this.extraClosures.has(dateText)
    ) {
      return null;
    }
    const earlyClose = earlyClosesForYear(date.year).has(dateText);
    return {
      date: dateText,
      open: marketTimeToInstant(dateText, "09:30:00"),
      close: marketTimeToInstant(dateText, earlyClose ? "13:00:00" : "16:00:00"),
      timezone: MARKET_TIMEZONE,
      earlyClose
    };
  }

  tradingDates(start: string, end: string): string[] {
    let cursor = Temporal.PlainDate.from(start);
    const final = Temporal.PlainDate.from(end);
    const dates: string[] = [];
    while (Temporal.PlainDate.compare(cursor, final) <= 0) {
      const date = cursor.toString();
      if (this.session(date)) dates.push(date);
      cursor = cursor.add({ days: 1 });
    }
    return dates;
  }
}
