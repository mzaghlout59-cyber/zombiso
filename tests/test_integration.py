import tempfile
from pathlib import Path

from core.ledger import PaperLedger
from core.raphael import Raphael
from divisions.investment.aegis import AegisAgent


def make_raphael(tmp):
    ledger = PaperLedger(Path(tmp) / "test_ledger.json")
    r = Raphael(ledger=ledger)
    r.register(AegisAgent())
    return r, ledger


def aegis_decision(r, symbol="AAPL"):
    """Run Aegis exactly the way run_goal does, with real ledger numbers."""
    aegis = r.agents["Aegis"]
    aegis.open_positions = r.ledger.open_positions()
    aegis.daily_pnl = r.ledger.daily_pnl()
    trade = {"entry": 105.0, "stop_loss": 102.90, "size": 11, "side": "buy"}
    return aegis.evaluate(symbol, trade)


def run():
    with tempfile.TemporaryDirectory() as tmp:
        r, ledger = make_raphael(tmp)

        # 1. empty ledger -> approved
        assert aegis_decision(r)["approved"] is True

        # 2. fill 3 positions -> 4th must be DENIED (Rule 2 finally fires)
        for sym in ("AAPL", "MSFT", "TSLA"):
            ledger.open_trade(sym, "buy", 11, 105.0, 102.90)
        assert ledger.open_positions() == 3
        decision = aegis_decision(r)
        assert decision["approved"] is False
        assert "max open positions" in decision["reason"]

        # 3. close all at a big loss -> daily loss limit (Rule 1 fires)
        # 11 shares * (80 - 105) = -275 each, far past the 1% limit
        for trade_id in (1, 2, 3):
            ledger.close_trade(trade_id, 80.0)
        assert ledger.open_positions() == 0
        decision = aegis_decision(r)
        assert decision["approved"] is False
        assert "daily loss limit" in decision["reason"]

    print("PASS: ledger + Aegis integration (Rules 1 and 2 are live)")



def run_duplicate_symbol():
    with tempfile.TemporaryDirectory() as tmp:
        r, ledger = make_raphael(tmp)
        aegis = r.agents["Aegis"]
        trade = {"entry": 105.0, "stop_loss": 102.90, "size": 11, "side": "buy"}

        # AAPL open -> a second AAPL must be DENIED
        ledger.open_trade("AAPL", "buy", 11, 105.0, 102.90)
        aegis.open_positions = r.ledger.open_positions()
        aegis.daily_pnl = r.ledger.daily_pnl()
        aegis.open_symbols = r.ledger.open_symbols()
        decision = aegis.evaluate("AAPL", trade)
        assert decision["approved"] is False
        assert "already holding" in decision["reason"]

        # a DIFFERENT symbol is still allowed
        assert aegis.evaluate("MSFT", trade)["approved"] is True

        # after AAPL closes, AAPL is allowed again
        ledger.close_trade(1, 106.0)
        aegis.open_positions = r.ledger.open_positions()
        aegis.open_symbols = r.ledger.open_symbols()
        assert aegis.evaluate("AAPL", trade)["approved"] is True

    print("PASS: duplicate-symbol rule (no stacking)")


if __name__ == "__main__":
    run()
    run_duplicate_symbol()
