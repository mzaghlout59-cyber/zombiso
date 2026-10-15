"""Run the city for one real US market session, on real Alpaca prices. PAPER ONLY.

    python market_day.py                 # wait for today's open, trade until the close
    python market_day.py --interval 60   # one cycle per minute instead of every 5
    python market_day.py --check         # just test the Alpaca keys and show the market clock
    python market_day.py --service       # run forever: every market day, PC kept awake in between

Started each weekday by Windows Task Scheduler. Alpaca's market clock decides
everything time-related (New York hours, daylight saving, holidays): if the
market does not open within --max-wait-hours, the script exits and does nothing.

One session = one city day. Every open position is exited a minute before the
close, so nothing is carried overnight. Trades are recorded only in the city's
own PaperLedger; no order is ever sent to Alpaca or anywhere else.
"""
import argparse
import os
import sys
import time
from datetime import datetime

from config import settings
from pathlib import Path

from core import trial
from core.alpaca import AlpacaError, AlpacaFeed, fetch_daily_bars, fetch_news, market_clock
from core.llm import LLMUnavailable, check_ready
from core.logger import safe_console
from core.treasury import Treasury
from divisions.research.bureau import ResearchBureau
from run_city import WINDOW, build_city, new_run_dir, run_city

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


LOCK_PATH = Path("data/market_day.lock")


def traded_today(runs_dir=Path("data/runs"), today=None):
    """True if a real-market run already finished today (it has an audit)."""
    today = today or datetime.now().strftime("%Y%m%d")
    if not runs_dir.is_dir():
        return False
    for d in runs_dir.glob(f"{today}-*"):
        meta = d / "meta.json"
        if (d / "audit.json").exists() and meta.exists() and '"alpaca"' in meta.read_text(encoding="utf-8"):
            return True
    return False


def _pid_alive(pid):
    try:
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    except (AttributeError, OSError):  # not Windows
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def clock_with_retry(tries=10, wait_s=60, clock=None):
    """Alpaca's market clock, retried through short network outages (about 10 minutes)."""
    clock = clock or market_clock
    for attempt in range(1, tries + 1):
        try:
            return clock()
        except AlpacaError as e:
            if attempt == tries:
                raise
            print(f"Market clock unavailable ({e}); retrying in {wait_s}s ({attempt}/{tries})")
            time.sleep(wait_s)


def keep_awake(on=True):
    """Ask Windows not to sleep while a session trades (like a video player does).
    No-op elsewhere. The request ends when this process exits."""
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0)
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))
    except (AttributeError, OSError):
        return False


def take_lock(path=LOCK_PATH):
    """One market day at a time: False if another live copy holds the lock."""
    # A session lasts under 8 hours, so an older lock is a leftover even if its PID
    # has since been reused by some other program.
    if path.exists() and time.time() - path.stat().st_mtime < 16 * 3600:
        try:
            if _pid_alive(int(path.read_text().strip())):
                return False
        except ValueError:
            pass  # unreadable lock: a leftover from a crash
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()))
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description="Run the city for one real market session (paper only).")
    p.add_argument("--interval", type=int, default=300, help="seconds between cycles (default 300 = 5 min)")
    p.add_argument("--max-wait-hours", type=float, default=3.0,
                   help="exit if the market does not open within this many hours")
    p.add_argument("--symbols", default=",".join(settings.WATCHLIST),
                   help="comma-separated watchlist (default: WATCHLIST in config/settings.py)")
    p.add_argument("--check", action="store_true", help="test the keys and print the market clock, then exit")
    p.add_argument("--service", action="store_true",
                   help="run forever: trade every market day and keep the PC awake in between")
    p.add_argument("--log", help="append all output to this file (for running with no window, via pythonw)")
    args = p.parse_args(argv)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if args.log:
        # pythonw has no console; write everything (tracebacks included) to the log instead.
        Path(args.log).parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(args.log, "a", encoding="utf-8", errors="replace", buffering=1)
    else:
        safe_console()

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== {settings.PROJECT_NAME} market day | {stamp} | mode: {settings.TRADING_MODE} ===")
    try:
        clock = clock_with_retry(tries=1 if args.check else 10)
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
            check_ready()
            print("Claude: ANTHROPIC_API_KEY set (News and Research can run)")
        except LLMUnavailable as e:
            print(f"Claude: unavailable, News stays neutral and no briefing ({e})")
        return 0

    if args.service:
        return run_service(args, symbols)

    # Started again after a restart or at login: never trade the same day twice,
    # and never run two copies at once.
    if traded_today():
        print("Today's market session is already done. Nothing to do.")
        return 0
    if not take_lock():
        print("Another copy of the market day is already running. Nothing to do.")
        return 0
    if keep_awake():
        print("Keeping the PC awake until the session ends.")
    try:
        return _session(args, symbols, clock)
    finally:
        keep_awake(False)
        LOCK_PATH.unlink(missing_ok=True)


SESSION_LEAD_HOURS = 1.0  # the service starts a day's session this long before the open


def next_nap(clock, lead_hours=SESSION_LEAD_HOURS, max_nap_s=30 * 60):
    """Seconds the service should wait before checking again: until shortly before the next
    session, in steps of at most 30 minutes (so a changed clock or holiday is noticed)."""
    until = (clock["next_open"] - clock["now"]).total_seconds() - lead_hours * 3600
    return max(60.0, min(float(max_nap_s), until))


def run_service(args, symbols):
    """Run forever: trade every market day, and keep the PC awake in between so it never
    sleeps through an opening bell (the user chose this over enabling wake timers)."""
    while not take_lock():  # a one-off market day may still be finishing
        print("Waiting for the running market day to finish...")
        time.sleep(300)
    keep_awake()
    print("Service mode: trading every market day and keeping the PC awake in between.")
    try:
        while True:
            try:
                clock = clock_with_retry(tries=60, wait_s=60)  # rides out outages up to an hour
            except AlpacaError as e:
                print(f"Still no connection to Alpaca ({e}); trying again in 5 minutes")
                time.sleep(300)
                continue
            if not traded_today() and plan_session(clock, args.interval, SESSION_LEAD_HOURS):
                stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"=== {settings.PROJECT_NAME} market day | {stamp} | mode: {settings.TRADING_MODE} ===")
                try:
                    _session(args, symbols, clock)
                except Exception:  # never let one bad day stop the service
                    import traceback
                    traceback.print_exc()
                    time.sleep(300)
                continue
            nap = next_nap(clock)
            print(f"[service {datetime.now():%Y-%m-%d %H:%M}] next open {clock['next_open']}; "
                  f"checking again in {nap / 60:.0f} min")
            time.sleep(nap)
            keep_awake()  # renew the request, just in case
    finally:
        keep_awake(False)
        LOCK_PATH.unlink(missing_ok=True)


def _session(args, symbols, clock):
    plan = plan_session(clock, args.interval, args.max_wait_hours)
    if plan is None:
        print("No market session within the wait window (weekend or holiday). Nothing to do.")
        return 0
    wait, cycles = plan
    briefing = write_briefing(symbols)
    if wait > 0:
        print(f"Waiting {wait / 60:.0f} minutes for the opening bell...")
        time.sleep(wait + 5)
        clock = clock_with_retry()
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
    result = trial.update()
    if result:
        s, v = result
        print(f"Trial: day {v['days_done']} of {v['days_total']}, {v['status']}, "
              f"P&L {'+' if s['pnl'] >= 0 else '-'}${abs(s['pnl']):,.2f} (scorecard: data/trial/scorecard.html)")
    return 0 if raphael.audit["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
