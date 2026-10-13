# Zombiso AI City

A city of AI agents that paper-trades US stocks (AAPL, MSFT, NVDA) and that you can watch in 2D or 3D.

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
| `python -m pytest -q` | Run the test suite |

Every run is saved under `data/runs/<timestamp>/` (ledger, `events.jsonl`, Ultron's `audit.json`, and on market days `briefing.md`) and can be replayed in the viewer.

## Keys (`.env`)

- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`: from a free Alpaca **paper** account, for real prices and news
- `ANTHROPIC_API_KEY`: optional, powers News sentiment and the Research briefing; without it they stay neutral
