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

# --- Aegis risk limits (paper trading) ---
ACCOUNT_SIZE = 10_000.0           # starting paper equity in USD; the Treasury tracks it from here
# Share of equity each trading division may size its trades on (must add up to <= 1.0)
TREASURY_ALLOCATIONS = {"Investment": 1.0}
MAX_RISK_PER_TRADE_PCT = 0.25     # % of account risked per trade
MAX_DAILY_LOSS_PCT = 1.0          # % of account, then Aegis halts trading for the day
MAX_OPEN_POSITIONS = 3
MAX_LOSS_STREAK = 4               # this many losses in a row in one day halts new trades until tomorrow
REQUIRE_STOP_LOSS = True

# Stops fill at the next price, not the stop, so a gap can lose more than planned.
# Size trades as if the stop could slip to this multiple of its distance.
STOP_GAP_BUFFER = 2.0

# Simulated time: the daily loss limit resets every this many cycles
CYCLES_PER_DAY = 20

# Exits: take profit at this multiple of the stop distance (reward:risk)
TAKE_PROFIT_RR = 2.0

# Sage gate: trades whose Sage confidence is below this are skipped.
# Can only make trading more conservative. Aegis still has the final say.
MIN_SAGE_CONFIDENCE = 0.25
