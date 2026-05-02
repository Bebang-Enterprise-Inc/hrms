#!/usr/bin/env python3
"""S231 Phase E-3: dedup duplicate BFC Companies in production.

Production probe (`dep_production_state.json.bfc_check`) confirmed that
both `Bebang Franchise Corp.` (mixed case) AND `BEBANG FRANCHISE CORP.`
(uppercase, matches `abbr=BFC`) exist as separate Company records.
The uppercase variant is canonical.

Migration approach (from plan E-3):
  1. Pre-check: count Sales Invoices + GL Entries under the duplicate.
  2. HARD BLOCKER: if (si_count + gl_count) > 100, abort and ask CEO —
     plan rule "naming canonicalization should not silently rewrite
     >100 records without review".
  3. Otherwise: `frappe.rename_doc("Company", duplicate, canonical,
     merge=True, force=True)` — Frappe re-points all Link fields
     pointing at the duplicate to the canonical.
  4. Capture migration log to bfc_dedup_log.json.

Modes:
    --probe       — read-only count check (default; safe to run anytime)
    --execute     — perform the rename (requires --confirm)
    --confirm     — actually mutate; without it, --execute is dry-run

Run probe first:
    python scripts/s231_dedup_bfc.py --probe

Then if counts are <100:
    python scripts/s231_dedup_bfc.py --execute --confirm
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from s231_ssm_helper import (  # noqa: E402
	PAYLOAD_PREAMBLE,
	decode_output,
	run_in_container,
)

OUT = REPO_ROOT / "output" / "s231" / "verification" / "bfc_dedup_log.json"

CANONICAL = "BEBANG FRANCHISE CORP."
DUPLICATE = "Bebang Franchise Corp."
HARD_BLOCKER_THRESHOLD = 100


def build_payload(probe_only: bool, execute: bool) -> str:
	return PAYLOAD_PREAMBLE + f"""
canonical = {CANONICAL!r}
duplicate = {DUPLICATE!r}
probe_only = {probe_only!r}
execute = {execute!r}

log = {{
    "canonical": canonical,
    "duplicate": duplicate,
    "canonical_exists": bool(frappe.db.exists("Company", canonical)),
    "duplicate_exists": bool(frappe.db.exists("Company", duplicate)),
}}

if log["duplicate_exists"]:
    log["si_count"] = frappe.db.count("Sales Invoice", {{"company": duplicate}})
    log["gl_count"] = frappe.db.count("GL Entry", {{"company": duplicate}})
    log["pi_count"] = frappe.db.count("Purchase Invoice", {{"company": duplicate}})
    log["je_count"] = frappe.db.count("Journal Entry", {{"company": duplicate}})
    log["pe_count"] = frappe.db.count("Payment Entry", {{"company": duplicate}})
    log["se_count"] = frappe.db.count("Stock Entry", {{"company": duplicate}})
    log["transactions_total"] = sum([
        log["si_count"], log["gl_count"], log["pi_count"],
        log["je_count"], log["pe_count"], log["se_count"]
    ])
else:
    log["si_count"] = 0
    log["gl_count"] = 0
    log["pi_count"] = 0
    log["je_count"] = 0
    log["pe_count"] = 0
    log["se_count"] = 0
    log["transactions_total"] = 0

if probe_only:
    log["mode"] = "probe"
    _s231_emit(log)
    frappe.destroy()
    raise SystemExit(0)

if not log["canonical_exists"]:
    log["error"] = f"Canonical {{canonical!r}} missing — cannot merge"
    log["mode"] = "execute_aborted"
    _s231_emit(log)
    frappe.destroy()
    raise SystemExit(0)

if not log["duplicate_exists"]:
    log["mode"] = "noop"
    log["note"] = "Duplicate already retired — nothing to do"
    _s231_emit(log)
    frappe.destroy()
    raise SystemExit(0)

if log["transactions_total"] > {HARD_BLOCKER_THRESHOLD}:
    log["mode"] = "hard_blocker"
    log["error"] = (
        f"S231 Phase E-3 HARD BLOCKER: {{log['transactions_total']}} transactions "
        f"under duplicate {{duplicate!r}} exceeds threshold {HARD_BLOCKER_THRESHOLD}. "
        "Pause and ask CEO before silently rewriting more than 100 records."
    )
    _s231_emit(log)
    frappe.destroy()
    raise SystemExit(0)

if execute:
    try:
        frappe.rename_doc(
            "Company", duplicate, canonical,
            merge=True, force=True,
        )
        frappe.db.commit()
        log["mode"] = "executed"
        log["renamed"] = True
        log["transactions_migrated"] = log["transactions_total"]
        log["duplicate_retired"] = duplicate
        log["canonical_after_count_si"] = frappe.db.count("Sales Invoice", {{"company": canonical}})
    except Exception as e:
        log["mode"] = "execute_failed"
        log["error"] = str(e)
else:
    log["mode"] = "dry_run"

_s231_emit(log)
frappe.destroy()
"""


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument("--probe", action="store_true", help="Read-only count probe (default)")
	parser.add_argument("--execute", action="store_true", help="Perform the rename")
	parser.add_argument("--confirm", action="store_true",
	                    help="Required with --execute to actually mutate")
	args = parser.parse_args()

	probe_only = not args.execute
	execute = bool(args.execute and args.confirm)
	if args.execute and not args.confirm:
		print("WARN: --execute without --confirm runs as dry-run", file=sys.stderr)

	OUT.parent.mkdir(parents=True, exist_ok=True)
	stdout = run_in_container(build_payload(probe_only, execute), timeout=300)
	log = decode_output(stdout)
	OUT.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
	print(f"Wrote {OUT}")
	print(f"Mode: {log.get('mode')}")
	print(f"Canonical exists: {log['canonical_exists']}")
	print(f"Duplicate exists: {log['duplicate_exists']}")
	print(f"Transactions under duplicate: {log['transactions_total']}")
	if log.get("error"):
		print(f"ERROR: {log['error']}", file=sys.stderr)
		return 3
	return 0


if __name__ == "__main__":
	sys.exit(main())
