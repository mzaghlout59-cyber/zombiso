from core.base_agent import BaseAgent


class MarketResearchAgent(BaseAgent):
    name = "MarketResearch"
    division = "Investment"

    def handle(self, task):
        self.say(f"Researching market for {task.get('symbol')}")
        return {"symbol": task.get("symbol"), "trend": "unknown", "status": "stub"}


class NewsResearchAgent(BaseAgent):
    name = "NewsResearch"
    division = "Investment"

    def handle(self, task):
        self.say(f"Scanning news for {task.get('symbol')}")
        return {"symbol": task.get("symbol"), "sentiment": "neutral", "status": "stub"}


class StrategyAgent(BaseAgent):
    name = "Strategy"
    division = "Investment"

    def handle(self, task):
        self.say(f"Building strategy for {task.get('symbol')}")
        return {"symbol": task.get("symbol"), "signal": "hold", "status": "stub"}



class PortfolioManagerAgent(BaseAgent):
    name = "PortfolioManager"
    division = "Investment"

    def handle(self, task):
        self.say("Reviewing portfolio")
        return {"positions": 0, "status": "stub"}


class PerformanceAnalystAgent(BaseAgent):
    name = "PerformanceAnalyst"
    division = "Investment"

    def handle(self, task):
        self.say("Analysing performance")
        return {"pnl": 0, "status": "stub"}
