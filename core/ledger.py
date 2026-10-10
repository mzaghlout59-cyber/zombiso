"""
Paper Ledger - the city's record of simulated trades.
PAPER ONLY: this file records pretend trades. It never touches a broker.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER_PATH = Path("data/paper_ledger.json")


class PaperLedger:
    def __init__(self, path: Path = LEDGER_PATH):
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
            "exit": None,
            "pnl": 0.0,
            "closed_at": None,
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
                self._save()
                return t
        raise ValueError(f"No open trade with id {trade_id}")

    # ---------- numbers Aegis needs ----------
    def open_positions(self) -> int:
        return sum(1 for t in self.trades if t["status"] == "open")

    def daily_pnl(self) -> float:
        today = datetime.now(timezone.utc).date().isoformat()
        return round(sum(
            t["pnl"] for t in self.trades
            if t["status"] == "closed" and t["closed_at"].startswith(today)
        ), 2)
