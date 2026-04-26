#!/usr/bin/env python3
"""S223 Phase 5 - apply HQ TIN to ORTIGAS GREENHILLS billing Customer + capture before/after snapshot + retroactive SI audit.

Per Sam directive 2026-04-25:
- Apply HQ TIN `688-721-280-00000` (BEIFRANCHISE FOOD OPC headquarters) to
  Customer.tax_id for "ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC".
- Snapshot before/after to output/s223/verification/ortigas_customer_*.json
- Audit prior submitted Sales Invoices for BIR §237 review.

This is the only canonical master-data UPDATE in the entire S223 sprint.
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
OUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "output" / "s223" / "verification"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CUSTOMER_NAME = "ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC"
HQ_TIN = "688-721-280-00000"  # per Sam directive 2026-04-25

SCRIPT = '''
import json
import frappe

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

CUSTOMER_NAME = ''' + json.dumps(CUSTOMER_NAME) + '''
HQ_TIN = ''' + json.dumps(HQ_TIN) + '''

result = {}

# Stage 1: snapshot before
if not frappe.db.exists("Customer", CUSTOMER_NAME):
    result["error"] = "Customer not found: " + CUSTOMER_NAME
    print("__B64_START__")
    import base64 as _b64
    import gzip as _gz
    print(_b64.b64encode(_gz.compress(json.dumps(result, default=str).encode())).decode())
    print("__B64_END__")
    raise SystemExit(1)

cust_before = frappe.get_doc("Customer", CUSTOMER_NAME)
result["before"] = {
    "name": cust_before.name,
    "tax_id": cust_before.tax_id or "",
    "customer_name": cust_before.customer_name,
    "is_internal_customer": cust_before.is_internal_customer,
    "modified": str(cust_before.modified),
}

# Stage 2: SI history audit (BIR §237)
si_history = frappe.db.sql("""
    SELECT name, posting_date, grand_total, status, docstatus
    FROM `tabSales Invoice`
    WHERE customer = %s
      AND docstatus = 1
    ORDER BY posting_date
""", (CUSTOMER_NAME,), as_dict=True)
result["si_history"] = si_history
result["si_history_count"] = len(si_history)

# Stage 3: apply the TIN (only if not already applied)
if cust_before.tax_id != HQ_TIN:
    frappe.set_value("Customer", CUSTOMER_NAME, "tax_id", HQ_TIN)
    frappe.db.commit()
    result["update"] = {"applied": True, "from": cust_before.tax_id or "", "to": HQ_TIN}
else:
    result["update"] = {"applied": False, "reason": "already correct", "current": cust_before.tax_id}

# Stage 4: snapshot after
cust_after = frappe.get_doc("Customer", CUSTOMER_NAME)
result["after"] = {
    "name": cust_after.name,
    "tax_id": cust_after.tax_id or "",
    "customer_name": cust_after.customer_name,
    "is_internal_customer": cust_after.is_internal_customer,
    "modified": str(cust_after.modified),
}

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
        f"echo '{enc}' | base64 -d > /tmp/s223tin.py",
        "docker cp /tmp/s223tin.py $BACKEND:/tmp/s223tin.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s223tin.py",
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

    # Write before/after snapshots
    if "before" in data:
        (OUT_DIR / "ortigas_customer_before.json").write_text(json.dumps(data["before"], indent=2, default=str))
    if "after" in data:
        (OUT_DIR / "ortigas_customer_after.json").write_text(json.dumps(data["after"], indent=2, default=str))
    # SI history
    si_history = data.get("si_history", [])
    (OUT_DIR / "ortigas_si_history.json").write_text(json.dumps(si_history, indent=2, default=str))

    print(f"Before: tax_id={data.get('before', {}).get('tax_id', '?')!r}")
    print(f"After:  tax_id={data.get('after', {}).get('tax_id', '?')!r}")
    print(f"Update: {data.get('update', {})}")
    print(f"Prior submitted SIs (BIR §237 audit): {len(si_history)}")
    if si_history:
        print("WARNING: prior submitted SIs exist with empty TIN — Sam/Denise must decide BIR §237 disposition.")
        print(f"  See {OUT_DIR / 'ortigas_si_history.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
