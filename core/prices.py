import random


class FeedError(RuntimeError):
    """A feed couldn't fetch new prices this time (e.g. the internet dropped).
    The city skips that cycle and keeps going on the last known prices."""


class PriceFeed:
    """Interface for anything that can supply prices. Paper-only: read-only data."""

    def get_price(self, symbol: str) -> float:
        raise NotImplementedError

    def get_history(self, symbol: str, n: int) -> list:
        raise NotImplementedError


class SimulatedFeed(PriceFeed):
    """Seeded random-walk prices. No network, fully repeatable.

    Each symbol gets its own walk, advanced one step per call to advance().
    """

    def __init__(self, start_prices: dict, seed: int = 42, volatility: float = 0.01):
        self._rng = random.Random(seed)
        self._volatility = volatility
        self._history = {sym: [float(p)] for sym, p in start_prices.items()}

    def advance(self):
        """Move every symbol one step forward."""
        for sym, hist in self._history.items():
            change = self._rng.gauss(0, self._volatility)
            new_price = max(0.01, hist[-1] * (1 + change))
            hist.append(round(new_price, 4))

    def get_price(self, symbol: str) -> float:
        if symbol not in self._history:
            raise KeyError(f"no price data for {symbol}")
        return self._history[symbol][-1]

    def get_history(self, symbol: str, n: int) -> list:
        if symbol not in self._history:
            raise KeyError(f"no price data for {symbol}")
        return self._history[symbol][-n:]
