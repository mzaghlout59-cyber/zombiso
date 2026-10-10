from divisions.investment.agents import (
    MarketResearchAgent,
    NewsResearchAgent,
    PortfolioManagerAgent,
    PerformanceAnalystAgent,
    ScoutAgent,
    SentimentAgent,
    ChartsAgent,
)

EXPECTED = [
    (MarketResearchAgent, "Scout", "Sage"),
    (NewsResearchAgent, "News", "Sage"),
    (SentimentAgent, "Pulse", "Sage"),
    (ChartsAgent, "Lens", "Sage"),
    (PortfolioManagerAgent, "Ledgerkeeper", "Aegis"),
    (PerformanceAnalystAgent, "Scorekeeper", "Aegis"),
]


def test_squad_ranks_and_commanders():
    for cls, alias, commander in EXPECTED:
        p = cls().profile()
        assert p["rank"] == "Squad"
        assert p["alias"] == alias
        assert p["commander"] == commander
        assert p["division"] == "Investment"
        assert p["purpose"] != "(purpose not documented)"


def test_scout_alias_still_points_to_market_research():
    assert ScoutAgent is MarketResearchAgent
