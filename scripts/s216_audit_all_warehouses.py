#!/usr/bin/env python3
"""S216 Phase 1 — audit NULL-batch stock at ALL warehouses (not just BKI).

Hypothesis: DEFECT-8 (3 stuck MRs still failing dispatch) might be caused
by NULL batches at warehouses my S213 audit missed. That audit scoped to
company='Bebang Kitchen Inc.', but some BKI-related warehouses might have
a different company field (store warehouses with BKI as source).

Emits output/l3/s216/batch_audit_all.json
"""
from __future__ import annotations
import base64, gzip, json, pathlib, sys, time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "output" / "l3" / "s216"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "batch_audit_all.json"

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"

SCRIPT = '''
import json, base64, gzip
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

tuples = frappe.db.sql(
    """SELECT sle.item_code, sle.warehouse, SUM(sle.actual_qty) AS null_qty
       FROM `tabStock Ledger Entry` sle
       JOIN `tabItem` i ON i.item_code = sle.item_code
       WHERE i.has_batch_no = 1
         AND sle.batch_no IS NULL
         AND sle.docstatus = 1
       GROUP BY sle.item_code, sle.warehouse
       HAVING null_qty > 0
       ORDER BY null_qty DESC""",
    as_dict=True,
)

wh_info = {}
if tuples:
    whs = list({t["warehouse"] for t in tuples})
    for chunk_start in range(0, len(whs), 20):
        batch = whs[chunk_start:chunk_start+20]
        phs = ",".join(["%s"] * len(batch))
        rows = frappe.db.sql(
            f"""SELECT name, company, warehouse_name FROM `tabWarehouse` WHERE name IN ({phs})""",
            tuple(batch), as_dict=True,
        )
        for r in rows:
            wh_info[r["name"]] = r

enriched = [{
    "item_code": t["item_code"],
    "warehouse": t["warehouse"],
    "null_qty": float(t["null_qty"]),
    "warehouse_company": (wh_info.get(t["warehouse"]) or {}).get("company"),
} for t in tuples]

payload = {
    "total_tuples": len(enriched),
    "total_qty": sum(x["null_qty"] for x in enriched),
    "tuples": enriched,
}
compressed = gzip.compress(json.dumps(payload, default=str).encode())
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
        f"echo '{enc}' | base64 -d > /tmp/s216_all.py",
        "docker cp /tmp/s216_all.py $BACKEND:/tmp/s216_all.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s216_all.py",
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
            if inv["Status"] != "Success":
                sys.stderr.write(inv.get("StandardErrorContent", ""))
            return out
    raise TimeoutError()

out = run()
s = out.find("__B64_START__"); e = out.find("__B64_END__")
b64 = out[s+len("__B64_START__"):e].strip()
data = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
print(f"Wrote {OUT}")
print(f"Total tuples: {data['total_tuples']}")
print(f"Total qty: {data['total_qty']}")
print()
print("By warehouse (top 15):")
from collections import Counter
whs_c = Counter()
whs_q = {}
for t in data["tuples"]:
    whs_c[t["warehouse"]] += 1
    whs_q[t["warehouse"]] = whs_q.get(t["warehouse"], 0) + t["null_qty"]
for wh, ct in whs_c.most_common(15):
    print(f"  {ct:3d} items | qty={whs_q[wh]:10.0f} | {wh}")
