from divisions.investment.aegis import AegisAgent

# Account = 10,000 -> max risk per trade = $25, max daily loss = $100


def check(label, result, expected):
    ok = result["approved"] is expected
    print(f"{'PASS' if ok else 'FAIL'} | {label}: approved={result['approved']} | {result['reason']}")
    return ok


results = []

a = AegisAgent()
results.append(check("valid trade, risk $20",
    a.evaluate("AAPL", {"entry": 100, "stop_loss": 99.0, "size": 20}), True))

a = AegisAgent()
results.append(check("risk too big, $50",
    a.evaluate("AAPL", {"entry": 100, "stop_loss": 99.0, "size": 50}), False))

a = AegisAgent()
results.append(check("no stop-loss",
    a.evaluate("AAPL", {"entry": 100, "stop_loss": None, "size": 10}), False))

a = AegisAgent()
a.open_positions = 3
results.append(check("3 positions already open",
    a.evaluate("AAPL", {"entry": 100, "stop_loss": 99.0, "size": 10}), False))

a = AegisAgent()
a.daily_pnl = -100.0
results.append(check("daily loss limit hit",
    a.evaluate("AAPL", {"entry": 100, "stop_loss": 99.0, "size": 10}), False))

a = AegisAgent()
results.append(check("invalid size 0",
    a.evaluate("AAPL", {"entry": 100, "stop_loss": 99.0, "size": 0}), False))

print(f"\n{sum(results)}/{len(results)} tests passed")
