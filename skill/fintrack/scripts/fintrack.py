#!/usr/bin/env python3
"""FinTrack file helper for AI assistants (and people).

A FinTrack file (fintrack.json) holds one person's finances. They keep it; FinTrack's
dashboard (https://theguy444.github.io/Fin-track/) loads it, and an assistant edits it.
This script does the parts an assistant should not do by hand:

  check   FILE [--fix] [--out OUT]                validate (and optionally tidy) a file
  commit  FILE --summary "..." [--out OUT]        after editing: validate, revision+1, updatedAt, log entry
  diff    OLD NEW                                 list exactly what changed between two files
  due     FILE [--days 30] [--today YYYY-MM-DD]   overdue and upcoming bills, card payments and income
  summary FILE [--today YYYY-MM-DD]               totals: debt, monthly bills, income, left over, payoff
  new     [--out FILE] [--currency USD]           start an empty file

Standard library only. Exit code 1 when a file has errors.
The due-date rules match index.html exactly (see "schedules" there).
"""
import argparse
import calendar
import copy
import datetime as dt
import json
import re
import sys

SITE = "https://theguy444.github.io/Fin-track/"
FREQS = ("weekly", "biweekly", "monthly", "quarterly", "yearly", "once")
PER_MONTH = {"weekly": 52 / 12, "biweekly": 26 / 12, "monthly": 1, "quarterly": 1 / 3, "yearly": 1 / 12, "once": 0}
# A payment made up to this many days before a due date counts for that due date.
LEAD = {"weekly": 3, "biweekly": 7, "monthly": 15, "quarterly": 45, "yearly": 182, "once": 36500}
CURRENCIES = ("USD", "CAD", "EUR", "GBP", "AUD", "NZD", "INR", "JPY", "MXN", "ZAR", "CHF", "SEK", "NOK", "DKK", "SGD", "PHP", "BRL")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Sensitive numbers that must never be stored.
CARDNUM_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")

AGENT = {
    "what": "FinTrack file: the owner's personal finances. They keep this file; there is no account or server. They load it at " + SITE + " to see their dashboard.",
    "spec": SITE + "llms.txt",
    "rules": [
        "You are helping the owner keep this file up to date. Answer questions from it, and when they tell you something changed, edit it.",
        "After any edit, reply with a one-line summary and the COMPLETE updated file in a single ```json code block. Never send only a fragment unless they ask for an import.",
        "Change only what they asked. Keep every other entry, id and field exactly as it was, including fields you don't recognise.",
        "On every edit: revision + 1; updatedAt = current date-time (ISO 8601); updatedBy = \"assistant\"; append {\"rev\", \"at\", \"by\": \"assistant\", \"summary\"} to log.",
        "Numbers are plain numbers (3400, not \"$3,400\"). apr is a percent (24.99). Dates are YYYY-MM-DD.",
        "New items get a short unique id made from the name (\"trash\", \"chase-visa\"). Link to cards by id.",
        "bills and income repeat by frequency: weekly, biweekly, monthly, quarterly, yearly or once. monthly needs dueDay (1-31). The others need nextDue: any real due date; it repeats from there.",
        "\"I paid <bill>\": set that bill's lastPaid to the date and add an expense transaction (bill = its id) unless they say not to. \"I paid <card> $X\": subtract X from its balance and add a history entry {kind: \"payment\"}; no transaction unless asked.",
        "Ask one short question when something important is missing (a card's APR, a bill's due day). If they don't know, leave the field out; never guess.",
        "Never store card or account numbers, CVV, PINs, passwords, SSNs or logins, even if the owner types them. Use nicknames like \"Chase Visa\".",
        "If they share a file with a lower revision than one you produced earlier in this chat, ask which one is current before editing.",
        "Due dates, totals and payoff dates you give are estimates; tell them to check against their statements.",
    ],
}
README = ("This is a FinTrack file: your own finances, kept by you. There is no account and no server. Open " + SITE +
          " and Load (or drop) this file to see your dashboard. To have an AI assistant update it, give it this whole file "
          "and say what changed; the rules it follows are in _agent.")


