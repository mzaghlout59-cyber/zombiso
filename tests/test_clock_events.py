import json

from core.clock import SimClock
from core.events import EventLog
from core.ledger import PaperLedger
from divisions.investment.aegis import AegisAgent
from run_city import build_city


def test_clock_days():
    c = SimClock(cycles_per_day=3)
    assert (c.tick, c.day) == (0, 0)
    days = []
    for _ in range(7):
        c.advance()
        days.append(c.day)
    assert days == [0, 0, 0, 1, 1, 1, 2]


def test_daily_pnl_resets_on_a_new_sim_day(tmp_path):
    clock = SimClock(cycles_per_day=2)
    ledger = PaperLedger(tmp_path / "l.json", clock=clock)
    clock.advance()  # day 0
    t = ledger.open_trade("AAPL", "buy", 10, 100.0, 98.0)
    ledger.close_trade(t["id"], 85.0)  # -150, past the daily limit
    assert ledger.daily_pnl() == -150.0

    aegis = AegisAgent()
    aegis.daily_pnl = ledger.daily_pnl()
    trade = {"entry": 100, "stop_loss": 99.0, "size": 5}
    assert aegis.evaluate("MSFT", trade)["approved"] is False

    clock.advance()
    clock.advance()  # day 1: the kill switch resets
    assert ledger.daily_pnl() == 0.0
    aegis.daily_pnl = ledger.daily_pnl()
    assert aegis.evaluate("MSFT", trade)["approved"] is True


def test_ledger_records_sim_time(tmp_path):
    clock = SimClock(cycles_per_day=2)
    ledger = PaperLedger(tmp_path / "l.json", clock=clock)
    clock.advance()
    t = ledger.open_trade("AAPL", "buy", 10, 100.0, 98.0)
    clock.advance()
    clock.advance()
    ledger.close_trade(t["id"], 101.0)
    assert (t["opened_tick"], t["opened_day"]) == (1, 0)
    assert (t["closed_tick"], t["closed_day"]) == (3, 1)


def test_events_are_stamped_and_written(tmp_path):
    clock = SimClock()
    log = EventLog(clock=clock, path=tmp_path / "events.jsonl")
    clock.advance()
    log.emit("tick", prices={"AAPL": 100.0})
    log.emit("decision", symbol="AAPL")
    lines = [json.loads(l) for l in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert lines == log.events
    assert [e["seq"] for e in lines] == [1, 2]
    assert lines[0] == {"seq": 1, "tick": 1, "day": 0, "kind": "tick", "prices": {"AAPL": 100.0}}
    assert len(log.of_kind("decision")) == 1


def test_each_run_gets_a_fresh_folder():
    a = build_city()
    b = build_city()
    assert a.ledger.path != b.ledger.path
    assert a.ledger.trades == [] and b.ledger.trades == []
    assert a.events.path.name == "events.jsonl"
