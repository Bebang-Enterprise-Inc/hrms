"""S225 Phase 3 — verify 3MD consolidation actually committed."""
from __future__ import annotations
import base64, json, sys, time
INSTANCE_ID = "i-026b7477d27bd46d6"

INNER = r'''
import os, json
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

DUP = "3MD LOGISTICS – CAMANGYANAN - BKI"
CAN = "3MD LOGISTICS - CAMANGYANAN - BKI"

# Check the SE
se = frappe.db.get_value("Stock Entry", "MAT-STE-2026-01038",
    ["name", "docstatus", "stock_entry_type", "from_warehouse", "to_warehouse", "remarks"], as_dict=True)

# Duplicate state
dup_state = frappe.db.get_value("Warehouse", DUP, ["name", "disabled", "is_group"], as_dict=True)
dup_bins_nonzero = frappe.db.sql(
    "SELECT item_code, actual_qty FROM `tabBin` WHERE warehouse=%s AND ABS(actual_qty) > 0.001 ORDER BY item_code",
    (DUP,), as_dict=True)

# Canonical state — sample of items
can_state = frappe.db.get_value("Warehouse", CAN, ["name", "disabled", "is_group"], as_dict=True)
can_bins_sample = frappe.db.sql(
    "SELECT item_code, actual_qty FROM `tabBin` WHERE warehouse=%s AND item_code IN ('A058','CM30','FG004','FG002-A','PM001','RM017') ORDER BY item_code",
    (CAN,), as_dict=True)

# Did dup_after stock fully drain?
total_remaining_dup = frappe.db.sql(
    "SELECT COALESCE(SUM(actual_qty),0) FROM `tabBin` WHERE warehouse=%s",
    (DUP,))[0][0]

result = {
    "se": se,
    "duplicate_doc": dup_state,
    "canonical_doc": can_state,
    "duplicate_total_stock_after": float(total_remaining_dup),
    "duplicate_nonzero_bins_count": len(dup_bins_nonzero),
    "duplicate_nonzero_sample": dup_bins_nonzero[:10],
    "canonical_sample_after": can_bins_sample,
}
print("=== VERIFY_BEGIN ===")
print(json.dumps(result, default=str))
print("=== VERIFY_END ===")
'''


def main() -> int:
    import boto3
    enc = base64.b64encode(INNER.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s225_verify.py",
        "docker cp /tmp/s225_verify.py $BACKEND:/tmp/s225_verify.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s225_verify.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds, "executionTimeout": ["60"]})
    cid = r["Command"]["CommandId"]
    inv = None
    for _ in range(20):
        time.sleep(2)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break
    out = inv.get("StandardOutputContent", "")
    if "=== VERIFY_BEGIN ===" not in out:
        print(f"FAIL stderr: {inv.get('StandardErrorContent','')[:1500]}")
        return 1
    s = out.index("=== VERIFY_BEGIN ===") + len("=== VERIFY_BEGIN ===")
    e = out.index("=== VERIFY_END ===")
    data = json.loads(out[s:e].strip())
    print(json.dumps(data, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
