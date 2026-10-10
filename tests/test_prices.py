import tempfile
from pathlib import Path

from core.ledger import PaperLedger
from core.prices import SimulatedFeed
from core.raphael import Raphael


def test_feed_is_deterministic():
    a = SimulatedFeed({"AAPL": 100.0}, seed=7)
    b = SimulatedFeed({"AAPL": 100.0}, seed=7)
    for _ in range(20):
        a.advance()
        b.advance()
    assert a.get_history("AAPL", 21) == b.get_history("AAPL", 21)
    print("PASS: same seed gives the same price path")


def test_feed_basics():
    feed = SimulatedFeed({"AAPL": 100.0, "MSFT": 200.0}, seed=1)
    assert feed.get_price("AAPL") == 100.0
    for _ in range(50):
        feed.advance()
    assert len(feed.get_history("AAPL", 10)) == 10
    assert all(p > 0 for p in feed.get_history("AAPL", 51))
    try:
        feed.get_price("NOPE")
        assert False, "expected KeyError"
    except KeyError:
        pass
    print("PASS: history length, positive prices, unknown symbol raises")


def test_tick_closes_a_stopped_trade():
    with tempfile.TemporaryDirectory() as tmp:
        ledger = PaperLedger(Path(tmp) / "t.json")
        r = Raphael(ledger=ledger)
        # stop is just under the start price, so a small dip stops it out
        ledger.open_trade("AAPL", "buy", 10, 100.0, 99.999)
        feed = SimulatedFeed({"AAPL": 100.0}, seed=3, volatility=0.05)

        closed = []
        for _ in range(200):
            feed.advance()
            closed += r.tick(feed)
            if closed:
                break

        assert len(closed) == 1
        assert next(iter(closed))["exit_reason"] in ("stop_loss", "take_profit")
        assert ledger.open_positions() == 0
        print(f"PASS: tick() closed a trade via {next(iter(closed))['exit_reason']}")


def test_tick_skips_unpriced_symbols():
    with tempfile.TemporaryDirectory() as tmp:
        ledger = PaperLedger(Path(tmp) / "t.json")
        r = Raphael(ledger=ledger)
        ledger.open_trade("ZZZ", "buy", 5, 50.0, 48.0)
        feed = SimulatedFeed({"AAPL": 100.0}, seed=1)
        assert r.tick(feed) == []
        assert ledger.open_positions() == 1
        print("PASS: tick() skips symbols the feed cannot price")


if __name__ == "__main__":
    test_feed_is_deterministic()
    test_feed_basics()
    test_tick_closes_a_stopped_trade()
    test_tick_skips_unpriced_symbols()
