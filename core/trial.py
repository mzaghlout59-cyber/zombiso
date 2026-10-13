"""The paper trial: N real market days on pretend money, judged by rules fixed up front.

Reads the market-day runs (real Alpaca prices) since the trial started and answers:
did the city make money, did it stay safe, and which agents helped or hurt?
An agent "votes" buy or sell with its reading; when a trade closes, every agent
that voted is scored right or wrong. Agents below the bar are marked for replacement.
"""
import json
from datetime import date, datetime
from html import escape
from pathlib import Path

from config import settings

TRIAL_DIR = Path("data/trial")
TREASURY_PATH = Path("data/treasury.json")

# agent_report name -> (city name, field it reads, how that reading votes)
VOTERS = {
    "MarketResearch": ("Scout", "trend", {"up": "buy", "down": "sell"}),
    "Sentiment": ("Pulse", "crowd_mood", {"bullish": "buy", "bearish": "sell"}),
    "Charts": ("Lens", "pattern", {"breakout": "buy", "breakdown": "sell"}),
    "NewsResearch": ("News", "sentiment", {"positive": "buy", "negative": "sell"}),
}


def start(days=None, trial_dir=TRIAL_DIR, treasury_path=TREASURY_PATH, today=None):
    """Begin a trial. The Treasury restarts at ACCOUNT_SIZE; an older balance is kept aside, not deleted."""
    today = today or date.today().isoformat()
    trial_dir.mkdir(parents=True, exist_ok=True)
    if treasury_path.exists():
        treasury_path.rename(treasury_path.with_name(f"treasury.before-trial-{today}.json"))
    trial = {"started": today, "days": days or settings.TRIAL_DAYS}
    (trial_dir / "trial.json").write_text(json.dumps(trial, indent=2), encoding="utf-8")
    return trial


def load(trial_dir=TRIAL_DIR):
    path = trial_dir / "trial.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def run_date(run_dir):
    """Run folders are named YYYYMMDD-HHMMSS-ffffff."""
    return datetime.strptime(run_dir.name[:8], "%Y%m%d").date().isoformat()


def market_runs(runs_dir, since):
    """Finished real-market runs on or after `since`, oldest first."""
    if not runs_dir.is_dir():
        return []
    out = []
    for d in sorted(runs_dir.iterdir()):
        meta_path, audit_path = d / "meta.json", d / "audit.json"
        if not (meta_path.exists() and audit_path.exists()):
            continue  # not finished (or not a run)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("source") == "alpaca" and run_date(d) >= since:
            out.append(d)
    return out


def _events(run_dir):
    with (run_dir / "events.jsonl").open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def score(run_dirs):
    """Totals, per-day results and per-agent accuracy across the runs."""
    days, closes = [], []
    agents = {name: {"right": 0, "wrong": 0} for name, _, _ in VOTERS.values()}
    agents["Axiom"] = {"right": 0, "wrong": 0}  # the Strategist proposes every trade
    for d in run_dirs:
        events = _events(d)
        audit = json.loads((d / "audit.json").read_text(encoding="utf-8"))
        start_eq = next((e["equity"] for e in events if e["kind"] == "treasury"), settings.ACCOUNT_SIZE)
        reports, votes, day_pnl, day_closes = {}, {}, 0.0, 0
        for e in events:
            if e["kind"] == "agent_report" and e["agent"] in VOTERS:
                reports[(e["tick"], e["symbol"], e["agent"])] = e["result"] or {}
            elif e["kind"] == "trade_opened":
                v = {}
                for agent, (name, field, rule) in VOTERS.items():
                    reading = reports.get((e["tick"], e["symbol"], agent), {}).get(field)
                    if reading in rule:
                        v[name] = rule[reading]
                v["Axiom"] = "buy"
                votes[e["trade_id"]] = v
            elif e["kind"] == "trade_closed":
                won = e["pnl"] > 0
                for name, vote in votes.pop(e["trade_id"], {}).items():
                    right = won if vote == "buy" else not won
                    agents[name]["right" if right else "wrong"] += 1
                day_pnl += e["pnl"]
                day_closes += 1
                closes.append(e["pnl"])
        days.append({"date": run_date(d), "run": d.name, "pnl": round(day_pnl, 2), "trades": day_closes,
                     "start_equity": start_eq, "end_equity": round(start_eq + day_pnl, 2),
                     "ultron_ok": audit["ok"]})

    start_equity = days[0]["start_equity"] if days else settings.ACCOUNT_SIZE
    equity = peak = start_equity
    max_drawdown = 0.0
    for pnl in closes:  # biggest drop from a high point, trade by trade
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    wins = [p for p in closes if p > 0]
    gross_loss = -sum(p for p in closes if p <= 0)
    for a in agents.values():
        n = a["right"] + a["wrong"]
        a["votes"] = n
        a["accuracy"] = round(a["right"] / n * 100) if n else None
    return {
        "days": days,
        "start_equity": start_equity,
        "end_equity": round(start_equity + sum(closes), 2),
        "pnl": round(sum(closes), 2),
        "trades": len(closes),
        "wins": len(wins),
        "win_rate": round(len(wins) / len(closes) * 100) if closes else None,
        "profit_factor": round(sum(wins) / gross_loss, 2) if gross_loss > 0 else None,
        "max_drawdown": round(max_drawdown, 2),
        "agents": agents,
    }


