#!/usr/bin/env python3
"""S217 cleanup — cancel all SEs + re-cancel MRs for S217 ledger."""
import base64, json, pathlib, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER = REPO_ROOT / "output/l3/s217/sweep_ledger.json"
entries = json.loads(LEDGER.read_text(encoding="utf-8"))
mr_names = sorted({e["payload"]["name"] for e in entries if e.get("kind") == "mr-create"})
order_names = sorted({e["payload"]["name"] for e in entries if e.get("kind") == "order-create"})
print(f"MRs: {len(mr_names)}, Orders: {len(order_names)}")

SCRIPT = f'''
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

MR_NAMES = {json.dumps(mr_names)}
ORDER_NAMES = {json.dumps(order_names)}

ok_se, ok_mr, ok_order = 0, 0, 0
errors = []
for mr_name in MR_NAMES:
    ses = frappe.db.sql(
        """SELECT DISTINCT se.name FROM `tabStock Entry` se
           JOIN `tabStock Entry Detail` sei ON sei.parent=se.name
           WHERE sei.material_request=%s AND se.docstatus=1""",
        (mr_name,), as_dict=True,
    )
    if not ses:
        continue
    mr_status = frappe.db.get_value("Material Request", mr_name, "docstatus")
    for se in ses:
        try:
            if mr_status == 2:
                frappe.db.set_value("Material Request", mr_name, "docstatus", 1)
                frappe.db.set_value("Material Request", mr_name, "status", "Ordered")
                frappe.db.commit()
            doc = frappe.get_doc("Stock Entry", se["name"])
            doc.cancel(); frappe.db.commit()
            ok_se += 1
        except Exception as e:
            errors.append(("SE", se["name"], repr(e)[:120]))
            frappe.db.rollback()
    try:
        mr = frappe.get_doc("Material Request", mr_name)
        if mr.docstatus == 1: mr.cancel(); frappe.db.commit(); ok_mr += 1
    except Exception as e:
        errors.append(("MR", mr_name, repr(e)[:120]))
        frappe.db.rollback()

for o in ORDER_NAMES:
    try:
        d = frappe.get_doc("BEI Store Order", o)
        if d.docstatus == 1: d.cancel(); frappe.db.commit(); ok_order += 1
        elif d.docstatus == 0: frappe.delete_doc("BEI Store Order", o, force=1); frappe.db.commit(); ok_order += 1
    except frappe.DoesNotExistError:
        pass
    except Exception as e:
        errors.append(("Order", o, repr(e)[:120]))
        frappe.db.rollback()

print(f"RESULT: ok_se={{ok_se}} ok_mr={{ok_mr}} ok_order={{ok_order}} errors={{len(errors)}}")
for e in errors[:10]:
    print(" | ".join(str(x) for x in e))
frappe.destroy()
'''


def main():
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s217_cl.py",
        "docker cp /tmp/s217_cl.py $BACKEND:/tmp/s217_cl.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s217_cl.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["600"]})
    cid = r["Command"]["CommandId"]; print(f"CommandId: {cid}")
    deadline = time.time() + 630
    while time.time() < deadline:
        time.sleep(5)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            print(inv.get("StandardOutputContent", "")[-3000:])
            return 0 if inv["Status"] == "Success" else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
