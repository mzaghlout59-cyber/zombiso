"""Hindsight on a made-up day where the right answers are known."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from divisions.review.hindsight import NY, RULES, Hindsight, simulate

DAY = datetime(2026, 10, 16, tzinfo=NY)
OPEN = DAY.replace(hour=9, minute=30)


def bar(minute, o, h, l, c):
    t = (OPEN + timedelta(minutes=minute)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": 1}


# Bought at 100 with the stop at 98 (R = 2, target 104). The price climbs to 103 (+1.5R) by
# minute 40, then slides all the way down through the stop at minute 120.
def path():
    out, p = [], 100.0
    for m in range(0, 390):
        if m < 40:
            p = 100 + 3 * (m / 40)
        elif m < 120:
            p = 103 - 5.2 * ((m - 40) / 80)
        else:
            p = 97.5
        out.append(bar(m, p, p + 0.05, p - 0.05, p))
    return out


def make_run(tmp_path, trades):
    run = tmp_path / "20261016-103023-000000"
    run.mkdir()
    events = []
    for i, (sym, size, entry, stop, exit_, pnl, reason, buy_min, sell_min) in enumerate(trades, start=1):
        at_in = (OPEN + timedelta(minutes=buy_min)).astimezone(timezone.utc).isoformat()
        at_out = (OPEN + timedelta(minutes=sell_min)).astimezone(timezone.utc).isoformat()
        events += [{"kind": "trade_opened", "trade_id": i, "tick": 1, "at": at_in, "symbol": sym, "size": size,
                    "entry": entry, "stop_loss": stop},
                   {"kind": "trade_closed", "trade_id": i, "tick": 2, "at": at_out, "symbol": sym, "size": size,
                    "entry": entry, "stop_loss": stop, "exit": exit_, "pnl": pnl, "reason": reason}]
    (run / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    (run / "meta.json").write_text(json.dumps({"source": "alpaca", "interval_s": 300}))
    return run


@pytest.fixture
def hindsight(tmp_path):
    return Hindsight(bars_source=lambda sym, start, end: path(), history_path=tmp_path / "history.json")


def test_selling_rules_on_a_trade_that_went_up_then_down():
    after = path()
    results = {r: simulate(r, after, 100.0, 98.0, 10, OPEN) for r in RULES}
    assert results["current"][2] == "stop"              # never reached 104, then hit 98
    assert results["break_even"][0] == pytest.approx(100.0)  # passed +1R at 102, so exits flat
    assert results["target_1r"][2] == "target" and results["target_1r"][0] == pytest.approx(102.0)
    assert results["trailing"][0] == pytest.approx(103.05 - 2)  # 1R below the high
    assert results["one_hour"][2] == "time"


def test_review_day_finds_best_moment_and_rule(tmp_path, hindsight):
    run = make_run(tmp_path, [("AAPL", 10, 100.0, 98.0, 97.5, -25.0, "stop_loss", 0, 120)])
    review = hindsight.review_day(run)
    t = review["trades"][0]
    assert t["best_pnl"] == pytest.approx(30.5) and t["best_at"] == "10:10"  # minute 40 after 9:30
    assert t["reached_target"] is False
    assert t["sell_after_30"] == pytest.approx(10 * (100 + 3 * 30 / 40 - 100), abs=0.01)
    assert review["rule_totals"]["target_1r"] > review["rule_totals"]["current"]
    assert any("Best selling rule today" in n for n in review["today"])
    assert any("in profit at some point" in n for n in review["today"])
    assert (run / "hindsight.json").exists()


def test_no_advice_until_enough_evidence(tmp_path, hindsight):
    run = make_run(tmp_path, [("AAPL", 10, 100.0, 98.0, 97.5, -25.0, "stop_loss", 0, 120)])
    review = hindsight.review_day(run)
    assert review["advice"][0].startswith("Still collecting evidence")


def test_advice_after_several_days(tmp_path, hindsight):
    for day in ("2026-10-13", "2026-10-14", "2026-10-15"):
        hindsight.remember({
            "date": day, "actual_total": -100.0,
            "rule_totals": {"current": -100.0, "break_even": -10.0, "trailing": -40.0,
                            "target_1r": -20.0, "one_hour": -60.0},
            "trades": [{"symbol": "X", "buy_hour": 9, "actual_pnl": -25.0, "best_pnl": 10.0,
                        "reached_target": False}] * 4,
        })
    advice = " | ".join(hindsight.advice())
    assert "once up 1R, move the safety exit up to the buy price" in advice
    assert "did badly" in advice and "09:00-09:59 New York" in advice
    assert "A profit-protecting rule may help" in advice


def test_markdown_has_the_tables(tmp_path, hindsight):
    review = hindsight.review_day(make_run(tmp_path, [("AAPL", 10, 100.0, 98.0, 97.5, -25.0, "stop_loss", 0, 120)]))
    md = Hindsight.to_markdown(review)
    assert "Trade by trade" in md and "| AAPL |" in md and "Selling rules" in md
