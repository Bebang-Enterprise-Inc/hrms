"""S225 Phase 5 follow-up — cancel the SEs created by the stress test.

The threaded stress test created 10 SEs (MAT-STE-2026-01039..01048) but
inline cleanup hit a transaction-isolation issue (each thread committed in
its own connection; main thread's connection didn't see the new docs). This
script cancels them in a single fresh connection.
"""
from __future__ import annotations
import base64, json, sys, time
INSTANCE_ID = "i-026b7477d27bd46d6"

INNER = r'''
import os, json
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Find all SEs created in the past hour with the stress-test remark
ses = frappe.db.sql("""
    SELECT name, docstatus
    FROM `tabStock Entry`
    WHERE remarks LIKE '%S225 Phase 5 stress%'
      AND creation > DATE_SUB(NOW(), INTERVAL 2 HOUR)
    ORDER BY name
""", as_dict=True)

cancelled = []
errors = []
for r in ses:
    try:
        if r["docstatus"] != 1:
            cancelled.append({"se": r["name"], "action": "skipped", "docstatus": r["docstatus"]})
            continue
        doc = frappe.get_doc("Stock Entry", r["name"])
        doc.flags.ignore_permissions = True
        doc.cancel()
        cancelled.append({"se": r["name"], "action": "cancelled"})
    except Exception as e:
        errors.append({"se": r["name"], "error": str(e)[:300]})

frappe.db.commit()
print(json.dumps({
    "found_ses": len(ses),
    "cancelled": cancelled,
    "errors": errors,
}, default=str))
'''


def main() -> int:
    import boto3
    enc = base64.b64encode(INNER.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s225_p5_cleanup.py",
        "docker cp /tmp/s225_p5_cleanup.py $BACKEND:/tmp/s225_p5_cleanup.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s225_p5_cleanup.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds, "executionTimeout": ["180"]})
    cid = r["Command"]["CommandId"]
    inv = None
    for _ in range(60):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break
    out = inv.get("StandardOutputContent", "")
    print(out)
    return 0 if inv["Status"] == "Success" else 1


if __name__ == "__main__":
    sys.exit(main())
