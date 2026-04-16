"""Streaming JSONL event log."""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any


class EventLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", buffering=1, encoding="utf-8")

    def emit(self, event_type: str, **fields: Any) -> None:
        rec = {"ts": time.time(), "type": event_type, **fields}
        self._fh.write(json.dumps(rec, default=_default) + "\n")

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass


def _default(o: Any) -> Any:
    if hasattr(o, "__dict__"):
        return o.__dict__
    return str(o)
