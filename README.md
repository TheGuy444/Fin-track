# FinTrack: private finance tracker

A free credit card payoff and cash-flow tracker that runs entirely in your browser.
**No account, no server, no tracking.** Your numbers never leave your device.

👉 **Use it:** https://theguy444.github.io/Fin-track/

## What it does

- **Credit cards:** balance, limit, APR, minimum, your payment, due day, autopay, utilization, and the "room before payment increase" estimate
- **Bills & due dates:** rent, utilities, insurance, subscriptions, anything that repeats (weekly to yearly). See what's coming up, what's overdue, and tap *Mark paid*
- **Income & your month, planned:** recurring paychecks vs. bills and card payments, and what's left over each month
- **Log payments and charges:** each card's balance updates and shows how much you've paid down since you started
- **Payoff plan:** compare *avalanche* (highest APR first) and *snowball* (smallest balance first) against your current payments: debt-free date, total interest, and which card to pay first
- **Transactions:** money in / money out by category, with search and month filters
- **Reports:** 12-month cash flow table and charts, CSV export
- **Market ticker:** S&P 500, gold and silver on the dashboard, with the % change over the last 7 days (can be turned off in *Save & data*)

## Your FinTrack file: let Claude manage it

Everything lives in one file you keep, **`fintrack.json`**: cards, bills, due dates, income, transactions and a change log. No account, no login. You supply the numbers.

```
 you ──"trash is $35/mo, due the 15th"──▶ Claude ──updated fintrack.json──▶ drop it on FinTrack ──▶ dashboard
  ▲                                                                                                  │
  └──────────────────────────── Download / "Copy for Claude" ◀──────────────────────────────────────┘
```

1. **Get your file:** *Save & data → Download fintrack.json* (or link an auto-save file in Chrome/Edge so it's always current).
2. **Give it to Claude** (or any assistant): attach it, or tap *Copy for Claude* and paste. Then talk normally: "I got a Chase card at 24.99%, owe 3,400, due the 18th", "my trash bill is 35 a month due the 15th", "I paid the Discover 200", "what's due this week?"
3. **Bring it back:** Claude returns the updated file. Save it over the old one and drop it on the page (or *Load*). A review screen shows exactly what changed, revision by revision, before anything is replaced; one tap undoes it.

No file yet? Start in any AI chat with:

> Read https://theguy444.github.io/Fin-track/llms.txt and help me make my FinTrack file.

**How assistants stay reliable**

- The file carries its own rules (`_agent`), so even an assistant that can't browse the web knows how to edit it: change only what was asked, bump `revision`, add a `log` entry, never store card or account numbers, and hand back the whole file.
- [`llms.txt`](llms.txt) is the full guide; [`fintrack.schema.json`](fintrack.schema.json) is the JSON Schema; [`examples/fintrack.example.json`](examples/fintrack.example.json) is a complete example.
- **Claude skill** ([`skill/fintrack`](skill/fintrack)): zip the `fintrack` folder and upload it to Claude as a skill. Its script validates the file, bumps the revision, proves the edit with a diff, rejects anything that looks like a card or account number, and computes due dates with the *same rules as the dashboard*, so "what's due this week?" gets the same answer in both places.
- `revision` decides which copy is newer (not timestamps, which assistants can get wrong). Loading an older file warns you first. A linked auto-save file picks up an assistant's newer revision when you come back to the tab.
- Quick one-off additions can still use a short **FinTrack import** (`"fintrack": "import"`), now including bills and income. Import links put the data after `#`, which browsers never send to the website.
- **Privacy note:** the file is plain text so assistants can read it; keep it somewhere private. What you share with an AI assistant goes to the company that runs it, under their privacy policy. FinTrack itself still sends nothing.

## How your data is saved

There's no server, so you keep your own data. Four options:

0. **Your FinTrack file (`fintrack.json`):** readable by you and by AI assistants; see above.
1. **Save code (works everywhere):** click **Save**, then **Copy to clipboard**, and paste it into a notepad file (e.g. `fintrack-save.txt`). Next time, click **Load** and paste it back.
   Add a **passphrase** and the code is encrypted (AES-256-GCM, PBKDF2 key). Without the passphrase it can't be read, and a forgotten passphrase can't be recovered.
2. **Auto-save file (Chrome / Edge on a computer):** link a `.json` file on your computer and every change is written to it automatically.
3. **Browser memory:** by default every change is kept in this browser automatically, so a backup code is only needed now and then (the status pill nudges you after 10 changes or a week). Turn this off in *Save & data* on shared computers.

Save codes are snapshots, so save again after making changes. The page warns you before closing if you haven't.

## Privacy

- The page includes a Content-Security-Policy that **blocks all network requests except reading `market.json` from this same site**, so it cannot send your data anywhere even if it wanted to. No third-party server is ever contacted from your browser.
- Market prices are fetched by a GitHub Action (`.github/workflows/market.yml`) a few times each weekday and saved to `market.json`. Prices are delayed, not real-time.
- No analytics, cookies, fonts or third-party scripts. One self-contained `index.html`.
- Anything loaded from a save code or an AI import is validated and sanitized before it's used.
- Note: every GitHub Pages site under the same account shares one browser origin (`username.github.io`). Only host pages you trust under the same account, or turn off "Remember my data in this browser".


## Disclaimer

Estimates use APR ÷ 12 monthly interest and assume no new charges, fees or rate changes. Real issuers calculate interest on average daily balance. This is a planning tool, not financial advice. Check numbers against your statements.

## License

MIT
