import copy

import pytest

from config import settings
from core.ledger import PaperLedger
from core.prices import SimulatedFeed
from core.treasury import Treasury
from core.ultron import Ultron
from divisions.investment.strategist import StrategistAgent
from run_city import build_city, run_city, START_PRICES

POP = [100, 99, 98, 97, 96, 105]


def test_equity_and_allocations():
    t = Treasury(start_equity=10_000, allocations={"Investment": 0.6, "Crypto": 0.4})
    t.record(250.0)
    t.record(-50.0)
    assert t.equity == 10_200.0
    assert t.capital_for("Investment") == 6_120.0
    assert t.capital_for("Unknown") == 0.0
    assert t.handle({})["capital"] == {"Investment": 6_120.0, "Crypto": 4_080.0}


def test_allocations_cannot_exceed_100_percent():
    with pytest.raises(ValueError):
        Treasury(allocations={"Investment": 0.8, "Crypto": 0.3})


def test_equity_carries_over_between_runs(tmp_path):
    path = tmp_path / "treasury.json"
    day1 = Treasury(path=path)
    assert day1.equity == settings.ACCOUNT_SIZE
    day1.record(-120.0)
    assert day1.settle("run-1")["end_equity"] == settings.ACCOUNT_SIZE - 120

    day2 = Treasury(path=path)
    assert day2.equity == settings.ACCOUNT_SIZE - 120
    day2.record(40.0)
    day2.settle("run-2")
    assert [h["run_id"] for h in Treasury(path=path).history] == ["run-1", "run-2"]
    assert Treasury(path=path).equity == settings.ACCOUNT_SIZE - 80


def test_positions_compound_with_capital():
    small = StrategistAgent().handle({"symbol": "AAPL", "prices": POP, "capital": 10_000})
    big = StrategistAgent().handle({"symbol": "AAPL", "prices": POP, "capital": 30_000})
    assert big["trade"]["size"] > small["trade"]["size"]


def test_city_uses_and_feeds_the_treasury(tmp_path):
    treasury = Treasury(start_equity=20_000)
    raphael = build_city(ledger=PaperLedger(tmp_path / "l.json"), treasury=treasury)
    run_city(SimulatedFeed(START_PRICES, seed=1), cycles=60, raphael=raphael)
    realized = sum(t["pnl"] for t in raphael.ledger.trades if t["status"] == "closed")
    assert treasury.equity == round(20_000 + realized, 2)
    first = raphael.events.of_kind("trade_opened")[0]
    assert first["capital"] == 20_000  # no trade had closed yet
    assert raphael.audit["ok"], raphael.audit["violations"]


def test_ultron_catches_wrong_capital(tmp_path):
    raphael = build_city(ledger=PaperLedger(tmp_path / "l.json"))
    run_city(SimulatedFeed(START_PRICES, seed=1), cycles=60, raphael=raphael)
    events = copy.deepcopy(raphael.events.events)
    next(e for e in events if e["kind"] == "trade_opened")["capital"] *= 2
    report = Ultron().audit(events)
    assert any("Treasury replay says" in v["message"] for v in report["violations"])
