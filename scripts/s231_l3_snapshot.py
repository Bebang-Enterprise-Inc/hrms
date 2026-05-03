#!/usr/bin/env python3
"""S231 L3 PRE-TEST SNAPSHOT — capture original state of every Company we
might touch, BEFORE any browser-driven mutation. Read-only.

Output: output/l3/s231/snapshots/companies_pretest.json
"""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}

# Snapshot ALL fields on Ayala Fairview Terraces + a few representative test
# candidates. Capture every default_*, store_ownership_type, parent_company,
# entity_category, etc. so we can rollback to exact pre-test state.

candidates = [
    "AYALA FAIRVIEW TERRACES - BEBANG FT INC.",  # Primary FT target
]

# Find safe Company Owned stores to test secondarily
co_owned = frappe.db.sql(
    "SELECT name FROM `tabCompany` WHERE store_ownership_type = 'Company Owned' AND entity_category = 'Store' ORDER BY name",
    as_dict=True,
)
mf = frappe.db.sql(
    "SELECT name FROM `tabCompany` WHERE store_ownership_type = 'Managed Franchise' AND entity_category = 'Store' ORDER BY name LIMIT 3",
    as_dict=True,
)
ff = frappe.db.sql(
    "SELECT name FROM `tabCompany` WHERE store_ownership_type = 'Full Franchise' AND entity_category = 'Store' ORDER BY name LIMIT 3",
    as_dict=True,
)
jv = frappe.db.sql(
    "SELECT name FROM `tabCompany` WHERE store_ownership_type = 'JV' AND entity_category = 'Store' ORDER BY name LIMIT 3",
    as_dict=True,
)

result["available_by_type"] = {
    "Company Owned": [r["name"] for r in co_owned],
    "Managed Franchise": [r["name"] for r in mf],
    "Full Franchise": [r["name"] for r in ff],
    "JV": [r["name"] for r in jv],
}

# Snapshot full state for Ayala + one CO-owned + one MF (the two we'll test)
to_snapshot = candidates[:]
if co_owned:
    to_snapshot.append(co_owned[0]["name"])
if mf:
    to_snapshot.append(mf[0]["name"])

snapshots = {}
for cname in to_snapshot:
    if not frappe.db.exists("Company", cname):
        snapshots[cname] = {"_missing": True}
        continue
    doc = frappe.db.sql(
        "SELECT * FROM `tabCompany` WHERE name = %s",
        (cname,),
        as_dict=True,
    )[0]
    snapshots[cname] = {k: v for k, v in doc.items()}

result["snapshots"] = snapshots
result["captured_at"] = frappe.utils.now()

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=180)
	data = decode_output(stdout)
	out = pathlib.Path("output/l3/s231/snapshots/companies_pretest.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(f"Wrote {out}")
	print("Available by ownership type:")
	for t, names in data["available_by_type"].items():
		print(f"  {t}: {len(names)} — {names[:3]}")
	print(f"\nSnapshotted {len(data['snapshots'])} Companies for rollback safety:")
	for cname, doc in data["snapshots"].items():
		if doc.get("_missing"):
			print(f"  MISSING: {cname}")
		else:
			print(f"  {cname}: ownership={doc.get('store_ownership_type')!r} entity_cat={doc.get('entity_category')!r}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
