"""S234 — Weekly cron skeleton: clone last-known cadence into next Monday's Week.

DISABLED by default. Will only print the intended action and exit. To activate:

* Pass ``--enable`` from the CLI for a one-off run, OR
* Wire into ``hrms/hooks.py`` with ``DISABLED_BY_DEFAULT = False`` after Sam's
  green light + logistics signoff on the cadence (deferred to a follow-up
  sprint; THIS sprint must NOT register the cron in hooks.py).

Behaviour
---------
* Find the latest ``BEI Delivery Schedule Week`` by ``week_start desc``.
* Compute ``next_monday = add_days(today, 7 - today.weekday())``.
* If ``latest_week_start >= next_monday``: nothing to do (already published),
  exit 0.
* Else: clone all Entry rows from the latest Week into a new Week with
  ``week_start = next_monday``.

Idempotency
-----------
Running multiple times in the same week is a no-op once next-Monday's Week
is created.

Plan: docs/plans/2026-05-03-sprint-234-ordering-schedule-defaults-and-data.md
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Sequence

# v2 audit fix W6 — explicit constant the verify script checks for.
DISABLED_BY_DEFAULT = True

try:  # pragma: no cover
    import frappe
    from frappe.utils import add_days, getdate, nowdate
except ImportError:
    frappe = None
    add_days = getdate = nowdate = None  # type: ignore[assignment]


WEEK_DOCTYPE = "BEI Delivery Schedule Week"


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("s234_publish_next_week_cron")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(sh)
    return logger


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S234 weekly cadence cloner (DISABLED by default)")
    p.add_argument("--enable", action="store_true",
                   help="Override DISABLED_BY_DEFAULT and actually clone the latest Week.")
    p.add_argument("--published", action="store_true",
                   help="Mark the cloned Week as published=1.")
    return p.parse_args(argv)


def run(args: argparse.Namespace, logger: logging.Logger) -> int:
    if frappe is None:  # pragma: no cover
        logger.error("frappe not importable — cron must run inside Frappe scheduler / bench / SSM.")
        return 2

    today = getdate(nowdate())
    today_weekday = today.weekday()  # 0 = Monday
    # add_days from frappe.utils accepts a date and an int offset.
    days_until_next_monday = (7 - today_weekday) if today_weekday > 0 else 7
    next_monday = add_days(today, days_until_next_monday)
    logger.info(f"today={today} today_weekday={today_weekday} next_monday={next_monday}")

    latest = frappe.db.sql(
        """
        SELECT name, week_start
        FROM `tabBEI Delivery Schedule Week`
        ORDER BY week_start DESC
        LIMIT 1
        """,
        as_dict=True,
    )
    if not latest:
        logger.warning("No existing BEI Delivery Schedule Week records — nothing to clone.")
        return 0
    latest_week = latest[0]
    logger.info(f"latest Week: {latest_week.name} (week_start={latest_week.week_start})")

    if str(latest_week.week_start) >= str(next_monday):
        logger.info("latest_week_start >= next_monday — already published, nothing to do.")
        return 0

    if DISABLED_BY_DEFAULT and not args.enable:
        logger.info(
            "DISABLED_BY_DEFAULT — would clone "
            f"{latest_week.name} → new Week (week_start={next_monday}). "
            "Pass --enable to actually run."
        )
        return 0

    # Real-write path.
    src = frappe.get_doc(WEEK_DOCTYPE, latest_week.name)
    new_doc = frappe.new_doc(WEEK_DOCTYPE)
    new_doc.week_start = next_monday
    if args.published:
        new_doc.published = 1
    for entry in src.entries:
        new_doc.append("entries", {
            "store": entry.store,
            "day_of_week": entry.day_of_week,
            "delivery_type": entry.delivery_type,
            "route_name": entry.route_name,
        })
    new_doc.insert(ignore_permissions=True)
    frappe.db.commit()
    logger.info(f"CLONED: {latest_week.name} → {new_doc.name} ({len(src.entries)} entries).")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    logger = _setup_logger()
    args = _parse_args(argv)
    logger.info(f"S234 cron start: enable={args.enable} DISABLED_BY_DEFAULT={DISABLED_BY_DEFAULT}")
    try:
        return run(args, logger)
    finally:
        logger.info("S234 cron end.")


if __name__ == "__main__":
    sys.exit(main())
