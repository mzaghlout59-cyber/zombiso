from config import settings
from core.base_agent import BaseAgent


class AegisAgent(BaseAgent):
    """Aegis, the Risk Manager. The shield that decides what gets through.

    Default deny: a trade is approved only if EVERY rule passes.
    Aegis answers to Raphael and has veto power over every trade.
    """

    name = "Aegis"
    division = "Investment"
    rank = "Commander"
    commander = "Raphael"
    alias = "Shield"
    purpose = "Risk manager: default-deny veto over every trade; a trade passes only if every rule passes."

    def __init__(self):
        self.account = settings.ACCOUNT_SIZE  # capital the Treasury allots; Raphael updates it
        self.open_positions = 0
        self.daily_pnl = 0.0  # realized P&L today, in USD (negative = loss)
        self.open_symbols = set()  # symbols already held
        self.loss_streak = 0       # longest run of losing closes today
        self.open_exposure = 0.0   # money already in open positions (entry x size)

    def handle(self, task):
        symbol = task.get("symbol")
        self.say(f"Checking risk for {symbol}")

        # Non-trade recommendations need no approval to "execute"
        recommendation = task.get("recommendation") or {}
        trade = task.get("trade") or recommendation.get("trade")
        if trade is None:
            return self._deny(symbol, "no trade details supplied")

        return self.evaluate(symbol, trade)

    def evaluate(self, symbol, trade):
        """trade = {"entry": float, "stop_loss": float|None, "size": float}"""
        account = self.account

        # Rule 1: kill switch. Daily loss limit reached.
        max_daily_loss = account * settings.MAX_DAILY_LOSS_PCT / 100
        if self.daily_pnl <= -max_daily_loss:
            return self._deny(symbol, f"daily loss limit hit ({self.daily_pnl:.2f} <= -{max_daily_loss:.2f})")

        # Rule 1b: cool-off. Too many losses in a row today halts new trades until tomorrow.
        if self.loss_streak >= settings.MAX_LOSS_STREAK:
            return self._deny(symbol, f"losing streak ({self.loss_streak} in a row today), "
                                      f"no new trades until tomorrow")

        # Rule 1c: good day. Once today's profit reaches the target, stop and keep it.
        if self.daily_pnl >= settings.DAILY_PROFIT_TARGET:
            return self._deny(symbol, f"daily profit target reached (+${self.daily_pnl:.2f}), "
                                      f"no new trades until tomorrow")

        # Rule 2: position cap
        if self.open_positions >= settings.MAX_OPEN_POSITIONS:
            return self._deny(symbol, f"max open positions reached ({self.open_positions}/{settings.MAX_OPEN_POSITIONS})")

        # Rule 2b: no stacking. One open position per symbol.
        if symbol in self.open_symbols:
            return self._deny(symbol, f"already holding an open position in {symbol}")

        # Rule 3: stop-loss required and valid
        entry = trade.get("entry")
        stop = trade.get("stop_loss")
        size = trade.get("size")
        if entry is None or size is None or size <= 0 or entry <= 0:
            return self._deny(symbol, "invalid entry or size")
        if settings.REQUIRE_STOP_LOSS and stop is None:
            return self._deny(symbol, "stop-loss is required")
        if stop is not None and stop <= 0:
            return self._deny(symbol, "invalid stop-loss")

        # Rule 4: risk per trade, assuming the stop may gap (see STOP_GAP_BUFFER)
        if stop is None:
            risk_usd = float("inf")
        else:
            risk_usd = abs(entry - stop) * size * settings.STOP_GAP_BUFFER
        max_risk_usd = account * settings.MAX_RISK_PER_TRADE_PCT / 100
        if risk_usd > max_risk_usd:
            return self._deny(symbol, f"worst-case risk ${risk_usd:.2f} exceeds max ${max_risk_usd:.2f} per trade")

        # Rule 5: no borrowing. All open positions together can't cost more than the capital.
        cost = entry * size
        if self.open_exposure + cost > account + 1e-9:
            return self._deny(symbol, f"not enough cash: ${cost:,.2f} needed, "
                                      f"${account - self.open_exposure:,.2f} free")

        return {
            "symbol": symbol,
            "approved": True,
            "reason": f"all rules passed (risk ${risk_usd:.2f} of ${max_risk_usd:.2f} allowed)",
            "status": "active",
        }

    def _deny(self, symbol, reason):
        self.say(f"DENIED {symbol}: {reason}")
        return {"symbol": symbol, "approved": False, "reason": reason, "status": "active"}
