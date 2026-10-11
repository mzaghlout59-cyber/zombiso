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
        if prices is None or prices[0] == 0:
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
        self.say("Reviewing portfolio")
        return {"positions": 0, "status": "stub"}


class PerformanceAnalystAgent(BaseAgent):
    name = "PerformanceAnalyst"
    alias = "Scorekeeper"
    division = "Investment"
    rank = "Squad"
    commander = "Aegis"
    purpose = "Scores closed trades: win rate and loss streaks, which the ledger alone does not give."

    def handle(self, task):
        self.say("Analysing performance")
        return {"pnl": 0, "status": "stub"}


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
























