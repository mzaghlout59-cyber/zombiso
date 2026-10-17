"""Raphael's daily report: one run, explained in plain language.

Built only from the run's event stream, so it always matches what the viewer and
Ultron saw. Written as report.html (open in any browser) and report.md (plain text)
in the run folder.
"""
import html
from collections import Counter
from datetime import datetime

from config import settings

WHY_CLOSED = {
    "take_profit": "hit its profit target",
    "stop_loss": "hit its stop-loss (safety exit)",
    "end_of_day": "closed at the end of the day",
}


def money(v):
    return ("-$" if v < 0 else "$") + f"{abs(v):,.2f}"


def signed(v):
    return ("+" if v >= 0 else "-") + f"${abs(v):,.2f}"


def _plain_reason(reason):
    """Aegis's technical reason, in everyday words."""
    r = reason or ""
    if "already holding" in r:
        return "already owned that stock"
    if "max open positions" in r:
        return f"already had {settings.MAX_OPEN_POSITIONS} trades open (the maximum)"
    if "daily loss limit" in r:
        return "today's loss limit was reached"
    if "losing streak" in r:
        return "too many losses in a row today"
    if "worst-case risk" in r:
        return "the trade would have risked too much money"
    if "stop-loss" in r:
        return "no safety exit (stop-loss)"
    return r


def summarize(events, meta=None, audit=None):
    """Turn a run's events into the facts the report shows."""
    meta = meta or {}
    start_equity = next((e["equity"] for e in events if e["kind"] == "treasury"),
                        meta.get("start_equity", settings.ACCOUNT_SIZE))
    briefing = next((e for e in events if e["kind"] == "briefing"), None)

    decisions, opened, trades = {}, {}, []
    blocked = Counter()
    for e in events:
        if e["kind"] == "decision":
            decisions[e["symbol"]] = e
            if e["action"] == "buy" and not e["executed"]:
                why = (_plain_reason(e.get("risk_reason")) if not e["approved"]
                       else "Sage wasn't confident enough")
                blocked[why] += 1
        elif e["kind"] == "trade_opened":
            d = decisions.get(e["symbol"], {})
            opened[e["trade_id"]] = {**e, "confidence": d.get("confidence"), "why": d.get("reasoning", "")}
        elif e["kind"] == "trade_closed":
            o = opened.pop(e["trade_id"], {})
            trades.append({
                "id": e["trade_id"], "symbol": e["symbol"], "size": e["size"],
                "entry": e["entry"], "exit": e["exit"], "pnl": e["pnl"],
                "closed_because": WHY_CLOSED.get(e["reason"], e["reason"]),
                "held": (e["tick"] - o["tick"]) if o.get("tick") is not None else None,
                "confidence": o.get("confidence"), "why": o.get("why", ""), "day": e["day"],
            })
    still_open = list(opened.values())

    realized = round(sum(t["pnl"] for t in trades), 2)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    days = sorted({t["day"] for t in trades})
    by_day = [{"day": d + 1, "pnl": round(sum(t["pnl"] for t in trades if t["day"] == d), 2),
               "trades": sum(1 for t in trades if t["day"] == d)} for d in days]
    max_risk = start_equity * settings.MAX_RISK_PER_TRADE_PCT / 100
    return {
        "source": meta.get("source", "simulated"),
        "run_id": meta.get("run_id", ""),
        "watchlist": meta.get("watchlist", []),
        "start_equity": start_equity,
        "end_equity": round(start_equity + realized, 2),
        "realized": realized,
        "pct": round(realized / start_equity * 100, 2) if start_equity else 0.0,
        "trades": trades,
        "still_open": still_open,
        "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100) if trades else None,
        "best": max(trades, key=lambda t: t["pnl"]) if trades else None,
        "worst": min(trades, key=lambda t: t["pnl"]) if trades else None,
        "blocked": blocked.most_common(),
        "by_day": by_day,
        "max_risk": max_risk,
        "over_limit": [t for t in trades if t["pnl"] < -max_risk],
        "briefing": briefing,
        "audit": audit,
    }


def headline(s):
    if not s["trades"]:
        return "No trades closed today. The city watched, but no setup passed all the safety rules."
    if s["realized"] > 0:
        result = f"made {money(s['realized'])} ({s['pct']:+.2f}%)"
    elif s["realized"] < 0:
        result = f"lost {money(-s['realized'])} ({s['pct']:+.2f}%)"
    else:
        result = "broke even"
    return f"The city {result}. Money: {money(s['start_equity'])} → {money(s['end_equity'])}."


