from core.logger import log


class Sage:
    """The thinking layer. Proposes plans and recommendations.
    It can never place a trade or override the Risk Manager."""

    name = "Sage"

    def plan(self, goal):
        """Decide which agents to run, in order, for a goal."""
        log(f"Sage planning for goal: {goal}")
        return ["MarketResearch", "NewsResearch", "Strategy"]

    def recommend(self, results):
        """Weigh agent results into a recommendation with confidence and reasoning."""
        signal = results.get("Strategy", {}).get("signal", "hold")
        sentiment = results.get("NewsResearch", {}).get("sentiment", "neutral")
        trend = results.get("MarketResearch", {}).get("trend", "unknown")

        recommendation = {
            "action": signal,
            "confidence": 0.0,
            "reasoning": f"trend={trend}, sentiment={sentiment}, strategy signal={signal}. "
                         f"Placeholder Sage: no real analysis yet.",
        }
        log(f"Sage recommendation: {recommendation}")
        return recommendation
