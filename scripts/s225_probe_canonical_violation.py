"""S225 — probe canonical state for warehouses that hit InvalidWarehouseCompany during sweep."""
from __future__ import annotations
import base64, json, sys, time
INSTANCE_ID = "i-026b7477d27bd46d6"

INNER = r'''
import os, json
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Stores from Sentry errors
SUSPECTS = [
    "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
    "ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.",
    "SM STA. ROSA - SWEET HARMONY FOOD CORP.",
]

result = []
for wh_name in SUSPECTS:
    wh = frappe.db.get_value("Warehouse", wh_name,
        ["name", "warehouse_name", "company", "disabled", "is_group", "parent_warehouse"], as_dict=True)
    if not wh:
        result.append({"warehouse": wh_name, "exists": False})
        continue

    # Get the per-store Company that SHOULD own this warehouse
    co = frappe.db.get_value("Company", wh_name,
        ["name", "parent_company", "abbr", "country"], as_dict=True)

    # Test resolve_warehouse_company
    from hrms.utils.supply_chain_contracts import resolve_warehouse_company
    resolved = resolve_warehouse_company(wh_name)

    # What does _resolve_store_order_source_warehouse return for this store?
    from hrms.api.store import _resolve_store_order_source_warehouse
    try:
        src_dry = _resolve_store_order_source_warehouse(wh_name, "DRY")
    except Exception as e:
        src_dry = f"ERR: {str(e)[:200]}"

    # If src_dry is a warehouse, what is its company?
    src_co = None
    src_resolve = None
    if isinstance(src_dry, str) and frappe.db.exists("Warehouse", src_dry):
        src_co = frappe.db.get_value("Warehouse", src_dry, "company")
        src_resolve = resolve_warehouse_company(src_dry)

    result.append({
        "warehouse": wh_name,
        "exists": True,
        "wh_company_field": wh["company"],
        "expected_per_store_company": wh_name,
        "is_canonical_match": wh["company"] == wh_name,
        "per_store_company_doc_exists": bool(co),
        "per_store_company_parent": co.get("parent_company") if co else None,
        "resolve_warehouse_company_returns": resolved,
        "source_warehouse_for_DRY": src_dry,
        "source_warehouse_company_field": src_co,
        "source_resolve_returns": src_resolve,
    })

print("=== PROBE_BEGIN ===")
print(json.dumps(result, indent=2, default=str))
print("=== PROBE_END ===")
'''


def main() -> int:
    import boto3
    enc = base64.b64encode(INNER.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s225_probe_canonical.py",
        "docker cp /tmp/s225_probe_canonical.py $BACKEND:/tmp/s225_probe_canonical.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s225_probe_canonical.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds, "executionTimeout": ["120"]})
    cid = r["Command"]["CommandId"]
    inv = None
    for _ in range(40):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break
    out = inv.get("StandardOutputContent", "")
    if "=== PROBE_BEGIN ===" not in out:
        print(f"FAIL stderr: {inv.get('StandardErrorContent','')[:1500]}")
        return 1
    s = out.index("=== PROBE_BEGIN ===") + len("=== PROBE_BEGIN ===")
    e = out.index("=== PROBE_END ===")
    print(out[s:e].strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
