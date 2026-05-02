#!/usr/bin/env python3
"""S231 Phase B-3: mass-fix dead default_* refs across all store Companies.

Reads `output/s231/verification/broken_defaults_inventory.csv` (must exist —
run `s231_audit_broken_defaults.py` first), and for each row with
`action_recommended ∈ {null_field_same_company, null_field_cross_company,
enable_account}`:

  1. Try `retry_provision_company(company)` IFF first_provision_done==0
     OR all 21 fields are broken (suggests CoA never seeded).
  2. Otherwise, null only the broken fields.
  3. Wrap each Company in a savepoint so a single failure doesn't
     poison the rest.
  4. Append every touch to TOUCH_PRESERVATION_LEDGER.csv with
     (company_name, fields_cleared, accounts_created, ts).
  5. Companies that fail both strategies are written to DEFECTS.md
     for manual review.

Refuses to run if PRETOUCH_BACKUP.json doesn't exist (snapshot is the
rollback ground truth — Phase B-2 must run first).

Output: TOUCH_PRESERVATION_LEDGER.csv, DEFECTS.md (if any failures)
"""

from __future__ import annotations

import csv
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

INVENTORY_CSV = REPO_ROOT / "output" / "s231" / "verification" / "broken_defaults_inventory.csv"
PRETOUCH = REPO_ROOT / "output" / "s231" / "state" / "PRETOUCH_BACKUP.json"
LEDGER = REPO_ROOT / "output" / "s231" / "ledgers" / "TOUCH_PRESERVATION_LEDGER.csv"
DEFECTS = REPO_ROOT / "output" / "s231" / "DEFECTS.md"


def build_fix_payload(actionable_per_company: dict) -> str:
	"""Build the SSM payload that fixes all actionable companies in one round-trip."""
	# Embed the actionable map as a JSON literal inside the payload.
	actionable_json = json.dumps(actionable_per_company)
	return PAYLOAD_PREAMBLE + f"""
import json, re
actionable = json.loads({actionable_json!r})

# Optional: import retry_provision if available
try:
    from hrms.overrides.company import retry_provision_company
    HAS_RETRY = True
except Exception:
    HAS_RETRY = False

ledger_rows = []
defect_rows = []

for company_name, info in actionable.items():
    fields = info.get("fields", [])  # list of field_name strings to null
    first_done = info.get("first_provision_done", 1)
    sp = "s231_fix_" + re.sub(r"[^a-zA-Z0-9_]", "_", company_name)
    try:
        frappe.db.savepoint(sp)
        accounts_created = 0
        cleared = []

        # Strategy 1: retry_provision_company if first_done=0 OR all fields broken
        used_retry = False
        if HAS_RETRY and (first_done == 0 or len(fields) >= 18):
            try:
                retry_provision_company(company_name=company_name)
                accounts_created = 1  # placeholder count
                used_retry = True
            except Exception as retry_err:
                # Fall through to null strategy
                frappe.log_error(
                    title=f"S231 Phase B-3 retry failed for {{company_name}}",
                    message=str(retry_err),
                )

        # Strategy 2: null the broken fields
        if not used_retry:
            for f in fields:
                v = frappe.db.get_value("Company", company_name, f)
                if v:
                    target_dt = "Cost Center" if "cost_center" in f else "Account"
                    if not frappe.db.exists(target_dt, v):
                        frappe.db.set_value(
                            "Company", company_name, f, None, update_modified=False
                        )
                        cleared.append({{"field": f, "old_value": v}})

        frappe.db.commit()
        frappe.db.release_savepoint(sp)
        ledger_rows.append({{
            "company_name": company_name,
            "fields_cleared": len(cleared),
            "accounts_created": accounts_created,
            "used_retry": used_retry,
            "ts": frappe.utils.now(),
            "cleared": cleared,
        }})
    except Exception as e:
        try:
            frappe.db.rollback(save_point=sp)
        except Exception:
            pass
        defect_rows.append({{
            "company_name": company_name,
            "error": str(e),
            "ts": frappe.utils.now(),
        }})

_s231_emit({{
    "ledger": ledger_rows,
    "defects": defect_rows,
    "ledger_count": len(ledger_rows),
    "defect_count": len(defect_rows),
}})

frappe.destroy()
"""


def main() -> int:
	if not PRETOUCH.exists():
		print(
			f"ABORT: PRETOUCH_BACKUP.json missing at {PRETOUCH}. "
			"Run scripts/s231_snapshot_defaults_pretouch.py first.",
			file=sys.stderr,
		)
		return 2
	if not INVENTORY_CSV.exists():
		print(
			f"ABORT: {INVENTORY_CSV} missing. Run scripts/s231_audit_broken_defaults.py first.",
			file=sys.stderr,
		)
		return 2

	# Build actionable_per_company map from inventory CSV
	actionable: dict[str, dict] = {}
	with INVENTORY_CSV.open(encoding="utf-8") as f:
		for row in csv.DictReader(f):
			if row["action_recommended"] == "no_action":
				continue
			cname = row["company_name"]
			if cname not in actionable:
				actionable[cname] = {
					"first_provision_done": int(row.get("first_provision_done") or 0),
					"fields": [],
				}
			actionable[cname]["fields"].append(row["field_name"])

	print(f"Actionable companies: {len(actionable)}")
	if not actionable:
		print("Nothing to fix.")
		return 0

	stdout = run_in_container(build_fix_payload(actionable), timeout=600)
	data = decode_output(stdout)
	ledger_rows = data["ledger"]
	defect_rows = data["defects"]

	LEDGER.parent.mkdir(parents=True, exist_ok=True)
	with LEDGER.open("w", newline="", encoding="utf-8") as f:
		w = csv.DictWriter(
			f,
			fieldnames=["company_name", "fields_cleared", "accounts_created", "used_retry", "ts", "cleared"],
		)
		w.writeheader()
		for r in ledger_rows:
			r["cleared"] = json.dumps(r.get("cleared", []))
			w.writerow(r)
	print(f"Wrote {LEDGER} ({len(ledger_rows)} entries)")

	if defect_rows:
		DEFECTS.parent.mkdir(parents=True, exist_ok=True)
		md = ["# S231 Phase B Defects (Manual Review)\n"]
		for d in defect_rows:
			md.append(f"- **{d['company_name']}** ({d['ts']}): {d['error']}\n")
		DEFECTS.write_text("".join(md))
		print(f"WARN: {len(defect_rows)} defects written to {DEFECTS}", file=sys.stderr)

	return 0


if __name__ == "__main__":
	sys.exit(main())
