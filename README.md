# FinTrack: private finance tracker

A free credit card payoff and cash-flow tracker that runs entirely in your browser.
**No account, no server, no tracking.** Your numbers never leave your device.

👉 **Use it:** https://theguy444.github.io/Fin-track/

## What it does

- **Credit cards:** balance, limit, APR, minimum, your payment, utilization, and the "room before payment increase" estimate
- **Log payments and charges:** each card's balance updates and shows how much you've paid down since you started
- **Payoff plan:** compare *avalanche* (highest APR first) and *snowball* (smallest balance first) against your current payments: debt-free date, total interest, and which card to pay first
- **Transactions:** money in / money out by category, with search and month filters
- **Reports:** 12-month cash flow table and charts, CSV export
- **Market ticker:** S&P 500, gold and silver on the dashboard, with the % change over the last 7 days (can be turned off in *Save & data*)

## How your data is saved

There's no server, so you keep your own data. Three options:

1. **Save code (works everywhere):** click **Save**, then **Copy to clipboard**, and paste it into a notepad file (e.g. `fintrack-save.txt`). Next time, click **Load** and paste it back.
   Add a **passphrase** and the code is encrypted (AES-256-GCM, PBKDF2 key). Without the passphrase it can't be read, and a forgotten passphrase can't be recovered.
2. **Auto-save file (Chrome / Edge on a computer):** link a `.json` file on your computer and every change is written to it automatically.
3. **Browser memory:** by default every change is kept in this browser automatically, so a backup code is only needed now and then (the status pill nudges you after 10 changes or a week). Turn this off in *Save & data* on shared computers.

Save codes are snapshots, so save again after making changes. The page warns you before closing if you haven't.

## Privacy

- The page includes a Content-Security-Policy that **blocks all network requests except reading `market.json` from this same site**, so it cannot send your data anywhere even if it wanted to. No third-party server is ever contacted from your browser.
- Market prices are fetched by a GitHub Action (`.github/workflows/market.yml`) a few times each weekday and saved to `market.json`. Prices are delayed, not real-time.
- No analytics, cookies, fonts or third-party scripts. One self-contained `index.html`.
- Anything loaded from a save code is validated and sanitized before it's used.
- Note: every GitHub Pages site under the same account shares one browser origin (`username.github.io`). Only host pages you trust under the same account, or turn off "Remember my data in this browser".


## Disclaimer

Estimates use APR ÷ 12 monthly interest and assume no new charges, fees or rate changes. Real issuers calculate interest on average daily balance. This is a planning tool, not financial advice. Check numbers against your statements.

## License

MIT
