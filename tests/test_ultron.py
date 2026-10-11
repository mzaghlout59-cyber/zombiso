"""Ultron must pass a clean run and catch every kind of tampering."""
import copy

import pytest

from core.ledger import PaperLedger
from core.prices import SimulatedFeed
from core.ultron import Ultron
from run_city import build_city, run_city, START_PRICES


@pytest.fixture(scope="module")
def clean_run(tmp_path_factory):
    ledger = PaperLedger(tmp_path_factory.mktemp("ultron") / "ledger.json")
    raphael = build_city(ledger=ledger)
    run_city(SimulatedFeed(START_PRICES, seed=1), cycles=60, raphael=raphael)
    return raphael


def events_of(raphael):
    return copy.deepcopy(raphael.events.events)


def messages(report):
    return " | ".join(v["message"] for v in report["violations"])


def opened(events):
    return [e for e in events if e["kind"] == "trade_opened"]


def test_clean_run_passes(clean_run):
    report = Ultron().audit(clean_run.events, clean_run.ledger)
    assert report["ok"], messages(report)
    assert report["stats"]["opened"] > 0 and report["stats"]["closed"] > 0
    assert report["stats"]["opened"] == len(clean_run.ledger.trades)


def test_flags_trade_without_decision(clean_run):
    events = events_of(clean_run)
    first = opened(events)[0]
    events = [e for e in events if not (e["kind"] == "decision" and e["executed"]
                                         and e["symbol"] == first["symbol"]
                                         and e["tick"] == first["tick"])]
    assert "without an executed decision" in messages(Ultron().audit(events))


def test_flags_execution_without_approval(clean_run):
    events = events_of(clean_run)
    next(e for e in events if e["kind"] == "decision" and e["executed"])["approved"] = False
    assert "without Aegis approval" in messages(Ultron().audit(events))


def test_flags_oversized_trade(clean_run):
    events = events_of(clean_run)
    opened(events)[0]["size"] *= 10
    assert "worst-case risk" in messages(Ultron().audit(events))


def test_flags_missing_stop(clean_run):
    events = events_of(clean_run)
    opened(events)[0]["stop_loss"] = None
    assert "no stop-loss" in messages(Ultron().audit(events))


def test_flags_wrong_pnl(clean_run):
    events = events_of(clean_run)
    next(e for e in events if e["kind"] == "trade_closed")["pnl"] += 5
    assert "should be" in messages(Ultron().audit(events))


def test_flags_stacking_and_position_cap():
    def decision(seq, sym):
        return {"seq": seq, "tick": 1, "day": 0, "kind": "decision", "symbol": sym,
                "action": "buy", "confidence": 0.5, "approved": True, "executed": True}

    def open_(seq, tid, sym):
        return {"seq": seq, "tick": 1, "day": 0, "kind": "trade_opened", "trade_id": tid,
                "symbol": sym, "side": "buy", "size": 5, "entry": 100.0, "stop_loss": 98.0}

    events, seq = [], 0
    for tid, sym in enumerate(["AAPL", "MSFT", "NVDA", "TSLA", "AAPL"], start=1):
        events += [decision(seq + 1, sym), open_(seq + 2, tid, sym)]
        seq += 2
    msg = messages(Ultron().audit(events))
    assert "positions already open" in msg
    assert "stacked on an open AAPL" in msg


def test_flags_trade_after_daily_limit():
    events = [
        {"seq": 1, "tick": 1, "day": 0, "kind": "decision", "symbol": "AAPL",
         "action": "buy", "confidence": 0.5, "approved": True, "executed": True},
        {"seq": 2, "tick": 1, "day": 0, "kind": "trade_opened", "trade_id": 1, "symbol": "AAPL",
         "side": "buy", "size": 5, "entry": 100.0, "stop_loss": 98.0},
        {"seq": 3, "tick": 2, "day": 0, "kind": "trade_closed", "trade_id": 1, "symbol": "AAPL",
         "side": "buy", "size": 5, "entry": 100.0, "stop_loss": 98.0, "exit": 70.0,
         "pnl": -150.0, "reason": "stop_loss"},
        {"seq": 4, "tick": 2, "day": 0, "kind": "decision", "symbol": "MSFT",
         "action": "buy", "confidence": 0.5, "approved": True, "executed": True},
        {"seq": 5, "tick": 2, "day": 0, "kind": "trade_opened", "trade_id": 2, "symbol": "MSFT",
         "side": "buy", "size": 5, "entry": 100.0, "stop_loss": 98.0},
    ]
    report = Ultron().audit(events)
    assert "after the daily loss limit" in messages(report)
    assert report["warnings"]  # the -150 loss itself is over the per-trade limit


def test_flags_trade_after_losing_streak():
    events, seq = [], 0

    def add(**e):
        nonlocal seq
        seq += 1
        events.append({"seq": seq, "day": 0, **e})

    for tid in range(1, 5):  # four small losses in a row, each well inside the daily limit
        add(tick=tid, kind="decision", symbol=f"S{tid}", action="buy", confidence=0.5,
            approved=True, executed=True)
        add(tick=tid, kind="trade_opened", trade_id=tid, symbol=f"S{tid}", side="buy",
            size=5, entry=100.0, stop_loss=98.0)
        add(tick=tid, kind="trade_closed", trade_id=tid, symbol=f"S{tid}", side="buy", size=5,
            entry=100.0, stop_loss=98.0, exit=99.0, pnl=-5.0, reason="stop_loss")
    add(tick=5, kind="decision", symbol="S5", action="buy", confidence=0.5, approved=True, executed=True)
    add(tick=5, kind="trade_opened", trade_id=5, symbol="S5", side="buy", size=5,
        entry=100.0, stop_loss=98.0)
    msg = messages(Ultron().audit(events))
    assert "after a losing streak of 4" in msg
    assert msg.count("losing streak") == 1  # trades 1-4 were fine


def test_flags_ledger_that_disagrees_with_events(clean_run, tmp_path):
    ledger = PaperLedger(tmp_path / "copy.json")
    ledger.trades = copy.deepcopy(clean_run.ledger.trades)
    next(t for t in ledger.trades if t["status"] == "closed")["pnl"] += 1
    assert "does not match the event replay" in messages(Ultron().audit(clean_run.events, ledger))


def test_ultron_answers_to_mohamad_not_raphael(clean_run):
    assert Ultron().profile()["commander"] == "Master Mohamad"
    assert "Ultron" not in clean_run.agents
