#!/usr/bin/env python3
"""Is FG004 (batch-tracked) actually stocked at PINNACLE / 3MD?"""
import base64, gzip, json, pathlib, sys, time
AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "l3" / "s212" / "fg004_batch_probe.json"

SCRIPT = '''
import base64, gzip, json
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# FG004 item meta
item_flags = frappe.db.sql("SELECT item_code, has_batch_no, has_serial_no FROM `tabItem` WHERE item_code='FG004'", as_dict=True)

# Batches existing for FG004
batches = frappe.db.sql(
    "SELECT name, batch_qty FROM `tabBatch` WHERE item='FG004' ORDER BY creation DESC LIMIT 20",
    as_dict=True,
)

# Bin qty at specific warehouses
bins = frappe.db.sql(
    """SELECT warehouse, actual_qty, reserved_qty FROM `tabBin`
       WHERE item_code='FG004' AND warehouse IN ('PINNACLE COLD STORAGE SOLUTIONS - BKI',
                                                   '3MD LOGISTICS - CAMANGYANAN - BKI',
                                                   'Commissary - BKI')""",
    as_dict=True,
)

# Stock Ledger sum per batch at those warehouses
sle_by_batch = frappe.db.sql(
    """SELECT warehouse, batch_no, SUM(actual_qty) AS qty
       FROM `tabStock Ledger Entry`
       WHERE item_code='FG004' AND docstatus=1
         AND warehouse IN ('PINNACLE COLD STORAGE SOLUTIONS - BKI',
                           '3MD LOGISTICS - CAMANGYANAN - BKI',
                           'Commissary - BKI')
       GROUP BY warehouse, batch_no
       HAVING qty > 0
       ORDER BY warehouse, qty DESC""",
    as_dict=True,
)

payload = {"item_flags": item_flags, "batches": batches, "bins": bins, "sle_by_batch": sle_by_batch}
compressed = gzip.compress(json.dumps(payload, default=str).encode())
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
        f"echo '{enc}' | base64 -d > /tmp/s212_fg.py",
        "docker cp /tmp/s212_fg.py $BACKEND:/tmp/s212_fg.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_fg.py",
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
                sys.stderr.write(err); raise RuntimeError(inv["Status"])
            return out
    raise TimeoutError()

out = run()
s = out.find("__B64_START__"); e = out.find("__B64_END__")
b64 = out[s+len("__B64_START__"):e].strip()
data = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
print(f"Wrote {OUT}")
print("Item flags:", data["item_flags"])
print(f"Batches ({len(data['batches'])}):")
for b in data["batches"][:10]:
    print(f"  - {b['name']} batch_qty={b['batch_qty']}")
print(f"Bins at target warehouses ({len(data['bins'])}):")
for b in data["bins"]:
    print(f"  - {b['warehouse']}: actual_qty={b['actual_qty']} reserved_qty={b['reserved_qty']}")
print(f"\nSLE qty by batch at target warehouses ({len(data['sle_by_batch'])}):")
for s in data["sle_by_batch"]:
    print(f"  - {s['warehouse']} | batch={s['batch_no']} | qty={s['qty']}")
