"""Keep tests from writing into the real logs/ and data/ folders, and pin the risk limits
the tests were written against, so changing config/settings.py can't break them.
(tests/test_new_limits.py checks the live values separately.)"""
import pytest

import core.logger
import run_city
from config import settings

BASELINE = {"MAX_RISK_PER_TRADE_PCT": 0.25, "MAX_DAILY_LOSS_PCT": 1.0, "DAILY_PROFIT_TARGET": 1000.0}


@pytest.fixture(scope="session", autouse=True)
def baseline_limits():
    # session scope, so module-scoped fixtures (shared simulated runs) see these values too
    mp = pytest.MonkeyPatch()
    for name, value in BASELINE.items():
        mp.setattr(settings, name, value)
    yield
    mp.undo()


@pytest.fixture(autouse=True)
def isolate_files(tmp_path, monkeypatch):
    monkeypatch.setattr(core.logger, "LOG_PATH", tmp_path / "logs" / "city.log")
    monkeypatch.setattr(run_city, "RUNS_DIR", tmp_path / "runs")
