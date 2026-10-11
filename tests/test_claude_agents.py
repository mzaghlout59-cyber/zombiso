"""News, Research and the Claude helper, with Claude faked: no API calls, no cost."""
import json
from types import SimpleNamespace

import pytest

import market_day
from config import settings
from core import llm
from core.alpaca import AlpacaError
from core.llm import LLMUnavailable, ask_json
from core.sage import Sage
from divisions.investment.agents import NewsResearchAgent
from divisions.research.bureau import ResearchBureau


class FakeClaude:
    """Stands in for anthropic.Anthropic(); records each request."""

    def __init__(self, answer, stop_reason="end_turn"):
        self.answer, self.stop_reason, self.calls = answer, stop_reason, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answer))])


SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"],
          "additionalProperties": False}


def test_ask_json_sends_model_schema_effort_and_fallbacks():
    fake = FakeClaude({"x": "hi"})
    assert ask_json("sys", "prompt", SCHEMA, effort="low", client=fake) == {"x": "hi"}
    req = fake.calls[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert req["fallbacks"] == "default" and req["betas"] == [llm.FALLBACK_BETA]
    assert req["system"] == "sys" and req["messages"] == [{"role": "user", "content": "prompt"}]


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_ask_json_unusable_answers_raise(stop):
    with pytest.raises(LLMUnavailable):
        ask_json("s", "p", SCHEMA, client=FakeClaude({"x": "?"}, stop_reason=stop))


def test_no_key_means_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    with pytest.raises(LLMUnavailable, match="ANTHROPIC_API_KEY"):
        ask_json("s", "p", SCHEMA)


# ---------- News ----------

HEADLINES = [{"id": 1, "headline": "Apple beats earnings", "summary": "Strong iPhone sales"},
             {"id": 2, "headline": "Analysts raise targets", "summary": ""}]


def test_news_without_a_source_stays_neutral_and_never_calls_claude():
    def boom(*a):
        raise AssertionError("Claude must not be called in simulations")
    r = NewsResearchAgent(llm=boom).handle({"symbol": "AAPL"})
    assert r["sentiment"] == "neutral" and r["status"] == "no_source"


def test_news_votes_and_only_asks_claude_when_headlines_change():
    calls = []

    def fake_llm(system, prompt, schema):
        calls.append(prompt)
        return {"sentiment": "positive", "reason": "earnings beat"}

    feed = {"items": HEADLINES}
    agent = NewsResearchAgent(news_source=lambda sym: feed["items"], llm=fake_llm)
    r1 = agent.handle({"symbol": "AAPL"})
    r2 = agent.handle({"symbol": "AAPL"})
    assert r1["sentiment"] == "positive" and r1["top"] == "Apple beats earnings"
    assert r2 == r1 and len(calls) == 1          # same headlines: cached
    assert "Apple beats earnings" in calls[0]

    feed["items"] = HEADLINES + [{"id": 3, "headline": "Recall announced", "summary": ""}]
    agent.handle({"symbol": "AAPL"})
    assert len(calls) == 2                        # new headline: asks again


@pytest.mark.parametrize("source, llm_fn, status", [
    (lambda s: [], None, "no_news"),
    (lambda s: (_ for _ in ()).throw(AlpacaError("down")), None, "unavailable"),
    (lambda s: HEADLINES, lambda *a: (_ for _ in ()).throw(LLMUnavailable("no key")), "unavailable"),
])
def test_news_falls_back_to_neutral(source, llm_fn, status):
    r = NewsResearchAgent(news_source=source, llm=llm_fn).handle({"symbol": "AAPL"})
    assert r["sentiment"] == "neutral" and r["status"] == status


# ---------- Research bureau ----------

BRIEF = {"summary": "Quiet open expected.", "symbols": [
    {"symbol": "AAPL", "bias": "bearish", "levels": "support 101, resistance 105", "notes": "Gapped down."},
    {"symbol": "ZZZZ", "bias": "bullish", "levels": "-", "notes": "Not on the watchlist."}]}


def test_bureau_returns_bias_only_for_the_watchlist():
    prompts = []
    bureau = ResearchBureau(llm=lambda s, p, schema: prompts.append(p) or BRIEF)
    out = bureau.handle({"symbols": ["AAPL", "MSFT"],
                         "bars": {"AAPL": [{"t": "2026-10-09T04:00:00Z", "o": 100, "h": 105, "l": 99, "c": 101, "v": 1}]},
                         "news": {"AAPL": [{"headline": "Apple gaps down"}]}})
    assert out["bias"] == {"AAPL": "bearish", "MSFT": "neutral"}
    assert "high 105" in prompts[0] and "Apple gaps down" in prompts[0] and "(no bars)" in prompts[0]
    md = ResearchBureau.to_markdown(out, "2026-10-12")
    assert "## AAPL: bearish" in md and "support 101" in md


def test_bureau_without_claude_gives_neutral_bias():
    bureau = ResearchBureau(llm=lambda *a: (_ for _ in ()).throw(LLMUnavailable("blocked")))
    out = bureau.handle({"symbols": ["AAPL"]})
    assert out["status"] == "unavailable" and out["bias"] == {"AAPL": "neutral"}
    assert "No briefing" in ResearchBureau.to_markdown(out)


def test_write_briefing_survives_missing_market_data(monkeypatch):
    def no_data(*a, **k):
        raise AlpacaError("keys missing")
    monkeypatch.setattr(market_day, "fetch_daily_bars", no_data)
    seen = {}
    bureau = ResearchBureau(llm=lambda s, p, schema: seen.setdefault("p", p) and BRIEF)
    out = market_day.write_briefing(["AAPL"], bureau=bureau)
    assert "(no bars)" in seen["p"] and out["bias"]["AAPL"] == "bearish"


# ---------- Sage's caution ----------

def results(signal, sym="AAPL"):
    return {"Strategy": {"signal": signal}, "MarketResearch": {"symbol": sym, "trend": "up"},
            "Sentiment": {"crowd_mood": "bullish"}, "Charts": {"pattern": "none"},
            "NewsResearch": {"sentiment": "neutral"}}


@pytest.mark.parametrize("bias, expected", [("neutral", 0.5), ("bullish", 0.5), ("bearish", 0.25)])
def test_research_bias_can_only_lower_a_buy(bias, expected):
    sage = Sage()
    sage.briefing = {"AAPL": bias}
    rec = sage.recommend(results("buy"))
    assert rec["confidence"] == expected
    assert ("halved" in rec["reasoning"]) == (bias == "bearish")


def test_research_bias_ignores_other_symbols_and_holds():
    sage = Sage()
    sage.briefing = {"MSFT": "bearish"}
    assert sage.recommend(results("buy"))["confidence"] == 0.5
    sage.briefing = {"AAPL": "bearish"}
    assert sage.recommend(results("hold"))["confidence"] == 0.0
