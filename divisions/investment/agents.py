from config import settings
from core.base_agent import BaseAgent


def _prices(task, minimum):
    """Return the price list from a task, or None if missing or too short."""
    prices = task.get("prices")
    if not isinstance(prices, (list, tuple)) or len(prices) < minimum:
        return None
    return list(prices)


class MarketResearchAgent(BaseAgent):
    name = "MarketResearch"
    alias = "Scout"
    division = "Investment"
    rank = "Squad"
    commander = "Sage"
    purpose = "Finds opportunities: scans the market for unusual movement, volume and momentum."

    FLAT_BAND = 0.01  # moves within +/-1% count as flat

    def handle(self, task):
        self.say(f"Researching market for {task.get('symbol')}")
        prices = _prices(task, 2)
        if prices is None or prices[-2] == 0:
            return {"symbol": task.get("symbol"), "trend": "unknown", "status": "stub"}
        change = (prices[-1] - prices[-2]) / prices[-2]
        if change > self.FLAT_BAND:
            trend = "up"
        elif change < -self.FLAT_BAND:
            trend = "down"
        else:
            trend = "flat"

        return {"symbol": task.get("symbol"), "trend": trend, "status": "simulated"}


ScoutAgent = MarketResearchAgent


class NewsResearchAgent(BaseAgent):
    name = "NewsResearch"
    alias = "News"
    division = "Investment"
    rank = "Squad"
    commander = "Sage"
    purpose = "Checks what just happened: news, catalysts and market context."

    def handle(self, task):
        self.say(f"Scanning news for {task.get('symbol')}")
        return {"symbol": task.get("symbol"), "sentiment": "neutral", "status": "stub"}


class PortfolioManagerAgent(BaseAgent):
    name = "PortfolioManager"
    alias = "Ledgerkeeper"
    division = "Investment"
    rank = "Squad"
    commander = "Aegis"
    purpose = "Turns the ledger into an exposure report: open positions and capital at risk."

    def handle(self, task):
        """task = {"trades": [ledger trade dicts]}. Reports on the open ones."""
        self.say("Reviewing portfolio")
        open_trades = [t for t in task.get("trades", []) if t["status"] == "open"]
        exposure = sum(t["entry"] * t["size"] for t in open_trades)
        at_risk = sum(abs(t["entry"] - t["stop_loss"]) * t["size"] for t in open_trades)
        account = settings.ACCOUNT_SIZE
        return {
            "positions": len(open_trades),
            "symbols": sorted(t["symbol"] for t in open_trades),
            "exposure": round(exposure, 2),
            "exposure_pct": round(exposure / account * 100, 2),
            "at_risk": round(at_risk, 2),
            "at_risk_pct": round(at_risk / account * 100, 3),
            "status": "active",
        }


class PerformanceAnalystAgent(BaseAgent):
    name = "PerformanceAnalyst"
    alias = "Scorekeeper"
    division = "Investment"
    rank = "Squad"
    commander = "Aegis"
    purpose = "Scores closed trades: win rate and loss streaks, which the ledger alone does not give."

    def handle(self, task):
        """task = {"trades": [ledger trade dicts]}. Scores the closed ones, oldest first."""
        self.say("Analysing performance")
        closed = sorted((t for t in task.get("trades", []) if t["status"] == "closed"),
                        key=lambda t: t["id"])
        pnls = [t["pnl"] for t in closed]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        streak = max_streak = 0
        for p in pnls:
            streak = streak + 1 if p <= 0 else 0
            max_streak = max(max_streak, streak)

        gross_loss = -sum(losses)
        return {
            "closed": len(pnls),
            "pnl": round(sum(pnls), 2),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(pnls), 3) if pnls else None,
            "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
            "profit_factor": round(sum(wins) / gross_loss, 2) if gross_loss > 0 else None,
            "loss_streak": streak,
            "max_loss_streak": max_streak,
            "status": "active",
        }


class SentimentAgent(BaseAgent):
    name = "Sentiment"
    alias = "Pulse"
    division = "Investment"
    rank = "Squad"
    commander = "Sage"
    purpose = "Reads the crowd: social and market mood around a symbol."

    MOOD_SHARE = 0.6

    def handle(self, task):
        self.say(f"Reading crowd sentiment for {task.get('symbol')}")
        prices = _prices(task, 3)
        if prices is None:
            return {"symbol": task.get("symbol"), "crowd_mood": "neutral", "status": "stub"}

        moves = [b - a for a, b in zip(prices, prices[1:])]
        ups = sum(1 for m in moves if m > 0)
        downs = sum(1 for m in moves if m < 0)

        if ups / len(moves) >= self.MOOD_SHARE:
            mood = "bullish"
        elif downs / len(moves) >= self.MOOD_SHARE:
            mood = "bearish"
        else:
            mood = "neutral"

        return {"symbol": task.get("symbol"), "crowd_mood": mood, "status": "simulated"}


class ChartsAgent(BaseAgent):
    name = "Charts"
    alias = "Lens"
    division = "Investment"
    rank = "Squad"
    commander = "Sage"
    purpose = "Reads price structure: support, resistance and chart patterns."

    def handle(self, task):
        self.say(f"Reading charts for {task.get('symbol')}")
        prices = _prices(task, 3)
        if prices is None:
            return {"symbol": task.get("symbol"), "pattern": "none", "status": "stub"}

        last = prices[-1]
        earlier = prices[:-1]

        if last > max(earlier):
            pattern = "breakout"
        elif last < min(earlier):
            pattern = "breakdown"
        else:
            pattern = "none"

        return {"symbol": task.get("symbol"), "pattern": pattern, "status": "simulated"}
