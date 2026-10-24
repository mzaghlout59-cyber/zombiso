# Zombiso AI City

A city of AI agents that paper-trades US stocks and that you can watch as a 2D map or a 3D cyber city. The watchlist (AAPL, MSFT, NVDA by default) is `WATCHLIST` in `config/settings.py`.

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
| `python view_city.py --phone` | Same, and prints a link your phone can open (same Wi-Fi) |
| `python trial.py start` | Begin a paper trial (default 7 market days) |
| `python trial.py` | Open the trial scorecard: pass/fail rules and each agent's accuracy |
| `python -m pytest -q` | Run the test suite |

Every run is saved under `data/runs/<timestamp>/` (ledger, `events.jsonl`, Ultron's `audit.json`, Raphael's plain-language `report.html`, and on market days `briefing.md`) and can be replayed in the viewer.

## The paper trial

The city runs on real market days with pretend money and is judged by rules fixed in advance (`TRIAL_*` in `config/settings.py`): make money overall, Ultron clean every day, never more than 3% below its best point, and at least 20 trades. Every agent that votes on a trade is scored right or wrong when it closes; the viewer's **survival board** shows who is safe, at risk, or dying (below 50% after 10 votes, marked for replacement).

## Keys (`.env`)

- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`: from a free Alpaca **paper** account, for real prices and news
- `ANTHROPIC_API_KEY`: optional, powers News sentiment and the Research briefing; without it they stay neutral

## Shop sites: websites for shops that have none

A separate side tool in `shopsites/`. It finds local businesses with no website, builds each one a preview site, and writes the sales message.

```bash
python shopsites/find_shops.py "Porto Alegre, Brazil"          # -> shopsites/out/leads.csv
python shopsites/build_sites.py --me "Your name" --my-phone "+55 ..." --price "R$ 300" \
       --base-url https://YOU.github.io/shops                  # -> shopsites/out/
```

1. `find_shops.py` asks OpenStreetMap (free, no key) for every named shop, café, salon, clinic, workshop and office in the city. It keeps the independent ones (no chains) that have a phone number and no website or Instagram/Facebook listed.
2. `build_sites.py` makes a one-page, phone-friendly site for each: name, Call / WhatsApp / Directions buttons, opening hours, a map. A "preview" banner marks it as not live yet.
3. Put `shopsites/out/sites/` online (GitHub Pages, or drag it into Netlify Drop) and pass that address as `--base-url` so each pitch links to that shop's own preview.
4. Open `shopsites/out/index.html`: every shop with **Send pitch on WhatsApp** (opens WhatsApp with the message filled in), **Call**, and **Check: really no site?**. OpenStreetMap is incomplete, so check before you pitch.

When a shop says yes, remove the preview banner from its `index.html`, buy their domain, and point it at the page.

## Clipper: long video -> short vertical clips

`clipper/clip.py` turns a podcast, stream or talk into TikTok / Shorts / Reels clips: 1080x1920, with big word-by-word captions, plus a title, caption and hashtags for each.

```bash
pip install -r clipper/requirements.txt     # Whisper + yt-dlp; ffmpeg must be installed too (winget install ffmpeg)
python clipper/clip.py podcast.mp4                       # 5 clips of 20-60 s
python clipper/clip.py "https://youtu.be/..." --clips 8 --max 45 --fit blur
```

Whisper transcribes the video on your PC (or pass `--subs file.srt`), Claude picks the moments with the strongest hook and payoff (needs `ANTHROPIC_API_KEY` in `.env`), and ffmpeg cuts them. Output: `clipper/out/<video>/clips/*.mp4` and `clips.md`. Only clip videos you have the rights to: your own, or a creator's clipping program.
