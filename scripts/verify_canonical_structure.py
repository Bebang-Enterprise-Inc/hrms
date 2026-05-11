"""Verify Frappe records conform to docs/STORE_COMPANY_CANONICAL.md.

Read-only. Reports violations. Exit code 0 = all stores canonical, 1 = at least one violation.

Usage:
    python scripts/verify_canonical_structure.py                  # all stores (v1 mode)
    python scripts/verify_canonical_structure.py --store "..."    # one store (v1 mode)
    python scripts/verify_canonical_structure.py --mode v2        # full canonical store spec (S246-v2)

S246-v2 (2026-05-11): added --mode v2 flag that delegates to scripts/s246/run_v2_verifier.py
which asserts the FULL canonical store master-data spec defined in
output/l3/s246/audit/CANONICAL_STORE_SPEC.md (every REQUIRED field on Company / Warehouse
/ Customer / Internal Customer / Account / BKI Trade Supplier accounts[] / BEI Settings
/ Custom Fields). v1 mode (default) preserves the original CANONICAL_OK / VIOLATION check
on WH+Customer+Internal-Customer existence + uniqueness + linkage.
"""
from __future__ import annotations
import argparse
import base64
import json
import sys
import time


def _build_script(store_filter: str | None) -> str:
    filter_literal = "None" if not store_filter else f'"{store_filter}"'
    return f'''
import os
# Frappe logger crashes if these directories don't exist (/frappe-bulk-edits boilerplate)
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files",
]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

store_filter = {filter_literal}

# Get stores to check
if store_filter:
    stores = frappe.db.sql(
        """SELECT name, parent_company, tax_id, operational_status
           FROM `tabCompany` WHERE name = %s AND entity_category = 'Store'""",
        (store_filter,), as_dict=True,
    )
else:
    stores = frappe.db.sql(
        """SELECT name, parent_company, tax_id, operational_status
           FROM `tabCompany`
           WHERE entity_category = 'Store'
             AND (operational_status IS NULL OR operational_status NOT IN ('Permanently Closed','Dormant'))
           ORDER BY name""",
        as_dict=True,
    )

total = len(stores)
violations = []

def V(store_name, rule, detail):
    violations.append({{"store": store_name, "rule": rule, "detail": detail}})

SUB_WH_SQL = "('FINISHED GOODS', 'GOODS IN TRANSIT', 'STORES', 'WORK IN PROGRESS')"

for co in stores:
    ps_co = co["name"]
    parent = co["parent_company"]

    # --- Warehouse check ---
    # Expected: exactly 1 orderable warehouse with docname == ps_co and company == ps_co
    canonical_wh = frappe.db.get_value(
        "Warehouse", ps_co,
        ["name", "warehouse_name", "company", "is_group", "disabled", "custom_area_supervisor"],
        as_dict=True,
    )
    if not canonical_wh:
        V(ps_co, "WH_MISSING", f"No Warehouse docname matches per-store Company name {{ps_co!r}}")
    else:
        if canonical_wh["company"] != ps_co:
            V(ps_co, "WH_COMPANY_MISMATCH", f"Warehouse.company = {{canonical_wh['company']!r}}, expected {{ps_co!r}}")
        if canonical_wh["is_group"]:
            V(ps_co, "WH_IS_GROUP", f"Warehouse is a group warehouse - canonical is non-group")
        if canonical_wh["disabled"]:
            V(ps_co, "WH_DISABLED", f"Canonical Warehouse is disabled")

    # Flag any OTHER active non-sub warehouse that references this store
    other_wh_ps = frappe.db.sql(
        "SELECT name FROM `tabWarehouse` "
        "WHERE company = %s AND is_group = 0 AND disabled = 0 "
        "AND warehouse_name NOT IN " + SUB_WH_SQL + " "
        "AND name != %s",
        (ps_co, ps_co), as_dict=True,
    )
    for ow in other_wh_ps:
        V(ps_co, "WH_DUPLICATE_UNDER_PER_STORE", f"Extra active warehouse under per-store Company: {{ow['name']!r}}")

    # Flag any warehouse under PARENT that references this store (heuristic)
    if parent:
        import re
        store_label = re.sub(r"\\s+-\\s+.+?(INC\\.|CORP\\.|OPC|HOLDINGS\\s+OPC).*$", "", ps_co).strip()
        if store_label:
            parent_wh = frappe.db.sql(
                "SELECT name FROM `tabWarehouse` "
                "WHERE company = %s AND is_group = 0 AND disabled = 0 "
                "AND warehouse_name NOT IN " + SUB_WH_SQL + " "
                "AND (name LIKE %s OR warehouse_name LIKE %s) "
                "AND name != %s",
                (parent, f"%{{store_label}}%", f"%{{store_label}}%", ps_co), as_dict=True,
            )
            for pw in parent_wh:
                V(ps_co, "WH_DUPLICATE_UNDER_PARENT", f"Extra active warehouse under parent linked to store: {{pw['name']!r}}")

    # --- Billing Customer check ---
    billing_cust = frappe.db.get_value(
        "Customer", {{"customer_name": ps_co, "is_internal_customer": 0}},
        ["name", "tax_id"],
        as_dict=True,
    )
    if not billing_cust:
        V(ps_co, "BILLING_CUST_MISSING", f"No non-internal Customer with customer_name = {{ps_co!r}}")
    else:
        expected_tin = co["tax_id"] or (frappe.db.get_value("Company", parent, "tax_id") if parent else None)
        if expected_tin and billing_cust.get("tax_id") != expected_tin:
            V(ps_co, "BILLING_CUST_TIN_MISMATCH", f"Customer tax_id = {{billing_cust['tax_id']!r}}, expected {{expected_tin!r}}")
        if not billing_cust.get("tax_id") and expected_tin is None:
            V(ps_co, "BILLING_CUST_TIN_EMPTY", f"Billing Customer has no TIN and no TIN is derivable from Company master")

    # --- Internal Customer check ---
    internal_cust = frappe.db.sql(
        """SELECT name, customer_name FROM `tabCustomer`
           WHERE represents_company = %s AND is_internal_customer = 1""",
        (ps_co,), as_dict=True,
    )
    if not internal_cust:
        V(ps_co, "INTERNAL_CUST_MISSING", f"No Internal Customer with represents_company = {{ps_co!r}} (S206 will fail on this store)")
    elif len(internal_cust) > 1:
        V(ps_co, "INTERNAL_CUST_DUPLICATE", f"Multiple Internal Customers: {{[c['name'] for c in internal_cust]}}")

    # Warn on orphan Customer with customer_name matching parent but no explicit link
    # (legacy parent-level billing Customer still being used for store sales)
    # Not a violation per se but reported as "drift candidate"
    pass

# Report
print("=" * 70)
print(f"CANONICAL STRUCTURE VERIFICATION")
print(f"Stores checked: {{total}}")
print(f"Violations: {{len(violations)}}")
print("=" * 70)

if violations:
    by_rule = {{}}
    for v in violations:
        by_rule.setdefault(v["rule"], []).append(v)
    for rule, vs in sorted(by_rule.items(), key=lambda x: -len(x[1])):
        print(f"\\n[{{rule}}] {{len(vs)}} stores:")
        for v in vs[:60]:
            print(f"  {{v['store']}}: {{v['detail']}}")
        if len(vs) > 60:
            print(f"  ... and {{len(vs)-60}} more")

if violations:
    print("\\n[RESULT] VIOLATIONS FOUND — see docs/STORE_COMPANY_CANONICAL.md to fix")
else:
    print("\\n[RESULT] ALL CANONICAL — no action required")

# exit codes via the container side don't matter; calling script handles outer exit
import sys as _sys
_sys.exit(1 if violations else 0)

frappe.destroy()
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", help="Check only this per-store Company name")
    ap.add_argument("--mode", choices=["v1", "v2"], default="v1",
                    help="v1 (default) = original WH+Customer canonical check. "
                         "v2 = S246 full master-data spec assertion (delegates to scripts/s246/run_v2_verifier.py)")
    args = ap.parse_args()

    # S246-v2: delegate to the extended verifier
    if args.mode == "v2":
        import subprocess
        import os
        v2_runner = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "s246", "run_v2_verifier.py")
        print(f"S246-v2 mode: delegating to {v2_runner}")
        return subprocess.call([sys.executable, v2_runner])

    script = _build_script(args.store)
    enc = base64.b64encode(script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/verify_canonical.py",
        "docker cp /tmp/verify_canonical.py $BACKEND:/tmp/verify_canonical.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/verify_canonical.py",
    ]

    import boto3
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=["i-026b7477d27bd46d6"],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["180"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    for _ in range(60):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            print(inv["StandardOutputContent"])
            # Script exits non-zero on violations; SSM surfaces that as Failed
            return 0 if inv["Status"] == "Success" else 1
    print("TIMEOUT waiting for SSM")
    return 2


if __name__ == "__main__":
    sys.exit(main())
