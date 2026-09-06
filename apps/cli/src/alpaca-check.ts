interface AlpacaBar {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

export {};

interface AlpacaBarsResponse {
  bars?: AlpacaBar[];
  symbol?: string;
  message?: string;
  code?: number;
}

const keyId = process.env.APCA_API_KEY_ID?.trim();
const secretKey = process.env.APCA_API_SECRET_KEY?.trim();
const feed = process.env.ALPACA_DATA_FEED?.trim() || "sip";

if (!keyId || !secretKey) {
  throw new Error(
    "Missing APCA_API_KEY_ID or APCA_API_SECRET_KEY. Add them to the ignored .env file."
  );
}

if (feed !== "sip" && feed !== "iex") {
  throw new Error("ALPACA_DATA_FEED must be either sip or iex");
}

const url = new URL("https://data.alpaca.markets/v2/stocks/SPY/bars");
url.search = new URLSearchParams({
  timeframe: "1Min",
  start: "2024-01-03T14:30:00Z",
  end: "2024-01-03T14:32:00Z",
  adjustment: "all",
  feed,
  sort: "asc",
  limit: "3"
}).toString();

const response = await fetch(url, {
  headers: {
    "APCA-API-KEY-ID": keyId,
    "APCA-API-SECRET-KEY": secretKey
  },
  signal: AbortSignal.timeout(15_000)
});

const payload = (await response.json()) as AlpacaBarsResponse;
if (!response.ok) {
  const detail = payload.message ?? `Alpaca returned HTTP ${response.status}`;
  throw new Error(`Alpaca connection check failed (${response.status}): ${detail}`);
}

const bars = payload.bars ?? [];
if (bars.length === 0) {
  throw new Error("Alpaca authenticated the request but returned no SPY bars");
}

const first = bars[0];
const last = bars.at(-1);
if (!first || !last) {
  throw new Error("Alpaca returned an invalid bars response");
}

console.log(
  JSON.stringify(
    {
      status: "ok",
      endpoint: "Alpaca Market Data API",
      symbol: payload.symbol ?? "SPY",
      feed,
      barsReceived: bars.length,
      firstBar: first.t,
      lastBar: last.t
    },
    null,
    2
  )
);
