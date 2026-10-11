from config import settings
from divisions.investment.aegis import AegisAgent
from divisions.investment.strategist import StrategistAgent


def propose(prices):
    return StrategistAgent().handle({"symbol": "AAPL", "prices": prices})


def test_downtrend_then_pop_buys():
    r = propose([100, 99, 98, 97, 96, 105])
    assert r["signal"] == "buy"
    trade = r["trade"]
    assert trade["entry"] == 105
    assert trade["stop_loss"] < trade["entry"]
    assert trade["size"] >= 1


def test_proposal_fits_risk_budget_and_passes_aegis():
    trade = propose([100, 99, 98, 97, 96, 105])["trade"]
    max_risk = settings.ACCOUNT_SIZE * settings.MAX_RISK_PER_TRADE_PCT / 100
    assert (trade["entry"] - trade["stop_loss"]) * trade["size"] <= max_risk
    assert AegisAgent().evaluate("AAPL", trade)["approved"] is True


def test_steady_downtrend_holds():
    r = propose([100, 99, 98, 97, 96, 95])
    assert r["signal"] == "hold" and r["trade"] is None


def test_too_little_data_holds():
    r = propose([100, 101])
    assert r["signal"] == "hold" and r["trade"] is None
