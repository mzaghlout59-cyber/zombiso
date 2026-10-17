"""Hindsight: reviews every closed trade against the real minute-by-minute prices.

After each market day it answers, per trade: when was the best moment to sell, how low did
it go, what would selling earlier or later have given, and would a different selling rule
have done better? It also scores buys by the hour they were made. Day by day it keeps a
record, and only gives advice once the evidence covers several days, because one day of
hindsight is easy to fool.

Hindsight advises only. It never changes how the city trades: any rule it recommends
needs Master Mohamad's yes first.
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.base_agent import BaseAgent

NY = timezone(timedelta(hours=-4))  # US Eastern daylight time (the trial runs in October)
HISTORY_PATH = Path("data/hindsight/history.json")

# Selling rules replayed on every trade. R = the trade's planned risk per share (entry - stop).
RULES = {
    "current": "today's rule: safety exit, target at 2R, close at the bell",
    "break_even": "once up 1R, move the safety exit up to the buy price",
    "trailing": "safety exit follows the highest price, 1R below it",
    "target_1r": "take profit at 1R instead of 2R",
    "one_hour": "sell 60 minutes after buying (or earlier at the safety exit)",
}
MIN_DAYS, MIN_TRADES, MIN_HOUR_TRADES = 3, 10, 3  # evidence needed before advising


def _t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def simulate(rule, bars, entry, stop, size, entry_time):
    """Replay one selling rule over minute bars after the buy. Returns (exit_price, minute, reason).
    If a bar touches both the exit and the target, the exit is assumed to come first (cautious)."""
    R = entry - stop
    target = entry + (R if rule == "target_1r" else 2 * R)
    exit_level, high = stop, entry
    for i, b in enumerate(bars):
        if rule == "one_hour" and _t(b["t"]) >= entry_time + timedelta(minutes=60):
            return b["o"], i, "time"
        if b["l"] <= exit_level:
            return min(exit_level, b["o"]), i, "stop"
        if b["h"] >= target:
            return max(target, b["o"]), i, "target"
        high = max(high, b["h"])
        if rule == "break_even" and high >= entry + R:
            exit_level = max(exit_level, entry)
        elif rule == "trailing":
            exit_level = max(exit_level, high - R)
    return (bars[-1]["c"], len(bars) - 1, "close") if bars else (entry, 0, "no data")


def review_trade(trade, bars, session_end):
    """trade: {"symbol","size","entry","stop_loss","bought_at","sold_at","exit","pnl","reason"}"""
    entry, stop, size = trade["entry"], trade["stop_loss"], trade["size"]
    t_in = trade["bought_at"]
    after = [b for b in bars if t_in <= _t(b["t"]) < session_end]
    if not after:
        return None
    best = max(after, key=lambda b: b["h"])
    worst = min(after, key=lambda b: b["l"])

    def sell_after(minutes):
        cut = t_in + timedelta(minutes=minutes)
        b = next((b for b in after if _t(b["t"]) >= cut), None)
        return round((b["o"] - entry) * size, 2) if b else None

    rules = {}
    for name in RULES:
        price, minute, why = simulate(name, after, entry, stop, size, t_in)
        rules[name] = {"pnl": round((price - entry) * size, 2), "exit_after_min": minute, "how": why}
    return {
        "symbol": trade["symbol"], "size": size, "entry": entry, "stop_loss": stop,
        "bought_at": t_in.astimezone(NY).strftime("%H:%M"),
        "buy_hour": t_in.astimezone(NY).hour,
        "actual_pnl": trade["pnl"], "actual_reason": trade["reason"],
        "best_pnl": round((best["h"] - entry) * size, 2),
        "best_at": _t(best["t"]).astimezone(NY).strftime("%H:%M"),
        "worst_pnl": round((worst["l"] - entry) * size, 2),
        "reached_target": best["h"] >= entry + 2 * (entry - stop),
        "sell_after_15": sell_after(15), "sell_after_30": sell_after(30), "sell_after_60": sell_after(60),
        "held_to_close": round((after[-1]["c"] - entry) * size, 2),
        "rules": rules,
    }


class Hindsight(BaseAgent):
    name = "Hindsight"
    alias = "Hindsight"
    division = "Review"
    rank = "Commander"
    commander = "Raphael"
    purpose = ("Reviews every closed trade on real minute prices: best time to sell, what other "
               "selling rules would have done, and which buying hours work. Advises only.")

    def __init__(self, bars_source=None, history_path=HISTORY_PATH):
        """bars_source(symbol, start, end) -> minute bars; defaults to Alpaca (read-only)."""
        if bars_source is None:
            from core.alpaca import fetch_minute_bars
            bars_source = fetch_minute_bars
        self.bars_source = bars_source
        self.history_path = Path(history_path)

    def handle(self, task):
        return self.review_day(Path(task["run_dir"]))

    # ---------- one day ----------
    def trades_from_run(self, run_dir):
        events = [json.loads(l) for l in (run_dir / "events.jsonl").open(encoding="utf-8") if l.strip()]
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        interval = meta.get("interval_s") or 300
        started = datetime.strptime(run_dir.name[:15], "%Y%m%d-%H%M%S").replace(
            tzinfo=timezone(timedelta(hours=-3)))  # run folders are named in Brasilia time

        def when(e):  # real time of an event; older runs had no "at", so estimate from the tick
            return _t(e["at"]) if e.get("at") else started + timedelta(seconds=(e["tick"] - 1) * interval)

        opened = {e["trade_id"]: e for e in events if e["kind"] == "trade_opened"}
        out = []
        for e in events:
            if e["kind"] == "trade_closed" and e["trade_id"] in opened:
                o = opened[e["trade_id"]]
                out.append({"symbol": e["symbol"], "size": e["size"], "entry": e["entry"],
                            "stop_loss": e["stop_loss"], "bought_at": when(o), "sold_at": when(e),
                            "exit": e["exit"], "pnl": e["pnl"], "reason": e["reason"]})
        return out

    def review_day(self, run_dir):
        run_dir = Path(run_dir)
        trades = self.trades_from_run(run_dir)
        day = datetime.strptime(run_dir.name[:8], "%Y%m%d").date()
        session_end = datetime(day.year, day.month, day.day, 16, 0, tzinfo=NY)
        reviews, bars_cache = [], {}
        for t in trades:
            if t["symbol"] not in bars_cache:
                bars_cache[t["symbol"]] = self.bars_source(
                    t["symbol"], datetime(day.year, day.month, day.day, 9, 30, tzinfo=NY), session_end)
            r = review_trade(t, bars_cache[t["symbol"]], session_end)
            if r:
                reviews.append(r)
        totals = {name: round(sum(r["rules"][name]["pnl"] for r in reviews), 2) for name in RULES}
        review = {
            "date": day.isoformat(), "run": run_dir.name, "trades": reviews,
            "actual_total": round(sum(r["actual_pnl"] for r in reviews), 2),
            "rule_totals": totals,
            "best_possible": round(sum(max(r["best_pnl"], 0) for r in reviews), 2),
            "reached_target": sum(r["reached_target"] for r in reviews),
        }
        review["today"] = self.today_notes(review)
        (run_dir / "hindsight.json").write_text(json.dumps(review, indent=2), encoding="utf-8")
        self.remember(review)
        review["advice"] = self.advice()
        self.say(f"Reviewed {len(reviews)} trades for {day}: {review['today'][0] if review['today'] else ''}")
        return review

    @staticmethod
    def today_notes(review):
        if not review["trades"]:
            return ["No trades closed today, nothing to review."]
        t, totals = review["trades"], review["rule_totals"]
        best_rule = max(totals, key=totals.get)
        notes = [f"Actual result {review['actual_total']:+.2f}; with perfect timing the trades could have made "
                 f"up to {review['best_possible']:+.2f}."]
        if best_rule != "current" and totals[best_rule] > totals["current"]:
            notes.append(f"Best selling rule today: {RULES[best_rule]} ({totals[best_rule]:+.2f} vs "
                         f"{totals['current']:+.2f} with today's rule). One day only, not advice yet.")
        else:
            notes.append(f"Today's selling rule was as good as any alternative ({totals['current']:+.2f}).")
        went_up = sum(1 for r in t if r["best_pnl"] > 0 and r["actual_pnl"] <= 0)
        if went_up:
            notes.append(f"{went_up} of {len(t)} losing trades were in profit at some point before turning down.")
        notes.append(f"{review['reached_target']} of {len(t)} trades ever reached their profit target.")
        return notes

    # ---------- the week ----------
    def remember(self, review):
        history = self.history()
        history = [h for h in history if h["date"] != review["date"]] + [{
            "date": review["date"], "actual_total": review["actual_total"],
            "rule_totals": review["rule_totals"],
            "trades": [{k: r[k] for k in ("symbol", "buy_hour", "actual_pnl", "best_pnl", "reached_target")}
                       for r in review["trades"]],
        }]
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(json.dumps(sorted(history, key=lambda h: h["date"]), indent=2),
                                     encoding="utf-8")

    def history(self):
        if self.history_path.exists():
            return json.loads(self.history_path.read_text(encoding="utf-8"))
        return []

    def advice(self):
        """Plain-language advice from all reviewed days, only where the evidence is enough."""
        h = self.history()
        trades = [t for d in h for t in d["trades"]]
        if len(h) < MIN_DAYS or len(trades) < MIN_TRADES:
            return [f"Still collecting evidence: {len(h)} day(s), {len(trades)} trade(s) reviewed. "
                    f"Advice starts after {MIN_DAYS} days and {MIN_TRADES} trades."]
        out = []
        totals = defaultdict(float)
        for d in h:
            for name, v in d["rule_totals"].items():
                totals[name] += v
        best = max(totals, key=totals.get)
        days_better = sum(1 for d in h if d["rule_totals"][best] > d["rule_totals"]["current"])
        if best != "current" and days_better > len(h) / 2:
            out.append(f"Selling: \"{RULES[best]}\" would have made {totals[best]:+.2f} over {len(h)} days, "
                       f"vs {totals['current']:+.2f} with today's rule, and was better on {days_better} of "
                       f"{len(h)} days. Worth considering.")
        else:
            out.append(f"Selling: no alternative rule beat today's rule consistently ({totals['current']:+.2f} "
                       f"over {len(h)} days).")
        by_hour = defaultdict(list)
        for t in trades:
            by_hour[t["buy_hour"]].append(t["actual_pnl"])
        for hour, pnls in sorted(by_hour.items()):
            if len(pnls) < MIN_HOUR_TRADES:
                continue
            wins = sum(p > 0 for p in pnls)
            label = f"{hour:02d}:00-{hour:02d}:59 New York ({hour + 1:02d}:00-{hour + 1:02d}:59 Brasilia)"
            if sum(pnls) < 0 and wins / len(pnls) < 0.3:
                out.append(f"Buying: trades bought {label} did badly ({wins}/{len(pnls)} wins, "
                           f"{sum(pnls):+.2f}). Consider avoiding that hour.")
            elif sum(pnls) > 0 and wins / len(pnls) >= 0.5:
                out.append(f"Buying: trades bought {label} did well ({wins}/{len(pnls)} wins, {sum(pnls):+.2f}).")
        turned = sum(1 for t in trades if t["best_pnl"] > 0 and t["actual_pnl"] <= 0)
        if turned >= len(trades) / 2:
            out.append(f"Pattern: {turned} of {len(trades)} trades were up at some point and still ended as "
                       f"losses. A profit-protecting rule may help.")
        return out

    @staticmethod
    def to_markdown(review):
        lines = [f"# Hindsight review: {review['date']}", ""]
        lines += [f"- {n}" for n in review["today"]] + ["", "## Trade by trade",
                  "| Stock | Bought | Actual | Best moment | Worst | Sold +30 min | Held to close |",
                  "|---|---|---|---|---|---|---|"]
        for r in review["trades"]:
            s30 = f"{r['sell_after_30']:+.2f}" if r["sell_after_30"] is not None else "-"
            lines.append(f"| {r['symbol']} | {r['bought_at']} | {r['actual_pnl']:+.2f} | {r['best_pnl']:+.2f} at "
                         f"{r['best_at']} | {r['worst_pnl']:+.2f} | {s30} | {r['held_to_close']:+.2f} |")
        lines += ["", "## Selling rules on today's trades"]
        lines += [f"- {RULES[n]}: {v:+.2f}" for n, v in review["rule_totals"].items()]
        lines += ["", "## Advice (from all reviewed days)"] + [f"- {a}" for a in review.get("advice", [])]
        return "\n".join(lines) + "\n"
