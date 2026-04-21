#!/usr/bin/env python3
"""Reproduce hrms.api.warehouse.create_stock_transfer on each stuck MR
to capture exact ValidationError text."""
import base64, gzip, pathlib, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "l3" / "s212" / "real_dispatch_traceback.txt"

SCRIPT = '''
import base64, gzip, traceback
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from hrms.api.warehouse import create_stock_transfer

reports = []
for mr_name in ("MAT-MR-2026-00258", "MAT-MR-2026-00260", "MAT-MR-2026-00262"):
    mr = frappe.get_doc("Material Request", mr_name)
    items = [{"item_code": i.item_code, "qty": float(i.qty), "uom": i.uom or "Nos",
              "mr_item_name": i.name} for i in mr.items]
    # Resolve target warehouse from custom_store_order or set_warehouse
    target_wh = frappe.db.get_value("BEI Store Order", mr.custom_store_order, "store") if mr.custom_store_order else None
    tb = ""
    result = None
    try:
        frappe.db.savepoint(f"repro_{mr_name[-5:]}")
        result = create_stock_transfer(
            target_warehouse=target_wh,
            items=items,
            mr_name=mr_name,
            source_warehouse=mr.set_warehouse,
            remarks=f"S212 retry",
        )
        frappe.db.sql(f"ROLLBACK TO SAVEPOINT repro_{mr_name[-5:]}")
    except Exception:
        tb = traceback.format_exc()
        try:
            frappe.db.sql(f"ROLLBACK TO SAVEPOINT repro_{mr_name[-5:]}")
        except Exception:
            pass
    reports.append({
        "mr": mr_name,
        "set_warehouse": mr.set_warehouse,
        "target_warehouse": target_wh,
        "items_count": len(items),
        "result": repr(result),
        "tb_head": tb[:8000] if tb else "",
    })

txt = "\\n".join(f"=== {r['mr']} ===\\nset_wh={r['set_warehouse']}\\ntarget={r['target_warehouse']}\\nitems={r['items_count']}\\nresult={r['result']}\\ntb_head:\\n{r['tb_head']}" for r in reports)
print("__LEN__", len(txt))
compressed = gzip.compress(txt.encode())
print("__B64_START__")
print(base64.b64encode(compressed).decode())
print("__B64_END__")
frappe.destroy()
'''

def run(timeout=180):
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_rd.py",
        "docker cp /tmp/s212_rd.py $BACKEND:/tmp/s212_rd.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_rd.py",
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
s = out.find("__B64_START__"); e = out.find("__B64_END__")
if s < 0 or e < 0:
    print(out[:3000]); sys.exit(1)
b64 = out[s+len("__B64_START__"):e].strip()
txt = gzip.decompress(base64.b64decode(b64)).decode()
OUT.write_text(txt, encoding="utf-8")
print(f"Wrote {OUT}")
print()
print(txt)
