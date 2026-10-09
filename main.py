from config import settings
from core.raphael import Raphael
from divisions.investment.agents import (
    MarketResearchAgent,
    NewsResearchAgent,
    StrategyAgent,
    PortfolioManagerAgent,
    PerformanceAnalystAgent,
)
from divisions.investment.aegis import AegisAgent

print(f"=== {settings.PROJECT_NAME} | mode: {settings.TRADING_MODE} ===")

raphael = Raphael()
for agent_class in [
    MarketResearchAgent,
    NewsResearchAgent,
    StrategyAgent,
    AegisAgent,
    PortfolioManagerAgent,
    PerformanceAnalystAgent,
]:
    raphael.register(agent_class())

print("\n--- Roster ---")
raphael.roster()

raphael.run_goal("Evaluate AAPL", {"symbol": "AAPL"})
