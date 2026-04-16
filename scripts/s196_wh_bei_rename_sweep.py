#!/usr/bin/env python3
"""S196 Item #3 - Cosmetic warehouse rename sweep.

Every leaf warehouse with `- BEI` suffix whose owner Company is NOT
`Bebang Enterprise Inc.` or its tree gets renamed to store-first pattern:
  `<Store> - BEI`  ->  `<Store> - <Real Company Name>`

Discovery + rename + regeneration of sales_dashboard_store_mapping fixture
via live SSM. Audit output is a CSV + JSON snapshot.

Safety:
  - Requires CONFIRM=yes env to execute renames
  - --dry-run flag: list candidates + planned new names, no mutations
  - Each rename wrapped in savepoint; rollback on failure
  - Skips any target where the new name would collide with an existing Warehouse
"""
import os
import sys
import json
import re
import csv

for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

DRY_RUN = "--dry-run" in sys.argv
CONFIRM = os.environ.get("CONFIRM", "").strip().lower() == "yes"

if not DRY_RUN and not CONFIRM:
    print("ERROR: Destructive run requires CONFIRM=yes env. Use --dry-run to preview.")
    sys.exit(2)

import frappe

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# ---- Settings -----------------------------------------------------------

# The holding parent and its internal group warehouses are the set we leave untouched.
# Any leaf `- BEI` warehouse whose `company` is NOT one of these stays as-is.
BEI_PARENT_COMPANY = "Bebang Enterprise Inc."

# Group warehouses with "- BEI" suffix that are structural — do not rename.
STRUCTURAL_GROUPS = {
    "Stores - BEI",
    "All Warehouses - BEI",
    "Stores",
    "All Warehouses",
    "In Transit - BEI",
    "Work In Progress - BEI",
    "Finished Goods - BEI",
    "Goods In Transit - BEI",
    "Raw Materials - BEI",
}

# ---- Helpers ------------------------------------------------------------

actions = []


def log(step, action, target, status, note=""):
    row = {"step": step, "action": action, "target": target, "status": status, "note": note}
    actions.append(row)
    print(f"  [{status:7s}] {step}: {action} {target!r} {('- ' + note) if note else ''}")


def _sp_name(raw):
    return re.sub(r"[^A-Za-z0-9_]", "_", raw)[:60]


def savepoint(name):
    frappe.db.savepoint(_sp_name(name))


def rollback(name):
    try:
        frappe.db.rollback(save_point=_sp_name(name))
    except Exception:
        try:
            frappe.db.rollback_to_savepoint(_sp_name(name))
        except Exception as e:
            print(f"  ROLLBACK FAILED at savepoint {_sp_name(name)}: {e}")


def strip_bei_suffix(wh_name):
    # "SM Taytay - BEI" -> "SM Taytay"
    return re.sub(r"\s*-\s*BEI\s*$", "", wh_name)


def derive_corp_suffix(company_name):
    """Extract the corp part of a store-first Company name.

    For a Company already in store-first form (`<Store> - <Corp>`), take the
    corp segment (after first ' - '). For single-operator corps with no
    dash (`BEBANG MEGA INC.`, `TRICERN FOOD CORP.`), return the whole name.
    """
    if " - " in company_name:
        return company_name.split(" - ", 1)[1]
    return company_name


# ---- Start --------------------------------------------------------------

print("=" * 72)
print(f"S196 ITEM #3 WAREHOUSE RENAME SWEEP - {'DRY-RUN' if DRY_RUN else 'LIVE'}")
print("=" * 72)

# ====== STEP A - Discovery ==============================================
print("\n=== STEP A: Discovery ===")
candidates = frappe.db.sql(
    """
    SELECT w.name, w.company, c.company_name
    FROM `tabWarehouse` w
    JOIN `tabCompany` c ON c.name = w.company
    WHERE w.name LIKE '%%- BEI'
      AND w.is_group = 0
      AND w.disabled = 0
      AND w.company != %s
    ORDER BY w.name
    """,
    BEI_PARENT_COMPANY,
    as_dict=True,
)
print(f"  Found {len(candidates)} leaf `- BEI` warehouses not owned by BEI parent")

# Filter out structural group warehouses (extra safety — they should have is_group=1 already)
candidates = [c for c in candidates if c["name"] not in STRUCTURAL_GROUPS]
print(f"  After structural filter: {len(candidates)}")

