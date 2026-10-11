"""The Research bureau: writes a pre-open market briefing for the watchlist.

Runs once before each real market session. Claude reads the last few daily bars
and the overnight headlines and returns a short briefing plus a bias per symbol.
Sage uses the bias only as caution: a bearish bias halves the confidence of a buy.
It can never create a trade or make one more likely.
"""
from core.base_agent import BaseAgent
from core.llm import LLMUnavailable, ask_json


class ResearchBureau(BaseAgent):
    name = "Research"
    alias = "Bureau"
    division = "Research"
    rank = "Commander"
    commander = "Raphael"
    purpose = "Writes the pre-open briefing: overnight news, key levels and a cautious bias per symbol."

    SYSTEM = ("You are the research desk of a paper-trading simulation. Write a short, factual "
              "pre-open briefing for the watchlist from the daily bars and headlines given. "
              "Name concrete levels (recent highs/lows/closes) from the data. Be conservative: "
              "use a bullish or bearish bias only when the data clearly supports it; otherwise "
              "neutral. Never invent numbers or news that are not in the input.")
    SCHEMA = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "symbols": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "bias": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
                        "levels": {"type": "string"},
                        "notes": {"type": "string"},
                    },
                    "required": ["symbol", "bias", "levels", "notes"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["summary", "symbols"],
        "additionalProperties": False,
    }

    def __init__(self, llm=None):
        self.llm = llm or (lambda system, prompt, schema: ask_json(
            system, prompt, schema, effort="medium", max_tokens=8000))

    def handle(self, task):
        """task = {"symbols": [...], "bars": {sym: [daily bars]}, "news": {sym: [headlines]}}"""
        symbols = task["symbols"]
        self.say(f"Writing the pre-open briefing for {', '.join(symbols)}")
        prompt = self._prompt(symbols, task.get("bars", {}), task.get("news", {}))
        try:
            out = self.llm(self.SYSTEM, prompt, self.SCHEMA)
        except LLMUnavailable as e:
            self.say(f"No briefing today: {e}")
            return {"status": "unavailable", "reason": str(e), "summary": "",
                    "bias": {s: "neutral" for s in symbols}, "symbols": []}
        bias = {s: "neutral" for s in symbols}
        for row in out["symbols"]:
            if row["symbol"] in bias:  # ignore anything outside the watchlist
                bias[row["symbol"]] = row["bias"]
        return {"status": "active", "summary": out["summary"], "symbols": out["symbols"], "bias": bias}

    @staticmethod
    def _prompt(symbols, bars, news):
        parts = []
        for sym in symbols:
            rows = bars.get(sym) or []
            bar_lines = "\n".join(
                f"  {b.get('t', '')[:10]}: open {b['o']} high {b['h']} low {b['l']} close {b['c']} "
                f"volume {b.get('v', '')}" for b in rows) or "  (no bars)"
            heads = "\n".join(f"  - {n['headline']}" for n in (news.get(sym) or [])) or "  (no headlines)"
            parts.append(f"{sym}\nDaily bars (oldest first):\n{bar_lines}\nHeadlines:\n{heads}")
        return "Watchlist data:\n\n" + "\n\n".join(parts)

    @staticmethod
    def to_markdown(briefing, date=""):
        lines = [f"# Pre-open briefing {date}".rstrip(), ""]
        if briefing["status"] != "active":
            lines.append(f"_No briefing: {briefing.get('reason', 'unavailable')}_")
            return "\n".join(lines) + "\n"
        lines += [briefing["summary"], ""]
        for row in briefing["symbols"]:
            lines += [f"## {row['symbol']}: {row['bias']}", f"**Levels:** {row['levels']}", "",
                      row["notes"], ""]
        return "\n".join(lines)
