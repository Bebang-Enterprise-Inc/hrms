#!/usr/bin/env python3
"""Attempt fulfill_store_order on MAT-MR-2026-00258 (stuck at dispatch) to get exact error."""
import base64, gzip, pathlib, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "l3" / "s212" / "dispatch_traceback.txt"

SCRIPT = '''
import base64, gzip, traceback, json
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

mr_name = "MAT-MR-2026-00258"
# Pull MR's items to synthesize the fulfillment payload
mr = frappe.get_doc("Material Request", mr_name)
items = [{"item_code": i.item_code, "qty": float(i.qty), "material_request_item": i.name} for i in mr.items]
print("MR items:", json.dumps(items))
print("set_warehouse:", mr.set_warehouse)
print("material_request_type:", mr.material_request_type)

from hrms.api.commissary import fulfill_store_order

result = None
tb = ""
try:
    frappe.db.savepoint("repro_dispatch")
    result = fulfill_store_order(mr_name=mr_name, items=items)
    frappe.db.sql("ROLLBACK TO SAVEPOINT repro_dispatch")
except Exception:
    tb = traceback.format_exc()
    try:
        frappe.db.sql("ROLLBACK TO SAVEPOINT repro_dispatch")
    except Exception:
        pass

txt = f"result: {result!r}\\n\\nTraceback:\\n{tb}"
print("__LEN__", len(txt))
compressed = gzip.compress(txt.encode())
print("__B64_START__")
print(base64.b64encode(compressed).decode())
print("__B64_END__")
frappe.destroy()
'''

def run(timeout=120):
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_dispatch.py",
        "docker cp /tmp/s212_dispatch.py $BACKEND:/tmp/s212_dispatch.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_dispatch.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": [str(timeout)]})
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    deadline = time.time() + timeout + 30
    while time.time() < deadline:
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            out = inv.get("StandardOutputContent", "")
            err = inv.get("StandardErrorContent", "")
            if inv["Status"] != "Success":
                sys.stderr.write(err)
            return out
    raise TimeoutError()

out = run()
print(out[:2000])
s = out.find("__B64_START__"); e = out.find("__B64_END__")
if s < 0 or e < 0:
    print("No marker found")
    sys.exit(1)
b64 = out[s+len("__B64_START__"):e].strip()
txt = gzip.decompress(base64.b64decode(b64)).decode()
OUT.write_text(txt, encoding="utf-8")
print(f"\n=== Wrote {OUT} ===")
print(txt)
