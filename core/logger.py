from datetime import datetime
from pathlib import Path

LOG_PATH = Path("logs/city.log")


def log(message):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = f'{datetime.now()} - {message}'
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
