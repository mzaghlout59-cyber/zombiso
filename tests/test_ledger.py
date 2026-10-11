import pytest

from core.ledger import PaperLedger


def test_open_close_and_reload(tmp_path):
    ledger = PaperLedger(tmp_path / "test_ledger.json")

    assert ledger.open_positions() == 0
    assert ledger.daily_pnl() == 0.0

    t1 = ledger.open_trade("AAPL", "buy", 11, 105.0, 102.90)
    ledger.open_trade("MSFT", "buy", 5, 200.0, 196.0)
    assert ledger.open_positions() == 2

    ledger.close_trade(t1["id"], 110.0)
    assert ledger.open_positions() == 1
    assert ledger.daily_pnl() == 55.0

    reloaded = PaperLedger(tmp_path / "test_ledger.json")
    assert reloaded.open_positions() == 1
    assert reloaded.daily_pnl() == 55.0


def test_sell_side_pnl(tmp_path):
    ledger = PaperLedger(tmp_path / "t.json")
    t = ledger.open_trade("TSLA", "sell", 10, 100.0, 105.0)
    assert ledger.close_trade(t["id"], 90.0)["pnl"] == 100.0


def test_closing_missing_or_closed_trade_raises(tmp_path):
    ledger = PaperLedger(tmp_path / "t.json")
    t = ledger.open_trade("AAPL", "buy", 11, 105.0, 102.9)
    with pytest.raises(ValueError):
        ledger.close_trade(999, 100.0)
    ledger.close_trade(t["id"], 110.0)
    with pytest.raises(ValueError):
        ledger.close_trade(t["id"], 120.0)


def test_open_trades_public_method(tmp_path):
    ledger = PaperLedger(tmp_path / "t.json")
    assert ledger.open_trades() == []
    ledger.open_trade("AAPL", "buy", 11, 105.0, 102.9)
    ledger.open_trade("MSFT", "buy", 5, 200.0, 196.0)
    assert len(ledger.open_trades()) == 2
    ledger.close_trade(1, 110.0)
    remaining = ledger.open_trades()
    assert len(remaining) == 1
    assert remaining[0]["symbol"] == "MSFT"
