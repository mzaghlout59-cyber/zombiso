"""Every BaseAgent must declare a purpose, so the roster is never blank."""
from divisions.investment.agents import (
    MarketResearchAgent,
    NewsResearchAgent,
    PortfolioManagerAgent,
    PerformanceAnalystAgent,
    SentimentAgent,
    ChartsAgent,
)
from divisions.investment.strategist import StrategistAgent
from divisions.investment.aegis import AegisAgent
from core.sage import Sage
from core.ultron import Ultron

ALL_AGENTS = [
    MarketResearchAgent, NewsResearchAgent, SentimentAgent, ChartsAgent,
    StrategistAgent, AegisAgent, PortfolioManagerAgent,
    PerformanceAnalystAgent, Sage, Ultron,
]
# Sage now inherits BaseAgent and is part of the roster.


def test_every_agent_has_a_purpose():
    missing = [cls.name for cls in ALL_AGENTS
               if cls().profile()["purpose"] == "(purpose not documented)"]
    assert not missing, f"agents without a purpose: {missing}"
    print("PASS: every agent declares a purpose")


def test_profile_shape():
    p = AegisAgent().profile()
    assert set(p) == {"name", "alias", "division", "rank", "commander", "purpose"}
    print("PASS: profile() has the expected fields")


if __name__ == "__main__":
    test_profile_shape()
    test_every_agent_has_a_purpose()
