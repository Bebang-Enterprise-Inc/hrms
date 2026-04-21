#!/usr/bin/env python3
"""Reproduce S203 Draft SI Error on SE MAT-STE-2026-00621 to get full traceback."""
import base64, gzip, pathlib, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "l3" / "s212" / "s203_traceback.txt"

SCRIPT = '''
import base64, gzip, traceback
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from hrms.api.commissary import build_bki_store_sale_invoice

result = None
tb = ""
try:
    frappe.db.savepoint("repro")
    result = build_bki_store_sale_invoice(stock_entry="MAT-STE-2026-00621", store_order_name="BEI-ORD-2026-00399")
    frappe.db.sql("ROLLBACK TO SAVEPOINT repro")  # don't leave a real SI behind
except Exception:
    tb = traceback.format_exc()
    try:
        frappe.db.sql("ROLLBACK TO SAVEPOINT repro")
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

def run(timeout=60):
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_repro.py",
        "docker cp /tmp/s212_repro.py $BACKEND:/tmp/s212_repro.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_repro.py",
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
print([l for l in out.splitlines() if "__LEN__" in l])
s = out.find("__B64_START__")
e = out.find("__B64_END__")
if s < 0 or e < 0:
    print(out)
    sys.exit(1)
b64 = out[s+len("__B64_START__"):e].strip()
txt = gzip.decompress(base64.b64decode(b64)).decode()
OUT.write_text(txt, encoding="utf-8")
print(f"Wrote {OUT}")
print()
print(txt)
