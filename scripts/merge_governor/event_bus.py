"""In-process async event bus for governor-erp.

Emits events to terminal, per-PR JSONL log files, and registered subscribers.
File I/O uses run_in_executor to avoid blocking the event loop.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import structlog

logger = structlog.get_logger("governor.event_bus")

LIVE_LOG_DIR = Path.home() / ".governor" / "live"


class EventBus:
    """In-process async pub/sub for governor events."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        LIVE_LOG_DIR.mkdir(parents=True, exist_ok=True)

    def emit(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Emit event to terminal, log file, and subscribers."""
        if data is None:
            data = {}
        data["ts"] = datetime.now().isoformat()
        data["event"] = event_type

        # Print to terminal
        ts = time.strftime("%H:%M:%S")
        summary = {k: v for k, v in data.items() if k not in ("ts", "event")}
        s = json.dumps(summary, default=str)
        if len(s) > 120:
            s = s[:117] + "..."
        print(f"[{ts}] {event_type}: {s}", flush=True)

        # Write to per-PR log file (non-blocking)
        pr_num = data.get("pr")
        if pr_num:
            log_file = str(LIVE_LOG_DIR / f"pr_{pr_num}.jsonl")
            line = json.dumps(data, default=str) + "\n"
            try:
                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, _write_log, log_file, line)
            except RuntimeError:
                _write_log(log_file, line)

        # Notify subscribers
        for cb in self._subscribers.get(event_type, []):
            try:
                cb(data)
            except Exception:
                pass
        for cb in self._subscribers.get("*", []):
            try:
                cb(data)
            except Exception:
                pass

    def subscribe(self, event_type: str, callback: Callable) -> None:
        self._subscribers.setdefault(event_type, []).append(callback)


def _write_log(path: str, line: str) -> None:
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
