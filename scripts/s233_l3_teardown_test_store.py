#!/usr/bin/env python3
"""S233 v3 L3 post-flight teardown.

Reverses any L3-test-created records left behind by the spec. Targets BOTH
test stores (S1-S5 happy/negative case AND S8 race-condition winner):
  - "L3 Test Store 233 - BEBANG FT INC."
  - "L3 Race Test Store - BEBANG FT INC."

Order: Customer (internal) → Customer (billing) → Warehouse → Company,
then strip the matching S037 register CSV row.

Idempotent — re-running after partial cleanup is a no-op for whatever's
already deleted. Writes output/l3/s233/teardown_complete.json with the
final reconciliation.
"""
from __future__ import annotations
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import run_in_container

PREAMBLE = """\
import os, sys, json, traceback
for d in (
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
):
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

def _emit(payload):
    print("---S233-TEARDOWN-START---")
    print(json.dumps(payload, indent=2, default=str))
    print("---S233-TEARDOWN-END---")
"""

TEARDOWN = PREAMBLE + """
import csv, os, tempfile

TEST_STORES = [
    {"label": "L3 Test Store 233", "parent": "BEBANG FT INC."},
    {"label": "L3 Race Test Store", "parent": "BEBANG FT INC."},
]

result = {"per_store": [], "csv_rows_removed": 0, "deleted_total": 0}
try:
    for spec in TEST_STORES:
        store_label = spec["label"]
        parent = spec["parent"]
        company_name = f"{store_label} - {parent}"
        internal = f"{store_label} (Internal)"
        per_store = {
            "store_label": store_label,
            "company_name": company_name,
            "actions": [],
        }

        # 1. Internal Customer
        if frappe.db.exists("Customer", internal):
            try:
                frappe.delete_doc("Customer", internal, force=True, ignore_permissions=True, ignore_on_trash=True)
                per_store["actions"].append({"doctype": "Customer", "name": internal, "action": "deleted"})
                result["deleted_total"] += 1
            except Exception as e:
                per_store["actions"].append({"doctype": "Customer", "name": internal, "action": "failed", "error": str(e)[:200]})

        # 2. Billing Customer
        if frappe.db.exists("Customer", company_name):
            try:
                frappe.delete_doc("Customer", company_name, force=True, ignore_permissions=True, ignore_on_trash=True)
                per_store["actions"].append({"doctype": "Customer", "name": company_name, "action": "deleted"})
                result["deleted_total"] += 1
            except Exception as e:
                per_store["actions"].append({"doctype": "Customer", "name": company_name, "action": "failed", "error": str(e)[:200]})

        # 3. Warehouse
        if frappe.db.exists("Warehouse", company_name):
            try:
                frappe.delete_doc("Warehouse", company_name, force=True, ignore_permissions=True, ignore_on_trash=True)
                per_store["actions"].append({"doctype": "Warehouse", "name": company_name, "action": "deleted"})
                result["deleted_total"] += 1
            except Exception as e:
                per_store["actions"].append({"doctype": "Warehouse", "name": company_name, "action": "failed", "error": str(e)[:200]})

        # 4. Company
        if frappe.db.exists("Company", company_name):
            try:
                frappe.delete_doc("Company", company_name, force=True, ignore_permissions=True, ignore_on_trash=True)
                per_store["actions"].append({"doctype": "Company", "name": company_name, "action": "deleted"})
                result["deleted_total"] += 1
            except Exception as e:
                per_store["actions"].append({"doctype": "Company", "name": company_name, "action": "failed", "error": str(e)[:200]})

        result["per_store"].append(per_store)

    frappe.db.commit()

    # 5. Strip matching rows from S037 register CSV (atomic write)
    from hrms.utils.bei_config import STORE_ENTITY_MAPPING_RELPATH
    s037_path = os.path.normpath(os.path.join(frappe.get_app_path("hrms"), *STORE_ENTITY_MAPPING_RELPATH))
    if os.path.exists(s037_path):
        with open(s037_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        labels_to_strip = {s["label"] for s in TEST_STORES}
        kept = [rows[0]]  # header
        for r in rows[1:]:
            if r and r[0].strip() in labels_to_strip:
                result["csv_rows_removed"] += 1
            else:
                kept.append(r)
        if result["csv_rows_removed"] > 0:
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(s037_path), text=True)
            os.close(fd)
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerows(kept)
            os.replace(tmp, s037_path)

    # Final reconciliation: confirm zero remaining
    remaining = []
    for spec in TEST_STORES:
        store_label = spec["label"]
        parent = spec["parent"]
        company_name = f"{store_label} - {parent}"
        for dt, name in [
            ("Company", company_name),
            ("Warehouse", company_name),
            ("Customer", company_name),
            ("Customer", f"{store_label} (Internal)"),
        ]:
            if frappe.db.exists(dt, name):
                remaining.append({"doctype": dt, "name": name})
    result["remaining"] = remaining
    result["remaining_count"] = len(remaining)
    result["status"] = "OK" if len(remaining) == 0 else "PARTIAL"
except Exception as e:
    result["error"] = str(e)
    result["traceback"] = traceback.format_exc()
    result["status"] = "ERROR"

_emit(result)
frappe.destroy()
"""


def main() -> int:
	stdout = run_in_container(TEARDOWN, timeout=180)
	if "---S233-TEARDOWN-START---" not in stdout:
		print("ERROR: teardown output missing markers:\n" + stdout[-2000:], file=sys.stderr)
		return 2
	s = stdout.split("---S233-TEARDOWN-START---", 1)[1].split("---S233-TEARDOWN-END---", 1)[0].strip()
	data = json.loads(s)
	out_path = REPO_ROOT / "output" / "l3" / "s233" / "teardown_complete.json"
	out_path.parent.mkdir(parents=True, exist_ok=True)
	out_path.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str))
	return 0 if data.get("status") == "OK" else 1


if __name__ == "__main__":
	sys.exit(main())