def _what_it_means(s):
    lines = []
    if s["trades"]:
        lines.append(f"{s['wins']} of {len(s['trades'])} trades made money ({s['win_rate']}% win rate).")
    if s["blocked"]:
        total = sum(n for _, n in s["blocked"])
        lines.append(f"The safety rules stopped {total} possible buy(s); that is the city being careful, not a problem.")
    if s["over_limit"]:
        lines.append("A price jumped past a safety exit, so one loss was a bit bigger than planned. "
                     "This can happen in fast markets; the trade size already allows for it.")
    else:
        lines.append(f"Every loss stayed within the {money(s['max_risk'])} per-trade limit.")
    a = s["audit"]
    if a is not None:
        lines.append("Ultron checked every step and found no broken rules."
                     if a["ok"] else f"Ultron found {len(a['violations'])} broken rule(s): see below.")
    return lines


def to_markdown(s, date=None):
    date = date or datetime.now().strftime("%Y-%m-%d")
    kind = "Market day" if s["source"] == "alpaca" else "Practice run"
    out = [f"# Raphael's daily report: {date}", f"_{kind} · watching {', '.join(s['watchlist'])}_", "",
           f"**{headline(s)}**", "", "## In short"]
    out += [f"- {l}" for l in _what_it_means(s)] + [""]
    out += ["## The numbers",
            f"- Trades closed: {len(s['trades'])} ({s['wins']} wins, {s['losses']} losses)",
            f"- Profit / loss: {signed(s['realized'])}"]
    if s["best"]:
        out += [f"- Best trade: {s['best']['symbol']} {signed(s['best']['pnl'])}",
                f"- Worst trade: {s['worst']['symbol']} {signed(s['worst']['pnl'])}"]
    out += [""]
    if s["trades"]:
        out += ["## Every trade", "| # | Stock | Shares | Bought at | Sold at | Result | Why it ended |",
                "|---|---|---|---|---|---|---|"]
        out += [f"| {t['id']} | {t['symbol']} | {t['size']} | ${t['entry']:,.2f} | ${t['exit']:,.2f} | "
                f"{signed(t['pnl'])} | {t['closed_because']} |" for t in s["trades"]]
        out += [""]
    if s["still_open"]:
        out += ["## Still open", *[f"- {t['symbol']}: {t['size']} shares bought at ${t['entry']:,.2f}"
                                   for t in s["still_open"]], ""]
    if s["blocked"]:
        out += ["## Buys the safety rules stopped", *[f"- {why}: {n}×" for why, n in s["blocked"]], ""]
    b = s["briefing"]
    if b and b.get("status") == "active":
        out += ["## Morning briefing (Research)", b["summary"], ""]
    a = s["audit"]
    if a is not None:
        out += ["## Ultron's check", "Clean: no rule was broken." if a["ok"] else "Problems found:"]
        out += [f"- {v['message']}" for v in a["violations"]] + [""]
    h = s.get("hindsight")
    if h:
        out += ["## Hindsight's review", *[f"- {n}" for n in h["today"]], "",
                "**Advice so far:**", *[f"- {n}" for n in h.get("advice", [])], ""]
    return "\n".join(out)


