"""Tests for the city runner: a short seeded run on a throwaway ledger."""
import tempfile
from pathlib import Path

from core.ledger import PaperLedger
from core.prices import SimulatedFeed
from run_city import build_city, run_city, START_PRICES


def _fresh_run(seed=42, cycles=30):
    tmp = Path(tempfile.mkdtemp()) / "ledger.json"
    ledger = PaperLedger(path=tmp)
    raphael = build_city(ledger=ledger)
    run_city(SimulatedFeed(START_PRICES, seed=seed), cycles=cycles, raphael=raphael)
    return ledger


def test_run_is_repeatable():
    a = _fresh_run(seed=42)
    b = _fresh_run(seed=42)
    pnl_a = [t["pnl"] for t in a.trades if t["status"] == "closed"]
    pnl_b = [t["pnl"] for t in b.trades if t["status"] == "closed"]
    assert pnl_a == pnl_b and len(pnl_a) > 0
    print("PASS: same seed gives identical trades on a fresh ledger")


def test_daily_pnl_matches_todays_closed_trades():
    ledger = _fresh_run()
    today = ledger.clock.day
    assert today > 0  # 30 cycles span more than one sim day
    closed_sum = round(sum(t["pnl"] for t in ledger.trades
                           if t["status"] == "closed" and t["closed_day"] == today), 2)
    assert round(ledger.daily_pnl(), 2) == closed_sum
    print("PASS: daily_pnl equals the sum of today's closed-trade pnl")


def test_never_more_than_three_open():
    ledger = _fresh_run()
    assert len(ledger.open_trades()) <= 3
    print("PASS: open positions never exceed the cap at the end of a run")


def test_no_duplicate_open_symbols():
    ledger = _fresh_run()
    symbols = [t["symbol"] for t in ledger.open_trades()]
    assert len(symbols) == len(set(symbols))
    print("PASS: no symbol held twice")


if __name__ == "__main__":
    test_run_is_repeatable()
    test_daily_pnl_matches_closed_trades()
    test_never_more_than_three_open()
    test_no_duplicate_open_symbols()
