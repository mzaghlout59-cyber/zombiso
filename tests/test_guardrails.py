"""Guardrails on trades shaped like the Strategist's proposals (2% stop at $105)."""
import pytest

from divisions.investment.aegis import AegisAgent


@pytest.mark.parametrize("label, trade, expected", [
    ("oversized", {"entry": 105, "stop_loss": 102.9, "size": 100}, False),
    ("no stop-loss", {"entry": 105, "stop_loss": None, "size": 5}, False),
    ("sane trade", {"entry": 105, "stop_loss": 102.9, "size": 11}, True),
])
def test_guardrails(label, trade, expected):
    v = AegisAgent().evaluate("AAPL", trade)
    assert v["approved"] is expected, f"{label}: {v['reason']}"
