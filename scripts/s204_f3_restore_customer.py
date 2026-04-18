"""S204 F3 restore: rename BEBANG MEGA INC. RENAMED-S204 back to BEBANG MEGA INC.

MUST ALWAYS run after F3 completes (pass OR fail). If left in renamed
state, every SM Tanza + Ayala Evo dispatch will billing-hold forever.

Idempotent: no-op if the renamed docname does not exist.

Reads state from .scratch/s204_f3_state.json when available; falls back
to hard-coded ORIGINAL/RENAMED so the script is still safe to run if the
state file is missing or corrupted.
"""
from __future__ import annotations
import base64
import json
import sys
import time
from pathlib import Path

DEFAULT_ORIGINAL = "BEBANG MEGA INC."
DEFAULT_RENAMED = "BEBANG MEGA INC. RENAMED-S204"
STATE_FILE = Path(__file__).resolve().parent.parent / ".scratch" / "s204_f3_state.json"


def _load_state() -> tuple[str, str]:
    if STATE_FILE.exists():
        try:
            obj = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            orig = obj.get("original") or DEFAULT_ORIGINAL
            renamed = obj.get("renamed") or DEFAULT_RENAMED
            return orig, renamed
        except Exception as e:
            print(f"state read WARN: {e}; using defaults")
    return DEFAULT_ORIGINAL, DEFAULT_RENAMED


ORIGINAL, RENAMED = _load_state()

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

orig_exists = frappe.db.exists("Customer", original)
renamed_exists = frappe.db.exists("Customer", renamed)
print(f"pre-state: original_exists={{bool(orig_exists)}}  renamed_exists={{bool(renamed_exists)}}")

if orig_exists and not renamed_exists:
    print(f"NO_OP: customer {{original!r}} already present; nothing to restore")
    frappe.destroy()
    raise SystemExit(0)

if not renamed_exists:
    print(f"ERROR: renamed customer {{renamed!r}} not present and original also missing")
    frappe.destroy()
    raise SystemExit(1)

if orig_exists and renamed_exists:
    print(f"CONFLICT: BOTH {{original!r}} and {{renamed!r}} exist; manual intervention required")
    frappe.destroy()
    raise SystemExit(2)

# Rename renamed → original. Running as Administrator (frappe.set_user above).
try:
    new_name = frappe.rename_doc("Customer", renamed, original, merge=False, force=True)
    frappe.db.commit()
    print(f"RESTORED: {{renamed}} -> {{new_name}}")
except Exception as e:
    import traceback
    print(f"RESTORE FAILED: {{type(e).__name__}}: {{e}}")
    traceback.print_exc()
    frappe.destroy()
    raise SystemExit(3)

# Verify
after = frappe.db.sql(
    "SELECT name, customer_name FROM `tabCustomer` WHERE name = %s",
    (original,), as_dict=True,
)
print(f"post-restore lookup: {{after}}")
leftover = frappe.db.exists("Customer", renamed)
print(f"post-restore: renamed {{renamed!r}} exists={{bool(leftover)}}")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_f3_restore.py",
    "docker cp /tmp/s204_f3_restore.py $BACKEND:/tmp/s204_f3_restore.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_f3_restore.py",
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
        print(inv["StandardOutputContent"][-3000:])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-1000:])
        if inv["Status"] == "Success":
            # Remove state file so the next F3 run starts clean
            try:
                STATE_FILE.unlink(missing_ok=True)
                print(f"STATE_FILE cleared: {STATE_FILE}")
            except Exception as e:
                print(f"state cleanup WARN: {e}")
        sys.exit(0 if inv["Status"] == "Success" else 1)
