"""S258 Phase 3a — Seed canonical 5-root tree on all 58 Companies via SSM bench execute.

Uses frappe.local.flags.ignore_root_company_validation = True to bypass the cascade
that prevents creating root accounts on child Companies via REST.
"""
from __future__ import annotations
import base64
import sys
import time

import boto3


SCRIPT = r'''
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files"]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
frappe.local.flags.ignore_root_company_validation = True
frappe.flags.in_migrate = True

REPORT_TYPE_MAP = {
    "Asset": "Balance Sheet", "Liability": "Balance Sheet", "Equity": "Balance Sheet",
    "Income": "Profit and Loss", "Expense": "Profit and Loss",
}

companies = frappe.get_all("Company", filters={"is_group": ["in", [0, 1]]},
                           fields=["name", "abbr", "default_currency"])
print(f"Companies: {len(companies)}")
assert len(companies) == 58, f"Expected 58, got {len(companies)}"

created = 0
skipped = 0
errors = []
for c in companies:
    for root_type in ["Asset", "Liability", "Equity", "Income", "Expense"]:
        target_name = f"{root_type} - {c['abbr']}"
        if frappe.db.exists("Account", target_name):
            skipped += 1
            continue
        try:
            doc = frappe.get_doc({
                "doctype": "Account",
                "account_name": root_type,
                "parent_account": "",
                "company": c["name"],
                "is_group": 1,
                "root_type": root_type,
                "report_type": REPORT_TYPE_MAP[root_type],
                "account_currency": (c.get("default_currency") or "PHP"),
                "account_number": "",
            })
            doc.flags.ignore_mandatory = True
            doc.flags.ignore_permissions = True
            doc.flags.ignore_links = True
            doc.insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            errors.append({"company": c["name"], "root_type": root_type, "error": str(e)[:200]})

frappe.db.commit()
print(f"Created: {created} | Skipped (already-exist): {skipped} | Errors: {len(errors)}")
if errors:
    import json
    print("FIRST 10 ERRORS:")
    for e in errors[:10]:
        print(json.dumps(e))

# Verification: every Company should have all 5 root groups
print("\nVerification per Company:")
for c in companies:
    have = []
    for rt in ("Asset","Liability","Equity","Income","Expense"):
        if frappe.db.exists("Account", f"{rt} - {c['abbr']}"):
            have.append(rt)
    if len(have) != 5:
        print(f"  INCOMPLETE: {c['name']!r} has only {have}")
print("DONE")
'''


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s258_C0.py",
        "docker cp /tmp/s258_C0.py $BACKEND:/tmp/s258_C0.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s258_C0.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=["i-026b7477d27bd46d6"],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["600"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    for _ in range(120):
        time.sleep(5)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            print(inv["StandardOutputContent"])
            if inv["StandardErrorContent"]:
                print("STDERR:", inv["StandardErrorContent"][-2000:])
            return 0 if inv["Status"] == "Success" else 1
    print("TIMEOUT")
    return 2


if __name__ == "__main__":
    sys.exit(main())
