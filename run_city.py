"""Zombiso AI City: single paper-trading runner.

Each cycle: advance the market, run exits first (realized losses reach Aegis),
then evaluate each watched symbol. Paper trading only; the safety lock in
config/settings.py still applies.
"""
from config import settings
from core.raphael import Raphael
from core.prices import SimulatedFeed
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


def build_city(ledger=None):
    raphael = Raphael(ledger=ledger)
    for agent_class in [
        MarketResearchAgent,
        NewsResearchAgent,
        StrategistAgent,
        AegisAgent,
        PortfolioManagerAgent,
        PerformanceAnalystAgent,
        SentimentAgent,
        ChartsAgent,
    ]:
        raphael.register(agent_class())
    return raphael


def run_city(feed, cycles=CYCLES, watchlist=None, raphael=None, window=WINDOW):
    raphael = raphael or build_city()
    watchlist = watchlist or list(START_PRICES)
    opened = closed = 0

    # Warm-up: let the market move so every symbol has enough history.
    for _ in range(window):
        feed.advance()

    for cycle in range(1, cycles + 1):
        feed.advance()

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

    print(f"\n=== RUN COMPLETE: {cycles} cycles | opened={opened} closed={closed} "
          f"| open now={len(raphael.ledger.open_trades())} "
          f"| daily pnl={raphael.ledger.daily_pnl():.2f} ===")
    return raphael


if __name__ == "__main__":
    print(f"=== {settings.PROJECT_NAME} | mode: {settings.TRADING_MODE} ===")
    run_city(SimulatedFeed(START_PRICES, seed=42))
