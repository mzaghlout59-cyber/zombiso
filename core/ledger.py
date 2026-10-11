"""
Paper Ledger - the city's record of simulated trades.
PAPER ONLY: this file records pretend trades. It never touches a broker.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER_PATH = Path("data/paper_ledger.json")


class PaperLedger:
    def __init__(self, path: Path = LEDGER_PATH, clock=None):
        """clock: a SimClock. With one, "today" is the city's day; without, the real UTC date."""
        self.clock = clock
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.trades: list[dict] = self._load()

    # ---------- persistence ----------
    def _load(self) -> list[dict]:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return []

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.trades, indent=2), encoding="utf-8")

    # ---------- recording ----------
    def open_trade(self, symbol: str, side: str, size: int,
                   entry: float, stop_loss: float) -> dict:
        trade = {
            "id": len(self.trades) + 1,
            "symbol": symbol,
            "side": side,
            "size": size,
            "entry": entry,
            "stop_loss": stop_loss,
            "status": "open",
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "opened_tick": self.clock.tick if self.clock else None,
            "opened_day": self.clock.day if self.clock else None,
            "exit": None,
            "pnl": 0.0,
            "closed_at": None,
            "closed_tick": None,
            "closed_day": None,
        }
        self.trades.append(trade)
        self._save()
        return trade

    def close_trade(self, trade_id: int, exit_price: float) -> dict:
        for t in self.trades:
            if t["id"] == trade_id and t["status"] == "open":
                direction = 1 if t["side"] == "buy" else -1
                t["exit"] = exit_price
                t["pnl"] = round((exit_price - t["entry"]) * t["size"] * direction, 2)
                t["status"] = "closed"
                t["closed_at"] = datetime.now(timezone.utc).isoformat()
                if self.clock:
                    t["closed_tick"] = self.clock.tick
                    t["closed_day"] = self.clock.day
                self._save()
                return t
        raise ValueError(f"No open trade with id {trade_id}")

    # ---------- numbers Aegis needs ----------
    def open_symbols(self) -> set:
        """Symbols that currently have an open position."""
        return {t["symbol"] for t in self._load() if t["status"] == "open"}

    def open_trades(self):
        """Return a list of all currently open paper trades."""
        return [t for t in self._load() if t["status"] == "open"]

    def open_positions(self) -> int:
        return sum(1 for t in self.trades if t["status"] == "open")

    def _closed_today(self) -> list:
        """Today's closed trades, in the order they closed."""
        if self.clock:
            today = [t for t in self.trades
                     if t["status"] == "closed" and t.get("closed_day") == self.clock.day]
        else:
            date = datetime.now(timezone.utc).date().isoformat()
            today = [t for t in self.trades
                     if t["status"] == "closed" and t["closed_at"].startswith(date)]
        return sorted(today, key=lambda t: (t.get("closed_tick") or 0, t["closed_at"]))

    def max_loss_streak_today(self) -> int:
        """Longest run of consecutive losing closes today (a breakeven counts as a loss)."""
        streak = best = 0
        for t in self._closed_today():
            streak = streak + 1 if t["pnl"] <= 0 else 0
            best = max(best, streak)
        return best

    def daily_pnl(self) -> float:
        """Realized P&L for today: the clock's day if there is a clock, else the UTC date."""
        if self.clock:
            return round(sum(
                t["pnl"] for t in self.trades
                if t["status"] == "closed" and t.get("closed_day") == self.clock.day
            ), 2)
        today = datetime.now(timezone.utc).date().isoformat()
        return round(sum(
            t["pnl"] for t in self.trades
            if t["status"] == "closed" and t["closed_at"].startswith(today)
        ), 2)
