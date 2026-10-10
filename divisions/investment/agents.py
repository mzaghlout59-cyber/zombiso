from core.base_agent import BaseAgent


class MarketResearchAgent(BaseAgent):
    name = "MarketResearch"
    alias = "Scout"
    division = "Investment"
    rank = "Squad"
    commander = "Sage"
    purpose = "Finds opportunities: scans the market for unusual movement, volume and momentum."

    def handle(self, task):
        self.say(f"Researching market for {task.get('symbol')}")
        return {"symbol": task.get("symbol"), "trend": "unknown", "status": "stub"}


ScoutAgent = MarketResearchAgent  # codename alias; old name keeps working


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

    def handle(self, task):
        self.say(f"Reading crowd sentiment for {task.get('symbol')}")
        return {"symbol": task.get("symbol"), "crowd_mood": "neutral", "status": "stub"}


class ChartsAgent(BaseAgent):
    name = "Charts"
    alias = "Lens"
    division = "Investment"
    rank = "Squad"
    commander = "Sage"
    purpose = "Reads price structure: support, resistance and chart patterns."

    def handle(self, task):
        self.say(f"Reading charts for {task.get('symbol')}")
        return {"symbol": task.get("symbol"), "pattern": "none", "status": "stub"}
