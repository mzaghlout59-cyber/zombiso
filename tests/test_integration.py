"""Ledger + Raphael + Aegis wired together, on a throwaway ledger."""
import pytest

from config import settings
from core.ledger import PaperLedger
from core.raphael import Raphael
from divisions.investment.aegis import AegisAgent
from run_city import build_city

TRADE = {"entry": 105.0, "stop_loss": 102.90, "size": 11, "side": "buy"}
POP = [100, 99, 98, 97, 96, 105]  # Strategist proposes a buy on this


@pytest.fixture
def ledger(tmp_path):
    return PaperLedger(tmp_path / "test_ledger.json")


@pytest.fixture
def raphael(ledger):
    r = Raphael(ledger=ledger)
    r.register(AegisAgent())
    return r


def aegis_decision(r, symbol="AAPL"):
    """Run Aegis exactly the way run_goal does, with real ledger numbers."""
    aegis = r.agents["Aegis"]
    aegis.open_positions = r.ledger.open_positions()
    aegis.daily_pnl = r.ledger.daily_pnl()
    aegis.open_symbols = r.ledger.open_symbols()
    return aegis.evaluate(symbol, TRADE)


def test_position_cap_and_daily_loss_limit(raphael, ledger):
    # 1. empty ledger -> approved
    assert aegis_decision(raphael)["approved"] is True

    # 2. fill 3 positions -> 4th must be denied
    for sym in ("AAPL", "MSFT", "TSLA"):
        ledger.open_trade(sym, "buy", 11, 105.0, 102.90)
    assert ledger.open_positions() == 3
    decision = aegis_decision(raphael, "NVDA")
    assert decision["approved"] is False
    assert "max open positions" in decision["reason"]

    # 3. close all at a big loss -> daily loss limit fires
    # 11 shares * (80 - 105) = -275 each, far past the 1% limit
    for trade_id in (1, 2, 3):
        ledger.close_trade(trade_id, 80.0)
    assert ledger.open_positions() == 0
    decision = aegis_decision(raphael, "NVDA")
    assert decision["approved"] is False
    assert "daily loss limit" in decision["reason"]


def test_duplicate_symbol_rule(raphael, ledger):
    ledger.open_trade("AAPL", "buy", 11, 105.0, 102.90)
    decision = aegis_decision(raphael, "AAPL")
    assert decision["approved"] is False
    assert "already holding" in decision["reason"]

    # a different symbol is still allowed
    assert aegis_decision(raphael, "MSFT")["approved"] is True

    # after AAPL closes, AAPL is allowed again
    ledger.close_trade(1, 106.0)
    assert aegis_decision(raphael, "AAPL")["approved"] is True


def test_run_goal_opens_trade_in_ledger(ledger, monkeypatch):
    monkeypatch.setattr(settings, "MIN_SAGE_CONFIDENCE", 0.0)
    r = build_city(ledger=ledger)
    decision = r.run_goal("Evaluate AAPL", {"symbol": "AAPL", "prices": POP})
    assert decision["executed"] is True
    assert [t["symbol"] for t in ledger.open_trades()] == ["AAPL"]


def test_low_sage_confidence_blocks_trade(ledger, monkeypatch):
    monkeypatch.setattr(settings, "MIN_SAGE_CONFIDENCE", 1.0)  # unreachable (max is 0.9)
    r = build_city(ledger=ledger)
    decision = r.run_goal("Evaluate AAPL", {"symbol": "AAPL", "prices": POP})
    assert decision["risk"]["approved"] is True  # Aegis said yes...
    assert decision["executed"] is False          # ...but Sage's gate said no
    assert ledger.open_trades() == []


def test_open_trade_closes_on_stop_loss(raphael, ledger):
    ledger.open_trade("AAPL", "buy", 11, 105.0, 102.90)
    assert raphael.check_exits({"AAPL": 104.0}) == []
    closed = raphael.check_exits({"AAPL": 102.0})
    assert len(closed) == 1 and closed[0]["exit_reason"] == "stop_loss"
    assert ledger.open_trades() == []
