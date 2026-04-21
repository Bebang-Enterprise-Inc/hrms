#!/usr/bin/env python3
"""S213 R1 cleanup — discover all S213 dispatch SEs from ledger MRs and cancel via MR resuscitate."""
import base64, json, pathlib, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER = REPO_ROOT / "output/l3/s213/sweep_ledger.json"

entries = json.loads(LEDGER.read_text(encoding="utf-8"))
mr_names = sorted({e["payload"]["name"] for e in entries if e.get("kind") == "mr-create"})
print(f"MRs in ledger: {len(mr_names)}")

SCRIPT = f'''
import frappe, traceback
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

MR_NAMES = {json.dumps(mr_names)}
results = []

for mr_name in MR_NAMES:
    # Find SEs linked to this MR (only submitted ones docstatus=1)
    ses = frappe.db.sql(
        """SELECT DISTINCT se.name, se.docstatus
           FROM `tabStock Entry` se
           JOIN `tabStock Entry Detail` sei ON sei.parent = se.name
           WHERE sei.material_request = %s AND se.docstatus = 1""",
        (mr_name,), as_dict=True,
    )
    if not ses:
        continue
    mr_status = frappe.db.get_value("Material Request", mr_name, "docstatus")
    for se in ses:
        se_name = se["name"]
        try:
            # Resuscitate MR if cancelled
            if mr_status == 2:
                frappe.db.set_value("Material Request", mr_name, "docstatus", 1)
                frappe.db.set_value("Material Request", mr_name, "status", "Ordered")
                frappe.db.commit()
            doc = frappe.get_doc("Stock Entry", se_name)
            doc.cancel()
            frappe.db.commit()
            results.append(("SE", se_name, "cancelled"))
        except Exception as e:
            results.append(("SE", se_name, f"error:{{str(e)[:200]}}"))
            frappe.db.rollback()
        # Re-cancel MR
        try:
            mr = frappe.get_doc("Material Request", mr_name)
            if mr.docstatus == 1:
                mr.cancel()
                frappe.db.commit()
                results.append(("MR", mr_name, "re-cancelled"))
        except Exception as e:
            results.append(("MR", mr_name, f"mr-cancel-err:{{str(e)[:150]}}"))
            frappe.db.rollback()

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
        f"echo '{enc}' | base64 -d > /tmp/s213_cl.py",
        "docker cp /tmp/s213_cl.py $BACKEND:/tmp/s213_cl.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s213_cl.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["300"]})
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    deadline = time.time() + 330
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
