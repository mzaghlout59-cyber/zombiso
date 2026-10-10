import tempfile
from pathlib import Path

from core.exits import exit_signal
from core.ledger import PaperLedger
from core.raphael import Raphael
from divisions.investment.aegis import AegisAgent

BUY = {"status": "open", "side": "buy", "entry": 105.0, "stop_loss": 102.9}
SELL = {"status": "open", "side": "sell", "entry": 105.0, "stop_loss": 107.1}


def test_pure_function():
    # buy: stop 102.9, target 105 + 2.1*2 = 109.2
    assert exit_signal(BUY, 104.0) is None
    assert exit_signal(BUY, 102.9) == "stop_loss"
    assert exit_signal(BUY, 100.0) == "stop_loss"
    assert exit_signal(BUY, 109.2) == "take_profit"
    assert exit_signal(BUY, 120.0) == "take_profit"
    # sell: stop 107.1, target 105 - 4.2 = 100.8
    assert exit_signal(SELL, 106.0) is None
    assert exit_signal(SELL, 107.1) == "stop_loss"
    assert exit_signal(SELL, 100.8) == "take_profit"
    # closed trades never exit again
    assert exit_signal({**BUY, "status": "closed"}, 90.0) is None
    print("PASS: exit_signal pure function")


def test_raphael_closes_trades():
    with tempfile.TemporaryDirectory() as tmp:
        ledger = PaperLedger(Path(tmp) / "t.json")
        r = Raphael(ledger=ledger)
        r.register(AegisAgent())
        ledger.open_trade("AAPL", "buy", 11, 105.0, 102.9)

        # price inside the range: nothing happens
        assert r.check_exits({"AAPL": 104.0}) == []
        assert ledger.open_positions() == 1

        # no price for the symbol: skipped safely
        assert r.check_exits({"MSFT": 1.0}) == []
        assert ledger.open_positions() == 1

        # stop hit: closed at a loss
        closed = r.check_exits({"AAPL": 102.5})
        assert len(closed) == 1
        assert closed<a href="" class="citation-link" target="_blank" style="vertical-align: super; font-size: 0.8em; margin-left: 3px;">[0]</a>["exit_reason"] == "stop_loss"
        assert ledger.open_positions() == 0
        assert ledger.daily_pnl() < 0
        print(f"PASS: Raphael closed a stopped trade, pnl={ledger.daily_pnl():.2f}")


def test_loss_feeds_rule_1():
    with tempfile.TemporaryDirectory() as tmp:
        ledger = PaperLedger(Path(tmp) / "t.json")
        r = Raphael(ledger=ledger)
        aegis = AegisAgent()
        r.register(aegis)

        # open and stop out 5 trades at a gap-down far below the stop
        for sym in ("A", "B", "C", "D", "E"):
            ledger.open_trade(sym, "buy", 11, 105.0, 102.9)
            r.check_exits({sym: 98.0})
        assert ledger.open_positions() == 0
        assert ledger.daily_pnl() <= -100.0  # past the 1% daily limit

        aegis.open_positions = ledger.open_positions()
        aegis.daily_pnl = ledger.daily_pnl()
        aegis.open_symbols = ledger.open_symbols()
        trade = {"entry": 105.0, "stop_loss": 102.9, "size": 11}
        decision = aegis.evaluate("ZZZ", trade)
        assert decision["approved"] is False
        assert "daily loss limit" in decision["reason"]
        print("PASS: realized exit losses trip the daily kill switch (Rule 1, live)")


if __name__ == "__main__":
    test_pure_function()
    test_raphael_closes_trades()
    test_loss_feeds_rule_1()
