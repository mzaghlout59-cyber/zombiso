from config import settings


def exit_signal(trade: dict, price: float):
    """Decide whether an open paper trade should close at this price.

    Returns "stop_loss", "take_profit", or None. Pure function: no I/O.
    Stops are checked first, so if a price satisfies both, the stop wins.
    """
    if trade.get("status") != "open":
        return None

    entry = trade["entry"]
    stop = trade["stop_loss"]
    distance = abs(entry - stop)
    if distance <= 0:
        return None

    if trade["side"] == "buy":
        target = entry + distance * settings.TAKE_PROFIT_RR
        if price <= stop:
            return "stop_loss"
        if price >= target:
            return "take_profit"
    else:  # sell / short
        target = entry - distance * settings.TAKE_PROFIT_RR
        if price >= stop:
            return "stop_loss"
        if price <= target:
            return "take_profit"
    return None