plan = []  # [(old, new, company)]
for c in candidates:
    old = c["name"]
    company_name = c["company_name"]  # Title-case human-readable
    store = strip_bei_suffix(old)
    corp_suffix = derive_corp_suffix(company_name)
    new = f"{store} - {corp_suffix}"
    # Collision check
    if old == new:
        log("A", "plan", old, "SKIP", f"old=new (already matches)")
        continue
    if frappe.db.exists("Warehouse", new):
        log("A", "plan", old, "SKIP", f"target exists: {new}")
        continue
    plan.append((old, new, c["company"]))
    print(f"  PLAN: {old!r} -> {new!r}  (company={c['company']}, corp_suffix={corp_suffix})")

print(f"\n  Total renames planned: {len(plan)}")


# ====== STEP B - Execute renames ========================================
print(f"\n=== STEP B: {'DRY' if DRY_RUN else 'LIVE'} renames ===")
for old, new, company in plan:
    if DRY_RUN:
        log("B", "rename_warehouse (dry)", f"{old} -> {new}", "DRY", f"company={company}")
        continue
    sp = f"rn_wh_{old[:25]}"
    try:
        savepoint(sp)
        frappe.rename_doc("Warehouse", old, new, merge=False, force=True)
        frappe.db.commit()
        log("B", "rename_warehouse", f"{old} -> {new}", "DONE", f"company={company}")
    except Exception as e:
        rollback(sp)
        log("B", "rename_warehouse", f"{old} -> {new}", "FAIL", str(e)[:140])


# ====== STEP C - Dump live fixture data for sales_dashboard_store_mapping =====
# The sales_dashboard_store_mapping fixture needs warehouse_record_name updated
# to the new docnames. Dump the current warehouse list so the host can regenerate
# the fixture CSV offline. The mapping also needs `location_id` from Mosaic
# which is static; this dump only provides the warehouse side.
print("\n=== STEP C: Dump live warehouse snapshot for fixture regeneration ===")
try:
    # Get all leaf warehouses (is_group=0) that would appear in fixtures
    snap = frappe.db.sql(
        """
        SELECT w.name AS warehouse_record_name,
               w.warehouse_name,
               w.company,
               c.company_name,
               w.warehouse_type,
               w.disabled
        FROM `tabWarehouse` w
        LEFT JOIN `tabCompany` c ON c.name = w.company
        WHERE w.is_group = 0
        ORDER BY w.company, w.name
        """,
        as_dict=True,
    )
    out_path = "/tmp/s196_warehouse_snapshot.csv"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        if snap:
            writer = csv.DictWriter(f, fieldnames=list(snap[0].keys()))
            writer.writeheader()
            writer.writerows(snap)
    print(f"  Warehouse snapshot: {out_path} ({len(snap)} rows)")
except Exception as e:
    print(f"  Snapshot failed: {e}")


# ====== STEP D - Final verification ====================================
print("\n=== STEP D: Final verification ===")
# Count remaining `- BEI` leaf warehouses not owned by BEI parent
remaining = frappe.db.sql(
    """
    SELECT COUNT(*) FROM `tabWarehouse` w
    WHERE w.name LIKE '%%- BEI'
      AND w.is_group = 0
      AND w.disabled = 0
      AND w.company != %s
    """,
    BEI_PARENT_COMPANY,
)[0][0]
print(f"  Remaining `- BEI` leaf warehouses with non-BEI company: {remaining}")
if not DRY_RUN:
    print(f"  Expected: 0 after live rename (unless a rename failed)")

# ---- Summary -----------------------------------------------------------
print("\n" + "=" * 72)
summary = {
    "dry_run": DRY_RUN,
    "total_actions": len(actions),
    "planned_renames": len(plan),
    "by_status": {},
}
for row in actions:
    summary["by_status"][row["status"]] = summary["by_status"].get(row["status"], 0) + 1
print(json.dumps(summary, indent=2))

try:
    log_path = "/tmp/s196_wh_rename_actions.csv"
    with open(log_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["step", "action", "target", "status", "note"])
        w.writeheader()
        w.writerows(actions)
    print(f"\nAction log: {log_path}")
except Exception as e:
    print(f"CSV write failed: {e}")

print("\n" + "=" * 72)
print(f"S196 WH RENAME SWEEP DONE ({'DRY-RUN' if DRY_RUN else 'LIVE'})")
print("=" * 72)
frappe.destroy()
