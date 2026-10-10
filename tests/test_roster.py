"""Every BaseAgent must declare a purpose, so the roster is never blank."""
from divisions.investment.agents import (
    MarketResearchAgent,
    NewsResearchAgent,
    PortfolioManagerAgent,
    PerformanceAnalystAgent,
)
from divisions.investment.strategist import StrategistAgent
from divisions.investment.aegis import AegisAgent

ALL_AGENTS = [
    MarketResearchAgent, NewsResearchAgent, StrategistAgent, AegisAgent,
    PortfolioManagerAgent, PerformanceAnalystAgent,
]
# Sage is intentionally excluded for now: it does not inherit BaseAgent yet.


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
