"""S204 F3 setup: rename BEBANG MEGA INC. Customer to trigger billing-hold.

Purpose: F3 negative scenario asserts the S190 buyer-customer resolver
(hrms/utils/supply_chain_contracts.py::resolve_store_buyer_entity after
PR #630) still fails-closed to billing-hold when NO Customer can be found
for a store's Company.

Scenario: renaming `BEBANG MEGA INC.` to `BEBANG MEGA INC. RENAMED-S204`:
- Step 1 (exact customer_name == "SM TANZA - BEBANG MEGA INC."): no match
- Step 2 (represents_company): no match
- Step 3 (parent_company chain): no match because the renamed docname is not a parent
- Step 4 (strip legal suffix "BEBANG MEGA"): no match

Result: buyer resolver returns "missing" → billing hold stamped.

Snapshot the original docname into `.scratch/s204_f3_state.json` so the
restore script has a deterministic source of truth.

IMPORTANT: the restore script MUST run after F3 finishes (pass OR fail),
otherwise SM Tanza + Ayala Evo dispatches will billing-hold on EVERY
subsequent order until someone manually renames back. The spec wraps F3
in try/finally and ALWAYS invokes restore.
"""
from __future__ import annotations
import base64
import json
import sys
import time
from pathlib import Path

ORIGINAL = "BEBANG MEGA INC."
RENAMED = "BEBANG MEGA INC. RENAMED-S204"
STATE_FILE = Path(__file__).resolve().parent.parent / ".scratch" / "s204_f3_state.json"

SCRIPT = rf'''
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

original = "{ORIGINAL}"
renamed = "{RENAMED}"

# Is original present?
orig_exists = frappe.db.exists("Customer", original)
renamed_exists = frappe.db.exists("Customer", renamed)
print(f"pre-state: original_exists={{bool(orig_exists)}}  renamed_exists={{bool(renamed_exists)}}")

if renamed_exists:
    print(f"NO_OP: customer already renamed to {{renamed}} — F3 state already set")
    frappe.destroy()
    raise SystemExit(0)

if not orig_exists:
    print(f"ERROR: Customer {{original}} does not exist; cannot rename")
    frappe.destroy()
    raise SystemExit(1)

# Snapshot current Customer fields so restore can verify integrity
cust_doc = frappe.db.sql(
    "SELECT name, customer_name, represents_company, tax_id FROM `tabCustomer` WHERE name = %s",
    (original,), as_dict=True,
)
print(f"snapshot: {{json.dumps(cust_doc[0]) if cust_doc else 'None'}}")

# Rename; merge=False keeps the row as-is (no data loss).
# We're running as Administrator (frappe.set_user above), so permissions
# are not a constraint. force=True bypasses the "no write perm on new docname" check.
try:
    new_name = frappe.rename_doc("Customer", original, renamed, merge=False, force=True)
    frappe.db.commit()
    print(f"RENAMED: {{original}} -> {{new_name}}")
except Exception as e:
    import traceback
    print(f"RENAME FAILED: {{type(e).__name__}}: {{e}}")
    traceback.print_exc()
    frappe.destroy()
    raise SystemExit(2)

# Verify the rename landed
after = frappe.db.sql(
    "SELECT name, customer_name FROM `tabCustomer` WHERE name = %s",
    (renamed,), as_dict=True,
)
print(f"post-rename lookup: {{after}}")
if not after:
    print("POST-RENAME VERIFICATION FAILED — row missing")
    frappe.destroy()
    raise SystemExit(3)

# Confirm original is gone
leftover = frappe.db.exists("Customer", original)
print(f"post-rename: original {{original!r}} exists={{bool(leftover)}}")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_f3_rename.py",
    "docker cp /tmp/s204_f3_rename.py $BACKEND:/tmp/s204_f3_rename.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_f3_rename.py",
]

import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(
    InstanceIds=["i-026b7477d27bd46d6"],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["180"]},
)
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(60):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print("STATUS:", inv["Status"])
        stdout = inv["StandardOutputContent"]
        print(stdout[-3000:])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-1000:])
        if inv["Status"] == "Success":
            # Save state file only if the rename succeeded
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(
                json.dumps({"original": ORIGINAL, "renamed": RENAMED, "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}),
                encoding="utf-8",
            )
            print(f"STATE_FILE: {STATE_FILE}")
        sys.exit(0 if inv["Status"] == "Success" else 1)
