"""Ask Hindsight to review a market day (default: the most recent finished one).

    python hindsight.py                       # review the latest market day
    python hindsight.py data/runs/<folder>    # review a specific day

Writes hindsight.json / hindsight.md into the run folder, adds the day to Hindsight's
week-long record, and prints the review and its advice. Read-only towards the market.
"""
import json
import sys
from pathlib import Path

from core.logger import safe_console
from divisions.review.hindsight import Hindsight


def latest_market_day(runs=Path("data/runs")):
    for d in sorted(runs.iterdir(), reverse=True):
        meta = d / "meta.json"
        if (d / "audit.json").exists() and meta.exists() and json.loads(meta.read_text())["source"] == "alpaca":
            return d
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    run_dir = Path(argv[0]) if argv else latest_market_day()
    if run_dir is None:
        print("No finished market day to review yet.")
        return 1
    review = Hindsight().review_day(run_dir)
    md = Hindsight.to_markdown(review)
    (run_dir / "hindsight.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    safe_console()
    sys.exit(main())
