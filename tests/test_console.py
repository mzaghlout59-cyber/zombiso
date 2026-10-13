"""Output redirected to a file on Windows uses cp1252; the city must still print anything."""
import io
import sys

from core.logger import safe_console
from core.report import headline


def test_safe_console_prints_the_report_headline_under_cp1252(monkeypatch):
    raw = io.BytesIO()
    fake = io.TextIOWrapper(raw, encoding="cp1252")  # what a redirected Windows console gets
    monkeypatch.setattr(sys, "stdout", fake)
    monkeypatch.setattr(sys, "stderr", fake)
    safe_console()
    print(headline({"trades": [{}], "realized": -1.96, "pct": -0.02,
                    "start_equity": 10_000, "end_equity": 9_998.04}))
    fake.flush()
    assert "→" in raw.getvalue().decode("utf-8")
