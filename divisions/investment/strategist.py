from config import settings
from core.base_agent import BaseAgent


def moving_average(prices, window):
    return sum(prices[-window:]) / window


class StrategistAgent(BaseAgent):
    """Turns prices into a concrete trade proposal using a moving-average crossover.

    Proposes only. Aegis decides whether the proposal is allowed.
    """

    name = "Strategist"
    division = "Investment"

    SHORT_WINDOW = 3
    LONG_WINDOW = 5
    STOP_PCT = 2.0  # stop-loss distance below entry, in %

    def handle(self, task):
        symbol = task.get("symbol")
        prices = task.get("prices")
        self.say(f"Building strategy for {symbol}")

        if not prices or len(prices) < self.LONG_WINDOW + 1:
            return self._hold(symbol, "not enough price data")

        short_now = moving_average(prices, self.SHORT_WINDOW)
        long_now = moving_average(prices, self.LONG_WINDOW)
        short_prev = moving_average(prices[:-1], self.SHORT_WINDOW)
        long_prev = moving_average(prices[:-1], self.LONG_WINDOW)

        crossed_up = short_prev <= long_prev and short_now > long_now
        if not crossed_up:
            return self._hold(symbol, "no bullish crossover")

        entry = prices[-1]
        stop_loss = round(entry * (1 - self.STOP_PCT / 100), 2)
        risk_per_share = entry - stop_loss

        max_risk_usd = settings.ACCOUNT_SIZE * settings.MAX_RISK_PER_TRADE_PCT / 100
        size = int(max_risk_usd // risk_per_share)
        if size < 1:
            return self._hold(symbol, "risk budget too small for even 1 share")

        trade = {"side": "buy", "entry": entry, "stop_loss": stop_loss, "size": size}
        self.say(f"PROPOSAL {symbol}: {trade}")
        return {"symbol": symbol, "signal": "buy", "trade": trade, "status": "active"}

    def _hold(self, symbol, reason):
        self.say(f"HOLD {symbol}: {reason}")
        return {"symbol": symbol, "signal": "hold", "trade": None, "reason": reason, "status": "active"}
