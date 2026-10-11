"""Alpaca feed + market-day runner, with Alpaca faked: no network, no keys needed."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import market_day
from config import settings
from core import alpaca
from core.alpaca import AlpacaError, AlpacaFeed, market_clock, parse_time
from core.ledger import PaperLedger
from core.prices import SimulatedFeed
from core.ultron import Ultron
from run_city import build_city, run_city, START_PRICES


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.text = data, status, str(data)

    def json(self):
        return self._data


class FakeAlpaca:
    """Answers the three endpoints the city uses, and records every URL called."""

    def __init__(self, prices):
        self.prices = prices  # symbol -> list of successive latest-trade prices
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append(url)
        assert headers["APCA-API-KEY-ID"] and headers["APCA-API-SECRET-KEY"]
        if url.endswith("/clock"):
            return FakeResponse({"is_open": True, "timestamp": "2026-10-12T10:00:00.123456789-04:00",
                                 "next_open": "2026-10-13T09:30:00-04:00",
                                 "next_close": "2026-10-12T16:00:00-04:00"})
        if url.endswith("/trades/latest"):
            out = {s: {"p": p.pop(0)} for s, p in self.prices.items() if p}
            return FakeResponse({"trades": out})
        if "/bars" in url:
            return FakeResponse({"bars": [{"c": 103.0}, {"c": 102.0}, {"c": 101.0}]})  # newest first
        return FakeResponse({"message": "not found"}, 404)


@pytest.fixture(autouse=True)
def fake_keys(monkeypatch):
    monkeypatch.setattr(settings, "ALPACA_API_KEY", "test-key-id")
    monkeypatch.setattr(settings, "ALPACA_SECRET_KEY", "test-secret")


def test_missing_keys_refuse_to_start(monkeypatch):
    monkeypatch.setattr(settings, "ALPACA_API_KEY", "")
    with pytest.raises(AlpacaError, match="must be set in .env"):
        market_clock(session=FakeAlpaca({}))


def test_clock_parses_nanosecond_timestamps():
    c = market_clock(session=FakeAlpaca({}))
    assert c["is_open"] is True
    assert c["now"].microsecond == 123456
    assert (c["next_close"] - c["now"]).total_seconds() == pytest.approx(6 * 3600, abs=1)
    assert parse_time("2026-10-12T14:00:00Z").tzinfo is not None


def test_feed_loads_history_oldest_first_and_appends_trades():
    fake = FakeAlpaca({"AAPL": [104.0, 105.0], "MSFT": [300.0]})
    feed = AlpacaFeed(["AAPL", "MSFT"], session=fake)
    feed.load_history(3)
    assert feed.get_history("AAPL", 10) == [101.0, 102.0, 103.0]
    feed.advance()
    feed.advance()  # MSFT has no new trade the second time: price carries forward
    assert feed.get_history("AAPL", 10)[-2:] == [104.0, 105.0]
    assert feed.get_history("MSFT", 10)[-2:] == [300.0, 300.0]


def test_symbol_without_any_data_raises_keyerror():
    feed = AlpacaFeed(["ZZZZ"], session=FakeAlpaca({}))
    feed.advance()
    with pytest.raises(KeyError):
        feed.get_price("ZZZZ")


def test_alpaca_module_never_touches_orders():
    source = Path(alpaca.__file__).read_text(encoding="utf-8").lower()
    code = "\n".join(l for l in source.splitlines() if not l.strip().startswith(("#", '"""')))
    for word in ("orders", "positions", ".post(", ".delete(", ".put(", ".patch("):
        assert word not in code, f"alpaca.py must stay read-only, found {word!r}"


def test_plan_session_waits_for_open_and_counts_cycles():
    ny = timezone(timedelta(hours=-4))
    before_open = {"is_open": False, "now": datetime(2026, 10, 12, 9, 0, tzinfo=ny),
                   "next_open": datetime(2026, 10, 12, 9, 30, tzinfo=ny),
                   "next_close": datetime(2026, 10, 12, 16, 0, tzinfo=ny)}
    wait, cycles = market_day.plan_session(before_open, 300, 3)
    assert wait == 30 * 60
    assert cycles == (6.5 * 3600 - 60) // 300  # 77 five-minute cycles

    holiday = {**before_open, "next_open": datetime(2026, 10, 13, 9, 30, tzinfo=ny)}
    assert market_day.plan_session(holiday, 300, 3) is None


def test_end_of_day_closes_everything_and_audit_stays_clean(tmp_path):
    ledger = PaperLedger(tmp_path / "ledger.json")
    raphael = build_city(ledger=ledger)
    run_city(SimulatedFeed(START_PRICES, seed=1), cycles=60, raphael=raphael, close_at_end=True)
    assert ledger.open_trades() == []
    eod = [e for e in raphael.events.of_kind("trade_closed") if e["reason"] == "end_of_day"]
    assert raphael.audit["ok"], raphael.audit["violations"]
    assert eod and all(e["tick"] == 60 for e in eod)  # seed 1 ends with positions still open


def test_one_market_day_with_fake_alpaca(tmp_path):
    prices = {"AAPL": [100 + i * 0.3 for i in range(10)], "MSFT": [200.0] * 10, "NVDA": [50.0] * 10}
    feed = AlpacaFeed(list(prices), session=FakeAlpaca(prices))
    feed.load_history(6)
    raphael = build_city(ledger=PaperLedger(tmp_path / "l.json"), cycles_per_day=8)
    run_city(feed, cycles=8, watchlist=list(prices), raphael=raphael,
             warmup=False, close_at_end=True, source="alpaca")
    assert raphael.clock.day == 0  # the whole session is one city day
    assert raphael.ledger.open_trades() == []
    assert Ultron().audit(raphael.events, raphael.ledger)["ok"]
