from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AttlogRow:
    pin: str
    event_time: datetime
    status_code: str
    verify_code: str | None
    workcode: str | None
    raw_line: str


def parse_attlog_line(line: str) -> AttlogRow | None:
    """Parse one ATTLOG row.

    Evidence format (tab-separated):
      Pin \t DateTime \t Status \t Verify \t Workcode \t ...

    Example seen in evidence:
      1156\t2024-08-05 12:40:57\t1\t1\t\t0\t0\t
    """
    raw = (line or "").rstrip("\r\n")
    if not raw.strip():
        return None

    parts = raw.split("\t")
    if len(parts) < 2:
        return None

    pin = (parts[0] or "").strip()
    dt_s = (parts[1] or "").strip()
    if not pin or not dt_s:
        return None

    try:
        event_time = datetime.strptime(dt_s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        # Some devices may include milliseconds; try a fallback
        try:
            event_time = datetime.strptime(dt_s.split(".")[0], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    status_code = (parts[2] if len(parts) > 2 else "").strip() or "0"
    verify_code = (parts[3] if len(parts) > 3 else "").strip() or None
    workcode = (parts[4] if len(parts) > 4 else "").strip() or None

    return AttlogRow(
        pin=pin,
        event_time=event_time,
        status_code=status_code,
        verify_code=verify_code,
        workcode=workcode,
        raw_line=raw,
    )
