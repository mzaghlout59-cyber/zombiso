"""News, Research and the Claude helper, with Claude faked: no API calls, no cost."""
import json

import pytest

import market_day
from config import settings
from core import llm
from core.alpaca import AlpacaError
from core.llm import LLMUnavailable, ask_json
from core.sage import Sage
from divisions.investment.agents import NewsResearchAgent
from divisions.research.bureau import ResearchBureau


class FakeResponse:
    def __init__(self, status, data):
        self.status_code, self._data, self.text = status, data, json.dumps(data)

    def json(self):
        return self._data


class FakeClaude:
    """Stands in for the HTTPS session; answers queued responses and records each request."""

    def __init__(self, answer=None, stop_reason="end_turn", responses=None):
        ok = FakeResponse(200, {"stop_reason": stop_reason,
                                "content": [{"type": "text", "text": json.dumps(answer)}]})
        self.responses = list(responses or [ok])
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "body": json})
        return self.responses.pop(0)


SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"],
          "additionalProperties": False}


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)  # no real waiting between retries


def test_ask_json_sends_model_schema_effort_and_fallbacks(key):
    fake = FakeClaude({"x": "hi"})
    assert ask_json("sys", "prompt", SCHEMA, effort="low", session=fake) == {"x": "hi"}
    call = fake.calls[0]
    assert call["url"] == "https://api.anthropic.com/v1/messages"
    assert call["headers"]["x-api-key"] == "test-key"
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    assert call["headers"]["anthropic-beta"] == llm.FALLBACK_BETA
    body = call["body"]
    assert body["model"] == "claude-opus-5-5" and body["fallbacks"] == "default"
    assert body["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert body["system"] == "sys" and body["messages"] == [{"role": "user", "content": "prompt"}]


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_ask_json_unusable_answers_raise(key, stop):
    with pytest.raises(LLMUnavailable):
        ask_json("s", "p", SCHEMA, session=FakeClaude({"x": "?"}, stop_reason=stop))


def test_overloaded_then_ok_is_retried(key):
    ok = FakeResponse(200, {"stop_reason": "end_turn", "content": [{"type": "text", "text": '{"x": "ok"}'}]})
    busy = FakeResponse(529, {"error": {"message": "Overloaded"}})
    fake = FakeClaude(responses=[busy, ok])
    assert ask_json("s", "p", SCHEMA, session=fake) == {"x": "ok"}
    assert len(fake.calls) == 2


def test_bad_request_is_not_retried_and_says_why(key):
    fake = FakeClaude(responses=[FakeResponse(400, {"error": {"message": "bad schema"}})])
    with pytest.raises(LLMUnavailable, match="400: bad schema"):
        ask_json("s", "p", SCHEMA, session=fake)
    assert len(fake.calls) == 1


def test_gives_up_after_repeated_server_errors(key):
    fake = FakeClaude(responses=[FakeResponse(500, {"error": {"message": "boom"}})] * llm.RETRIES)
    with pytest.raises(LLMUnavailable, match="after 3 tries"):
        ask_json("s", "p", SCHEMA, session=fake)


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
