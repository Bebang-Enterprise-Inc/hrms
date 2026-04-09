#!/usr/bin/env python3
"""S175 Phase 6 + Phase 7 — BEI 6xxxxxx bulk fix + BEI Settings cutover.

Phase 6: Fix 134 BEI 6xxxxxx accounts from root_type='Income' → 'Expense'
  - Re-verify 0 GL entries (HB-4 gate)
  - Snapshot pre-update state as rollback artifact
  - Raw SQL UPDATE (documented Frappe validator bypass)
  - Post-update verification: all 136 6xxxxxx = Expense

Phase 7: BEI Settings.bki_sales_income_account cutover
  - Update from "SALES - BKI TO STORES - BKI" (deleted) to "4000210 - DELIVERIES - BKI"
  - Grep hrms/api/ consumers (done separately via repo grep)
  - HB-1: final verify link resolves
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s175_ssm_runner import run_on_frappe  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output" / "s175"

PAYLOAD = r'''
#!/usr/bin/env python3
import os, json, sys, traceback
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
frappe.local.flags.ignore_root_company_validation = True

BEI = "Bebang Enterprise Inc."
BKI = "Bebang Kitchen Inc."
result = {"phase6": {}, "phase7": {}}

# ===== PHASE 6: BEI 6xxxxxx =====
p6 = result["phase6"]

# HB-4 gate: re-verify 0 GL entries
gl_count = frappe.db.sql("""
    SELECT COUNT(*) FROM `tabGL Entry` ge
    JOIN `tabAccount` a ON ge.account=a.name
    WHERE a.company=%s AND a.account_number LIKE '6%%'
""", BEI)[0][0]
p6["gl_count_pre"] = gl_count
if gl_count != 0:
    p6["HB4_BLOCKED"] = True
    print("S175_P67_JSON_START")
    print(json.dumps(result, default=str))
    print("S175_P67_JSON_END")
    sys.exit(0)

# Pre-update snapshot (rollback artifact)
pre_snapshot = frappe.db.sql("""
    SELECT name, account_number, account_name, root_type, report_type
    FROM `tabAccount` WHERE company=%s AND account_number LIKE '6%%'
    ORDER BY account_number
""", BEI, as_dict=True)
p6["pre_count"] = len(pre_snapshot)
p6["pre_breakdown"] = {}
for r in pre_snapshot:
    key = f"{r['root_type']}|{r['report_type']}"
    p6["pre_breakdown"][key] = p6["pre_breakdown"].get(key, 0) + 1

# Bulk UPDATE
rows_updated = frappe.db.sql("""
    UPDATE `tabAccount`
    SET root_type='Expense', report_type='Profit and Loss'
    WHERE company=%s AND account_number LIKE '6%%' AND root_type='Income'
""", BEI)
frappe.db.commit()

# Post verify
post_breakdown = frappe.db.sql("""
    SELECT root_type, COUNT(*)
    FROM `tabAccount` WHERE company=%s AND account_number LIKE '6%%'
    GROUP BY root_type
""", BEI, as_list=True)
p6["post_breakdown"] = {r[0]: r[1] for r in post_breakdown}
p6["post_income_count"] = p6["post_breakdown"].get("Income", 0)
p6["post_expense_count"] = p6["post_breakdown"].get("Expense", 0)
p6["success"] = (p6["post_income_count"] == 0 and p6["post_expense_count"] >= 136)

# Save snapshot to container file (too big for stdout if we embed)
snapshot_path = "/tmp/phase6_pretouch_backup.json"
with open(snapshot_path, "w") as f:
    json.dump(pre_snapshot, f, default=str, indent=2)
p6["snapshot_path"] = snapshot_path

# ===== PHASE 7: BEI Settings cutover =====
p7 = result["phase7"]

# Resolve new account: 4000210 DELIVERIES on BKI
new_account = frappe.db.get_value(
    "Account",
    {"company": BKI, "account_number": "4000210", "account_name": "DELIVERIES"},
    "name",
)
p7["new_account"] = new_account
if not new_account:
    p7["HB1_BLOCKED"] = "4000210 DELIVERIES - BKI not found"
    print("S175_P67_JSON_START")
    print(json.dumps(result, default=str))
    print("S175_P67_JSON_END")
    sys.exit(0)

# Current value
bs = frappe.get_single("BEI Settings")
p7["old_value"] = bs.bki_sales_income_account
frappe.db.set_single_value("BEI Settings", "bki_sales_income_account", new_account)
frappe.db.commit()

# Verify
bs2 = frappe.get_single("BEI Settings")
p7["new_value"] = bs2.bki_sales_income_account
p7["linked_account_exists"] = bool(frappe.db.exists("Account", bs2.bki_sales_income_account))

print("S175_P67_JSON_START")
print(json.dumps(result, default=str))
print("S175_P67_JSON_END")
frappe.destroy()
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    payload_path = OUT / "_phase67_payload.py"
    payload_path.write_text(PAYLOAD, encoding="utf-8")

    stdout, stderr, status = run_on_frappe(payload_path, tag="phase67_bei6xxx_settings", timeout_seconds=900)
    if status != "Success":
        print(stderr[-2000:]); sys.exit(1)

    raw = stdout.split("S175_P67_JSON_START", 1)[1].split("S175_P67_JSON_END", 1)[0].strip()
    result = json.loads(raw)

    (OUT / "phase6_verification.json").write_text(json.dumps(result["phase6"], indent=2, default=str), encoding="utf-8")
    (OUT / "phase7_hb1_final.json").write_text(json.dumps(result["phase7"], indent=2, default=str), encoding="utf-8")

    p6 = result["phase6"]
    print("Phase 6 (BEI 6xxxxxx):")
    print(f"  HB-4 gl_count_pre: {p6.get('gl_count_pre')}")
    print(f"  pre_breakdown: {p6.get('pre_breakdown')}")
    print(f"  post_breakdown: {p6.get('post_breakdown')}")
    print(f"  success: {p6.get('success')}")

    p7 = result["phase7"]
    print("\nPhase 7 (BEI Settings cutover):")
    print(f"  new_account: {p7.get('new_account')}")
    print(f"  old_value: {p7.get('old_value')}")
    print(f"  new_value: {p7.get('new_value')}")
    print(f"  linked_account_exists: {p7.get('linked_account_exists')}")

    ok = p6.get("success") and p7.get("linked_account_exists")
    if not ok:
        print("PHASE6/7 FAIL")
        sys.exit(2)
    print("PHASE6/7 OK")


if __name__ == "__main__":
    main()
