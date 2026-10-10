import tempfile
from pathlib import Path
from core.ledger import PaperLedger


def run():
    with tempfile.TemporaryDirectory() as d:
        ledger = PaperLedger(Path(d) / "test_ledger.json")

        assert ledger.open_positions() == 0
        assert ledger.daily_pnl() == 0.0

        t1 = ledger.open_trade("AAPL", "buy", 11, 105.0, 102.90)
        ledger.open_trade("MSFT", "buy", 5, 200.0, 196.0)
        assert ledger.open_positions() == 2

        ledger.close_trade(t1["id"], 110.0)
        assert ledger.open_positions() == 1
        assert ledger.daily_pnl() == 55.0

        reloaded = PaperLedger(Path(d) / "test_ledger.json")
        assert reloaded.open_positions() == 1
        assert reloaded.daily_pnl() == 55.0

        try:
            ledger.close_trade(999, 100.0)
            assert False, "should have raised"
        except ValueError:
            pass

    print("PASS: ledger")


if __name__ == "__main__":
    run()


def test_open_trades_public_method():
    import tempfile
    from pathlib import Path
    from core.ledger import PaperLedger

    with tempfile.TemporaryDirectory() as tmp:
        ledger = PaperLedger(Path(tmp) / "t.json")
        assert ledger.open_trades() == []
        ledger.open_trade("AAPL", "buy", 11, 105.0, 102.9)
        ledger.open_trade("MSFT", "buy", 5, 200.0, 196.0)
        assert len(ledger.open_trades()) == 2
        ledger.close_trade(1, 110.0)
        remaining = ledger.open_trades()
        assert len(remaining) == 1
        assert remaining[0]["symbol"] == "MSFT"
        print("PASS: ledger.open_trades() returns only open trades")


test_open_trades_public_method()
