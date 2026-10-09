from divisions.investment.strategist import StrategistAgent
from divisions.investment.aegis import AegisAgent

s = StrategistAgent()
a = AegisAgent()


def show(label, prices):
    print(f"\n--- {label} ---")
    result = s.handle({"symbol": "AAPL", "prices": prices})
    print("Strategist:", result["signal"], result.get("trade"))
    if result["trade"]:
        verdict = a.evaluate("AAPL", result["trade"])
        print("Aegis:", "APPROVED" if verdict["approved"] else "DENIED", "|", verdict["reason"])
    return result


r1 = show("downtrend then pop (should BUY)", [100, 99, 98, 97, 96, 105])
r2 = show("steady downtrend (should HOLD)", [100, 99, 98, 97, 96, 95])
r3 = show("too little data (should HOLD)", [100, 101])

ok = r1["signal"] == "buy" and r2["signal"] == "hold" and r3["signal"] == "hold"
print("\nPASS" if ok else "\nFAIL")