# ---------------------------------------------------------------- io
def load(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Tolerate a pasted chat message: take the first {...} that parses.
        start = text.find("{")
        while start >= 0:
            depth, in_str, esc = 0, False, False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break
            start = text.find("{", start + 1)
        sys.exit(f"{path}: not valid JSON and no JSON object found in it.")


def save(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def to_date(s):
    try:
        return dt.date.fromisoformat(s) if isinstance(s, str) and DATE_RE.match(s) else None
    except ValueError:
        return None


def money(n, cur="USD"):
    sym = {"USD": "$", "CAD": "$", "AUD": "$", "NZD": "$", "SGD": "$", "MXN": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥", "PHP": "₱", "BRL": "R$", "ZAR": "R"}.get(cur, cur + " ")
    return f"{'-' if n < 0 else ''}{sym}{abs(n):,.2f}"


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v else None


# ---------------------------------------------------------------- schedules (mirror of index.html)
def ymd(y, m0, d):
    """Date for year y, 0-based month m0 (may overflow), day d clamped to the month's length."""
    y += m0 // 12
    m0 %= 12
    return dt.date(y, m0 + 1, min(d, calendar.monthrange(y, m0 + 1)[1]))


def sched_of(x):
    f = x.get("frequency") if x.get("frequency") in FREQS else "monthly"
    anchor = to_date(x.get("nextDue"))
    day = int(num(x.get("dueDay")) or 0)
    day = max(0, min(day, 31))
    if f == "monthly":
        if not day and anchor:
            day = anchor.day
        return {"f": f, "day": day} if day else None
    return {"f": f, "anchor": anchor} if anchor else None


def on_or_after(sc, x):
    f = sc["f"]
    if f == "monthly":
        c = ymd(x.year, x.month - 1, sc["day"])
        return c if c >= x else ymd(x.year, x.month, sc["day"])
    a = sc["anchor"]
    if f == "once":
        return a if a >= x else None
    if f in ("weekly", "biweekly"):
        st = 7 if f == "weekly" else 14
        n = -((a - x).days // st)  # ceil((x - a) / st)
        return a + dt.timedelta(days=n * st)
    st = 3 if f == "quarterly" else 12
    k = (((x.year - a.year) * 12 + (x.month - a.month)) // st) * st
    c = ymd(a.year, a.month - 1 + k, a.day)
    return c if c >= x else ymd(a.year, a.month - 1 + k + st, a.day)


def due_state(x, last_paid, autopay, today):
    """Next date this item needs paying, and whether it is overdue."""
    sc = sched_of(x)
    if not sc:
        return None
    if autopay or not last_paid:
        if sc["f"] == "once" and not autopay and not last_paid and sc["anchor"] < today:
            return {"date": sc["anchor"], "days": (sc["anchor"] - today).days, "status": "overdue", "sc": sc}
        nxt = on_or_after(sc, today)
        if not nxt:
            return {"status": "done", "sc": sc}
        return {"date": nxt, "days": (nxt - today).days, "status": "auto" if autopay else "due", "sc": sc}
    covered = on_or_after(sc, last_paid - dt.timedelta(days=LEAD[sc["f"]]))
    nxt = on_or_after(sc, covered + dt.timedelta(days=1)) if covered else None
    if not nxt:
        return {"status": "done", "paid": last_paid, "sc": sc}
    days = (nxt - today).days
    return {"date": nxt, "days": days, "status": "overdue" if days < 0 else "due", "paid": last_paid, "sc": sc}


def card_last_paid(f, c):
    dates = [to_date(h.get("date")) for h in f.get("history", []) if h.get("card", h.get("cardId")) == c.get("id") and h.get("kind") == "payment"]
    dates.append(to_date(c.get("lastPaid")))
    dates = [d for d in dates if d]
    return max(dates) if dates else None


# ---------------------------------------------------------------- validation
def check(f, fix=False):
    errors, warns = [], []
    if not isinstance(f, dict):
        return ["The file is not a JSON object."], []
    if f.get("fintrack") != "profile":
        if f.get("fintrack") == "import":
            errors.append('This is a FinTrack *import* (a one-off snippet), not a FinTrack file. Load it in the app, then download the file.')
            return errors, warns
        (warns if fix else errors).append('"fintrack" should be "profile".')
        if fix:
            f["fintrack"] = "profile"
    if f.get("version") != 3:
        (warns if fix else errors).append('"version" should be 3.')
        if fix:
            f["version"] = 3
    if not isinstance(f.get("revision"), int) or f["revision"] < 0:
        errors.append('"revision" must be a whole number (0 or more).')

    ids = {}

    def coerce_num(o, k, where):
        v = o.get(k)
        if v is None:
            return
        if isinstance(v, str) and fix:
            m = re.fullmatch(r"\s*\$?\s*(-?[\d,]*\.?\d+)\s*%?\s*", v)
            if m:
                o[k] = round(float(m.group(1).replace(",", "")), 2)
                warns.append(f"{where}: {k} was text {v!r}; changed to {o[k]}.")
                return
        if num(v) is None:
            errors.append(f"{where}: {k} must be a plain number (got {v!r}).")
        elif v < 0:
            errors.append(f"{where}: {k} can't be negative.")

    def check_id(o, where):
        i = o.get("id")
        if not isinstance(i, str) or not ID_RE.match(i):
            errors.append(f"{where}: id must be 1-40 letters, digits, - or _ (got {i!r}).")
        elif i in ids:
            errors.append(f"{where}: id {i!r} is already used by {ids[i]}.")
        else:
            ids[i] = where

    def check_date(o, k, where, required=False):
        v = o.get(k)
        if v is None:
            if required:
                errors.append(f"{where}: {k} is required (YYYY-MM-DD).")
            return
        if not to_date(v):
            errors.append(f"{where}: {k} must be a real date written YYYY-MM-DD (got {v!r}).")

    def check_sched(o, where):
        fr = o.get("frequency")
        if isinstance(fr, str) and fix and fr.lower().replace("-", "").replace(" ", "") in ("weekly", "biweekly", "monthly", "quarterly", "yearly", "once", "annual", "annually", "fortnightly", "everyotherweek"):
            fr = {"annual": "yearly", "annually": "yearly", "fortnightly": "biweekly", "everyotherweek": "biweekly"}.get(fr.lower().replace("-", "").replace(" ", ""), fr.lower().replace("-", "").replace(" ", ""))
            o["frequency"] = fr
        if fr not in FREQS:
            errors.append(f"{where}: frequency must be one of {', '.join(FREQS)} (got {fr!r}).")
            return
        dd = o.get("dueDay")
        if dd is not None and (not isinstance(dd, int) or not 1 <= dd <= 31):
            errors.append(f"{where}: dueDay must be a whole number 1-31 (got {dd!r}).")
        check_date(o, "nextDue", where)
        if fr == "monthly" and dd is None and o.get("nextDue") is None:
            warns.append(f"{where}: no dueDay, so FinTrack can't show when it's due. Ask the owner.")
        if fr != "monthly" and o.get("nextDue") is None:
            warns.append(f"{where}: {fr} needs nextDue (a real due date) to show when it's due. Ask the owner.")

    s = f.get("settings") or {}
    if s.get("currency") and s["currency"] not in CURRENCIES:
        errors.append(f"settings.currency {s['currency']!r} isn't supported ({', '.join(CURRENCIES)}).")

    cards = f.get("cards", [])
    for n, c in enumerate(cards):
        w = f"cards[{n}] {c.get('name', '?')!r}"
        check_id(c, w)
        if not str(c.get("name") or "").strip():
            errors.append(f"{w}: name is required.")
        for k in ("balance", "apr", "payment", "min", "limit", "startBalance", "step"):
            coerce_num(c, k, w)
        if num(c.get("apr")) is not None and c["apr"] > 100:
            errors.append(f"{w}: apr is a percent, 0-100 (got {c['apr']}).")
        if num(c.get("apr")) is not None and 0 < c["apr"] < 1:
            warns.append(f"{w}: apr {c['apr']} looks like a fraction; FinTrack wants a percent (e.g. 24.99).")
        if c.get("apr") is None and num(c.get("balance")):
            warns.append(f"{w}: no APR; payoff estimates will be too rosy. Ask the owner.")
        dd = c.get("dueDay")
        if dd is not None and (not isinstance(dd, int) or not 1 <= dd <= 31):
            errors.append(f"{w}: dueDay must be 1-31.")
        check_date(c, "lastPaid", w)
        if num(c.get("payment")) and num(c.get("balance")) and num(c.get("apr")) is not None and c["payment"] <= c["balance"] * c["apr"] / 1200:
            warns.append(f"{w}: the payment doesn't cover the monthly interest, so the balance won't go down.")
    card_ids = {c.get("id") for c in cards}
    if fix:  # links written as a card's name instead of its id are repaired
        by_name = {str(c.get("name", "")).strip().lower(): c.get("id") for c in cards}
        for sec, key in (("bills", "card"), ("history", "card"), ("transactions", "card")):
            for n, x in enumerate(f.get(sec, [])):
                v = x.get(key, x.get("cardId") if sec == "history" else None)
                if isinstance(v, str) and v and v not in card_ids and v.strip().lower() in by_name:
                    x[key] = by_name[v.strip().lower()]
                    x.pop("cardId", None)
                    warns.append(f"{sec}[{n}]: card {v!r} was a name; changed to its id {x[key]!r}.")

    for sec in ("bills", "income"):
        for n, b in enumerate(f.get(sec, [])):
            w = f"{sec}[{n}] {b.get('name', '?')!r}"
            check_id(b, w)
            if not str(b.get("name") or "").strip():
                errors.append(f"{w}: name is required.")
            coerce_num(b, "amount", w)
            if b.get("amount") is None:
                errors.append(f"{w}: amount is required.")
            check_sched(b, w)
            check_date(b, "lastPaid", w)
            if b.get("card") and b["card"] not in card_ids:
                errors.append(f"{w}: card {b['card']!r} isn't the id of any card.")

    for n, h in enumerate(f.get("history", [])):
        w = f"history[{n}]"
        if h.get("id") is not None:
            check_id(h, w)
        if h.get("card", h.get("cardId")) not in card_ids:
            errors.append(f"{w}: card {h.get('card')!r} isn't the id of any card.")
        if h.get("kind") not in ("payment", "charge"):
            errors.append(f"{w}: kind must be payment or charge.")
        check_date(h, "date", w, True)
        coerce_num(h, "amount", w)

    bill_ids = {b.get("id") for b in f.get("bills", [])}
    for n, t in enumerate(f.get("transactions", [])):
        w = f"transactions[{n}]"
        if t.get("id") is not None:
            check_id(t, w)
        if t.get("type") not in ("income", "expense"):
            errors.append(f"{w}: type must be income or expense.")
        check_date(t, "date", w, True)
        coerce_num(t, "amount", w)
        if t.get("card") and t["card"] not in card_ids:
            warns.append(f"{w}: card {t['card']!r} isn't a card id; FinTrack will keep it without a card.")
        if t.get("bill") and t["bill"] not in bill_ids:
            warns.append(f"{w}: bill {t['bill']!r} isn't a bill id.")

    # Sensitive data sweep over every string in the file except the instructions.
    def sweep(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if path == "" and k in ("_agent", "_readme", "$schema", "updatedAt"):
                    continue
                sweep(v, f"{path}.{k}" if path else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                sweep(v, f"{path}[{i}]")
        elif isinstance(o, str):
            if CARDNUM_RE.search(o) or SSN_RE.search(o):
                errors.append(f"{path}: looks like a card, account or ID number. Remove it; FinTrack never stores those.")
    sweep(f, "")

    if fix:
        f.setdefault("_agent", copy.deepcopy(AGENT))
        f.setdefault("_readme", README)
    elif "_agent" not in f:
        warns.append("No _agent block; run `check --fix` to add the assistant instructions.")
    return errors, warns


# ---------------------------------------------------------------- commands
def cmd_check(a):
    f = load(a.file)
    errors, warns = check(f, fix=a.fix)
    for w in warns:
        print("warning:", w)
    for e in errors:
        print("ERROR:", e)
    if a.fix and not errors:
        save(f, a.out or a.file)
        print("Tidied and saved to", a.out or a.file)
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


def cmd_commit(a):
    f = load(a.file)
    errors, warns = check(f, fix=True)
    for w in warns:
        print("warning:", w)
    if errors:
        for e in errors:
            print("ERROR:", e)
        print("Not saved. Fix the errors and run commit again.")
        return 1
    if a.base:
        base = load(a.base)
        if isinstance(base.get("revision"), int) and f.get("revision", 0) > base["revision"]:
            print(f"note: revision was already raised from {base['revision']} to {f['revision']}; using {base['revision'] + 1}.")
            f["revision"] = base["revision"]
    rev = int(f.get("revision") or 0) + 1
    at = now_iso()
    f["revision"], f["updatedAt"], f["updatedBy"] = rev, at, a.by
    f.setdefault("log", []).append({"rev": rev, "at": at, "by": a.by, "summary": a.summary[:200]})
    f["log"] = f["log"][-200:]
    save(f, a.out or a.file)
    print(f"Saved revision {rev} to {a.out or a.file}: {a.summary}")
    return 0


def _index(f, sec):
    return {x.get("id") or json.dumps(x, sort_keys=True): x for x in f.get(sec, []) if isinstance(x, dict)}


def cmd_diff(a):
    old, new = load(a.old), load(a.new)
    print(f"revision {old.get('revision')} -> {new.get('revision')}")
    changed = 0
    for sec in ("cards", "bills", "income", "history", "transactions"):
        o, n = _index(old, sec), _index(new, sec)
        for k in n.keys() - o.keys():
            print(f"+ {sec}: {n[k].get('name') or n[k].get('description') or k} {json.dumps(n[k], ensure_ascii=False)}")
            changed += 1
        for k in o.keys() - n.keys():
            print(f"- {sec}: {o[k].get('name') or o[k].get('description') or k} REMOVED")
            changed += 1
        for k in o.keys() & n.keys():
            for fld in sorted(set(o[k]) | set(n[k])):
                if o[k].get(fld) != n[k].get(fld):
                    print(f"~ {sec}[{k}].{fld}: {json.dumps(o[k].get(fld))} -> {json.dumps(n[k].get(fld))}")
                    changed += 1
    for k in sorted((set(old) | set(new)) - {"cards", "bills", "income", "history", "transactions", "log", "revision", "updatedAt", "updatedBy"}):
        if old.get(k) != new.get(k):
            print(f"~ {k} changed")
            changed += 1
    added_log = new.get("log", [])[len(old.get("log", [])):]
    for e in added_log:
        print(f"log: rev {e.get('rev')} by {e.get('by')}: {e.get('summary')}")
    print(f"{changed} change(s)")
    return 0


def upcoming(f, today, days):
    end = today + dt.timedelta(days=days)
    items = []
    for b in f.get("bills", []):
        st = due_state(b, to_date(b.get("lastPaid")), bool(b.get("autopay")), today)
        if not st or st["status"] == "done":
            continue
        d, n = st["date"], 0
        while d and d <= end and n < 10:
            first = n == 0
            items.append({"date": d, "kind": "bill", "name": b.get("name"), "amount": num(b.get("amount")) or 0, "approx": bool(b.get("variable")),
                          "status": st["status"] if first else ("auto" if b.get("autopay") else "due"), "id": b.get("id")})
            d = on_or_after(st["sc"], d + dt.timedelta(days=1))
            n += 1
    for c in f.get("cards", []):
        if not num(c.get("balance")) or not c.get("dueDay"):
            continue
        st = due_state({"frequency": "monthly", "dueDay": c["dueDay"]}, card_last_paid(f, c), bool(c.get("autopay")), today)
        if st and st["status"] != "done" and st["date"] <= end:
            items.append({"date": st["date"], "kind": "card", "name": c.get("name"), "amount": num(c.get("payment")) or num(c.get("min")) or 0,
                          "approx": False, "status": st["status"], "id": c.get("id")})
    for i in f.get("income", []):
        sc = sched_of(i)
        d, n = (on_or_after(sc, today) if sc else None), 0
        while d and d <= end and n < 10:
            items.append({"date": d, "kind": "income", "name": i.get("name"), "amount": num(i.get("amount")) or 0, "approx": False, "status": "income", "id": i.get("id")})
            d = on_or_after(sc, d + dt.timedelta(days=1))
            n += 1
    return sorted(items, key=lambda x: (x["date"], x["kind"] == "income"))


def cmd_due(a):
    f = load(a.file)
    today = to_date(a.today) or dt.date.today()
    cur = (f.get("settings") or {}).get("currency", "USD")
    items = upcoming(f, today, a.days)
    print(f"As of {today:%a %b %d, %Y}, next {a.days} days:")
    if not items:
        print("  nothing scheduled (bills need a dueDay or nextDue)")
    for x in items:
        delta = (x["date"] - today).days
        when = "TODAY" if delta == 0 else (f"{-delta} day(s) OVERDUE" if delta < 0 else f"in {delta} day(s)")
        tag = {"auto": " [autopay]", "overdue": " [OVERDUE]", "income": " [income]"}.get(x["status"], "")
        sign = "+" if x["kind"] == "income" else ""
        print(f"  {x['date']:%a %b %d}  {when:<20} {x['name']:<26} {sign}{'~' if x['approx'] else ''}{money(x['amount'], cur)}{tag}")
    out = sum(x["amount"] for x in items if x["kind"] != "income" and x["status"] != "auto")
    print(f"To pay yourself in this window (not autopay): {money(out, cur)}")
    return 0


def payoff_months(cards):
    bal = [num(c.get("balance")) or 0 for c in cards]
    months, total_int = 0, 0.0
    while sum(bal) > 0.005 and months < 600:
        months += 1
        before = sum(bal)
        for i, c in enumerate(cards):
            it = bal[i] * (num(c.get("apr")) or 0) / 1200
            bal[i] += it
            total_int += it
            bal[i] -= min(num(c.get("payment")) or 0, bal[i])
        if sum(bal) >= before - 0.001:
            return None, total_int
    return (months if sum(bal) <= 0.005 else None), total_int


def cmd_summary(a):
    f = load(a.file)
    today = to_date(a.today) or dt.date.today()
    cur = (f.get("settings") or {}).get("currency", "USD")
    cards = f.get("cards", [])
    debt = sum(num(c.get("balance")) or 0 for c in cards)
    pay = sum(num(c.get("payment")) or 0 for c in cards)
    bills = sum((num(b.get("amount")) or 0) * PER_MONTH.get(b.get("frequency"), 0) for b in f.get("bills", []))
    inc = sum((num(i.get("amount")) or 0) * PER_MONTH.get(i.get("frequency"), 0) for i in f.get("income", []))
    print(f"FinTrack file revision {f.get('revision')} (updated {f.get('updatedAt')} by {f.get('updatedBy')})")
    print(f"Cards: {len(cards)}, total owed {money(debt, cur)}" + (f", weighted APR {sum((num(c.get('balance')) or 0) * (num(c.get('apr')) or 0) for c in cards) / debt:.2f}%" if debt else ""))
    for c in cards:
        print(f"  - {c.get('name')}: {money(num(c.get('balance')) or 0, cur)} at {c.get('apr', '?')}% APR, paying {money(num(c.get('payment')) or 0, cur)}/mo" + (f", due day {c['dueDay']}" if c.get("dueDay") else ""))
    if debt:
        m, it = payoff_months(cards)
        if m:
            end = ymd(today.year, today.month - 1 + m, 1)
            print(f"At current payments: debt-free in about {m} months (~{end:%b %Y}), about {money(it, cur)} interest.")
        else:
            print("At current payments: not paying down (a payment doesn't cover its interest).")
    print(f"Per month: income {money(inc, cur)}, bills {money(bills, cur)}, card payments {money(pay, cur)}, left over {money(inc - bills - pay, cur)}")
    print("Estimates only (APR/12 monthly interest, no new charges).")
    return 0


def cmd_new(a):
    f = {"fintrack": "profile", "version": 3, "$schema": SITE + "fintrack.schema.json", "_readme": README, "_agent": copy.deepcopy(AGENT),
         "revision": 0, "updatedAt": now_iso(), "updatedBy": "assistant", "settings": {"currency": a.currency, "strategy": "avalanche"},
         "cards": [], "bills": [], "income": [], "history": [], "transactions": [], "log": []}
    save(f, a.out)
    print("Created", a.out)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("check"); c.add_argument("file"); c.add_argument("--fix", action="store_true"); c.add_argument("--out")
    c = sp.add_parser("commit"); c.add_argument("file"); c.add_argument("--summary", required=True); c.add_argument("--by", default="assistant"); c.add_argument("--out")
    c.add_argument("--base", help="the file as the owner gave it; keeps revision = base + 1 even if you already changed it")
    c = sp.add_parser("diff"); c.add_argument("old"); c.add_argument("new")
    c = sp.add_parser("due"); c.add_argument("file"); c.add_argument("--days", type=int, default=30); c.add_argument("--today")
    c = sp.add_parser("summary"); c.add_argument("file"); c.add_argument("--today")
    c = sp.add_parser("new"); c.add_argument("--out", default="fintrack.json"); c.add_argument("--currency", default="USD", choices=CURRENCIES)
    a = p.parse_args(argv)
    return {"check": cmd_check, "commit": cmd_commit, "diff": cmd_diff, "due": cmd_due, "summary": cmd_summary, "new": cmd_new}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
