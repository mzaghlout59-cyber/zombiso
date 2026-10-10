from core.sage import Sage


def make_results(signal, trend, crowd, pattern, sentiment="neutral"):
    return {
        "Strategy": {"signal": signal},
        "MarketResearch": {"trend": trend},
        "NewsResearch": {"sentiment": sentiment},
        "Sentiment": {"crowd_mood": crowd},
        "Charts": {"pattern": pattern},
    }


def test_all_signals_agree_with_buy():
    rec = Sage().recommend(make_results("buy", "up", "bullish", "breakout", "positive"))
    assert rec["action"] == "buy"
    assert rec["confidence"] == 0.9  # 4/4 agree, capped at 0.9


def test_partial_agreement_scales_confidence():
    rec = Sage().recommend(make_results("buy", "up", "bullish", "none"))
    assert rec["confidence"] == 0.5  # 2 of 4 agree


def test_conflicting_signals_lower_confidence():
    rec = Sage().recommend(make_results("buy", "up", "bearish", "breakdown"))
    assert rec["confidence"] == 0.25  # only trend agrees


def test_hold_has_zero_confidence():
    rec = Sage().recommend(make_results("hold", "up", "bullish", "breakout"))
    assert rec["action"] == "hold"
    assert rec["confidence"] == 0.0


def test_missing_results_do_not_crash():
    rec = Sage().recommend({})
    assert rec["action"] == "hold"
    assert rec["confidence"] == 0.0
