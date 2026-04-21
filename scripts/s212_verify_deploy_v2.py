#!/usr/bin/env python3
"""Verify PR #664 (DEFECT-5 Company Owned markup) is live on hq.bebang.ph."""
import base64, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"

CHECK = r'''
try:
    import hrms.api.commissary as c
    src = open(c.__file__).read()
    print("defect_5_company_owned_key:", '"Company Owned":' in src)
    print("defect_5_settings_field:", "bki_markup_company_owned_percent" in src)
    # All 4 S212 fixes should still be present:
    import hrms.api.store as s
    store_src = open(s.__file__).read()
    print("defect_1_commit_call:", src.count("frappe.db.commit()") >= 1)
    idx = store_src.find("mr.submit()")
    print("defect_1_post_submit_commit:", "frappe.db.commit()" in store_src[idx:idx+800])
    print("defect_1_mr_exists_verify:", 'frappe.db.exists("Material Request"' in store_src)
    import hrms.api.warehouse as w
    wh_src = open(w.__file__).read()
    print("defect_2_helper:", "def _reconcile_si_qty_from_wr" in wh_src)
except Exception as e:
    print("ERR:", e)
'''


def main() -> int:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(CHECK.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_v2.py",
        "docker cp /tmp/s212_v2.py $BACKEND:/tmp/s212_v2.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python -c 'import sys; sys.path.insert(0, \"/home/frappe/frappe-bench/apps/hrms\"); exec(open(\"/tmp/s212_v2.py\").read())'",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["60"]})
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    deadline = time.time() + 90
    while time.time() < deadline:
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            print(inv.get("StandardOutputContent", ""))
            return 0 if inv["Status"] == "Success" else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
