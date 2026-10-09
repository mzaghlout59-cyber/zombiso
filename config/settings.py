import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_NAME = "Zombiso AI City"

# Safety: paper trading is hard-enforced
TRADING_MODE = os.getenv("TRADING_MODE", "paper").lower()
if TRADING_MODE != "paper":
    raise RuntimeError("Only TRADING_MODE=paper is allowed. Real-money trading is disabled.")

# Secrets (from environment only, never hard-coded)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")

# Account
STARTING_BALANCE = 10000

# Hard risk rules (enforced in code in Phase 5)
MAX_RISK_PER_TRADE_PCT = 0.25
MAX_DAILY_LOSS_PCT = 1.0
MAX_OPEN_POSITIONS = 3
STOP_LOSS_REQUIRED = True
