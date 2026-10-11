from core.base_agent import BaseAgent
from core.logger import log


class Sage(BaseAgent):
    """The thinking layer. Proposes plans and recommendations.
    It can never place a trade or override the Risk Manager."""

    name = "Sage"
    alias = "Sage"
    division = "Investment"
    rank = "Commander"
    commander = "Raphael"
    purpose = "Thinker and planner: decides which agents run and weighs their results into a recommendation."

    def handle(self, task):
        """Sage works through plan() and recommend(); handle() is not used directly."""
        raise NotImplementedError("Sage uses plan() and recommend(), not handle()")

    def plan(self, goal):
        """Decide which agents to run, in order, for a goal."""
        log(f"Sage planning for goal: {goal}")
        return ["MarketResearch", "NewsResearch", "Sentiment", "Charts", "Strategy"]

    # How each research signal votes. Anything not listed abstains.
    VOTES = {
        "trend": {"up": "buy", "down": "sell"},
        "sentiment": {"positive": "buy", "negative": "sell"},
        "crowd_mood": {"bullish": "buy", "bearish": "sell"},
        "pattern": {"breakout": "buy", "breakdown": "sell"},
    }
    MAX_CONFIDENCE = 0.9
    # A research bias against the signal halves confidence. Caution only: never raises it.
    OPPOSING_BIAS = {"buy": "bearish", "sell": "bullish"}

    def __init__(self):
        self.briefing = {}  # symbol -> "bullish" | "bearish" | "neutral", set before the open

    def recommend(self, results):
        """Weigh agent results into a recommendation with confidence and reasoning.
        Advisory only: Sage never places trades and never overrides Aegis."""
        signal = results.get("Strategy", {}).get("signal", "hold")
        sentiment = results.get("NewsResearch", {}).get("sentiment", "neutral")
        trend = results.get("MarketResearch", {}).get("trend", "unknown")
        crowd_mood = results.get("Sentiment", {}).get("crowd_mood", "neutral")
        pattern = results.get("Charts", {}).get("pattern", "none")

        readings = {
            "trend": trend,
            "sentiment": sentiment,
            "crowd_mood": crowd_mood,
            "pattern": pattern,
        }

        agree = 0
        disagree = 0
        for name, value in readings.items():
            vote = self.VOTES.get(name, {}).get(value)
            if vote is None:
                continue
            if vote == signal:
                agree += 1
            else:
                disagree += 1

        if signal == "hold":
            confidence = 0.0
        else:
            confidence = min(self.MAX_CONFIDENCE, round(agree / len(readings), 2))

        caution = ""
        symbol = results.get("MarketResearch", {}).get("symbol")
        bias = self.briefing.get(symbol, "neutral")
        if confidence > 0 and bias == self.OPPOSING_BIAS.get(signal):
            confidence = round(confidence / 2, 2)
            caution = f" Research bias is {bias}: confidence halved."

        recommendation = {
            "action": signal,
            "confidence": confidence,
            "reasoning": f"trend={trend}, sentiment={sentiment}, "
                         f"crowd_mood={crowd_mood}, pattern={pattern}, "
                         f"strategy signal={signal}. "
                         f"{agree} signals agree, {disagree} disagree.{caution}",
        }
        log(f"Sage recommendation: {recommendation}")
        return recommendation
