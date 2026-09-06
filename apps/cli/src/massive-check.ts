export {};

const apiKey = process.env.MASSIVE_API_KEY?.trim();

if (!apiKey) {
  throw new Error("Missing MASSIVE_API_KEY. Add it to the ignored .env file.");
}

const url = new URL("https://api.massive.com/futures/v1/contracts");
url.search = new URLSearchParams({
  product_code: "ES",
  date: "2026-09-03",
  active: "true",
  limit: "1",
  sort: "ticker.asc"
}).toString();

const response = await fetch(url, {
  headers: { Authorization: `Bearer ${apiKey}` },
  signal: AbortSignal.timeout(15_000)
});
const payload = (await response.json()) as {
  status?: string;
  results?: Array<{ ticker?: string }>;
  error?: string;
};
if (!response.ok) {
  throw new Error(
    `Massive connection check failed (${response.status}): ${payload.error ?? payload.status ?? "unknown response"}`
  );
}
const ticker = payload.results?.[0]?.ticker;
if (!ticker) throw new Error("Massive authenticated but returned no ES contracts");

console.log(JSON.stringify({ status: "ok", endpoint: "Massive Futures REST API", ticker }, null, 2));
