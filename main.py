"""Quick demo: show the roster and evaluate one symbol on a fresh run ledger."""
from config import settings
from run_city import build_city

print(f"=== {settings.PROJECT_NAME} | mode: {settings.TRADING_MODE} ===")

raphael = build_city()
raphael.clock.advance()

print("\n--- Roster ---")
raphael.roster()

raphael.run_goal("Evaluate AAPL", {"symbol": "AAPL", "prices": [100, 99, 98, 97, 96, 105]})
