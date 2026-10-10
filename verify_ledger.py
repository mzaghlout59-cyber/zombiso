import sys
import tempfile
from pathlib import Path

results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition)))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f"  -> {detail}" if detail and not condition else ""))


check("core/ledger.py exists", Path("core/ledger.py").exists())
check("tests/test_ledger.py exists", Path("tests/test_ledger.py").exists())

try:
    from core.ledger import PaperLedger
    check("PaperLedger imports", True)
except Exception as e:
    check("PaperLedger imports", False, str(e))
    print("\nCannot continue without the import. Fix that first.")
    sys.exit(1)

with tempfile.TemporaryDirectory() as d:
    path = Path(d) / "check.json"
    ledger = PaperLedger(path)

    check("starts with 0 open positions", ledger.open_positions() == 0)
    check("starts with 0.0 daily pnl", ledger.daily_pnl() == 0.0)

    t1 = ledger.open_trade("AAPL", "buy", 11, 105.0, 102.90)
    check("open_trade returns id 1", t1["id"] == 1)
    check("new trade status is open", t1["status"] == "open")
    check("1 open position after opening", ledger.open_positions() == 1)

    ledger.open_trade("MSFT", "buy", 5, 200.0, 196.0)
    check("2 open positions after second trade", ledger.open_positions() == 2)

    closed = ledger.close_trade(t1["id"], 110.0)
    check("close sets status closed", closed["status"] == "closed")
    check("pnl math correct (110-105)*11 = 55.0", closed["pnl"] == 55.0, str(closed["pnl"]))
    check("open positions drops to 1", ledger.open_positions() == 1)
    check("daily_pnl reflects closed trade", ledger.daily_pnl() == 55.0)

    t3 = ledger.open_trade("TSLA", "sell", 10, 100.0, 105.0)
    ledger.close_trade(t3["id"], 90.0)
    check("sell-side pnl math correct", ledger.trades[-1]["pnl"] == 100.0,
          str(ledger.trades[-1]["pnl"]))

    reloaded = PaperLedger(path)
    check("data survives reload", len(reloaded.trades) == 3)
    check("open positions survive reload", reloaded.open_positions() == 1)

    try:
        ledger.close_trade(999, 100.0)
        check("closing missing trade raises error", False)
    except ValueError:
        check("closing missing trade raises error", True)

    try:
        ledger.close_trade(t1["id"], 120.0)
        check("closing an already-closed trade raises error", False)
    except ValueError:
        check("closing an already-closed trade raises error", True)

source = Path("core/ledger.py").read_text(encoding="utf-8").lower()
forbidden = ["requests", "alpaca", "ccxt", "socket", "urllib", "http", "api_key"]
found = [w for w in forbidden if w in source]
check("ledger has no broker/network code", not found, f"found: {found}")

gi = Path(".gitignore")
check("data/ is in .gitignore",
      gi.exists() and "data/" in gi.read_text(encoding="utf-8"))

passed = sum(1 for _, ok in results if ok)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
