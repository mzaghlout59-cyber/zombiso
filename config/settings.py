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


# --- Aegis risk limits (paper trading) ---
ACCOUNT_SIZE = 10_000.0           # paper account size in USD
MAX_RISK_PER_TRADE_PCT = 0.25     # % of account risked per trade
MAX_DAILY_LOSS_PCT = 1.0          # % of account, then Aegis halts trading for the day
MAX_OPEN_POSITIONS = 3
REQUIRE_STOP_LOSS = True

# Exits: take profit at this multiple of the stop distance (reward:risk)
TAKE_PROFIT_RR = 2.0
