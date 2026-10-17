"""Structured event stream: what happened, when, in city time.

Every event is a flat dict: {"seq", "tick", "day", "at", "kind", ...data}, where "at" is the
real UTC time it happened (Hindsight lines trades up with the market's minute prices by it).
The visual city and Ultron both read this stream; neither needs the printed log.
"""
import json
from datetime import datetime, timezone
from pathlib import Path


class EventLog:
    def __init__(self, clock=None, path=None):
        self.clock = clock
        self.path = Path(path) if path else None
        self.events = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    def emit(self, kind, **data):
        event = {
            "seq": len(self.events) + 1,
            "tick": self.clock.tick if self.clock else None,
            "day": self.clock.day if self.clock else None,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": kind,
            **data,
        }
        self.events.append(event)
        if self.path:
            with self.path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(event, default=list) + "\n")
        return event

    def of_kind(self, kind):
        return [e for e in self.events if e["kind"] == kind]
