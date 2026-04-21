#!/usr/bin/env python3
"""S213 Phase 0 — audit every has_batch_no=1 item at BKI warehouses for NULL-batch stock.

Emits output/l3/s213/batch_audit_report.json with the structure:
    {
      "bki_warehouses": [{"name": ..., "company": ...}],
      "null_batch_tuples": [{"item_code": ..., "warehouse": ..., "null_qty": ...,
                              "valuation_rate": ..., "has_batch_no": 1}, ...],
      "summary": {"total_tuples": N, "total_qty": Q, "distinct_items": I, "distinct_warehouses": W}
    }
"""
from __future__ import annotations
import base64
import gzip
import json
import pathlib
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "output" / "l3" / "s213"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "batch_audit_report.json"

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"


SCRIPT = '''
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass

import json, base64, gzip
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Scope: all warehouses whose company == 'Bebang Kitchen Inc.'
# (BKI covers commissary, cold-storage 3PL hubs, and staging)
bki_warehouses = frappe.db.sql(
    """SELECT name, company, warehouse_name, is_group FROM `tabWarehouse`
       WHERE company = 'Bebang Kitchen Inc.' AND disabled = 0 AND is_group = 0
       ORDER BY name""",
    as_dict=True,
)
bki_wh_names = [w["name"] for w in bki_warehouses]

# NULL-batch qty per (item, warehouse) for items flagged has_batch_no=1
tuples = []
if bki_wh_names:
    placeholders = ",".join(["%s"] * len(bki_wh_names))
    tuples = frappe.db.sql(
        f"""SELECT sle.item_code, sle.warehouse, SUM(sle.actual_qty) AS null_qty,
                   i.has_batch_no
           FROM `tabStock Ledger Entry` sle
           JOIN `tabItem` i ON i.item_code = sle.item_code
           WHERE i.has_batch_no = 1
             AND sle.batch_no IS NULL
             AND sle.docstatus = 1
             AND sle.warehouse IN ({placeholders})
           GROUP BY sle.item_code, sle.warehouse
           HAVING null_qty > 0
           ORDER BY null_qty DESC""",
        tuple(bki_wh_names),
        as_dict=True,
    )

# Enrich with valuation_rate so the backfill script can post correct values
enriched = []
for t in tuples:
    val = frappe.db.sql(
        """SELECT valuation_rate FROM `tabStock Ledger Entry`
           WHERE item_code=%s AND warehouse=%s AND docstatus=1
           ORDER BY posting_datetime DESC LIMIT 1""",
        (t["item_code"], t["warehouse"]),
        as_dict=True,
    )
    vr = float(val[0]["valuation_rate"]) if val and val[0].get("valuation_rate") is not None else 0.0
    enriched.append({
        "item_code": t["item_code"],
        "warehouse": t["warehouse"],
        "null_qty": float(t["null_qty"]),
        "valuation_rate": vr,
        "has_batch_no": t["has_batch_no"],
    })

payload = {
    "bki_warehouses": bki_warehouses,
    "null_batch_tuples": enriched,
    "summary": {
        "total_tuples": len(enriched),
        "total_qty": sum(x["null_qty"] for x in enriched),
        "distinct_items": len(set(x["item_code"] for x in enriched)),
        "distinct_warehouses": len(set(x["warehouse"] for x in enriched)),
    },
}
compressed = gzip.compress(json.dumps(payload, default=str).encode())
print("__AUDIT_B64_START__")
print(base64.b64encode(compressed).decode())
print("__AUDIT_B64_END__")
frappe.destroy()
'''


def run_in_container(python_script: str, timeout: int = 120) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(python_script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s213_audit.py",
        "docker cp /tmp/s213_audit.py $BACKEND:/tmp/s213_audit.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s213_audit.py",
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


def extract_between(haystack: str, start: str, end: str) -> str:
    s = haystack.find(start); e = haystack.find(end)
    if s < 0 or e < 0:
        raise RuntimeError(f"Could not find markers {start}/{end}")
    return haystack[s + len(start):e].strip()


def main() -> int:
    out = run_in_container(SCRIPT)
    b64 = extract_between(out, "__AUDIT_B64_START__", "__AUDIT_B64_END__")
    payload = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
    OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"[S213] Wrote {OUT}")
    s = payload["summary"]
    print(f"[S213] BKI warehouses audited: {len(payload['bki_warehouses'])}")
    print(f"[S213] NULL-batch tuples: {s['total_tuples']}")
    print(f"[S213] Total NULL-batch qty: {s['total_qty']}")
    print(f"[S213] Distinct items: {s['distinct_items']}")
    print(f"[S213] Distinct warehouses: {s['distinct_warehouses']}")
    print()
    print("Top 15 tuples by qty:")
    for t in sorted(payload["null_batch_tuples"], key=lambda x: -x["null_qty"])[:15]:
        print(f"  {t['item_code']:10s} | {t['warehouse']:50s} | qty={t['null_qty']:10.2f} | rate={t['valuation_rate']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
