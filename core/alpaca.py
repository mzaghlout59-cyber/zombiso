"""Real prices from Alpaca. READ-ONLY.

PAPER ONLY: this module calls the market clock and the market-data endpoints,
nothing else. It has no order code; trades live only in the city's PaperLedger.
Keys come from .env (ALPACA_API_KEY / ALPACA_SECRET_KEY, paper account).
"""
import re
from datetime import datetime, timedelta, timezone

import requests

from config import settings
from core.prices import PriceFeed

DATA_URL = "https://data.alpaca.markets/v2"
CLOCK_URL = "https://paper-api.alpaca.markets/v2/clock"


class AlpacaError(RuntimeError):
    pass


def _headers():
    if not settings.ALPACA_API_KEY or not settings.ALPACA_SECRET_KEY:
        raise AlpacaError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env "
                          "(keys from a free Alpaca paper account)")
    return {"APCA-API-KEY-ID": settings.ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": settings.ALPACA_SECRET_KEY}


def _get(url, params=None, session=None):
    r = (session or requests).get(url, headers=_headers(), params=params, timeout=15)
    if r.status_code != 200:
        raise AlpacaError(f"{url} -> HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def parse_time(s):
    """Alpaca timestamps can carry nanoseconds; Python takes at most microseconds."""
    s = re.sub(r"(\.\d{6})\d+", r"\1", s).replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def market_clock(session=None):
    """{"is_open", "now", "next_open", "next_close"}. Handles weekends, holidays and DST."""
    d = _get(CLOCK_URL, session=session)
    return {
        "is_open": bool(d["is_open"]),
        "now": parse_time(d["timestamp"]),
        "next_open": parse_time(d["next_open"]),
        "next_close": parse_time(d["next_close"]),
    }


NEWS_URL = "https://data.alpaca.markets/v1beta1/news"


def fetch_news(symbols, hours=24, limit=10, session=None):
    """Recent headlines for the symbols, newest first: [{"id", "headline", "summary", "created_at"}]."""
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    d = _get(NEWS_URL, {"symbols": ",".join(symbols), "start": start, "limit": limit,
                        "sort": "desc"}, session=session)
    return [{"id": n["id"], "headline": n.get("headline", ""), "summary": n.get("summary", ""),
             "created_at": n.get("created_at", "")} for n in (d.get("news") or [])]


def fetch_daily_bars(symbols, days=5, session=None):
    """Last few daily bars per symbol, oldest first: {sym: [{"t","o","h","l","c","v"}]}."""
    start = (datetime.now(timezone.utc) - timedelta(days=days * 2 + 4)).isoformat()
    out = {}
    for sym in symbols:
        d = _get(f"{DATA_URL}/stocks/{sym}/bars",
                 {"timeframe": "1Day", "start": start, "limit": days, "sort": "desc", "feed": "iex"},
                 session=session)
        out[sym] = list(reversed(d.get("bars") or []))
    return out


class AlpacaFeed(PriceFeed):
    """Real prices. advance() appends each symbol's latest trade price.

    Same interface as SimulatedFeed, so the city cannot tell the difference.
    """

    def __init__(self, symbols, timeframe="5Min", feed="iex", session=None):
        self.symbols = list(symbols)
        self.timeframe = timeframe
        self.feed = feed              # "iex" is the free data feed
        self._session = session
        self._history = {sym: [] for sym in self.symbols}

    def load_history(self, n):
        """Seed each symbol with its last n bar closes, so the Strategist can start at once."""
        start = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        for sym in self.symbols:
            d = _get(f"{DATA_URL}/stocks/{sym}/bars",
                     {"timeframe": self.timeframe, "start": start, "limit": n,
                      "sort": "desc", "feed": self.feed},
                     session=self._session)
            closes = [float(b["c"]) for b in (d.get("bars") or [])]
            self._history[sym] = list(reversed(closes))

    def advance(self):
        d = _get(f"{DATA_URL}/stocks/trades/latest",
                 {"symbols": ",".join(self.symbols), "feed": self.feed},
                 session=self._session)
        trades = d.get("trades") or {}
        for sym in self.symbols:
            trade = trades.get(sym)
            if trade:
                self._history[sym].append(float(trade["p"]))
            elif self._history[sym]:
                self._history[sym].append(self._history[sym][-1])  # no new trade: price unchanged

    def get_price(self, symbol):
        hist = self._history.get(symbol)
        if not hist:
            raise KeyError(f"no price data for {symbol}")
        return hist[-1]

    def get_history(self, symbol, n):
        if symbol not in self._history:
            raise KeyError(f"no price data for {symbol}")
        return self._history[symbol][-n:]
