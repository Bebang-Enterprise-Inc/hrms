"""State persistence for governor-erp using atomic writes."""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PRRecord:
    number: int
    title: str
    head_ref: str
    head_sha: str
    updated_at: str
    labels: list[str] = field(default_factory=list)
    staging_port: int | None = None
    review_decision: str | None = None  # APPROVE / REJECT / NEEDS_FIX
    review_sha: str | None = None  # SHA that was reviewed
    queued_at: float | None = None
    merged_at: float | None = None
    touched_files: list[str] = field(default_factory=list)


@dataclass
class GovernorState:
    # Port registry: port -> PR number (or None if free)
    port_registry: dict[str, int | None] = field(default_factory=dict)
    # Active PRs: PR number -> PRRecord
    active_prs: dict[str, PRRecord] = field(default_factory=dict)
    # Merge queue: list of PR numbers in order
    merge_queue: list[int] = field(default_factory=list)
    # Last 10 merged PRs with touched files
    merge_history: list[dict[str, Any]] = field(default_factory=list)
    # Governor metadata
    started_at: float = 0.0
    last_poll_at: float = 0.0
    paused: bool = False
    production_head: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert PRRecord objects properly
        active = {}
        for k, v in self.active_prs.items():
            active[str(k)] = asdict(v) if isinstance(v, PRRecord) else v
        d["active_prs"] = active
        return d

    @classmethod
    def from_dict(cls, d: dict) -> GovernorState:
        state = cls()
        state.port_registry = d.get("port_registry", {})
        state.merge_queue = d.get("merge_queue", [])
        state.merge_history = d.get("merge_history", [])
        state.started_at = d.get("started_at", 0.0)
        state.last_poll_at = d.get("last_poll_at", 0.0)
        state.paused = d.get("paused", False)
        state.production_head = d.get("production_head", "")
        # Reconstruct PRRecords
        active = {}
        for k, v in d.get("active_prs", {}).items():
            if isinstance(v, dict):
                active[str(k)] = PRRecord(**v)
            else:
                active[str(k)] = v
        state.active_prs = active
        return state


class StateManager:
    """Manages governor state with atomic file writes for crash safety."""

    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.state_file = state_dir / "governor_erp_state.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state = GovernorState()

    def load(self) -> GovernorState:
        """Load state from disk. Raises on corrupt file."""
        if not self.state_file.exists():
            self.state = GovernorState()
            return self.state

        raw = self.state_file.read_text(encoding="utf-8")
        if not raw.strip():
            raise ValueError(
                f"State file is empty: {self.state_file}\n"
                "Recovery: delete the file and restart."
            )

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"State file is corrupt: {self.state_file}\n"
                f"JSON error: {e}\n"
                "Recovery: restore from backup or delete and restart."
            ) from e

        self.state = GovernorState.from_dict(data)
        return self.state

    def save(self) -> None:
        """Write state to file with retry for Dropbox/antivirus file locks."""
        data = self.state.to_dict()
        content = json.dumps(data, indent=2, default=str)

        # Write to temp file in same directory
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.state_dir), suffix=".tmp", prefix="state_"
        )
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1  # Mark as closed

            # os.replace with retry — Dropbox/antivirus can hold brief locks
            import time as _time
            for attempt in range(5):
                try:
                    os.replace(tmp_path, str(self.state_file))
                    return  # Success
                except PermissionError:
                    if attempt < 4:
                        _time.sleep(0.1 * (attempt + 1))
                    else:
                        # Last resort: direct write (not atomic but works)
                        with open(str(self.state_file), "w", encoding="utf-8") as f:
                            f.write(content)
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                        return
        except Exception:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def add_to_merge_history(self, pr_number: int, touched_files: list[str]) -> None:
        """Add a merged PR to history, keeping last 10."""
        self.state.merge_history.append({
            "number": pr_number,
            "touched_files": touched_files,
            "merged_at": time.time(),
        })
        # Keep only last 10
        self.state.merge_history = self.state.merge_history[-10:]
        self.save()
