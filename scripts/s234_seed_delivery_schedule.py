"""S234 — Idempotent CSV → BEI Delivery Schedule Week+Entry seeder.

Designed to run inside the Frappe backend container via SSM (see
``scripts/s225/README.md`` for the SSM script-from-stdin pattern). Can also
be run via ``bench --site hq.bebang.ph execute`` if a local bench is
configured.

Behaviour
---------
* Reads a CSV with columns: ``store``, ``delivery_type`` (COLD/DRY),
  ``day_of_week`` (Mon..Sun), ``route_name`` (optional).
* Groups rows by ``--week-start`` (one CSV → one Week record).
* For each Week:
    * Looks up an existing ``BEI Delivery Schedule Week`` whose ``week_start``
      matches; if found, **replaces** its child ``entries`` table with the
      CSV rows (delete-then-insert).
    * If absent, creates a new Week + child entries.
* Wraps the Week+entries write in ``frappe.db.savepoint("s234_week_<n>")``
  per DM-2 — rollback on any exception so a partially-imported Week never
  ships.
* Defaults to ``--dry-run`` (safe-by-default, v2 audit fix W6). Use
  ``--no-dry-run`` to actually write.

Idempotency
-----------
Re-running with the same CSV against a Week that already matches is a no-op
(end-state convergent). Re-running with a different CSV replaces the Week's
entries to match the new CSV.

CLI
---
::

    python scripts/s234_seed_delivery_schedule.py \\
        --csv data/operational/delivery_cadence_2026-05-04.csv \\
        --week-start 2026-05-04
    # by default --dry-run is True; pass --no-dry-run to actually write.

Plan: docs/plans/2026-05-03-sprint-234-ordering-schedule-defaults-and-data.md
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import logging
import os
import sys
from typing import List, Optional, Sequence

# Frappe is only importable inside a bench/SSM context.
try:  # pragma: no cover - import-time pivot
    import frappe
    from frappe.utils import getdate
except ImportError:  # script may be inspected outside Frappe
    frappe = None
    getdate = None  # type: ignore[assignment]


WEEK_DOCTYPE = "BEI Delivery Schedule Week"
ENTRY_DOCTYPE = "BEI Delivery Schedule Entry"
DAYS_OF_WEEK = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
DELIVERY_TYPES = {"COLD", "DRY"}


def _setup_logger(log_path: str) -> logging.Logger:
    logger = logging.getLogger("s234_seed_delivery_schedule")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


def _str2bool(v: str) -> bool:
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "1", "y"):
        return True
    if v.lower() in ("no", "false", "f", "0", "n"):
        return False
    raise argparse.ArgumentTypeError(f"Boolean value expected, got: {v!r}")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S234 BEI Delivery Schedule seeder")
    p.add_argument("--csv", required=True, help="Path to delivery cadence CSV")
    p.add_argument("--week-start", required=True,
                   help="Week start date (Monday, YYYY-MM-DD); becomes Week.week_start")
    p.add_argument("--dry-run", type=_str2bool, default=True,
                   help="Default True. Pass --dry-run=false (or --no-dry-run) to actually write.")
    p.add_argument("--no-dry-run", action="store_const", dest="dry_run", const=False,
                   help="Shorthand for --dry-run=false")
    p.add_argument("--log-dir", default="tmp/s234",
                   help="Where to write the seed_dry_run_<timestamp>.log file")
    p.add_argument("--published", type=_str2bool, default=False,
                   help="Mark new Week records as published=1. Default False.")
    return p.parse_args(argv)


def _load_csv(path: str) -> List[dict]:
    rows: List[dict] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_num, raw in enumerate(reader, start=2):  # header is line 1
            # Defensive: DictReader assigns None to keys/values when the row has
            # too few or too many fields. Skip those gracefully — comment lines
            # with embedded commas trip this otherwise.
            row = {}
            for k, v in raw.items():
                if k is None:
                    continue
                key = k.strip()
                if isinstance(v, str):
                    row[key] = v.strip()
                else:
                    row[key] = v
            store = row.get("store") or ""
            if not store or store.startswith("#"):
                continue
            errs = []
            if row.get("delivery_type") not in DELIVERY_TYPES:
                errs.append(f"delivery_type must be COLD or DRY, got {row.get('delivery_type')!r}")
            if row.get("day_of_week") not in DAYS_OF_WEEK:
                errs.append(f"day_of_week must be one of {sorted(DAYS_OF_WEEK)}, got {row.get('day_of_week')!r}")
            if errs:
                raise ValueError(f"Line {line_num}: {'; '.join(errs)}")
            rows.append(row)
    return rows


def _intent_summary(week_start: str, rows: List[dict]) -> dict:
    return {
        "week_start": week_start,
        "row_count": len(rows),
        "stores": sorted({r["store"] for r in rows}),
        "by_type": {
            t: sum(1 for r in rows if r["delivery_type"] == t)
            for t in DELIVERY_TYPES
        },
    }


def _upsert_week(week_start: str, dry_run: bool, published: bool, logger: logging.Logger):
    """Find or create the Week record. Returns the Week doc (or a stub dict for dry-run)."""
    if frappe is None:  # pragma: no cover
        raise RuntimeError("frappe not importable — must run inside Frappe bench/SSM")

    existing = frappe.db.get_value(WEEK_DOCTYPE, {"week_start": week_start}, "name")
    if existing:
        logger.info(f"INTENT: reuse existing Week {existing} (week_start={week_start})")
        if dry_run:
            return {"name": existing, "_dry_run": True}
        return frappe.get_doc(WEEK_DOCTYPE, existing)

    logger.info(f"INTENT: create Week (week_start={week_start}, published={published})")
    if dry_run:
        return {"name": "<NEW>", "_dry_run": True}
    doc = frappe.new_doc(WEEK_DOCTYPE)
    doc.week_start = week_start
    if published:
        doc.published = 1
    doc.insert(ignore_permissions=True)
    return doc


def _replace_entries(week_doc, csv_rows: List[dict], dry_run: bool, logger: logging.Logger) -> None:
    """Replace the Week's child entries with the CSV rows."""
    if frappe is None:  # pragma: no cover
        raise RuntimeError("frappe not importable")

    if dry_run:
        logger.info(f"INTENT: replace {len(csv_rows)} entries on Week {week_doc.get('name')}")
        for r in csv_rows[:3]:
            logger.info(f"  sample row: store={r['store']} day={r['day_of_week']} type={r['delivery_type']}")
        return

    # Production path
    week_doc.set("entries", [])
    for r in csv_rows:
        week_doc.append("entries", {
            "store": r["store"],
            "day_of_week": r["day_of_week"],
            "delivery_type": r["delivery_type"],
            "route_name": r.get("route_name") or None,
        })
    week_doc.save(ignore_permissions=True)
    logger.info(f"EXECUTED: wrote {len(csv_rows)} entries to Week {week_doc.name}")


