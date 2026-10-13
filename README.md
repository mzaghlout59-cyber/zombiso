# Zombiso AI City

A city of AI agents that paper-trades US stocks and that you can watch as a 3D cyber city. The watchlist (AAPL, MSFT, NVDA by default) is `WATCHLIST` in `config/settings.py`.

**Paper only.** No real money is ever used: the city refuses to run unless `TRADING_MODE=paper`, and it has no code that sends orders to a broker. Every trade lives in its own practice ledger.

## Who works in the city

| Agent | Role |
|---|---|
| **Raphael** | Headquarters: runs every step and records trades |
| **Sage** | Weighs the squad's signals into a confidence score |
| Scout · Pulse · Lens · News | Sage's squad: trend, crowd mood, chart patterns, headlines |
| **Axiom** (Strategist) | Proposes trades and sizes them |
| **Aegis** | Risk gate with veto power over every trade |
| Ledgerkeeper · Scorekeeper | Aegis's squad: exposure, win rate, losing streaks |
| **Treasury** | The bank: tracks equity and allots capital |
| **Research bureau** | Writes a pre-open briefing (with Claude) |
| **Ultron** | Independent auditor; replays every run and reports broken rules |

## Aegis's rules

A trade only happens if every rule passes:

- worst-case risk at most 0.25% of capital (stop gaps included)
- stop-loss required
- at most 3 open positions, one per symbol
- daily loss under 1% of capital
- fewer than 4 losses in a row today
- Sage at least 25% confident

Trades close at their stop-loss or at a 2:1 take-profit, or at the closing bell on market days.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env          # then fill in your keys (never commit .env)
```

| Command | What it does |
|---|---|
| `python run_city.py --cycles 60 --seed 7` | Practice run on a simulated market |
| `python run_city.py --delay 0.5` | Same, slowed down to watch live |
| `python market_day.py --check` | Test the Alpaca/Claude keys and show live prices |
| `python market_day.py` | One real market session on real prices (paper only) |
| `python view_city.py` | Open the viewer at http://127.0.0.1:8765/ |
| `python trial.py start` | Begin a paper trial (default 7 market days) |
| `python trial.py` | Open the trial scorecard: pass/fail rules and each agent's accuracy |
| `python -m pytest -q` | Run the test suite |

Every run is saved under `data/runs/<timestamp>/` (ledger, `events.jsonl`, Ultron's `audit.json`, Raphael's plain-language `report.html`, and on market days `briefing.md`) and can be replayed in the viewer.

## The paper trial

The city runs on real market days with pretend money and is judged by rules fixed in advance (`TRIAL_*` in `config/settings.py`): make money overall, Ultron clean every day, never more than 3% below its best point, and at least 20 trades. Every agent that votes on a trade is scored right or wrong when it closes; the viewer's **survival board** shows who is safe, at risk, or dying (below 50% after 10 votes, marked for replacement).

## Keys (`.env`)

- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`: from a free Alpaca **paper** account, for real prices and news
- `ANTHROPIC_API_KEY`: optional, powers News sentiment and the Research briefing; without it they stay neutral
