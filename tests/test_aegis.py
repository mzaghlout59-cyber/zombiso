import pytest

from divisions.investment.aegis import AegisAgent

# Account = 10,000 -> max risk per trade = $25, max daily loss = $100.
# Risk is worst-case: stop distance x size x STOP_GAP_BUFFER (2.0).


@pytest.mark.parametrize("label, trade, state, expected", [
    ("valid trade, risk $20", {"entry": 100, "stop_loss": 99.0, "size": 10}, {}, True),
    ("risk exactly at max, $25", {"entry": 100, "stop_loss": 99.0, "size": 12.5}, {}, True),
    ("risk too big, $26", {"entry": 100, "stop_loss": 99.0, "size": 13}, {}, False),
    ("fits without buffer, not with it", {"entry": 100, "stop_loss": 99.0, "size": 20}, {}, False),
    ("no stop-loss", {"entry": 100, "stop_loss": None, "size": 10}, {}, False),
    ("negative stop-loss", {"entry": 100, "stop_loss": -1, "size": 10}, {}, False),
    ("invalid size 0", {"entry": 100, "stop_loss": 99.0, "size": 0}, {}, False),
    ("invalid entry 0", {"entry": 0, "stop_loss": 99.0, "size": 10}, {}, False),
    ("3 positions already open", {"entry": 100, "stop_loss": 99.0, "size": 10},
     {"open_positions": 3}, False),
    ("daily loss limit hit", {"entry": 100, "stop_loss": 99.0, "size": 10},
     {"daily_pnl": -100.0}, False),
    ("loss just under limit", {"entry": 100, "stop_loss": 99.0, "size": 10},
     {"daily_pnl": -99.99}, True),
    ("symbol already held", {"entry": 100, "stop_loss": 99.0, "size": 10},
     {"open_symbols": {"AAPL"}}, False),
    ("losing streak hit", {"entry": 100, "stop_loss": 99.0, "size": 10},
     {"loss_streak": 4}, False),
    ("streak one below limit", {"entry": 100, "stop_loss": 99.0, "size": 10},
     {"loss_streak": 3}, True),
])
def test_evaluate(label, trade, state, expected):
    a = AegisAgent()
    for attr, value in state.items():
        setattr(a, attr, value)
    result = a.evaluate("AAPL", trade)
    assert result["approved"] is expected, f"{label}: {result['reason']}"


def test_handle_denies_when_no_trade_supplied():
    result = AegisAgent().handle({"symbol": "AAPL", "recommendation": {"action": "hold"}})
    assert result["approved"] is False
    assert "no trade details" in result["reason"]
