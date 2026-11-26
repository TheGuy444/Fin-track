---
name: fintrack
description: Manage a person's FinTrack file (fintrack.json) - their credit cards, APRs, bills, due dates, income and transactions - when they share it or ask to set one up. Use for "here's my FinTrack file", "add my trash bill", "I paid the Discover", "what's due this week", or any edit/question about a JSON file with "fintrack": "profile".
---

# FinTrack file manager

A FinTrack file (`fintrack.json`) is one person's finances in a file **they** keep. There is no account and no server. They load it at https://theguy444.github.io/Fin-track/ to see their dashboard, and they give it to you to update. You never log in anywhere and never fetch their data: you only work with the numbers and file they give you.

The file carries its own rules in `_agent.rules`. Follow them. This skill adds a script so the bookkeeping is exact rather than eyeballed.

## Every time

1. **Get the file.** If they attached or pasted it, save it as `base.json` exactly as given (a pasted chat message is fine; the script finds the JSON). If they don't have one, create it: `python scripts/fintrack.py new --out base.json --currency USD`, then fill it in from what they tell you.
2. **Questions only?** Run the matching read command and answer in plain words. No new file needed.
   - "What's due / coming up / did I miss anything?" → `python scripts/fintrack.py due base.json --days 14`
   - "Where do I stand / how much is left over / when am I debt-free?" → `python scripts/fintrack.py summary base.json`
3. **Changes:** copy `base.json` to `fintrack.json`, edit `fintrack.json` (in code, e.g. a short Python snippet that loads, changes and dumps the JSON with `indent=2`). Change only what they asked.
4. **Commit:** `python scripts/fintrack.py commit fintrack.json --base base.json --summary "Added trash bill: $35/mo, due the 15th"`. This validates, sets revision = base + 1, updatedAt, updatedBy and the log entry. If it prints ERROR lines, fix them and run it again. Never hand back a file that failed.
5. **Prove it:** `python scripts/fintrack.py diff base.json fintrack.json`. Every line should be something they asked for. If anything else changed, undo it.
6. **Hand it back:** one plain sentence of what changed, then the complete `fintrack.json` (as a file if you can share files, otherwise in one ```json block). Tell them: *save it over your old file, then Load it (or drop it) in FinTrack.* In voice chat, never read JSON aloud.

## How things map

| They say | You do |
|---|---|
| "Chase card, owe 3,400, 24.99%, I pay 200, due the 18th" | `cards` entry: id `chase`, name, balance 3400, apr 24.99, payment 200, dueDay 18 |
| "Trash bill is $35 a month, due the 15th" | `bills`: `{id:"trash", name:"Trash pickup", amount:35, category:"Utilities", frequency:"monthly", dueDay:15}` |
| "Car insurance, $390 every 3 months, next one Dec 10" | `bills`: frequency `quarterly`, nextDue `2026-12-10` |
| "Electric is usually around 120, due the 22nd" | `bills`: amount 120, dueDay 22, `variable: true` |
| "Phone's on autopay on my Chase" | that bill: `autopay: true`, `card: "chase"` |
| "I get paid 2,100 every other Friday, next one the 27th" | `income`: frequency `biweekly`, nextDue that Friday |
| "Paid the trash bill" | bill `lastPaid` = date; add expense transaction `{date, type:"expense", amount, category, description: bill name, bill:"trash"}` |
| "Paid 200 on the Chase" | card balance −200; `history` += `{id, card:"chase", date, kind:"payment", amount:200}` |
| "New charge, 80 at Target on the Discover" | card balance +80; `history` += `{kind:"charge"}`; expense transaction with `card` if they track spending |
| "Cancel Netflix" | remove that bill (mention they can undo by loading the previous file) |
| "Chase raised my APR to 27.24" | change only that card's `apr` |

Frequencies: `weekly`, `biweekly`, `monthly` (needs `dueDay`), `quarterly`, `yearly`, `once` (these need `nextDue`, any real due date). Short months use their last day. Ids are short, lowercase-with-dashes and unique across the whole file.

## Ask, don't guess

Ask one short question at a time when something that changes the math is missing: a card's APR or balance, a bill's amount or due day. If they don't know, leave the field out (`check` will remind you). Don't invent past months of transactions.

## Never

- Store card numbers, account numbers, CVV, PINs, passwords, SSNs or bank logins, even if they say them. `check` rejects number patterns that look like these. Use nicknames.
- Rewrite, reorder or "clean up" entries they didn't ask about. Unknown fields stay as they are.
- Present estimates as facts. Interest is approximated as APR/12; due dates come from what they told you. Say so briefly.

## If the file is huge

If the file has thousands of transactions and they're on a phone, you may instead give a small **FinTrack import** with only the new or changed items (format in `_agent.spec` → "Quick import"). The app merges it by id or name. Default to the full file.
