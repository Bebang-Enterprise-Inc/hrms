#!/usr/bin/env python3
"""S212 R1 cleanup — resuscitate MR briefly to cancel dispatch SE properly."""
import base64, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"

SCRIPT = '''
import frappe, traceback
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

SE_MR_PAIRS = [
    ("MAT-STE-2026-00619", "MAT-MR-2026-00256"),
    ("MAT-STE-2026-00621", "MAT-MR-2026-00257"),
    ("MAT-STE-2026-00623", "MAT-MR-2026-00259"),
    ("MAT-STE-2026-00625", "MAT-MR-2026-00261"),
]

for se_name, mr_name in SE_MR_PAIRS:
    try:
        # Check SE status
        se_status = frappe.db.get_value("Stock Entry", se_name, "docstatus")
        print(f"[before] SE={se_name} docstatus={se_status}")
        if se_status != 1:
            continue
        # Temporarily un-cancel MR (set docstatus back to 1) so SE can cancel
        frappe.db.set_value("Material Request", mr_name, "docstatus", 1)
        frappe.db.set_value("Material Request", mr_name, "status", "Ordered")
        frappe.db.commit()
        # Cancel SE
        doc = frappe.get_doc("Stock Entry", se_name)
        doc.cancel()
        frappe.db.commit()
        print(f"[cancelled] SE={se_name}")
        # Re-cancel MR
        mr = frappe.get_doc("Material Request", mr_name)
        mr.cancel()
        frappe.db.commit()
        print(f"[re-cancelled] MR={mr_name}")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[error] {se_name}: {e!r}")
        print(tb[-500:])
        frappe.db.rollback()

# Verify final state
for se_name, mr_name in SE_MR_PAIRS:
    se_s = frappe.db.get_value("Stock Entry", se_name, "docstatus")
    mr_s = frappe.db.get_value("Material Request", mr_name, "docstatus")
    print(f"[final] SE={se_name} docstatus={se_s} | MR={mr_name} docstatus={mr_s}")

frappe.destroy()
'''


def main() -> int:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_cl2.py",
        "docker cp /tmp/s212_cl2.py $BACKEND:/tmp/s212_cl2.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_cl2.py",
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
