"""The limits set on 2026-10-15: $100 risk per trade, $100 daily loss stop, $1,000 daily
profit stop, no borrowing, and a 10-stock watchlist."""
import pytest

from config import settings
from core.ultron import Ultron
from divisions.investment.aegis import AegisAgent
from divisions.investment.strategist import StrategistAgent

POP = [100, 99, 98, 97, 96, 105]


@pytest.fixture
def live_limits(monkeypatch):
    monkeypatch.setattr(settings, "MAX_RISK_PER_TRADE_PCT", 1.0)
    monkeypatch.setattr(settings, "MAX_DAILY_LOSS_PCT", 1.0)
    monkeypatch.setattr(settings, "DAILY_PROFIT_TARGET", 1000.0)


def test_configured_values():
    import runpy
    from pathlib import Path
    # read the real file into its own namespace (not the pinned test baseline, and without
    # reloading the shared module, which would undo the pins for every other test)
    real = runpy.run_path(str(Path(settings.__file__)))
    assert real["MAX_RISK_PER_TRADE_PCT"] == 1.0 and real["MAX_DAILY_LOSS_PCT"] == 1.0
    assert real["DAILY_PROFIT_TARGET"] == 1000.0
    assert len(real["WATCHLIST"]) == 10 and len(set(real["WATCHLIST"])) == 10


def test_trades_risk_about_a_hundred_dollars(live_limits):
    trade = StrategistAgent().handle({"symbol": "X", "prices": POP, "capital": 10_000})["trade"]
    worst = (trade["entry"] - trade["stop_loss"]) * trade["size"] * settings.STOP_GAP_BUFFER
    assert 90 < worst <= 100
    assert AegisAgent().evaluate("X", trade)["approved"] is True


def test_daily_loss_stop_is_100(live_limits):
    a = AegisAgent()
    a.daily_pnl = -99.99
    assert a.evaluate("X", {"entry": 100, "stop_loss": 99, "size": 5})["approved"] is True
    a.daily_pnl = -100.0
    assert "daily loss limit" in a.evaluate("X", {"entry": 100, "stop_loss": 99, "size": 5})["reason"]


def test_profit_target_stops_new_trades_for_the_day(live_limits):
    a = AegisAgent()
    a.daily_pnl = 999.99
    assert a.evaluate("X", {"entry": 100, "stop_loss": 99, "size": 5})["approved"] is True
    a.daily_pnl = 1000.0
    r = a.evaluate("X", {"entry": 100, "stop_loss": 99, "size": 5})
    assert r["approved"] is False and "profit target" in r["reason"]


def test_never_spends_more_than_the_capital(live_limits):
    a = AegisAgent()
    a.account = 10_000
    a.open_exposure = 9_500
    r = a.evaluate("X", {"entry": 100, "stop_loss": 99.5, "size": 6})  # $600, only $500 free
    assert r["approved"] is False and "not enough cash" in r["reason"]
    assert a.evaluate("X", {"entry": 100, "stop_loss": 99.5, "size": 5})["approved"] is True


def test_strategist_caps_shares_at_free_cash(live_limits):
    r = StrategistAgent().handle({"symbol": "X", "prices": POP, "capital": 10_000, "cash": 300})
    assert r["trade"]["size"] == 2  # $105 a share, $300 free
    none = StrategistAgent().handle({"symbol": "X", "prices": POP, "capital": 10_000, "cash": 50})
    assert none["signal"] == "hold"


def test_ultron_flags_borrowing_and_trading_past_the_profit_target(live_limits):
    def ev(seq, tick, kind, **k):
        return {"seq": seq, "tick": tick, "day": 0, "kind": kind, **k}

    def decision(seq, tick, sym):
        return ev(seq, tick, "decision", symbol=sym, action="buy", confidence=0.5, approved=True, executed=True)

    events = [
        decision(1, 1, "A"), ev(2, 1, "trade_opened", trade_id=1, symbol="A", side="buy", size=60,
                                 entry=100.0, stop_loss=99.8),
        decision(3, 1, "B"), ev(4, 1, "trade_opened", trade_id=2, symbol="B", side="buy", size=50,
                                 entry=100.0, stop_loss=99.8),               # $11,000 > $10,000
        ev(5, 2, "trade_closed", trade_id=1, symbol="A", side="buy", size=60, entry=100.0,
           stop_loss=99.8, exit=120.0, pnl=1200.0, reason="take_profit"),
        decision(6, 3, "C"), ev(7, 3, "trade_opened", trade_id=3, symbol="C", side="buy", size=1,
                                 entry=100.0, stop_loss=99.8),               # after +$1,200 today
    ]
    msgs = " | ".join(v["message"] for v in Ultron().audit(events)["violations"])
    assert "spends more than the capital" in msgs
    assert "after the daily profit target" in msgs
