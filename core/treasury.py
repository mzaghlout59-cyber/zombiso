"""The Treasury: the city's bank. Tracks equity and hands each division its capital.

Equity = starting equity + realized P&L. Trading divisions size their trades on
the capital the Treasury allots them, so the account compounds both ways:
winning makes positions a little larger, losing makes them smaller.

With a path, the Treasury remembers its equity between runs (used by market_day.py
so each real market day starts where the last one ended). Without one, every run
starts fresh at ACCOUNT_SIZE.
"""
import json
from datetime import datetime
from pathlib import Path

from config import settings
from core.base_agent import BaseAgent


class Treasury(BaseAgent):
    name = "Treasury"
    alias = "Vault"
    division = "Treasury"
    rank = "Commander"
    commander = "Raphael"
    purpose = "Bank: tracks the account's equity and gives each division its share of capital."

    def __init__(self, start_equity=None, allocations=None, path=None):
        self.path = Path(path) if path else None
        self.allocations = dict(allocations or settings.TREASURY_ALLOCATIONS)
        if sum(self.allocations.values()) > 1.0 + 1e-9:
            raise ValueError(f"allocations add up to more than 100%: {self.allocations}")
        self.history = []
        self.start_equity = float(start_equity or settings.ACCOUNT_SIZE)
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.start_equity = float(data["equity"])
            self.history = data.get("history", [])
        self.realized = 0.0

    @property
    def equity(self):
        return round(self.start_equity + self.realized, 2)

    def capital_for(self, division):
        return round(self.equity * self.allocations.get(division, 0.0), 2)

    def record(self, pnl):
        """A trade closed: its P&L lands in the bank."""
        self.realized += pnl

    def settle(self, run_id):
        """End of a run: write the day into the books and, with a path, save the new equity."""
        entry = {
            "run_id": run_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "start_equity": round(self.start_equity, 2),
            "pnl": round(self.realized, 2),
            "end_equity": self.equity,
        }
        self.history.append(entry)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"equity": self.equity, "history": self.history},
                                            indent=2), encoding="utf-8")
        return entry

    def handle(self, task):
        return {
            "equity": self.equity,
            "capital": {div: self.capital_for(div) for div in self.allocations},
            "status": "active",
        }
