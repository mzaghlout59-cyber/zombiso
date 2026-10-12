"""The paper trial scorecard: totals, pass/fail rules and agent scoring."""
import json
from datetime import date


from config import settings
from core import trial
from core.prices import SimulatedFeed
from run_city import build_city, new_run_dir, run_city, START_PRICES


def market_day(runs_dir, seed, cycles=60):
    """A practice run labelled as a real market day, standing in for Alpaca."""
    run_dir = new_run_dir(runs_dir)
    run_city(SimulatedFeed(START_PRICES, seed=seed), cycles=cycles, raphael=build_city(run_dir=run_dir),
             close_at_end=True, source="alpaca")
    return run_dir


def test_start_sets_the_trial_and_keeps_old_treasury_aside(tmp_path):
    treasury = tmp_path / "treasury.json"
    treasury.write_text('{"equity": 9000, "history": []}')
    t = trial.start(days=7, trial_dir=tmp_path / "trial", treasury_path=treasury, today="2026-10-13")
    assert t == {"started": "2026-10-13", "days": 7}
    assert trial.load(tmp_path / "trial") == t
    assert not treasury.exists()
    assert json.loads((tmp_path / "treasury.before-trial-2026-10-13.json").read_text())["equity"] == 9000


def test_only_finished_market_runs_since_the_start_count(tmp_path):
    runs = tmp_path / "runs"
    real = market_day(runs, seed=1, cycles=20)
    practice = new_run_dir(runs)
    run_city(SimulatedFeed(START_PRICES, seed=2), cycles=10, raphael=build_city(run_dir=practice))
    (runs / "20200101-000000-000000").mkdir()  # old and unfinished: ignored
    today = date.today().isoformat()
    assert trial.market_runs(runs, today) == [real]
    assert trial.market_runs(runs, "2999-01-01") == []


def test_score_matches_the_books(tmp_path):
    runs = tmp_path / "runs"
    dirs = [market_day(runs, seed) for seed in (1, 4)]
    s = trial.score(dirs)
    closed = []
    for d in dirs:
        closed += [t for t in json.loads((d / "ledger.json").read_text()) if t["status"] == "closed"]
    assert s["trades"] == len(closed)
    assert s["pnl"] == round(sum(t["pnl"] for t in closed), 2)
    assert [d["trades"] for d in s["days"]] and len(s["days"]) == 2
    assert s["max_drawdown"] >= 0
    # Axiom proposes every trade, so its votes = trades and its accuracy = the win rate
    assert s["agents"]["Axiom"]["votes"] == s["trades"]
    assert s["agents"]["Axiom"]["right"] == s["wins"]


def test_agents_are_scored_right_or_wrong(tmp_path):
    def report(agent, result):
        return {"kind": "agent_report", "agent": agent, "tick": 1, "symbol": "A", "result": result}

    events = [
        {"kind": "treasury", "equity": 10_000, "tick": 0},
        report("MarketResearch", {"trend": "up"}),          # Scout votes buy
        report("Sentiment", {"crowd_mood": "bearish"}),     # Pulse votes sell (warns)
        report("Charts", {"pattern": "none"}),              # Lens abstains
        {"kind": "trade_opened", "trade_id": 1, "tick": 1, "symbol": "A"},
        {"kind": "trade_closed", "trade_id": 1, "tick": 5, "symbol": "A", "pnl": -10.0},
    ]
    run = tmp_path / "20261013-100000-000000"
    run.mkdir()
    (run / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    (run / "audit.json").write_text(json.dumps({"ok": True}))
    agents = trial.score([run])["agents"]
    assert (agents["Scout"]["right"], agents["Scout"]["wrong"]) == (0, 1)   # said up, trade lost
    assert (agents["Pulse"]["right"], agents["Pulse"]["wrong"]) == (1, 0)   # warned, trade lost
    assert agents["Lens"]["votes"] == 0                                     # abstained
    assert (agents["Axiom"]["right"], agents["Axiom"]["wrong"]) == (0, 1)


def test_verdict_runs_until_enough_days_then_judges(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    dirs = [market_day(runs, seed) for seed in (1, 4)]
    s = trial.score(dirs)
    running = trial.verdict(s, {"started": "x", "days": 7})
    assert running["status"] == "running" and running["days_done"] == 2

    monkeypatch.setattr(settings, "TRIAL_MIN_TRADES", 1)
    done = trial.verdict(s, {"started": "x", "days": 2})
    expected = "passed" if all(ok for _, ok, _ in done["checks"]) else "failed"
    assert done["status"] == expected
    assert [label for label, _, _ in done["checks"]][0] == "Made money overall"


def test_update_writes_the_scorecard(tmp_path):
    runs, trial_dir = tmp_path / "runs", tmp_path / "trial"
    assert trial.update(runs, trial_dir) is None
    trial.start(trial_dir=trial_dir, treasury_path=tmp_path / "none.json")
    market_day(runs, seed=1)
    s, v = trial.update(runs, trial_dir)
    page = (trial_dir / "scorecard.html").read_text(encoding="utf-8")
    assert v["days_done"] == 1 and "Day 1 of 7" in page
    assert "Agents: who helped, who hurt" in page and "report.html" in page