def run(args: argparse.Namespace, logger: logging.Logger) -> int:
    rows = _load_csv(args.csv)
    summary = _intent_summary(args.week_start, rows)
    logger.info(f"INTENT_SUMMARY: {json.dumps(summary, default=str)}")

    if not rows:
        logger.info("No data rows in CSV — nothing to do.")
        return 0

    if frappe is None:
        logger.warning("frappe module not importable — running in CSV-validation-only mode.")
        logger.info(f"VALIDATION: {len(rows)} rows parsed cleanly. Re-run inside Frappe bench/SSM to seed.")
        return 0

    sp = f"s234_week_{args.week_start.replace('-', '')}"
    try:
        # DM-2: wrap multi-doc write in savepoint with rollback on error.
        if not args.dry_run:
            frappe.db.savepoint(sp)
        week_doc = _upsert_week(args.week_start, args.dry_run, args.published, logger)
        _replace_entries(week_doc, rows, args.dry_run, logger)
        if not args.dry_run:
            frappe.db.release_savepoint(sp)
            frappe.db.commit()
        logger.info("DONE.")
        return 0
    except Exception as e:
        if not args.dry_run:
            try:
                frappe.db.rollback_to_savepoint(sp)
            except Exception:  # pragma: no cover - best-effort rollback
                pass
        logger.error(f"FAILED: Week {args.week_start} import: {e}; rolled back via savepoint {sp}.")
        raise


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    os.makedirs(args.log_dir, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = os.path.join(args.log_dir, f"seed_dry_run_{ts}.log")
    logger = _setup_logger(log_path)
    logger.info(f"S234 seeder start: csv={args.csv} week_start={args.week_start} dry_run={args.dry_run}")
    try:
        return run(args, logger)
    finally:
        logger.info(f"S234 seeder end. Log: {log_path}")


if __name__ == "__main__":
    sys.exit(main())
