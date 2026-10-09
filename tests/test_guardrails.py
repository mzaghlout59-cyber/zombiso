from divisions.investment.aegis import AegisAgent

a = AegisAgent()

cases = {
    "oversized (should DENY)": {"entry": 105, "stop_loss": 102.9, "size": 100},
    "no stop-loss (should DENY)": {"entry": 105, "stop_loss": None, "size": 5},
    "sane trade (should APPROVE)": {"entry": 105, "stop_loss": 102.9, "size": 11},
}

ok = True
for label, trade in cases.items():
    v = a.evaluate("AAPL", trade)
    print(f"{label}: {'APPROVED' if v['approved'] else 'DENIED'} | {v['reason']}")
    expected = "APPROVE" in label
    ok = ok and (v["approved"] == expected)

print("\nPASS" if ok else "\nFAIL")
