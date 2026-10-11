"""Ledgerkeeper and Scorekeeper: Aegis's squad reports on the books."""
from core.ledger import PaperLedger
from core.prices import SimulatedFeed
from divisions.investment.agents import PerformanceAnalystAgent, PortfolioManagerAgent
from run_city import build_city, run_city, START_PRICES


def trade(tid, sym, pnl=None, entry=100.0, stop=98.0, size=5):
    t = {"id": tid, "symbol": sym, "side": "buy", "size": size, "entry": entry,
         "stop_loss": stop, "status": "open", "pnl": 0.0}
    if pnl is not None:
        t.update(status="closed", pnl=pnl)
    return t


def test_ledgerkeeper_reports_exposure_and_risk():
    r = PortfolioManagerAgent().handle({"trades": [
        trade(1, "AAPL"), trade(2, "MSFT", entry=200.0, stop=196.0, size=2), trade(3, "NVDA", pnl=5.0)]})
    assert r["positions"] == 2 and r["symbols"] == ["AAPL", "MSFT"]
    assert r["exposure"] == 900.0           # 5*100 + 2*200
    assert r["exposure_pct"] == 9.0
    assert r["at_risk"] == 18.0             # 5*2 + 2*4
    assert r["at_risk_pct"] == 0.18


def test_ledgerkeeper_empty_book():
    r = PortfolioManagerAgent().handle({"trades": []})
    assert (r["positions"], r["exposure"], r["at_risk"]) == (0, 0, 0)


def test_scorekeeper_scores_closed_trades_in_order():
    pnls = [10.0, -5.0, -4.0, -3.0, 20.0, -2.0]
    r = PerformanceAnalystAgent().handle({"trades": [trade(i + 1, "AAPL", p) for i, p in enumerate(pnls)]
                                                    + [trade(99, "MSFT")]})
    assert r["closed"] == 6 and r["pnl"] == 16.0
    assert (r["wins"], r["losses"]) == (2, 4)
    assert r["win_rate"] == 0.333
    assert r["avg_win"] == 15.0 and r["avg_loss"] == -3.5
    assert r["profit_factor"] == round(30 / 14, 2)
    assert r["loss_streak"] == 1 and r["max_loss_streak"] == 3


def test_scorekeeper_with_no_closed_trades():
    r = PerformanceAnalystAgent().handle({"trades": [trade(1, "AAPL")]})
    assert r["closed"] == 0 and r["win_rate"] is None and r["profit_factor"] is None


def test_squad_reports_every_cycle_and_matches_the_ledger(tmp_path):
    ledger = PaperLedger(tmp_path / "l.json")
    raphael = build_city(ledger=ledger)
    run_city(SimulatedFeed(START_PRICES, seed=1), cycles=40, raphael=raphael)
    reports = [e for e in raphael.events.of_kind("agent_report")
               if e["agent"] in ("PortfolioManager", "PerformanceAnalyst")]
    assert len(reports) == 2 * 40
    last = raphael.review()
    closed = [t for t in ledger.trades if t["status"] == "closed"]
    assert last["PerformanceAnalyst"]["closed"] == len(closed)
    assert last["PerformanceAnalyst"]["pnl"] == round(sum(t["pnl"] for t in closed), 2)
    assert last["PortfolioManager"]["positions"] == len(ledger.open_trades())
    assert raphael.audit["ok"]
