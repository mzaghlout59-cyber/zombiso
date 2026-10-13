import sys
from datetime import datetime
from pathlib import Path

LOG_PATH = Path("logs/city.log")


def safe_console():
    """Make print() survive any character (e.g. "→"). When output is redirected to a file,
    as the scheduled task does, Windows defaults to cp1252, which can't encode many
    characters and crashed the end of a market day."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass  # not a regular text stream (e.g. under a test runner)


def log(message):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = f'{datetime.now()} - {message}'
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
