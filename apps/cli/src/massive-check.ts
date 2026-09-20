export {};

const apiKey = process.env.MASSIVE_API_KEY?.trim();

if (!apiKey) {
  throw new Error("Missing MASSIVE_API_KEY. Add it to the ignored .env file.");
}

const futuresUrl = new URL("https://api.massive.com/futures/v1/contracts");
futuresUrl.search = new URLSearchParams({
  product_code: "ES",
  date: "2026-09-03",
  active: "true",
  limit: "1",
  sort: "ticker.asc"
}).toString();

const requestedIndices = ["I:VIX", "I:VIX3M"];
const indicesUrls = requestedIndices.map((ticker) => {
  const url = new URL("https://api.massive.com/v3/snapshot/indices");
  url.search = new URLSearchParams({ ticker }).toString();
  return url;
});
const headers = { Authorization: `Bearer ${apiKey}` };

async function check(url: URL) {
  const response = await fetch(url, { headers, signal: AbortSignal.timeout(15_000) });
  const payload = (await response.json()) as {
    status?: string;
    results?: Array<{ ticker?: string; value?: number; timeframe?: string; last_updated?: number }>;
    error?: string;
    message?: string;
  };
  return { response, payload };
}

const [futures, ...indices] = await Promise.all([check(futuresUrl), ...indicesUrls.map(check)]);
const futuresTicker = futures.payload.results?.[0]?.ticker;
const indexRows = indices.flatMap((result) => result.payload.results ?? []);
const indexTickers = indexRows.map((row) => row.ticker).filter(Boolean);
const futuresStatus = futures.response.ok && futuresTicker ? "ok" : "unavailable";
const indicesStatus = indices.every((result) => result.response.ok) &&
  requestedIndices.every((ticker) => indexTickers.includes(ticker))
  ? "ok" : indices.some((result) => result.response.status === 403) ? "not_entitled" : "unavailable";

console.log(JSON.stringify({
  status: futuresStatus === "ok" && indicesStatus === "ok" ? "ok" : "partial",
  futures: { status: futuresStatus, http_status: futures.response.status, ticker: futuresTicker ?? null },
  indices: {
    status: indicesStatus,
    http_status: indices.map((result) => result.response.status),
    requested: requestedIndices,
    returned: indexTickers,
    provider_timeframes: [...new Set(indexRows.map((row) => row.timeframe).filter(Boolean))],
    reason: indicesStatus === "not_entitled" ? "Massive index snapshot entitlement is required" : null
  }
}, null, 2));
