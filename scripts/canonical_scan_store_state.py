"""Canonical State Scan — produces STORE_CANONICAL_STATE_<date>.csv

For every store (Company.entity_category='Store', active), capture:
  - per-store Company + parent_company + store_ownership_type + operational_status
  - every Warehouse linked to either the per-store Company OR the parent Company
    (when warehouse_name matches store context) — flags duplicates
  - every Customer where customer_name/name matches the per-store Company
    OR represents_company == per-store Company OR customer_name == parent Company
  - every Cost Center linked to the per-store Company
  - TINs + is_internal flags on each Customer
  - area_supervisor assignment on each warehouse

Pure read-only SSM scan. Zero mutations.

Output: data/_CONSOLIDATED/STORE_CANONICAL_STATE_2026-04-19.csv
"""
from __future__ import annotations
import base64
import json
import sys
import time
from pathlib import Path

OUTPUT_DIR = Path("F:/Dropbox/Projects/BEI-ERP/data/_CONSOLIDATED")
OUTPUT_CSV = OUTPUT_DIR / "STORE_CANONICAL_STATE_2026-04-19.csv"
OUTPUT_JSON = OUTPUT_DIR / "STORE_CANONICAL_STATE_2026-04-19.json"

SCRIPT = r'''
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# 1. All active Store Companies
store_companies = frappe.db.sql(
    """SELECT name, parent_company, store_ownership_type, operational_status, abbr,
              country, default_currency, tax_id
       FROM `tabCompany`
       WHERE entity_category = 'Store'
         AND (operational_status IS NULL OR operational_status NOT IN ('Permanently Closed', 'Dormant'))
       ORDER BY name""",
    as_dict=True,
)

# 2. For each store, collect the whole footprint
SUB_WH_NAMES = ("FINISHED GOODS", "GOODS IN TRANSIT", "STORES", "WORK IN PROGRESS")

rows = []
for co in store_companies:
    parent = co["parent_company"]

    # Parent company TIN
    parent_tin = None
    if parent:
        parent_tin = frappe.db.get_value("Company", parent, "tax_id")

    # All warehouses whose company = this per-store Company OR = parent (non-sub)
    # and whose warehouse_name references this store
    wh_per_store = frappe.db.sql(
        """SELECT name, warehouse_name, company, is_group, disabled, custom_area_supervisor
           FROM `tabWarehouse`
           WHERE company = %s
             AND warehouse_name NOT IN ({})
           ORDER BY name""".format(",".join(f"'{n}'" for n in SUB_WH_NAMES)),
        (co["name"],), as_dict=True,
    )

    # Warehouses under parent whose docname references this store's abbr or key tokens
    wh_parent_linked = []
    if parent:
        # Heuristic: warehouse_name contains the store code OR docname begins with parent name + store fragment
        # Match on Warehouse.name containing any significant token from the per-store Company name
        # Tokens: strip the legal suffix from the per-store Company name
        import re
        store_label = re.sub(r"\s+-\s+.+?(INC\.|CORP\.|OPC|HOLDINGS\s+OPC).*$", "", co["name"]).strip()
        if store_label:
            wh_parent_linked = frappe.db.sql(
                """SELECT name, warehouse_name, company, is_group, disabled, custom_area_supervisor
                   FROM `tabWarehouse`
                   WHERE company = %s
                     AND warehouse_name NOT IN ({})
                     AND (name LIKE %s OR warehouse_name LIKE %s OR warehouse_name LIKE %s)
                   ORDER BY name""".format(",".join(f"'{n}'" for n in SUB_WH_NAMES)),
                (parent, f"%{store_label}%", f"%{store_label}%", f"{store_label}%"), as_dict=True,
            )

    # Customers: three lookups
    # A. customer_name exactly = per-store Company
    cust_exact = frappe.db.sql(
        """SELECT name, customer_name, represents_company, is_internal_customer, tax_id
           FROM `tabCustomer` WHERE customer_name = %s""",
        (co["name"],), as_dict=True,
    )
    # B. represents_company = per-store Company (S206 internals)
    cust_represents = frappe.db.sql(
        """SELECT name, customer_name, represents_company, is_internal_customer, tax_id
           FROM `tabCustomer` WHERE represents_company = %s""",
        (co["name"],), as_dict=True,
    )
    # C. customer_name = parent Company (the classic parent-level billing Customer)
    cust_parent = []
    if parent:
        cust_parent = frappe.db.sql(
            """SELECT name, customer_name, represents_company, is_internal_customer, tax_id
               FROM `tabCustomer` WHERE customer_name = %s""",
            (parent,), as_dict=True,
        )

    # Cost centers
    ccs = frappe.db.sql(
        """SELECT name, cost_center_name, company, disabled, is_group
           FROM `tabCost Center` WHERE company = %s""",
        (co["name"],), as_dict=True,
    )

    # Resolver snapshot — what does the live resolver return for the per-store Company?
    try:
        from hrms.utils.supply_chain_contracts import _resolve_buyer_customer_for_company
        resolver_cust, resolver_matched = _resolve_buyer_customer_for_company(co["name"])
    except Exception as e:
        resolver_cust, resolver_matched = None, f"error:{e}"

    row = {
        "per_store_company": co["name"],
        "parent_company": parent,
        "parent_tin": parent_tin,
        "store_ownership_type": co["store_ownership_type"],
        "operational_status": co["operational_status"],
        "abbr": co["abbr"],
        "per_store_tin": co["tax_id"],
        "default_currency": co["default_currency"],
        "warehouses_under_per_store": wh_per_store,
        "warehouses_under_parent_linked_to_store": wh_parent_linked,
        "customer_exact_match_per_store_company": cust_exact,
        "customer_represents_per_store_company": cust_represents,
        "customer_match_parent_company": cust_parent,
        "cost_centers_under_per_store": ccs,
        "resolver_returns_customer": resolver_cust,
        "resolver_matched_company": resolver_matched,
    }
    rows.append(row)

# Also collect a list of all BEI/BKI/Commissary/other Warehouses that are NOT mapped to a store
# to flag orphan warehouses
orphan_wh = frappe.db.sql(
    """SELECT w.name, w.warehouse_name, w.company, w.disabled
       FROM `tabWarehouse` w
       LEFT JOIN `tabCompany` c ON c.name = w.company
       WHERE w.is_group = 0
         AND w.warehouse_name NOT IN ({})
         AND (c.entity_category IS NULL OR c.entity_category NOT IN ('Store','Commissary','Head Office','3PL','Cold Storage'))
       ORDER BY w.warehouse_name
       LIMIT 200""".format(",".join(f"'{n}'" for n in SUB_WH_NAMES)),
    as_dict=True,
)

out = {
    "scan_timestamp_utc": frappe.utils.now(),
    "store_count": len(rows),
    "stores": rows,
    "orphan_warehouses": orphan_wh,
}

with open("/tmp/canonical_state.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2, default=str)
print(f"WROTE_IN_CONTAINER /tmp/canonical_state.json with {len(rows)} stores")

# Summary
dup_wh = 0
dup_cust = 0
missing_per_store_cust = 0
for r in rows:
    total_wh = len(r["warehouses_under_per_store"]) + len(r["warehouses_under_parent_linked_to_store"])
    if total_wh > 1:
        dup_wh += 1
    total_cust = len(r["customer_exact_match_per_store_company"]) + len(r["customer_represents_per_store_company"]) + len(r["customer_match_parent_company"])
    if total_cust > 2:
        dup_cust += 1
    if len(r["customer_exact_match_per_store_company"]) == 0:
        missing_per_store_cust += 1
print(f"  stores with >1 warehouse: {dup_wh}")
print(f"  stores with >2 customer records: {dup_cust}")
print(f"  stores MISSING a per-store billing customer (no exact customer_name match): {missing_per_store_cust}")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/cscan.py",
    "docker cp /tmp/cscan.py $BACKEND:/tmp/cscan.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/cscan.py",
    "docker cp $BACKEND:/tmp/canonical_state.json /tmp/canonical_state.json",
    "gzip -c /tmp/canonical_state.json | base64 -w0 > /tmp/cs.b64",
    "echo '===B64_GZ_BEGIN==='",
    "cat /tmp/cs.b64",
    "echo",
    "echo '===B64_GZ_END==='",
]

import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(
    InstanceIds=["i-026b7477d27bd46d6"],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["360"]},
)
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(120):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        out = inv["StandardOutputContent"]
        print("STATUS:", inv["Status"])
        if inv["Status"] != "Success":
            print(out[-3000:])
            if inv["StandardErrorContent"]:
                print("STDERR:", inv["StandardErrorContent"][-1500:])
            sys.exit(1)
        if "===B64_GZ_BEGIN===" not in out or "===B64_GZ_END===" not in out:
            print(f"Markers missing. Tail:\n{out[-2000:]}")
            sys.exit(1)
        b64_text = out.split("===B64_GZ_BEGIN===", 1)[1].split("===B64_GZ_END===", 1)[0].strip()
        import gzip, io as _io
        gz_bytes = base64.b64decode(b64_text)
        raw = gzip.GzipFile(fileobj=_io.BytesIO(gz_bytes)).read()
        parsed = json.loads(raw.decode("utf-8"))
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"WROTE {OUTPUT_JSON} with {parsed['store_count']} stores")

        # Flatten to CSV
        import csv
        with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "per_store_company", "parent_company", "parent_tin",
                "store_ownership_type", "operational_status", "per_store_tin",
                "wh_under_per_store_count", "wh_under_per_store_list",
                "wh_under_parent_linked_count", "wh_under_parent_linked_list",
                "cust_exact_match_count", "cust_exact_match_list",
                "cust_represents_count", "cust_represents_list",
                "cust_parent_match_count", "cust_parent_match_list",
                "cost_center_count", "cost_center_list",
                "resolver_returns_customer", "resolver_matched_company",
                "flag_duplicate_warehouse", "flag_missing_per_store_customer",
                "flag_has_s206_internal_customer",
            ])
            for r in parsed["stores"]:
                wh_ps = [x["name"] for x in r["warehouses_under_per_store"]]
                wh_pa = [x["name"] for x in r["warehouses_under_parent_linked_to_store"]]
                cust_e = [x["name"] for x in r["customer_exact_match_per_store_company"]]
                cust_r = [x["name"] for x in r["customer_represents_per_store_company"]]
                cust_p = [x["name"] for x in r["customer_match_parent_company"]]
                ccs = [x["name"] for x in r["cost_centers_under_per_store"]]
                dup_wh = len(wh_ps) + len(wh_pa) > 1
                missing_ps = len(cust_e) == 0
                has_s206 = any(c.get("is_internal_customer") for c in r["customer_represents_per_store_company"])
                w.writerow([
                    r["per_store_company"], r["parent_company"], r["parent_tin"],
                    r["store_ownership_type"], r["operational_status"], r["per_store_tin"],
                    len(wh_ps), "|".join(wh_ps),
                    len(wh_pa), "|".join(wh_pa),
                    len(cust_e), "|".join(cust_e),
                    len(cust_r), "|".join(cust_r),
                    len(cust_p), "|".join(cust_p),
                    len(ccs), "|".join(ccs),
                    r["resolver_returns_customer"], r["resolver_matched_company"],
                    dup_wh, missing_ps, has_s206,
                ])
        print(f"WROTE {OUTPUT_CSV}")
        sys.exit(0)
