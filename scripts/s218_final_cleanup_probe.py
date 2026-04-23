#!/usr/bin/env python3
"""S218 final cleanup probe — find and cancel any lingering S218-window SEs + reset MRs."""
import base64, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"

# S218 sweep ran 2026-04-22 10:00 UTC → 11:00 UTC roughly
SCRIPT = '''
import frappe, traceback
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Find any submitted SEs from S218 window linked to S218 MRs
ses = frappe.db.sql("""
    SELECT DISTINCT se.name, se.docstatus
    FROM `tabStock Entry` se
    JOIN `tabStock Entry Detail` sei ON sei.parent = se.name
    JOIN `tabMaterial Request` mr ON mr.name = sei.material_request
    WHERE se.creation >= '2026-04-22 09:30:00'
      AND se.docstatus = 1
""", as_dict=True)
print(f"Dangling S218 SEs (docstatus=1): {len(ses)}")
for se in ses:
    # Get linked MR, resuscitate if cancelled, cancel SE, re-cancel
    mr_names = frappe.db.sql(
        "SELECT DISTINCT material_request FROM `tabStock Entry Detail` WHERE parent=%s",
        (se["name"],), as_dict=True)
    for m in mr_names:
        mr_name = m["material_request"]
        if not mr_name: continue
        try:
            mr_status = frappe.db.get_value("Material Request", mr_name, "docstatus")
            if mr_status == 2:
                frappe.db.set_value("Material Request", mr_name, "docstatus", 1)
                frappe.db.set_value("Material Request", mr_name, "status", "Ordered")
                frappe.db.commit()
            doc = frappe.get_doc("Stock Entry", se["name"])
            doc.cancel(); frappe.db.commit()
            mr = frappe.get_doc("Material Request", mr_name)
            if mr.docstatus == 1: mr.cancel(); frappe.db.commit()
            print(f"SE {se['name']} cancelled (via MR {mr_name})")
        except Exception as e:
            print(f"SE {se['name']} err: {repr(e)[:100]}")
            frappe.db.rollback()
        break
frappe.destroy()
'''


def main():
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s218_final.py",
        "docker cp /tmp/s218_final.py $BACKEND:/tmp/s218_final.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s218_final.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["600"]})
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    deadline = time.time() + 630
    while time.time() < deadline:
        time.sleep(5)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            print(inv.get("StandardOutputContent", "")[-3000:])
            return 0 if inv["Status"] == "Success" else 1
    return 2


sys.exit(main())
