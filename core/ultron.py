from collections import defaultdict

from config import settings
from core.base_agent import BaseAgent


class Ultron(BaseAgent):
    """The auditor. Answers to Master Mohamad directly, not to Raphael.

    Read-only: Ultron never trades, approves or vetoes. It replays the event
    stream from scratch, rebuilding positions and daily P&L itself instead of
    trusting Raphael's or the ledger's numbers, and reports every broken rule.
    """

    name = "Ultron"
    alias = "Ultron"
    division = "Oversight"
    rank = "Auditor"
    commander = "Master Mohamad"
    purpose = "Independent auditor: replays every event and reports any broken rule. Read-only."

    def handle(self, task):
        return self.audit(task["events"], task.get("ledger"))

    def audit(self, events, ledger=None):
        """events: an EventLog or a list of event dicts. ledger: optional PaperLedger to cross-check."""
        events = getattr(events, "events", events)
        # Ultron replays the Treasury himself: capital = (start equity + realized P&L) x share.
        start_equity, share = settings.ACCOUNT_SIZE, 1.0
        realized = 0.0

        def capital_now():
            return round((start_equity + realized) * share, 2)

        def max_risk(capital):
            return capital * settings.MAX_RISK_PER_TRADE_PCT / 100

        def max_daily_loss(capital):
            return capital * settings.MAX_DAILY_LOSS_PCT / 100

        violations, warnings = [], []
        open_trades = {}           # trade_id -> trade_opened event
        closed_pnl = {}            # trade_id -> pnl from trade_closed event
        day_pnl = defaultdict(float)
        day_streak = defaultdict(int)       # current run of losing closes, per day
        day_max_streak = defaultdict(int)   # longest run so far, per day
        last_decision = {}         # symbol -> latest decision event

        def flag(bucket, event, message):
            bucket.append({"seq": event["seq"] if event else None,
                           "tick": event["tick"] if event else None,
                           "message": message})

        seen_treasury = False
        for e in events:
            kind = e["kind"]

            if kind == "treasury" and not seen_treasury:
                seen_treasury = True
                start_equity = e["equity"]
                share = e["allocations"].get(e["division"], 0.0)

            if kind in ("decision", "trade_opened") and "capital" in e:
                if abs(e["capital"] - capital_now()) > 0.011:
                    flag(violations, e, f"{e['symbol']} {kind} used capital ${e['capital']:.2f}, "
                                        f"the Treasury replay says ${capital_now():.2f}")

            if kind == "decision":
                last_decision[e["symbol"]] = e
                if e["executed"]:
                    if not e["approved"]:
                        flag(violations, e, f"{e['symbol']} executed without Aegis approval")
                    if e["confidence"] < settings.MIN_SAGE_CONFIDENCE:
                        flag(violations, e, f"{e['symbol']} executed below Sage confidence gate "
                                            f"({e['confidence']} < {settings.MIN_SAGE_CONFIDENCE})")
                    if e["action"] == "hold":
                        flag(violations, e, f"{e['symbol']} executed on a hold")

            elif kind == "trade_opened":
                sym = e["symbol"]
                d = last_decision.pop(sym, None)
                if d is None or not d["executed"] or d["tick"] != e["tick"]:
                    flag(violations, e, f"trade #{e['trade_id']} {sym} opened without an executed decision")

                stop, entry = e["stop_loss"], e["entry"]
                if stop is None:
                    flag(violations, e, f"trade #{e['trade_id']} {sym} has no stop-loss")
                else:
                    wrong_side = stop >= entry if e["side"] == "buy" else stop <= entry
                    if wrong_side:
                        flag(violations, e, f"trade #{e['trade_id']} {sym} stop is on the wrong side of entry")
                    risk = abs(entry - stop) * e["size"] * settings.STOP_GAP_BUFFER
                    if risk > max_risk(capital_now()) + 1e-9:
                        flag(violations, e, f"trade #{e['trade_id']} {sym} worst-case risk "
                                            f"${risk:.2f} > ${max_risk(capital_now()):.2f}")

                if len(open_trades) >= settings.MAX_OPEN_POSITIONS:
                    flag(violations, e, f"trade #{e['trade_id']} {sym} opened with "
                                        f"{len(open_trades)} positions already open")
                if sym in {t["symbol"] for t in open_trades.values()}:
                    flag(violations, e, f"trade #{e['trade_id']} {sym} stacked on an open {sym} position")
                if day_pnl[e["day"]] <= -max_daily_loss(capital_now()):
                    flag(violations, e, f"trade #{e['trade_id']} {sym} opened after the daily loss "
                                        f"limit was hit (day {e['day']} pnl {day_pnl[e['day']]:.2f})")
                if day_max_streak[e["day"]] >= settings.MAX_LOSS_STREAK:
                    flag(violations, e, f"trade #{e['trade_id']} {sym} opened after a losing streak of "
                                        f"{day_max_streak[e['day']]} on day {e['day']}")
                open_trades[e["trade_id"]] = {**e, "limit": max_risk(capital_now())}

            elif kind == "trade_closed":
                opened = open_trades.pop(e["trade_id"], None)
                if opened is None:
                    flag(violations, e, f"trade #{e['trade_id']} closed but was never open")
                limit = opened["limit"] if opened else max_risk(capital_now())
                direction = 1 if e["side"] == "buy" else -1
                expected = round((e["exit"] - e["entry"]) * e["size"] * direction, 2)
                if e["pnl"] != expected:
                    flag(violations, e, f"trade #{e['trade_id']} pnl {e['pnl']} should be {expected}")
                if e["pnl"] < -limit:
                    flag(warnings, e, f"trade #{e['trade_id']} {e['symbol']} lost ${-e['pnl']:.2f}, "
                                      f"over the ${limit:.2f} limit (stop gapped)")
                realized += e["pnl"]
                closed_pnl[e["trade_id"]] = e["pnl"]
                day_pnl[e["day"]] += e["pnl"]
                day_streak[e["day"]] = day_streak[e["day"]] + 1 if e["pnl"] <= 0 else 0
                day_max_streak[e["day"]] = max(day_max_streak[e["day"]], day_streak[e["day"]])

        if ledger is not None:
            ledger_open = {t["id"] for t in ledger.trades if t["status"] == "open"}
            if ledger_open != set(open_trades):
                flag(violations, None, f"ledger open trades {sorted(ledger_open)} do not match "
                                       f"the event replay {sorted(open_trades)}")
            for t in ledger.trades:
                if t["status"] == "closed" and closed_pnl.get(t["id"]) != t["pnl"]:
                    flag(violations, None, f"ledger trade #{t['id']} pnl {t['pnl']} does not match "
                                           f"the event replay {closed_pnl.get(t['id'])}")

        report = {
            "ok": not violations,
            "violations": violations,
            "warnings": warnings,
            "stats": {
                "events": len(events),
                "opened": sum(1 for e in events if e["kind"] == "trade_opened"),
                "closed": len(closed_pnl),
                "still_open": len(open_trades),
                "realized_pnl": round(sum(closed_pnl.values()), 2),
                "trading_days": len(day_pnl),
            },
        }
        verdict = "CLEAN" if report["ok"] else f"{len(violations)} VIOLATION(S)"
        self.say(f"Audit {verdict}, {len(warnings)} warning(s), stats={report['stats']}")
        return report