def verdict(s, trial):
    """The pass/fail checks, fixed before the trial started (see TRIAL_* in config/settings.py)."""
    max_dd = s["start_equity"] * settings.TRIAL_MAX_DRAWDOWN_PCT / 100
    checks = [
        ("Made money overall", s["pnl"] > 0, f"{'+' if s['pnl'] >= 0 else '-'}${abs(s['pnl']):,.2f}"),
        ("Ultron found no broken rules, every day", all(d["ultron_ok"] for d in s["days"]),
         f"{sum(d['ultron_ok'] for d in s['days'])} of {len(s['days'])} days clean"),
        (f"Never fell more than {settings.TRIAL_MAX_DRAWDOWN_PCT}% below its best point",
         s["max_drawdown"] <= max_dd, f"worst drop ${s['max_drawdown']:,.2f} (limit ${max_dd:,.2f})"),
        (f"At least {settings.TRIAL_MIN_TRADES} trades, enough to judge", s["trades"] >= settings.TRIAL_MIN_TRADES,
         f"{s['trades']} trades"),
    ]
    replace = [name for name, a in s["agents"].items()
               if a["votes"] >= settings.TRIAL_MIN_AGENT_VOTES and a["accuracy"] < settings.TRIAL_MIN_AGENT_ACCURACY]
    done = len(s["days"]) >= trial["days"]
    status = "running" if not done else ("passed" if all(ok for _, ok, _ in checks) else "failed")
    return {"status": status, "days_done": len(s["days"]), "days_total": trial["days"],
            "checks": checks, "replace": replace}


