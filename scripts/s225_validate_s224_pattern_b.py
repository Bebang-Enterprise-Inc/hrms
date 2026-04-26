"""S225 Phase 1 task 2 — REST probe validating S224 Pattern B (idempotent approve).

Audit B-6 fix: validation order in approve_material_request is:
  1. Missing required parameters check (line 1230) — must pass non-empty approved_items
  2. Material Request exists check (line 1235)
  3. FOR UPDATE status check (line 1247)
  4. Idempotency branch (line 1250)

So the probe MUST construct approved_items from the MR's actual items so it passes
step 1 and reaches step 4.

Pre-S224: this would throw "...already been approved" with HTTP 417.
Post-S224: this should return {"success": True, "already_approved": True}.

Run from worktree:
    python scripts/s225_validate_s224_pattern_b.py

Output:
    output/s225/verification/s224_pattern_b_validation.json
"""
from __future__ import annotations
import base64
import json
import pathlib
import sys
import time

OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "s225" / "verification" / "s224_pattern_b_validation.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"

INNER_SCRIPT = r'''
import os
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files",
]:
    os.makedirs(d, exist_ok=True)

import json, sys, traceback
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")  # enough for read; we'll set to scm role for the call

result = {"step": "init"}

try:
    # Find an existing Ordered MR (Material Transfer or Material Issue, docstatus=1)
    mr_name = frappe.db.get_value(
        "Material Request",
        {"status": "Ordered", "docstatus": 1, "material_request_type": ["in", ["Material Transfer", "Material Issue"]]},
        "name",
        order_by="creation desc",
    )
    result["step"] = "found_mr"
    result["mr_name"] = mr_name

    if not mr_name:
        result["status"] = "SKIPPED"
        result["reason"] = "No existing Ordered MR found in production. Phase 1 sweep will exercise the path instead."
        print(json.dumps(result))
        sys.exit(0)

    # B-6 FIX: build approved_items from MR's items so probe passes the line 1230 validation
    items = frappe.get_all(
        "Material Request Item",
        filters={"parent": mr_name},
        fields=["item_code", "qty"],
    )
    approved_items = json.dumps([{"item_code": it["item_code"], "approved_qty": it["qty"]} for it in items])
    result["approved_items_count"] = len(items)
    result["approved_items_sample"] = items[:2]
    result["step"] = "built_approved_items"

    # Switch to a user with SCM approval role for the call
    scm_user = "test.scm@bebang.ph"
    if frappe.db.exists("User", scm_user):
        frappe.set_user(scm_user)
        result["called_as"] = scm_user
    else:
        result["called_as"] = "Administrator"
        result["scm_user_missing"] = True

    # Call the function
    from hrms.api.warehouse import approve_material_request
    try:
        resp = approve_material_request(mr_name=mr_name, approved_items=approved_items)
        result["call_succeeded"] = True
        result["response"] = resp
        result["already_approved"] = bool(resp.get("already_approved")) if isinstance(resp, dict) else False
        result["status"] = "PASS" if result["already_approved"] else "FAIL_NO_IDEMPOTENCY"
    except Exception as e:
        result["call_succeeded"] = False
        result["error_class"] = type(e).__name__
        result["error_message"] = str(e)[:600]
        # Pre-S224 behavior threw "Already been approved"
        if "already" in str(e).lower() and "approved" in str(e).lower():
            result["status"] = "FAIL_THROWS_PRE_S224_ERROR"
        else:
            result["status"] = "FAIL_OTHER_EXCEPTION"

    # CRITICAL: rollback any side-effects (the Comment doctype write at line 1262 if reached)
    frappe.db.rollback()

except Exception as e:
    result["fatal_error"] = str(e)[:600]
    result["traceback"] = traceback.format_exc()[:1500]
    result["status"] = "FATAL"

print(json.dumps(result))
'''


def main() -> int:
    import boto3
    enc = base64.b64encode(INNER_SCRIPT.encode()).decode()

    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s225_pattern_b_probe.py",
        "docker cp /tmp/s225_pattern_b_probe.py $BACKEND:/tmp/s225_pattern_b_probe.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s225_pattern_b_probe.py",
    ]

    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["120"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}", flush=True)

    inv = None
    for _ in range(40):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break

    if inv is None:
        print("SSM call did not complete", flush=True)
        return 2

    stdout = inv.get("StandardOutputContent", "")
    stderr = inv.get("StandardErrorContent", "")
    print("--- STDOUT ---")
    print(stdout)
    if stderr.strip():
        print("--- STDERR ---")
        print(stderr)

    # Parse the inner JSON line (last non-blank line)
    inner_result = None
    for line in stdout.splitlines()[::-1]:
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                inner_result = json.loads(line)
                break
            except json.JSONDecodeError:
                continue

    evidence = {
        "checked_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ssm_command_id": cid,
        "ssm_status": inv["Status"],
        "instance_id": INSTANCE_ID,
        "inner_result": inner_result,
        "status": (inner_result or {}).get("status", "UNKNOWN"),
        "already_approved": bool((inner_result or {}).get("already_approved", False)),
        "raw_stdout": stdout[-5000:],
        "raw_stderr": stderr[-2000:],
    }
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}", flush=True)

    if evidence["status"] == "PASS":
        print("\nPASS: Pattern B idempotency confirmed in deployed container", flush=True)
        return 0
    if evidence["status"] == "SKIPPED":
        print("\nSKIPPED: no Ordered MR found in production. Pattern B will be exercised by Phase 1 sweep.", flush=True)
        return 0  # Skipped is OK per plan — sweep covers it
    print(f"\nFAIL: status={evidence['status']}", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
