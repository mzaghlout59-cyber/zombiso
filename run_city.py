"""Zombiso AI City: single paper-trading runner.

Each cycle: advance the market and the city clock, run exits first (realized
losses reach Aegis), then evaluate each watched symbol. When the run ends,
Ultron audits the event stream. Paper trading only; the safety lock in
config/settings.py still applies.

Every run gets its own folder under data/runs/ with a fresh ledger and an
events.jsonl stream, so runs never leak into each other.
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from config import settings
from core.clock import SimClock
from core.events import EventLog
from core.ledger import PaperLedger
from core.raphael import Raphael
from core.prices import SimulatedFeed
from core.ultron import Ultron
from divisions.investment.agents import (
    MarketResearchAgent,
    NewsResearchAgent,
    PortfolioManagerAgent,
    PerformanceAnalystAgent,
    SentimentAgent,
    ChartsAgent,
)
from divisions.investment.strategist import StrategistAgent
from divisions.investment.aegis import AegisAgent

START_PRICES = {"AAPL": 100.0, "MSFT": 100.0, "NVDA": 100.0}
CYCLES = 30
WINDOW = 6  # how many recent prices the Strategist sees
RUNS_DIR = Path("data/runs")

AGENT_CLASSES = [
    MarketResearchAgent,
    NewsResearchAgent,
    StrategistAgent,
    AegisAgent,
    PortfolioManagerAgent,
    PerformanceAnalystAgent,
    SentimentAgent,
    ChartsAgent,
]


def new_run_dir(root=None):
    """A fresh, timestamped folder for one run's ledger and events."""
    run_dir = Path(root or RUNS_DIR) / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def build_city(ledger=None, run_dir=None, cycles_per_day=None):
    """Wire up the city. Pass a ledger (tests) or a run_dir; with neither, a new run dir is made."""
    clock = SimClock(cycles_per_day)
    events_path = None
    if ledger is None:
        run_dir = run_dir or new_run_dir()
        ledger = PaperLedger(Path(run_dir) / "ledger.json", clock=clock)
    if run_dir:
        events_path = Path(run_dir) / "events.jsonl"
    raphael = Raphael(ledger=ledger, clock=clock, events=EventLog(clock=clock, path=events_path))
    for agent_class in AGENT_CLASSES:
        raphael.register(agent_class())
    return raphael


def _write_run_file(raphael, name, data):
    """Save a JSON file next to the run's events.jsonl, if this run has a folder."""
    if raphael.events.path:
        (raphael.events.path.parent / name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _prices_now(feed, watchlist):
    prices = {}
    for sym in watchlist:
        try:
            prices[sym] = feed.get_price(sym)
        except KeyError:
            pass  # no data for this symbol yet
    return prices


def run_city(feed, cycles=CYCLES, watchlist=None, raphael=None, window=WINDOW, tick_delay=0.0,
             warmup=True, close_at_end=False, source="simulated"):
    """Run the city for a number of cycles.

    tick_delay: seconds per cycle (wall clock), so a viewer can follow live, or so a
        real-market run takes one cycle every few minutes.
    warmup: advance the feed `window` times first (simulated feeds start with one price).
    close_at_end: exit every open trade after the last cycle (market close).
    """
    raphael = raphael or build_city()
    watchlist = watchlist or list(START_PRICES)
    opened = closed = 0
    if raphael.events.path:
        _write_run_file(raphael, "meta.json", {
            "run_id": raphael.events.path.parent.name,
            "source": source,
            "cycles": cycles,
            "cycles_per_day": raphael.clock.cycles_per_day,
            "watchlist": watchlist,
            "account_size": settings.ACCOUNT_SIZE,
            "max_open_positions": settings.MAX_OPEN_POSITIONS,
            "max_daily_loss": settings.ACCOUNT_SIZE * settings.MAX_DAILY_LOSS_PCT / 100,
            "max_risk_per_trade": settings.ACCOUNT_SIZE * settings.MAX_RISK_PER_TRADE_PCT / 100,
            "take_profit_rr": settings.TAKE_PROFIT_RR,
        })

    # Warm-up: let the market move so every symbol has enough history.
    if warmup:
        for _ in range(window):
            feed.advance()

    started = time.monotonic()
    for cycle in range(1, cycles + 1):
        feed.advance()
        raphael.clock.advance()
        raphael.events.emit("tick", prices=_prices_now(feed, watchlist))

        # 1. Exits first, so realized losses count before new entries
        for t in raphael.tick(feed):
            closed += 1
            print(f"[cycle {cycle}] CLOSED {t['symbol']} ({t['exit_reason']}) pnl={t['pnl']}")

        # 2. Evaluate each symbol on its latest prices
        for sym in watchlist:
            history = feed.get_history(sym, window)
            before = len(raphael.ledger.open_trades())
            raphael.run_goal(f"Evaluate {sym}", {"symbol": sym, "prices": history})
            if len(raphael.ledger.open_trades()) > before:
                opened += 1
                print(f"[cycle {cycle}] OPENED {sym}")

        if tick_delay and cycle < cycles:
            # sleep to the next scheduled cycle, so slow cycles don't drift the schedule
            time.sleep(max(0.0, started + cycle * tick_delay - time.monotonic()))

    if close_at_end:
        for t in raphael.close_all(feed):
            closed += 1
            print(f"[close] CLOSED {t['symbol']} (end of day) pnl={t['pnl']}")

    print(f"\n=== RUN COMPLETE: {cycles} cycles, {raphael.clock.day + 1} day(s) "
          f"| opened={opened} closed={closed} "
          f"| open now={len(raphael.ledger.open_trades())} "
          f"| today's pnl={raphael.ledger.daily_pnl():.2f} ===")

    raphael.audit = Ultron().audit(raphael.events, raphael.ledger)
    for v in raphael.audit["violations"]:
        print(f"ULTRON VIOLATION (tick {v['tick']}): {v['message']}")
    for w in raphael.audit["warnings"]:
        print(f"ULTRON warning (tick {w['tick']}): {w['message']}")
    _write_run_file(raphael, "audit.json", raphael.audit)
    return raphael


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Zombiso AI City paper-trading simulation.")
    parser.add_argument("--seed", type=int, default=42, help="market seed (same seed = same run)")
    parser.add_argument("--cycles", type=int, default=CYCLES, help="number of cycles to run")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="seconds per cycle; use e.g. 0.5 to watch live in view_city.py")
    args = parser.parse_args()

    print(f"=== {settings.PROJECT_NAME} | mode: {settings.TRADING_MODE} ===")
    run_dir = new_run_dir()
    print(f"Run folder: {run_dir}")
    run_city(SimulatedFeed(START_PRICES, seed=args.seed), cycles=args.cycles,
             raphael=build_city(run_dir=run_dir), tick_delay=args.delay)
    print(f"Run saved to {run_dir}")
