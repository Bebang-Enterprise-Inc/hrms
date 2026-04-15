#!/usr/bin/env python3
"""S196 follow-up — SJDM attribution fix.

Per CEO directive 2026-04-16: JL TRADE OPC (TIN 775-842-763-00003 / RDO 045)
is the real operator for SM San Jose Del Monte, not LEGACY77 FOOD CORP.

Operations:
  1. Re-point `SJDM - BEI` warehouse from LEGACY77 FOOD CORP. -> JL TRADE OPC
     + SLE + GL company backfill
  2. Rename JL TRADE OPC -> `SM San Jose Del Monte - JL TRADE OPC` (store-first S196 convention)
  3. Archive LEGACY77 FOOD CORP. (operational_status=Permanently Closed, entity_category=Franchisor already,
     disable its 5 template warehouses) — branch_tin conflict deferred to data-hygiene sprint
"""
import os
import sys
import re

for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

if os.environ.get("CONFIRM","").lower() != "yes":
    print("ERROR: CONFIRM=yes required")
    sys.exit(2)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

def sp(name): return re.sub(r"[^A-Za-z0-9_]", "_", name)

print("=" * 60)
print("S196 SJDM ATTRIBUTION FIX")
print("=" * 60)

LEGACY = "LEGACY77 FOOD CORP."
JL_OLD = "JL TRADE OPC"
JL_NEW = "SM San Jose Del Monte - JL TRADE OPC"
SJDM_WH = "SJDM - BEI"

# Step 1: Re-point SJDM warehouse + SLE/GL back-fill
print(f"\n=== Step 1: Re-point {SJDM_WH} {LEGACY} -> {JL_OLD} ===")
if not frappe.db.exists("Warehouse", SJDM_WH):
    print(f"  SKIP: {SJDM_WH} not found")
else:
    current_co = frappe.db.get_value("Warehouse", SJDM_WH, "company")
    print(f"  current company: {current_co!r}")
    if current_co == LEGACY:
        try:
            frappe.db.savepoint(sp("repoint_sjdm"))
            frappe.db.set_value("Warehouse", SJDM_WH, "company", JL_OLD)
            frappe.db.sql("UPDATE `tabStock Ledger Entry` SET company=%s WHERE warehouse=%s AND company!=%s",
                          (JL_OLD, SJDM_WH, JL_OLD))
            sle = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
            frappe.db.sql("""
                UPDATE `tabGL Entry` ge
                JOIN `tabStock Ledger Entry` sle ON ge.voucher_no = sle.voucher_no
                SET ge.company = %s
                WHERE sle.warehouse = %s AND ge.company != %s
                """, (JL_OLD, SJDM_WH, JL_OLD))
            gl = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
            frappe.db.commit()
            print(f"  DONE: {SJDM_WH} -> {JL_OLD}; SLE backfilled={sle}; GL backfilled={gl}")
        except Exception as e:
            print(f"  FAIL: {e}")
    else:
        print(f"  SKIP: already on {current_co}")

# Step 2: Rename JL TRADE OPC to store-first
print(f"\n=== Step 2: Rename {JL_OLD} -> {JL_NEW} ===")
if frappe.db.exists("Company", JL_NEW):
    print(f"  SKIP: {JL_NEW} already exists (rename already done)")
elif not frappe.db.exists("Company", JL_OLD):
    print(f"  SKIP: {JL_OLD} not found")
else:
    try:
        frappe.db.savepoint(sp("rename_jl"))
        abbr_pre = frappe.db.get_value("Company", JL_OLD, "abbr")
        frappe.rename_doc("Company", JL_OLD, JL_NEW, merge=False)
        frappe.db.commit()
        abbr_post = frappe.db.get_value("Company", JL_NEW, "abbr")
        print(f"  DONE: renamed. abbr preserved: {abbr_pre} -> {abbr_post}")
    except Exception as e:
        print(f"  FAIL: {e}")

# Step 3: Archive LEGACY77 FOOD CORP.
print(f"\n=== Step 3: Archive {LEGACY} ===")
if not frappe.db.exists("Company", LEGACY):
    print(f"  SKIP: {LEGACY} not found")
else:
    current_status = frappe.db.get_value("Company", LEGACY, "operational_status")
    if current_status == "Permanently Closed":
        print(f"  SKIP: already Permanently Closed")
    else:
        try:
            frappe.db.savepoint(sp("archive_legacy"))
            frappe.db.set_value("Company", LEGACY, "operational_status", "Permanently Closed")
            child_whs = frappe.get_all("Warehouse", filters={"company": LEGACY, "disabled": 0}, pluck="name")
            for wh in child_whs:
                frappe.db.set_value("Warehouse", wh, "disabled", 1)
            frappe.db.commit()
            print(f"  DONE: operational_status=Permanently Closed; {len(child_whs)} child warehouses disabled")
        except Exception as e:
            print(f"  FAIL: {e}")

# Step 4: Final verification
print(f"\n=== Step 4: Verification ===")
orderable = frappe.get_all("Company",
    filters={"entity_category": ["in", ["Store","Commissary"]],
             "operational_status": ["in", ["Active","Pre-Opening","Temporarily Closed","Pipeline"]]},
    pluck="name")
print(f"  Orderable Companies: {len(orderable)}")
print(f"  JL_NEW in orderable: {JL_NEW in orderable}")
print(f"  LEGACY in orderable (should be False after archive): {LEGACY in orderable}")

sjdm_co = frappe.db.get_value("Warehouse", SJDM_WH, "company")
print(f"  {SJDM_WH} company: {sjdm_co!r}")

# Count orderable warehouses
from collections import Counter
NON_ORD_TYPES = {"3PL","Commissary","Cold Storage","Transit"}
NON_ORD_PATTERNS = ("Jentec","Pinnacle","Royal Cold","RCS","3MD","Commissary","Kitchen",
                    "TEST-COMMISSARY","TEST-STORE","Finished Goods","Work In Progress","Raw Materials")
NON_ORD_NAMES = {"Stores","Stores - BEI","Stores - BK","All Warehouses","All Warehouses - BEI"}
whs = frappe.get_all("Warehouse",
    filters={"company": ["in", orderable], "is_group": 0, "disabled": 0},
    fields=["name","company","warehouse_type","warehouse_name"])
def is_ord(w):
    wt = (w.get("warehouse_type") or "").strip()
    if wt and wt in NON_ORD_TYPES: return False
    n = w.get("warehouse_name") or w.get("name") or ""
    if n in NON_ORD_NAMES: return False
    if any(p in n for p in NON_ORD_PATTERNS): return False
    return True
ord_whs = [w for w in whs if is_ord(w)]
print(f"  Orderable warehouses: {len(ord_whs)}")
by_co = Counter(w["company"] for w in ord_whs)
zero = [c for c in orderable if c not in by_co]
print(f"  Companies w/ 0 wh: {zero}")

print("\n" + "=" * 60)
print("S196 SJDM FIX DONE")
print("=" * 60)
frappe.destroy()
