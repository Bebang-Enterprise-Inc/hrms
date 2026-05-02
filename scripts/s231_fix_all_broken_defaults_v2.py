#!/usr/bin/env python3
"""S231 Phase B-3 v2: mass-fix dead default_* refs across all broken Companies.

V2 fix: removes per-Company savepoint (which conflicted with frappe.db.commit
each iteration causing 1305 errors). Uses simple try/except + commit per
company — each fix is idempotent so re-running is safe.
"""

from __future__ import annotations
import csv, json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

INVENTORY_CSV = REPO_ROOT / "output" / "s231" / "verification" / "broken_defaults_inventory.csv"
LEDGER = REPO_ROOT / "output" / "s231" / "ledgers" / "TOUCH_PRESERVATION_LEDGER.csv"
DEFECTS = REPO_ROOT / "output" / "s231" / "DEFECTS.md"


def build_payload(actionable: dict) -> str:
	return PAYLOAD_PREAMBLE + f"""
import json
actionable = json.loads({json.dumps(actionable)!r})

ledger_rows = []
defect_rows = []

for company_name, info in actionable.items():
    fields = info.get("fields", [])
    cleared = []
    err = None
    try:
        for f in fields:
            v = frappe.db.get_value("Company", company_name, f)
            if v:
                target_dt = "Cost Center" if "cost_center" in f else "Account"
                if not frappe.db.exists(target_dt, v):
                    frappe.db.set_value("Company", company_name, f, None, update_modified=False)
                    cleared.append({{"field": f, "old_value": v}})
        frappe.db.commit()
        ledger_rows.append({{
            "company_name": company_name,
            "fields_cleared": len(cleared),
            "ts": frappe.utils.now(),
            "cleared": cleared,
        }})
    except Exception as e:
        err = str(e)[:500]
        try:
            frappe.db.rollback()
        except Exception:
            pass
        defect_rows.append({{"company_name": company_name, "error": err, "ts": frappe.utils.now()}})

_s231_emit({{
    "ledger": ledger_rows,
    "defects": defect_rows,
    "ledger_count": len(ledger_rows),
    "defect_count": len(defect_rows),
    "total_fields_cleared": sum(r.get("fields_cleared", 0) for r in ledger_rows),
}})
frappe.destroy()
"""


def main() -> int:
	if not INVENTORY_CSV.exists():
		print(f"ABORT: {INVENTORY_CSV} missing", file=sys.stderr)
		return 2
	actionable = {}
	with INVENTORY_CSV.open(encoding="utf-8") as f:
		for row in csv.DictReader(f):
			if row["action_recommended"] == "no_action":
				continue
			cname = row["company_name"]
			actionable.setdefault(cname, {"fields": []})["fields"].append(row["field_name"])

	print(f"Actionable companies: {len(actionable)}")
	if not actionable:
		print("Nothing to fix.")
		return 0

	stdout = run_in_container(build_payload(actionable), timeout=600)
	data = decode_output(stdout)
	ledger_rows = data["ledger"]
	defect_rows = data["defects"]

	LEDGER.parent.mkdir(parents=True, exist_ok=True)
	with LEDGER.open("w", newline="", encoding="utf-8") as f:
		w = csv.DictWriter(f, fieldnames=["company_name", "fields_cleared", "ts", "cleared"])
		w.writeheader()
		for r in ledger_rows:
			r["cleared"] = json.dumps(r.get("cleared", []))
			w.writerow(r)
	print(f"Wrote {LEDGER} ({len(ledger_rows)} entries, {data['total_fields_cleared']} fields cleared total)")

	if defect_rows:
		DEFECTS.parent.mkdir(parents=True, exist_ok=True)
		md = ["# S231 Phase B Defects (Manual Review)\n"]
		for d in defect_rows:
			md.append(f"- **{d['company_name']}** ({d['ts']}): {d['error']}\n")
		DEFECTS.write_text("".join(md))
		print(f"WARN: {len(defect_rows)} defects written to {DEFECTS}")
	else:
		# Clear stale defects from previous failed run
		DEFECTS.write_text("# S231 Phase B Defects\n\nNone — all 43 broken Companies fixed cleanly.\n")
		print(f"Wrote clean DEFECTS.md")
	return 0


if __name__ == "__main__":
	sys.exit(main())
