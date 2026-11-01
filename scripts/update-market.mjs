// Fetches the last price and 7-day % change for the dashboard ticker and writes market.json.
// Runs in GitHub Actions (see .github/workflows/market.yml), so visitors' browsers never
// contact a third-party data provider. The page only reads market.json from its own site.
import { readFile, writeFile } from 'node:fs/promises';

const OUT = new URL('../market.json', import.meta.url);
const DAY = 86400;
const ASSETS = [
  { id: 'spx', name: 'S&P 500', symbol: '^GSPC', unit: 'pts' },
  { id: 'gold', name: 'Gold', symbol: 'GC=F', unit: 'oz' },
  { id: 'silver', name: 'Silver', symbol: 'SI=F', unit: 'oz' },
];

const round = (n, d = 2) => Math.round(n * 10 ** d) / 10 ** d;

async function chart(symbol) {
  let lastErr;
  for (const host of ['query1', 'query2']) {
    try {
      const url = `https://${host}.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=1mo&interval=1d`;
      const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 (fin-track market updater)', Accept: 'application/json' } });
      if (!r.ok) throw new Error(`${host} HTTP ${r.status}`);
      const res = (await r.json())?.chart?.result?.[0];
      if (!res) throw new Error(`${host}: empty result`);
      return res;
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr;
}

function summarize(res) {
  const ts = res.timestamp || [];
  const closes = res.indicators?.quote?.[0]?.close || [];
  const pts = ts.map((t, i) => ({ t, c: closes[i] })).filter(p => Number.isFinite(p.c) && p.c > 0);
  if (!pts.length) throw new Error('no closing prices');
  const meta = res.meta || {};
  const price = Number.isFinite(meta.regularMarketPrice) ? meta.regularMarketPrice : pts.at(-1).c;
  const lastT = Number.isFinite(meta.regularMarketTime) ? meta.regularMarketTime : pts.at(-1).t;
  // 7-day change: compare with the last daily close on or before 7 calendar days ago
  // (same weekday last week = 5 trading days).
  const ref = [...pts].reverse().find(p => p.t <= lastT - 7 * DAY);
  return {
    price: round(price),
    change7d: ref ? round((price / ref.c - 1) * 100) : null,
    asOf: new Date(lastT * 1000).toISOString().slice(0, 10),
  };
}

let prev = null;
try { prev = JSON.parse(await readFile(OUT, 'utf8')); } catch {}

let ok = 0;
const items = [];
for (const a of ASSETS) {
  try {
    items.push({ id: a.id, name: a.name, symbol: a.symbol, unit: a.unit, ...summarize(await chart(a.symbol)) });
    ok++;
  } catch (e) {
    console.error(`${a.symbol}: ${e.message}`);
    const old = prev?.items?.find(x => x.id === a.id);
    if (old) items.push({ ...old, stale: true }); // keep the last good value rather than dropping it
  }
}

if (!ok) {
  console.error('No prices could be fetched; leaving market.json unchanged.');
  process.exit(1);
}

// Only rewrite the file when prices changed, so weekends and holidays don't create commits.
if (prev && JSON.stringify(prev.items) === JSON.stringify(items)) {
  console.log('Prices unchanged.');
} else {
  await writeFile(OUT, JSON.stringify({ updatedAt: new Date().toISOString(), source: 'Yahoo Finance (delayed)', items }, null, 2) + '\n');
  console.log(items.map(i => `${i.name}: ${i.price} (${i.change7d ?? '—'}% 7d)`).join('\n'));
}
