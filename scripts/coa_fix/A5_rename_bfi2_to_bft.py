"""S258 Phase 1.5 (A5) — Rename BEBANG FT INC. abbr BFI2 -> BFT via SSM bench execute.

Plan v1.1 mechanism per audit C1:
- `flags.ignore_validate_constants = True`
- `frappe.db.set_value('Company', 'BEBANG FT INC.', 'abbr', 'BFT', update_modified=True)`
- Per-Account loop renaming '%- BFI2' -> '%- BFT' (no-op for now: BFT has 0 accounts)

SEC legal name 'BEBANG FT INC.' UNCHANGED — only Frappe abbr field changes.
"""
from __future__ import annotations
import base64
import sys
import time

import boto3


SCRIPT = r'''
import os
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

company_name = "BEBANG FT INC."
old_abbr = "BFI2"
new_abbr = "BFT"

cur = frappe.db.get_value("Company", company_name, "abbr")
print(f"Current abbr on {company_name!r}: {cur!r}")
if cur == new_abbr:
    print(f"Already {new_abbr}; no-op.")
else:
    assert cur == old_abbr, f"Unexpected current abbr {cur!r}; expected {old_abbr!r}"
    # v1.1 mechanism: set flag, then use db.set_value (bypasses validate_constants)
    co = frappe.get_doc("Company", company_name)
    co.flags.ignore_validate_constants = True
    frappe.db.set_value("Company", company_name, "abbr", new_abbr, update_modified=True)
    print(f"SET tabCompany.abbr = {new_abbr!r}")

    # Per-Account loop (BFT has 0 accounts pre-seed; should be 0 iterations)
    accts = frappe.get_all("Account", filters={"name": ("like", "%- BFI2")}, pluck="name")
    print(f"Accounts ending '- BFI2': {len(accts)}")
    for a in accts:
        new_name = a.replace("- BFI2", "- BFT")
        frappe.rename_doc("Account", a, new_name, force=True, ignore_permissions=False)
        print(f"  renamed: {a!r} -> {new_name!r}")

    # Same for Cost Centers, Warehouses etc that may have - BFI2 suffix
    for doctype in ("Cost Center", "Warehouse"):
        rows = frappe.get_all(doctype, filters={"name": ("like", "%- BFI2")}, pluck="name")
        print(f"{doctype} ending '- BFI2': {len(rows)}")
        for n in rows:
            new_name = n.replace("- BFI2", "- BFT")
            try:
                frappe.rename_doc(doctype, n, new_name, force=True, ignore_permissions=False)
                print(f"  renamed {doctype}: {n!r} -> {new_name!r}")
            except Exception as e:
                print(f"  ERROR renaming {doctype} {n!r}: {e}")

    frappe.db.commit()

# Verify
verify = frappe.db.get_value("Company", company_name, "abbr")
remaining = frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE name LIKE '%- BFI2%'")[0][0]
print(f"FINAL: abbr={verify!r}, tabAccount '- BFI2' rows remaining: {remaining}")
'''


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s258_A5.py",
        "docker cp /tmp/s258_A5.py $BACKEND:/tmp/s258_A5.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s258_A5.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=["i-026b7477d27bd46d6"],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["300"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    for _ in range(60):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            print(inv["StandardOutputContent"])
            if inv["StandardErrorContent"]:
                print("STDERR:", inv["StandardErrorContent"])
            return 0 if inv["Status"] == "Success" else 1
    print("TIMEOUT waiting for SSM")
    return 2


if __name__ == "__main__":
    sys.exit(main())
