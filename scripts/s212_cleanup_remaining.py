#!/usr/bin/env python3
"""S212 R1 cleanup — cancel 4 dispatch SEs + retry SI/MR cancel."""
import base64, json, pathlib, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"

# Known R1 dispatch SEs (from cleanup_sweep failure messages)
SES_TO_CANCEL = [
    "MAT-STE-2026-00619",
    "MAT-STE-2026-00621",
    "MAT-STE-2026-00623",
    "MAT-STE-2026-00625",
]
# Re-run targets after SEs cancel
REMAINING = [
    ("Sales Invoice", "ACC-SINV-2026-00094"),
    ("Sales Invoice", "ACC-SINV-2026-00093"),
    ("Sales Invoice", "ACC-SINV-2026-00092"),
    ("Material Request", "MAT-MR-2026-00261"),
    ("Material Request", "MAT-MR-2026-00259"),
    ("Material Request", "MAT-MR-2026-00257"),
    ("Material Request", "MAT-MR-2026-00256"),
]

SCRIPT = f'''
import frappe, traceback
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

results = []

# 1. Cancel dispatch SEs (reverses stock ledger)
for se_name in {json.dumps(SES_TO_CANCEL)}:
    try:
        doc = frappe.get_doc("Stock Entry", se_name)
        if doc.docstatus == 1:
            doc.cancel()
            frappe.db.commit()
            results.append(("Stock Entry", se_name, "cancelled"))
        elif doc.docstatus == 2:
            results.append(("Stock Entry", se_name, "already_cancelled"))
        else:
            frappe.delete_doc("Stock Entry", se_name, force=1)
            frappe.db.commit()
            results.append(("Stock Entry", se_name, "deleted_draft"))
    except frappe.DoesNotExistError:
        results.append(("Stock Entry", se_name, "not_found"))
    except Exception as e:
        results.append(("Stock Entry", se_name, f"error:{{e!r}}"))
        frappe.db.rollback()

# 2. Now SIs and MRs should cancel
for dt, name in {json.dumps(REMAINING)}:
    try:
        doc = frappe.get_doc(dt, name)
        if doc.docstatus == 1:
            doc.cancel()
            frappe.db.commit()
            results.append((dt, name, "cancelled"))
        elif doc.docstatus == 2:
            results.append((dt, name, "already_cancelled"))
        else:
            frappe.delete_doc(dt, name, force=1)
            frappe.db.commit()
            results.append((dt, name, "deleted_draft"))
    except frappe.DoesNotExistError:
        results.append((dt, name, "not_found"))
    except Exception as e:
        results.append((dt, name, f"error:{{e!r}}"))
        frappe.db.rollback()

# 3. Also cleanup remaining orders
for order_name in ("BEI-ORD-2026-00402", "BEI-ORD-2026-00401", "BEI-ORD-2026-00400",
                   "BEI-ORD-2026-00399", "BEI-ORD-2026-00398"):
    try:
        doc = frappe.get_doc("BEI Store Order", order_name)
        if doc.docstatus == 1:
            doc.cancel()
            frappe.db.commit()
            results.append(("BEI Store Order", order_name, "cancelled"))
        elif doc.docstatus == 2:
            results.append(("BEI Store Order", order_name, "already_cancelled"))
        else:
            frappe.delete_doc("BEI Store Order", order_name, force=1)
            frappe.db.commit()
            results.append(("BEI Store Order", order_name, "deleted_draft"))
    except frappe.DoesNotExistError:
        results.append(("BEI Store Order", order_name, "not_found"))
    except Exception as e:
        results.append(("BEI Store Order", order_name, f"error:{{str(e)[:200]}}"))
        frappe.db.rollback()

print("=== RESULTS ===")
for r in results:
    print(" | ".join(str(x) for x in r))
frappe.destroy()
'''


def main() -> int:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_cl.py",
        "docker cp /tmp/s212_cl.py $BACKEND:/tmp/s212_cl.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_cl.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["180"]})
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    deadline = time.time() + 210
    while time.time() < deadline:
        time.sleep(4)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            print(inv.get("StandardOutputContent", ""))
            if inv.get("StandardErrorContent"):
                sys.stderr.write(inv.get("StandardErrorContent", ""))
            return 0 if inv["Status"] == "Success" else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
