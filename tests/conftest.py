"""Keep tests from writing into the real logs/ and data/ folders."""
import pytest

import core.logger
import run_city


@pytest.fixture(autouse=True)
def isolate_files(tmp_path, monkeypatch):
    monkeypatch.setattr(core.logger, "LOG_PATH", tmp_path / "logs" / "city.log")
    monkeypatch.setattr(run_city, "RUNS_DIR", tmp_path / "runs")