def to_html(s, v, trial):
    title = {"running": f"Day {v['days_done']} of {v['days_total']}: trial in progress",
             "passed": "Trial passed: this team of agents earned its place",
             "failed": "Trial failed: time to change the team"}[v["status"]]
    tone = {"running": "gold", "passed": "pos", "failed": "neg"}[v["status"]]
    checks = "".join(
        f"<li><b class='{'pos' if ok else 'neg'}'>{'✓' if ok else '✗'}</b> {escape(label)} "
        f"<span class='muted'>({escape(detail)})</span></li>" for label, ok, detail in v["checks"])
    days = "".join(
        f"<tr><td>{d['date']}</td><td class='{'pos' if d['pnl'] > 0 else 'neg' if d['pnl'] < 0 else ''}'>"
        f"{'+' if d['pnl'] >= 0 else '-'}${abs(d['pnl']):,.2f}</td><td>{d['trades']}</td>"
        f"<td>${d['end_equity']:,.2f}</td><td>{'✓ clean' if d['ultron_ok'] else '✗ problems'}</td>"
        f"<td><a href='../runs/{d['run']}/report.html'>report</a></td></tr>" for d in s["days"])
    agent_rows = ""
    for name, a in sorted(s["agents"].items(), key=lambda kv: -(kv[1]["accuracy"] or -1)):
        acc = "not enough votes yet" if a["votes"] < settings.TRIAL_MIN_AGENT_VOTES else f"{a['accuracy']}% right"
        fate = ("replace" if name in v["replace"] else "keep") if a["votes"] >= settings.TRIAL_MIN_AGENT_VOTES else "–"
        agent_rows += (f"<tr><td><b>{name}</b></td><td>{a['votes']}</td><td>{acc}</td>"
                       f"<td class='{'neg' if fate == 'replace' else 'pos' if fate == 'keep' else ''}'>{fate}</td></tr>")
    pf = s["profit_factor"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Trial scorecard</title><style>
:root {{ --bg:#0b1020; --panel:#131b31; --text:#e6ecf8; --muted:#8e9ab8; --green:#4cd497; --red:#ff6b6b; --gold:#f2b84b; }}
@media (prefers-color-scheme: light) {{ :root {{ --bg:#f6f7fb; --panel:#fff; --text:#1b2135; --muted:#5d6782; --green:#178a55; --red:#c63d3d; --gold:#a8750c; }} }}
body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.6 "Segoe UI",system-ui,sans-serif; }}
main {{ max-width:860px; margin:0 auto; padding:32px 16px 64px; }} h1 {{ font-size:28px; margin:4px 0 16px; }}
.kicker,.muted {{ color:var(--muted); }} .kicker {{ margin:0; font-size:14px; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }}
.tile,section {{ background:var(--panel); border-radius:12px; padding:14px 18px; }} section {{ margin-top:12px; }}
.tile span {{ display:block; color:var(--muted); font-size:13px; }} .tile b {{ font-size:22px; }}
h2 {{ font-size:17px; color:var(--gold); margin:4px 0 8px; }} ul {{ list-style:none; padding:0; margin:0; }} li {{ margin:4px 0; }}
.scroll {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-size:14px; }}
th,td {{ text-align:left; padding:7px 8px; border-bottom:1px solid rgba(128,140,170,.2); white-space:nowrap; }}
th {{ color:var(--muted); }} a {{ color:var(--gold); }}
.pos {{ color:var(--green); }} .neg {{ color:var(--red); }} .gold {{ color:var(--gold); }}
</style></head><body><main>
<p class="kicker">Paper trial · started {escape(trial['started'])} · {v['days_done']} of {v['days_total']} market days</p>
<h1 class="{tone}">{escape(title)}</h1>
<div class="tiles">
<div class="tile"><span>Profit / loss</span><b class="{'pos' if s['pnl'] > 0 else 'neg' if s['pnl'] < 0 else ''}">{'+' if s['pnl'] >= 0 else '-'}${abs(s['pnl']):,.2f}</b></div>
<div class="tile"><span>Money now</span><b>${s['end_equity']:,.2f}</b></div>
<div class="tile"><span>Win rate</span><b>{f"{s['win_rate']}%" if s['win_rate'] is not None else '–'}</b></div>
<div class="tile"><span>Profit factor</span><b>{pf if pf is not None else '–'}</b></div>
</div>
<section><h2>The rules it must pass</h2><ul>{checks}</ul>
<p class="muted">Profit factor = money won ÷ money lost. Above 1 means the wins outweigh the losses.</p></section>
<section><h2>Agents: who helped, who hurt</h2>
<p class="muted">Each time a trade closes, every agent that voted on it is scored. Below {settings.TRIAL_MIN_AGENT_ACCURACY}% right (after at least {settings.TRIAL_MIN_AGENT_VOTES} votes) means the agent should be replaced.</p>
<div class="scroll"><table><thead><tr><th>Agent</th><th>Votes</th><th>Accuracy</th><th>Verdict</th></tr></thead><tbody>{agent_rows}</tbody></table></div></section>
<section><h2>Day by day</h2><div class="scroll"><table><thead><tr><th>Date</th><th>Result</th><th>Trades</th><th>Money after</th><th>Ultron</th><th></th></tr></thead>
<tbody>{days or "<tr><td colspan='6' class='muted'>No market days yet. The first one runs at 10:00 on the next weekday.</td></tr>"}</tbody></table></div></section>
</main></body></html>"""


def update(runs_dir=Path("data/runs"), trial_dir=TRIAL_DIR):
    """Rebuild the scorecard. Returns (summary, verdict), or None if no trial has started."""
    trial = load(trial_dir)
    if trial is None:
        return None
    runs = market_runs(runs_dir, trial["started"])
    s = score(runs)
    v = verdict(s, trial)
    (trial_dir / "scorecard.html").write_text(to_html(s, v, trial), encoding="utf-8")
    # For the viewer's survival board: finished days only; the viewer adds today live.
    (trial_dir / "scores.json").write_text(json.dumps({
        "started": trial["started"], "days_done": v["days_done"], "days_total": v["days_total"],
        "status": v["status"], "runs": [d.name for d in runs], "agents": s["agents"],
        "min_votes": settings.TRIAL_MIN_AGENT_VOTES, "min_accuracy": settings.TRIAL_MIN_AGENT_ACCURACY,
    }, indent=2), encoding="utf-8")
    return s, v