def to_html(s, date=None):
    date = date or datetime.now().strftime("%Y-%m-%d")
    esc = html.escape
    kind = "Market day" if s["source"] == "alpaca" else "Practice run"
    tone = "pos" if s["realized"] > 0 else "neg" if s["realized"] < 0 else ""
    rows = "".join(
        f"<tr><td>{t['id']}</td><td><b>{esc(t['symbol'])}</b></td><td>{t['size']}</td>"
        f"<td>${t['entry']:,.2f}</td><td>${t['exit']:,.2f}</td>"
        f"<td class='{'pos' if t['pnl'] > 0 else 'neg'}'>{signed(t['pnl'])}</td>"
        f"<td>{esc(t['closed_because'])}</td></tr>" for t in s["trades"])
    tiles = [("Profit / loss", signed(s["realized"]), tone),
             ("Money now", money(s["end_equity"]), ""),
             ("Trades", f"{s['wins']} won · {s['losses']} lost", ""),
             ("Win rate", f"{s['win_rate']}%" if s["win_rate"] is not None else "–", "")]
    a = s["audit"]
    sections = [f"<ul>{''.join(f'<li>{esc(l)}</li>' for l in _what_it_means(s))}</ul>"]
    body = [
        f"<header><p class='kicker'>{kind} · {esc(date)} · watching {esc(', '.join(s['watchlist']))}</p>",
        "<h1>Raphael's daily report</h1>",
        f"<p class='headline {tone}'>{esc(headline(s))}</p></header>",
        "<section class='tiles'>" + "".join(
            f"<div class='tile'><span>{k}</span><b class='{c}'>{esc(v)}</b></div>" for k, v, c in tiles) + "</section>",
        "<section><h2>In short</h2>" + sections[0] + "</section>",
    ]
    if s["trades"]:
        body.append("<section><h2>Every trade</h2><div class='scroll'><table><thead><tr><th>#</th><th>Stock</th>"
                    "<th>Shares</th><th>Bought at</th><th>Sold at</th><th>Result</th><th>Why it ended</th>"
                    f"</tr></thead><tbody>{rows}</tbody></table></div></section>")
    if s["still_open"]:
        body.append("<section><h2>Still open</h2><ul>" + "".join(
            f"<li><b>{esc(t['symbol'])}</b>: {t['size']} shares bought at ${t['entry']:,.2f}</li>"
            for t in s["still_open"]) + "</ul></section>")
    if s["blocked"]:
        body.append("<section><h2>Buys the safety rules stopped</h2><ul>" + "".join(
            f"<li>{esc(why)}: <b>{n}×</b></li>" for why, n in s["blocked"]) + "</ul></section>")
    b = s["briefing"]
    if b and b.get("status") == "active":
        body.append(f"<section><h2>Morning briefing</h2><p>{esc(b['summary'])}</p></section>")
    if a is not None:
        verdict = ("<p class='pos'><b>Clean:</b> no rule was broken.</p>" if a["ok"] else
                   "<ul>" + "".join(f"<li class='neg'>{esc(v['message'])}</li>" for v in a["violations"]) + "</ul>")
        body.append(f"<section><h2>Ultron's check</h2>{verdict}</section>")
    h = s.get("hindsight")
    if h:
        body.append("<section><h2>Hindsight's review</h2><ul>"
                    + "".join(f"<li>{esc(n)}</li>" for n in h["today"])
                    + "</ul><p><b>Advice so far:</b></p><ul>"
                    + "".join(f"<li>{esc(n)}</li>" for n in h.get("advice", [])) + "</ul></section>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Raphael's report {esc(date)}</title><style>
:root {{ --bg:#0b1020; --panel:#131b31; --text:#e6ecf8; --muted:#8e9ab8; --green:#4cd497; --red:#ff6b6b; --gold:#f2b84b; }}
@media (prefers-color-scheme: light) {{ :root {{ --bg:#f6f7fb; --panel:#fff; --text:#1b2135; --muted:#5d6782; --green:#178a55; --red:#c63d3d; --gold:#a8750c; }} }}
body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.6 "Segoe UI",system-ui,sans-serif; }}
main {{ max-width:860px; margin:0 auto; padding:32px 16px 64px; }}
.kicker {{ color:var(--muted); margin:0; font-size:14px; }} h1 {{ margin:4px 0 8px; font-size:30px; }}
.headline {{ font-size:20px; font-weight:600; margin:0 0 24px; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin-bottom:12px; }}
.tile {{ background:var(--panel); border-radius:12px; padding:14px 16px; }}
.tile span {{ display:block; color:var(--muted); font-size:13px; }} .tile b {{ font-size:22px; }}
section {{ background:var(--panel); border-radius:12px; padding:6px 20px 14px; margin-top:12px; }}
section.tiles {{ background:none; padding:0; }} h2 {{ font-size:17px; margin:14px 0 8px; color:var(--gold); }}
.scroll {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-size:14px; }}
th,td {{ text-align:left; padding:7px 8px; border-bottom:1px solid rgba(128,140,170,.2); white-space:nowrap; }}
th {{ color:var(--muted); font-weight:600; }} .pos {{ color:var(--green); }} .neg {{ color:var(--red); }}
</style></head><body><main>{''.join(body)}</main></body></html>"""


def write_report(run_dir, events, meta=None, audit=None, hindsight=None):
    """Write report.html and report.md into the run folder. Returns the summary.
    hindsight: the day's Hindsight review, added as its own section when given."""
    s = summarize(events, meta, audit)
    s["hindsight"] = hindsight
    (run_dir / "report.html").write_text(to_html(s), encoding="utf-8")
    (run_dir / "report.md").write_text(to_markdown(s), encoding="utf-8")
    return s
