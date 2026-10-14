"""A market day must survive the internet dropping (day 2 crashed on a DNS failure at 12:25)."""
import pytest
import requests

import market_day
from config import settings
from core.alpaca import AlpacaError, AlpacaFeed
from core.ledger import PaperLedger
from core.ultron import Ultron
from run_city import build_city, run_city


class FlakyAlpaca:
    """Real-looking answers, except the latest-trades call fails on chosen attempts."""

    def __init__(self, prices, fail_on):
        self.prices, self.fail_on, self.calls = prices, set(fail_on), 0

    def get(self, url, headers=None, params=None, timeout=None):
        class R:
            status_code = 200
            text = ""

            def __init__(self, data):
                self._d = data

            def json(self):
                return self._d

        if "/bars" in url:
            return R({"bars": [{"c": 100.0}] * 6})
        self.calls += 1
        if self.calls in self.fail_on:
            raise requests.exceptions.ConnectionError("Failed to resolve 'data.alpaca.markets'")
        return R({"trades": {s: {"p": p.pop(0)} for s, p in self.prices.items() if p}})


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "ALPACA_API_KEY", "k")
    monkeypatch.setattr(settings, "ALPACA_SECRET_KEY", "s")


def test_network_errors_become_alpaca_errors():
    feed = AlpacaFeed(["AAPL"], session=FlakyAlpaca({"AAPL": [1.0]}, fail_on=[1]))
    with pytest.raises(AlpacaError, match="network problem"):
        feed.advance()


def test_a_day_with_an_outage_skips_cycles_and_still_finishes(tmp_path):
    prices = {s: [100 + i * 0.2 for i in range(20)] for s in ("AAPL", "MSFT", "NVDA")}
    fake = FlakyAlpaca(prices, fail_on=[3, 4, 5])  # three cycles without internet
    feed = AlpacaFeed(list(prices), session=fake)
    feed.load_history(6)
    raphael = build_city(ledger=PaperLedger(tmp_path / "l.json"), cycles_per_day=10)
    run_city(feed, cycles=10, watchlist=list(prices), raphael=raphael,
             warmup=False, close_at_end=True, source="alpaca")
    assert len(raphael.events.of_kind("feed_error")) == 3
    assert len(raphael.events.of_kind("tick")) == 7
    assert raphael.ledger.open_trades() == []  # still closed everything at the end
    assert Ultron().audit(raphael.events, raphael.ledger)["ok"]


def test_market_clock_is_retried_through_a_short_outage(monkeypatch):
    monkeypatch.setattr(market_day.time, "sleep", lambda s: None)
    answers = [AlpacaError("network problem"), AlpacaError("network problem"), {"is_open": True}]

    def clock():
        a = answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a

    assert market_day.clock_with_retry(tries=5, clock=clock) == {"is_open": True}
    with pytest.raises(AlpacaError):
        market_day.clock_with_retry(tries=2, clock=lambda: (_ for _ in ()).throw(AlpacaError("down")))
