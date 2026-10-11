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
