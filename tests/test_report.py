"""Raphael's daily report matches the run it describes."""
from core.prices import SimulatedFeed
from core.report import headline, summarize, to_html, to_markdown
from run_city import build_city, new_run_dir, run_city, START_PRICES


def finished(seed=1, cycles=60):
    run_dir = new_run_dir()
    raphael = run_city(SimulatedFeed(START_PRICES, seed=seed), cycles=cycles,
                       raphael=build_city(run_dir=run_dir))
    return run_dir, raphael


def test_every_run_writes_a_report_that_matches_the_books():
    run_dir, raphael = finished()
    assert (run_dir / "report.html").exists() and (run_dir / "report.md").exists()
    s = summarize(raphael.events.events, audit=raphael.audit)
    closed = [t for t in raphael.ledger.trades if t["status"] == "closed"]
    assert len(s["trades"]) == len(closed)
    assert s["realized"] == round(sum(t["pnl"] for t in closed), 2)
    assert s["end_equity"] == raphael.treasury.equity
    assert s["wins"] + s["losses"] == len(closed)
    assert len(s["still_open"]) == len(raphael.ledger.open_trades())


def test_report_explains_trades_in_plain_words():
    run_dir, raphael = finished()
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    page = (run_dir / "report.html").read_text(encoding="utf-8")
    assert "Raphael's daily report" in md and "Every trade" in md
    assert any(w in md for w in ("hit its profit target", "hit its stop-loss"))
    assert "Ultron's check" in md and "no rule was broken" in md
    assert "<table>" in page and "Raphael&#x27;s daily report" not in page  # no double escaping
    assert "max open positions" not in md  # technical reasons are translated


def test_headline_cases():
    base = {"start_equity": 10_000, "trades": [{}]}
    assert headline({**base, "realized": 50, "pct": 0.5, "end_equity": 10_050}).startswith("The city made $50.00 (+0.50%)")
    assert "lost $20.00" in headline({**base, "realized": -20, "pct": -0.2, "end_equity": 9_980})
    assert "broke even" in headline({**base, "realized": 0, "pct": 0, "end_equity": 10_000})
    assert headline({"trades": []}).startswith("No trades closed today")


def test_report_with_no_trades_still_renders():
    s = summarize([{"seq": 1, "tick": 0, "day": 0, "kind": "treasury", "equity": 10_000.0,
                    "allocations": {"Investment": 1.0}, "division": "Investment"}])
    assert "No trades closed today" in to_markdown(s)
    assert "No trades closed today" in to_html(s)
