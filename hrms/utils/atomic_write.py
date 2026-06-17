"""Atomic file write helpers — prevents partial-write corruption on SoT files.

The bug class this prevents:
    with open(path, "w") as f:
        csv.DictWriter(f, fieldnames=cols).writerows(rows)
    # If any row fails validation mid-stream, the file is left truncated to whatever
    # was committed before the failure. Python's csv.DictWriter validates per-row.

Use these helpers any time you write to:
    - data/_FINAL/*.csv
    - data/_FINAL/CHANGE_LOG.csv
    - data/POS_Extraction/mosaic_tenants.json
    - any other authoritative file the project depends on

Pattern: write to <path>.tmp, fsync, os.replace() to swap atomically.
On POSIX this is atomic. On Windows os.replace is near-atomic (no torn writes;
either old contents or new contents are visible to readers).

Incident reference: 2026-06-04 18:46 PHT — EMPLOYEE_MASTER.csv truncated 843→72 rows.
See memory/feedback_csv_dictwriter_atomic.md and
tmp/csv_truncation_forensic_2026-06-05/FORENSIC_REPORT.md.
"""
from __future__ import annotations

import csv
import json
import os
from contextlib import contextmanager
from typing import Iterable, Mapping, Sequence


@contextmanager
def atomic_open(path: str, mode: str = "w", encoding: str | None = "utf-8", newline: str | None = None):
    """Context manager: write to <path>.tmp, swap on success, remove on failure.

    Usage:
        with atomic_open("data/_FINAL/EMPLOYEE_MASTER.csv", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(rows)
    """
    if "w" not in mode and "a" not in mode:
        raise ValueError(f"atomic_open requires a write mode, got {mode!r}")
    if "a" in mode:
        raise ValueError("atomic_open does not support append mode — read full, modify, write whole")

    tmp_path = path + ".tmp"
    f = open(tmp_path, mode, encoding=encoding, newline=newline)
    try:
        yield f
        f.flush()
        try:
            os.fsync(f.fileno())
        except (OSError, AttributeError):
            pass  # not all filesystems support fsync (e.g., some virtual ones)
        f.close()
        os.replace(tmp_path, path)
    except BaseException:
        try:
            f.close()
        except Exception:
            pass
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise


def atomic_write_csv_dict(
    path: str,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, object]],
    *,
    encoding: str = "utf-8-sig",
    strict: bool = True,
) -> None:
    """Atomically write a list-of-dicts to a CSV file.

    If strict=True (default), validates every row's keys against fieldnames BEFORE
    opening the destination file. This catches schema mismatches without ever
    touching the SoT file.

    If strict=False, sets extrasaction='ignore' on the writer (extra keys are
    silently dropped). Use only for derived outputs, never for SoT files.
    """
    rows_list = list(rows)
    if strict:
        fieldset = set(fieldnames)
        for i, row in enumerate(rows_list):
            extras = set(row.keys()) - fieldset
            if extras:
                raise ValueError(
                    f"Row {i} has unknown fields {sorted(extras)!r}; "
                    f"declared fieldnames: {sorted(fieldset)!r}. "
                    f"Refusing to write to {path!r} (would risk partial-write corruption)."
                )
        extras_action = "raise"
    else:
        extras_action = "ignore"

    with atomic_open(path, "w", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction=extras_action)
        writer.writeheader()
        writer.writerows(rows_list)


def atomic_append_csv_dict(
    path: str,
    fieldnames: Sequence[str],
    new_rows: Iterable[Mapping[str, object]],
    *,
    encoding: str = "utf-8-sig",
    strict: bool = True,
) -> None:
    """Atomically append rows to an existing CSV file.

    Reads the existing file, merges in the new rows, and writes back atomically.
    Use instead of mode='a' when the file is an SoT — append mode is not atomic
    either (a torn append can corrupt the last row if the process dies mid-write).
    """
    existing: list[dict] = []
    if os.path.exists(path):
        with open(path, "r", encoding=encoding, newline="") as f:
            reader = csv.DictReader(f)
            existing = list(reader)
    atomic_write_csv_dict(path, fieldnames, existing + list(new_rows), encoding=encoding, strict=strict)


def atomic_write_json(path: str, data, *, indent: int = 2, encoding: str = "utf-8", ensure_ascii: bool = False) -> None:
    """Atomically write JSON data to file. Validates serializability before opening dest."""
    # Serialize to string FIRST — catches non-serializable data without touching the file
    text = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    with atomic_open(path, "w", encoding=encoding) as f:
        f.write(text)


def atomic_write_text(path: str, text: str, *, encoding: str = "utf-8") -> None:
    """Atomically write text to a file."""
    with atomic_open(path, "w", encoding=encoding) as f:
        f.write(text)
