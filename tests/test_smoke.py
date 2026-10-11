"""Multi-seed smoke + regression run: the city's safety rules hold across many markets.

Every trade the ledger opens is checked against the state Aegis saw at that moment.
"""
import pytest

from config import settings
from core.ledger import PaperLedger
from core.prices import SimulatedFeed
from run_city import build_city, run_city, START_PRICES

SEEDS = range(10)
CYCLES = 60
MAX_RISK = settings.ACCOUNT_SIZE * settings.MAX_RISK_PER_TRADE_PCT / 100
MAX_DAILY_LOSS = settings.ACCOUNT_SIZE * settings.MAX_DAILY_LOSS_PCT / 100


def _run(seed, tmp_path):
    """Run the city and record the ledger state just before each trade opens."""
    ledger = PaperLedger(tmp_path / f"ledger_{seed}.json")
    snapshots = []
    open_trade = ledger.open_trade

    def recording_open_trade(symbol, side, size, entry, stop_loss):
        snapshots.append({
            "symbol": symbol,
            "planned_risk": abs(entry - stop_loss) * size,
            "daily_pnl": ledger.daily_pnl(),
            "open_positions": ledger.open_positions(),
            "open_symbols": ledger.open_symbols(),
        })
        return open_trade(symbol, side, size, entry, stop_loss)

    ledger.open_trade = recording_open_trade
    run_city(SimulatedFeed(START_PRICES, seed=seed), cycles=CYCLES,
             raphael=build_city(ledger=ledger))
    return ledger, snapshots


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("smoke")
    return {seed: _run(seed, tmp) for seed in SEEDS}


def test_city_trades_at_all(runs):
    assert sum(len(ledger.trades) for ledger, _ in runs.values()) > 0


@pytest.mark.parametrize("seed", SEEDS)
def test_every_open_respected_aegis_rules(runs, seed):
    _, snapshots = runs[seed]
    for s in snapshots:
        assert s["planned_risk"] <= MAX_RISK + 1e-9
        assert s["daily_pnl"] > -MAX_DAILY_LOSS
        assert s["open_positions"] < settings.MAX_OPEN_POSITIONS
        assert s["symbol"] not in s["open_symbols"]


@pytest.mark.parametrize("seed", SEEDS)
def test_every_trade_has_stop_and_valid_close(runs, seed):
    ledger, _ = runs[seed]
    for t in ledger.trades:
        assert t["stop_loss"] is not None and t["stop_loss"] < t["entry"]
        if t["status"] == "closed":
            expected = round((t["exit"] - t["entry"]) * t["size"], 2)
            assert t["pnl"] == expected


@pytest.mark.parametrize("seed", [0, 5])
def test_same_seed_is_repeatable(seed, tmp_path):
    a, _ = _run(seed, tmp_path / "a")
    b, _ = _run(seed, tmp_path / "b")
    strip = lambda ledger: [(t["symbol"], t["entry"], t["exit"], t["pnl"]) for t in ledger.trades]
    assert strip(a) == strip(b)


@pytest.mark.xfail(strict=True, reason=(
    "Known gap: exits fill at the tick price, not the stop. When price gaps "
    "through the stop in one step, the realized loss exceeds MAX_RISK_PER_TRADE."))
def test_realized_loss_never_exceeds_max_risk(runs):
    worst = min(t["pnl"] for ledger, _ in runs.values()
                for t in ledger.trades if t["status"] == "closed")
    assert worst >= -MAX_RISK
