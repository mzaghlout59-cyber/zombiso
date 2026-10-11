"""Run the city for one real US market session, on real Alpaca prices. PAPER ONLY.

    python market_day.py                 # wait for today's open, trade until the close
    python market_day.py --interval 60   # one cycle per minute instead of every 5
    python market_day.py --check         # just test the Alpaca keys and show the market clock

Started each weekday by Windows Task Scheduler. Alpaca's market clock decides
everything time-related (New York hours, daylight saving, holidays): if the
market does not open within --max-wait-hours, the script exits and does nothing.

One session = one city day. Every open position is exited a minute before the
close, so nothing is carried overnight. Trades are recorded only in the city's
own PaperLedger; no order is ever sent to Alpaca or anywhere else.
"""
import argparse
import sys
import time
from datetime import datetime

from config import settings
from pathlib import Path

from core.alpaca import AlpacaError, AlpacaFeed, fetch_daily_bars, fetch_news, market_clock
from core.llm import LLMUnavailable, make_client
from core.treasury import Treasury
from divisions.research.bureau import ResearchBureau
from run_city import START_PRICES, WINDOW, build_city, new_run_dir, run_city

CLOSE_BUFFER_S = 60  # stop this long before the closing bell
TREASURY_PATH = Path("data/treasury.json")  # equity carried from one market day to the next


def plan_session(clock, interval, max_wait_hours):
    """Return (seconds to wait for the open, number of cycles), or None if no session soon."""
    if clock["is_open"]:
        wait = 0.0
        start = clock["now"]
    else:
        wait = (clock["next_open"] - clock["now"]).total_seconds()
        if wait > max_wait_hours * 3600:
            return None
        start = clock["next_open"]
    session_s = (clock["next_close"] - start).total_seconds() - CLOSE_BUFFER_S
    cycles = int(session_s // interval)
    if cycles < 1:
        return None
    return wait, cycles


def write_briefing(symbols, bureau=None, session=None):
    """Pre-open: the Research bureau reads daily bars + overnight news and writes a briefing."""
    bureau = bureau or ResearchBureau()
    try:
        bars = fetch_daily_bars(symbols, days=5, session=session)
        news = {sym: fetch_news([sym], hours=18, limit=8, session=session) for sym in symbols}
    except AlpacaError as e:
        print(f"Research: no market data for the briefing ({e})")
        bars, news = {}, {}
    briefing = bureau.handle({"symbols": symbols, "bars": bars, "news": news})
    print(f"Research briefing: {briefing['status']} | bias {briefing['bias']}")
    return briefing


def main(argv=None):
    p = argparse.ArgumentParser(description="Run the city for one real market session (paper only).")
    p.add_argument("--interval", type=int, default=300, help="seconds between cycles (default 300 = 5 min)")
    p.add_argument("--max-wait-hours", type=float, default=3.0,
                   help="exit if the market does not open within this many hours")
    p.add_argument("--symbols", default=",".join(START_PRICES), help="comma-separated watchlist")
    p.add_argument("--check", action="store_true", help="test the keys and print the market clock, then exit")
    args = p.parse_args(argv)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== {settings.PROJECT_NAME} market day | {stamp} | mode: {settings.TRADING_MODE} ===")
    try:
        clock = market_clock()
    except AlpacaError as e:
        print(f"Cannot reach Alpaca: {e}")
        return 1
    print(f"Market open now: {clock['is_open']} | next open {clock['next_open']} | "
          f"next close {clock['next_close']}")
    if args.check:
        feed = AlpacaFeed(symbols)
        feed.advance()
        for sym in symbols:
            try:
                print(f"  {sym}: {feed.get_price(sym)}")
            except KeyError:
                print(f"  {sym}: no price")
        try:
            make_client()
            print("Claude: ANTHROPIC_API_KEY set and SDK loads (News and Research can run)")
        except LLMUnavailable as e:
            print(f"Claude: unavailable, News stays neutral and no briefing ({e})")
        return 0

    plan = plan_session(clock, args.interval, args.max_wait_hours)
    if plan is None:
        print("No market session within the wait window (weekend or holiday). Nothing to do.")
        return 0
    wait, cycles = plan
    briefing = write_briefing(symbols)
    if wait > 0:
        print(f"Waiting {wait / 60:.0f} minutes for the opening bell...")
        time.sleep(wait + 5)
        clock = market_clock()
        plan = plan_session(clock, args.interval, 0)
        if plan is None:
            print("Market did not open as expected. Nothing to do.")
            return 0
        _, cycles = plan

    feed = AlpacaFeed(symbols)
    feed.load_history(WINDOW)
    run_dir = new_run_dir()
    print(f"Session: {cycles} cycles, one every {args.interval}s | run folder {run_dir}")
    treasury = Treasury(path=TREASURY_PATH)
    print(f"Treasury: starting equity ${treasury.equity:,.2f}")
    raphael = build_city(run_dir=run_dir, cycles_per_day=cycles, treasury=treasury,
                         news_source=lambda sym: fetch_news([sym], hours=24, limit=10))
    raphael.sage.briefing = briefing["bias"]
    raphael.events.emit("briefing", status=briefing["status"], summary=briefing["summary"],
                        symbols=briefing["symbols"], bias=briefing["bias"])
    (run_dir / "briefing.md").write_text(
        ResearchBureau.to_markdown(briefing, datetime.now().strftime("%Y-%m-%d")), encoding="utf-8")
    run_city(feed, cycles=cycles, watchlist=symbols, raphael=raphael, tick_delay=args.interval,
             warmup=False, close_at_end=True, source="alpaca")
    day = treasury.settle(run_dir.name)
    print(f"Treasury: day P&L ${day['pnl']:+,.2f}, equity now ${day['end_equity']:,.2f}")
    print(f"Session saved to {run_dir}")
    return 0 if raphael.audit["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
