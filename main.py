from config import settings
from core.raphael import Raphael
from divisions.investment.agents import (
    MarketResearchAgent,
    NewsResearchAgent,
    PortfolioManagerAgent,
    PerformanceAnalystAgent,
)
from divisions.investment.strategist import StrategistAgent
from divisions.investment.aegis import AegisAgent

print(f"=== {settings.PROJECT_NAME} | mode: {settings.TRADING_MODE} ===")

raphael = Raphael()
for agent_class in [
    MarketResearchAgent,
    NewsResearchAgent,
    StrategistAgent,
    AegisAgent,
    PortfolioManagerAgent,
    PerformanceAnalystAgent,
]:
    raphael.register(agent_class())

print("\n--- Roster ---")
raphael.roster()

raphael.run_goal("Evaluate AAPL", {"symbol": "AAPL", "prices": [100, 99, 98, 97, 96, 105]})
