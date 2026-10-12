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

# --- What the city watches ---
# Stock symbols the city evaluates every cycle. Add any US stock Alpaca has data for,
# e.g. "AMZN", "GOOGL", "META", "TSLA", "AMD", "SPY". Aegis still allows only
# MAX_OPEN_POSITIONS trades at once, however long this list is.
WATCHLIST = ["AAPL", "MSFT", "NVDA"]

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

# --- The paper trial (python trial.py) ---
# Fixed before the trial starts, so the result can't be argued with afterwards.
TRIAL_DAYS = 7                    # real market days on pretend money
TRIAL_MAX_DRAWDOWN_PCT = 3.0      # never fall more than this % below the best point
TRIAL_MIN_TRADES = 20             # fewer trades than this is too little to judge
TRIAL_MIN_AGENT_VOTES = 10        # an agent needs this many scored votes before it's judged
TRIAL_MIN_AGENT_ACCURACY = 50     # % right; below this an agent is marked for replacement

# Simulated time: the daily loss limit resets every this many cycles
CYCLES_PER_DAY = 20

# Exits: take profit at this multiple of the stop distance (reward:risk)
TAKE_PROFIT_RR = 2.0

# Sage gate: trades whose Sage confidence is below this are skipped.
# Can only make trading more conservative. Aegis still has the final say.
MIN_SAGE_CONFIDENCE = 0.25
