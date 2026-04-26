#!/usr/bin/env python3
"""S224 Pattern A diagnostic - inspect negative-stock FG004 backfill batches.

Sentry showed:
- BACKFILL-20260421-FG004-3MD-LOGISTICS-CAMANGYANAN: negative stock at 3MD LOGISTICS - CAMANGYANAN - BKI
- BACKFILL-20260421-FG004-PINNACLE-COLD-STORAGE-SOLUTIONS: negative stock at PINNACLE COLD STORAGE SOLUTIONS - BKI

Reports:
- Current actual_qty per batch+warehouse
- Top 10 stock ledger entries that consumed the batch (so we can see where the over-issue happened)
- The Stock Reconciliation that would zero out the negative balance

Read-only — does NOT mutate state. Use this output to design a Stock
Reconciliation entry that Sam can review + submit.
"""
from __future__ import annotations
import base64
import gzip
import json
import pathlib
import subprocess
import sys
import time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "s223" / "verification" / "pattern_a_batch_diagnostic.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

SCRIPT = '''
import json
import frappe

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

TARGETS = [
    {"batch": "BACKFILL-20260421-FG004-3MD-LOGISTICS-CAMANGYANAN", "warehouse": "3MD LOGISTICS - CAMANGYANAN - BKI"},
    {"batch": "BACKFILL-20260421-FG004-PINNACLE-COLD-STORAGE-SOLUTIONS", "warehouse": "PINNACLE COLD STORAGE SOLUTIONS - BKI"},
]

result = {"targets": []}
for t in TARGETS:
    info = {"batch": t["batch"], "warehouse": t["warehouse"]}

    # Does the batch exist?
    info["batch_exists"] = bool(frappe.db.exists("Batch", t["batch"]))
    if info["batch_exists"]:
        batch_doc = frappe.get_doc("Batch", t["batch"])
        info["batch_item"] = batch_doc.item
        info["batch_creation"] = str(batch_doc.creation)
        info["batch_modified"] = str(batch_doc.modified)
        info["batch_disabled"] = batch_doc.disabled

    # Bin record (live actual_qty)
    bin_qty = frappe.db.sql(
        """SELECT actual_qty, item_code FROM `tabBin`
           WHERE warehouse = %s AND item_code = (
               SELECT item FROM `tabBatch` WHERE name = %s
           )""",
        (t["warehouse"], t["batch"]),
        as_dict=True,
    )
    info["bin_actual_qty"] = (bin_qty[0].get("actual_qty") if bin_qty else None)
    info["item_code"] = (bin_qty[0].get("item_code") if bin_qty else None)

    # Sum of stock ledger entries against this batch
    sle_balance = frappe.db.sql(
        """SELECT SUM(actual_qty) as total
           FROM `tabStock Ledger Entry`
           WHERE batch_no = %s AND warehouse = %s AND is_cancelled = 0""",
        (t["batch"], t["warehouse"]),
        as_dict=True,
    )
    info["batch_sle_total"] = (sle_balance[0].get("total") if sle_balance else None)

    # Top 10 most recent stock movements affecting this batch
    recent_sles = frappe.db.sql(
        """SELECT name, posting_date, posting_time, voucher_type, voucher_no,
                  actual_qty, qty_after_transaction
           FROM `tabStock Ledger Entry`
           WHERE batch_no = %s AND warehouse = %s AND is_cancelled = 0
           ORDER BY creation DESC
           LIMIT 10""",
        (t["batch"], t["warehouse"]),
        as_dict=True,
    )
    info["recent_sles"] = recent_sles

    # First 10 SLEs to see the original receipt
    first_sles = frappe.db.sql(
        """SELECT name, posting_date, voucher_type, voucher_no, actual_qty
           FROM `tabStock Ledger Entry`
           WHERE batch_no = %s AND warehouse = %s AND is_cancelled = 0
           ORDER BY creation ASC
           LIMIT 10""",
        (t["batch"], t["warehouse"]),
        as_dict=True,
    )
    info["first_sles"] = first_sles

    result["targets"].append(info)

# Also check: what items are FG004?
fg004 = frappe.db.get_value("Item", "FG004", ["item_name", "stock_uom", "is_stock_item"], as_dict=True)
result["item_fg004"] = fg004

# What other batches of FG004 exist with positive stock that we could use instead?
positive_batches = frappe.db.sql(
    """SELECT batch_no, warehouse, SUM(actual_qty) as total
       FROM `tabStock Ledger Entry`
       WHERE batch_no LIKE 'BACKFILL%FG004%' AND is_cancelled = 0
       GROUP BY batch_no, warehouse
       HAVING total > 0
       ORDER BY total DESC
       LIMIT 20""",
    as_dict=True,
)
result["positive_fg004_batches"] = positive_batches

import gzip as _gz, base64 as _b64
compressed = _gz.compress(json.dumps(result, default=str).encode())
print("__B64_START__")
print(_b64.b64encode(compressed).decode())
print("__B64_END__")
frappe.destroy()
'''


def run(timeout: int = 120) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s224batch.py",
        "docker cp /tmp/s224batch.py $BACKEND:/tmp/s224batch.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s224batch.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds, "executionTimeout": [str(timeout)]})
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}", flush=True)
    deadline = time.time() + timeout + 30
    while time.time() < deadline:
        time.sleep(8)
        try:
            inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            out = inv.get("StandardOutputContent", "")
            if inv["Status"] != "Success":
                sys.stderr.write(inv.get("StandardErrorContent", "") + "\n")
            return out
    raise TimeoutError()


def main() -> int:
    out = run()
    s = out.find("__B64_START__")
    e = out.find("__B64_END__")
    if s < 0 or e < 0:
        sys.stderr.write(out[:5000] + "\n")
        return 1
    b64 = out[s + len("__B64_START__"):e].strip()
    data = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
    OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote: {OUT}\n")
    print(f"Item FG004: {data.get('item_fg004', {}).get('item_name')!r}")
    print()
    for t in data["targets"]:
        print(f"=== Batch: {t['batch']} ===")
        print(f"  warehouse: {t['warehouse']}")
        print(f"  exists: {t['batch_exists']}")
        print(f"  Bin.actual_qty: {t.get('bin_actual_qty')}")
        print(f"  SLE total: {t.get('batch_sle_total')}")
        print(f"  Last 5 SLEs:")
        for sle in (t.get("recent_sles") or [])[:5]:
            print(f"    {sle.get('posting_date')} {sle.get('voucher_type')}/{sle.get('voucher_no')} qty={sle.get('actual_qty')} after={sle.get('qty_after_transaction')}")
        print(f"  First 3 SLEs:")
        for sle in (t.get("first_sles") or [])[:3]:
            print(f"    {sle.get('posting_date')} {sle.get('voucher_type')}/{sle.get('voucher_no')} qty={sle.get('actual_qty')}")
        print()
    print("Other positive FG004 batches:")
    for b in (data.get("positive_fg004_batches") or [])[:10]:
        print(f"  {b['warehouse']}/{b['batch_no']}: +{b['total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
