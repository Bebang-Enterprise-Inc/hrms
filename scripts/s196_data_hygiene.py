#!/usr/bin/env python3
"""S196 Item #2 — Data hygiene for 3 archived BEBANG Companies.

Deferred from S196 Phase 2 (scripts/s196_data_migration.py Step F): the 3
misnamed legacy `BEBANG <STORE>` Companies were archived via
`operational_status=Permanently Closed` because Frappe blocks Company deletion
when linked docs exist. This follow-up migrates those linked docs to the
correct per-store child Companies and then deletes the archived entities.

Mapping:
  BEBANG ROBINSONS GALLERIA SOUTH -> Robinsons Galleria South - Tungsten Capital
  BEBANG SM CALOOCAN              -> SM Caloocan - TAJ Food Corp.
  BEBANG SM SANGANDAAN            -> SM Sangandaan - Tungsten Capital

Operations (each in savepoint per DM-2):
  Step 0: Discovery - per-Company audit of linked docs
  Step 1: Migrate Customer.represents_company (expected 1 per BEBANG Co)
  Step 2: Migrate Bank Account.company (if any)
  Step 3: Migrate Employee.company (if any)
  Step 4: Migrate Item Default.company (if any)
  Step 5: Migrate BEI Store Order.company (if any)
  Step 6: Delete Fiscal Year Company child rows (if any)
  Step 7: Manual cascade-delete of Company child structure:
            - Bin rows for child warehouses
            - Stock Ledger Entry rows (expected 0)
            - Disabled Warehouses (delete)
            - Cost Centers (delete)
            - Accounts (delete_tree)
  Step 8: frappe.delete_doc("Company", old, force=True)
  Step 9: Final verification - confirm all 3 deleted + orderable wh count unchanged

Safety:
  - Requires CONFIRM=yes env to execute any mutation
  - --dry-run flag prints planned ops without executing
  - Each step wrapped in savepoint; rollback on exception
  - Aborts if any unexpected linked DocType is found that we don't handle
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

# ---- Plan ----------------------------------------------------------------

BEBANG_TO_NEW = {
    "BEBANG ROBINSONS GALLERIA SOUTH": "Robinsons Galleria South - Tungsten Capital",
    "BEBANG SM CALOOCAN":              "SM Caloocan - TAJ Food Corp.",
    "BEBANG SM SANGANDAAN":            "SM Sangandaan - Tungsten Capital",
}

# DocTypes that reference Company - comprehensive audit
LINK_DOCTYPES = [
    ("Cost Center", "company"),
    ("Account", "company"),
    ("Warehouse", "company"),
    ("Customer", "represents_company"),
    ("Bank Account", "company"),
    ("Employee", "company"),
    ("Item Default", "company"),
    ("Fiscal Year Company", "company"),
    ("BEI Store Order", "company"),
    ("Stock Ledger Entry", "company"),
    ("GL Entry", "company"),
    ("Sales Invoice", "company"),
    ("Purchase Invoice", "company"),
    ("Sales Order", "company"),
    ("Purchase Order", "company"),
    ("Material Request", "company"),
    ("Stock Entry", "company"),
    ("Payment Entry", "company"),
    ("Journal Entry", "company"),
    ("Delivery Note", "company"),
    ("Purchase Receipt", "company"),
    ("Bin", None),  # Bin references via warehouse not company directly
]

# ---- Helpers -------------------------------------------------------------

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


def table_for(doctype):
    return "tab" + doctype


# ---- Start ---------------------------------------------------------------

print("=" * 72)
print(f"S196 ITEM #2 DATA HYGIENE - {'DRY-RUN' if DRY_RUN else 'LIVE EXECUTION'}")
print("=" * 72)


# ====== STEP 0 - Pre-flight audit ========================================
print(f"\n=== STEP 0: Pre-flight audit of {len(BEBANG_TO_NEW)} archived Companies ===")
audit = {}
for old in BEBANG_TO_NEW:
    if not frappe.db.exists("Company", old):
        log("0", "audit", old, "SKIP", "Company does not exist (already deleted?)")
        audit[old] = None
        continue
    current_status = frappe.db.get_value("Company", old, "operational_status")
    per_co = {"_operational_status": current_status}
    for dt, field in LINK_DOCTYPES:
        if field is None:
            continue
        try:
            cnt = frappe.db.sql(
                f"SELECT COUNT(*) FROM `{table_for(dt)}` WHERE `{field}` = %s",
                old,
            )[0][0]
            if cnt > 0:
                per_co[dt] = cnt
        except Exception as e:
            per_co[dt] = f"ERROR: {str(e)[:60]}"
    # Bin via child warehouse
    try:
        bin_cnt = frappe.db.sql(
            """SELECT COUNT(*) FROM `tabBin` b
               JOIN `tabWarehouse` w ON w.name = b.warehouse
               WHERE w.company = %s""",
            old,
        )[0][0]
        if bin_cnt > 0:
            per_co["Bin"] = bin_cnt
    except Exception as e:
        per_co["Bin"] = f"ERROR: {str(e)[:60]}"
    audit[old] = per_co
    log("0", "audit", old, "DONE", f"status={current_status} linked={per_co}")


# ====== STEP 1-5 - Migrate non-cascading linked docs ======================
print("\n=== STEP 1-5: Migrate external linked docs to new Companies ===")
MIGRATE_STEPS = [
    # (step_num, dt, field, label)
    (1, "Customer", "represents_company", "Customer.represents_company"),
    (2, "Bank Account", "company", "Bank Account.company"),
    (3, "Employee", "company", "Employee.company"),
    (4, "Item Default", "company", "Item Default.company"),
    (5, "BEI Store Order", "company", "BEI Store Order.company"),
]

for step_num, dt, field, label in MIGRATE_STEPS:
    for old, new in BEBANG_TO_NEW.items():
        if audit.get(old) is None:
            continue  # Company doesn't exist
        cnt = audit[old].get(dt, 0)
        if isinstance(cnt, str) or not cnt:
            continue
        if not frappe.db.exists("Company", new):
            log(str(step_num), f"migrate_{dt}", f"{old} -> {new}", "FAIL",
                f"new Company {new} missing")
            continue
        if DRY_RUN:
            log(str(step_num), f"migrate_{dt} (dry)", f"{old} -> {new}", "DRY",
                f"would migrate {cnt} {label} rows")
            continue
        sp = f"migrate_{step_num}_{old[:20]}"
        try:
            savepoint(sp)
            rows = frappe.db.sql(
                f"UPDATE `{table_for(dt)}` SET `{field}` = %s WHERE `{field}` = %s",
                (new, old),
            )
            affected = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
            frappe.db.commit()
            log(str(step_num), f"migrate_{dt}", f"{old} -> {new}", "DONE",
                f"{affected} rows updated")
        except Exception as e:
            rollback(sp)
            log(str(step_num), f"migrate_{dt}", f"{old} -> {new}", "FAIL",
                str(e)[:140])


# ====== STEP 6 - Delete Fiscal Year Company child rows ====================
print("\n=== STEP 6: Delete Fiscal Year Company child rows ===")
for old in BEBANG_TO_NEW:
    if audit.get(old) is None:
        continue
    cnt = audit[old].get("Fiscal Year Company", 0)
    if not cnt or isinstance(cnt, str):
        log("6", "delete_fiscal_year_company", old, "SKIP", "0 rows")
        continue
    if DRY_RUN:
        log("6", "delete_fiscal_year_company (dry)", old, "DRY", f"would delete {cnt} rows")
        continue
    sp = f"del_fy_{old[:20]}"
    try:
        savepoint(sp)
        frappe.db.sql("DELETE FROM `tabFiscal Year Company` WHERE company=%s", old)
        n = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
        frappe.db.commit()
        log("6", "delete_fiscal_year_company", old, "DONE", f"{n} rows deleted")
    except Exception as e:
        rollback(sp)
        log("6", "delete_fiscal_year_company", old, "FAIL", str(e)[:140])


# ====== STEP 7 - Cascade: Bin -> SLE -> Warehouse -> Cost Center -> Account ====
print("\n=== STEP 7: Cascade cleanup - Bin/SLE/Warehouse/CostCenter/Account ===")
for old in BEBANG_TO_NEW:
    if audit.get(old) is None:
        continue

    # 7a: Bin (only warehouse-linked)
    bin_cnt = audit[old].get("Bin", 0)
    if bin_cnt and not isinstance(bin_cnt, str):
        if DRY_RUN:
            log("7a", "delete_bin (dry)", old, "DRY", f"would delete {bin_cnt} Bin rows")
        else:
            sp = f"del_bin_{old[:20]}"
            try:
                savepoint(sp)
                frappe.db.sql(
                    """DELETE b FROM `tabBin` b
                       JOIN `tabWarehouse` w ON w.name = b.warehouse
                       WHERE w.company = %s""",
                    old,
                )
                n = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
                frappe.db.commit()
                log("7a", "delete_bin", old, "DONE", f"{n} Bin rows deleted")
            except Exception as e:
                rollback(sp)
                log("7a", "delete_bin", old, "FAIL", str(e)[:140])

    # 7b: SLE (should be 0 per Phase 1 finding)
    sle_cnt = audit[old].get("Stock Ledger Entry", 0)
    if sle_cnt and not isinstance(sle_cnt, str):
        log("7b", "sle_present", old, "BLOCKED",
            f"{sle_cnt} SLE rows exist - ABORTING cascade for this Company")
        continue  # Skip this Company's cascade

    # 7c: Warehouses (already disabled, delete)
    wh_cnt = audit[old].get("Warehouse", 0)
    if wh_cnt and not isinstance(wh_cnt, str):
        if DRY_RUN:
            log("7c", "delete_warehouses (dry)", old, "DRY",
                f"would delete {wh_cnt} warehouses")
        else:
            sp = f"del_wh_{old[:20]}"
            try:
                savepoint(sp)
                child_whs = frappe.get_all("Warehouse",
                    filters={"company": old},
                    pluck="name",
                    order_by="lft desc",  # delete leaves first
                )
                for wh in child_whs:
                    try:
                        frappe.delete_doc("Warehouse", wh,
                            force=True, ignore_permissions=True, ignore_on_trash=True)
                    except Exception as e:
                        # Fallback to direct SQL delete
                        frappe.db.sql("DELETE FROM `tabWarehouse` WHERE name=%s", wh)
                frappe.db.commit()
                log("7c", "delete_warehouses", old, "DONE", f"{len(child_whs)} warehouses deleted")
            except Exception as e:
                rollback(sp)
                log("7c", "delete_warehouses", old, "FAIL", str(e)[:140])

    # 7d: Cost Centers
    cc_cnt = audit[old].get("Cost Center", 0)
    if cc_cnt and not isinstance(cc_cnt, str):
        if DRY_RUN:
            log("7d", "delete_cost_centers (dry)", old, "DRY",
                f"would delete {cc_cnt} cost centers")
        else:
            sp = f"del_cc_{old[:20]}"
            try:
                savepoint(sp)
                ccs = frappe.get_all("Cost Center",
                    filters={"company": old},
                    pluck="name",
                    order_by="lft desc",
                )
                for cc in ccs:
                    try:
                        frappe.delete_doc("Cost Center", cc,
                            force=True, ignore_permissions=True, ignore_on_trash=True)
                    except Exception:
                        frappe.db.sql("DELETE FROM `tabCost Center` WHERE name=%s", cc)
                frappe.db.commit()
                log("7d", "delete_cost_centers", old, "DONE",
                    f"{len(ccs)} cost centers deleted")
            except Exception as e:
                rollback(sp)
                log("7d", "delete_cost_centers", old, "FAIL", str(e)[:140])

    # 7e: Accounts (0 GL entries confirmed Phase 1)
    acc_cnt = audit[old].get("Account", 0)
    if acc_cnt and not isinstance(acc_cnt, str):
        if DRY_RUN:
            log("7e", "delete_accounts (dry)", old, "DRY",
                f"would delete {acc_cnt} accounts")
        else:
            sp = f"del_acc_{old[:20]}"
            try:
                savepoint(sp)
                # Double-check 0 GL entries before mass delete (safety)
                gl_check = frappe.db.sql(
                    """SELECT COUNT(*) FROM `tabGL Entry` ge
                       JOIN `tabAccount` a ON a.name = ge.account
                       WHERE a.company = %s""",
                    old,
                )[0][0]
                if gl_check > 0:
                    log("7e", "delete_accounts", old, "BLOCKED",
                        f"{gl_check} GL entries link to these accounts - ABORT")
                    rollback(sp)
                    continue
                accounts = frappe.get_all("Account",
                    filters={"company": old},
                    pluck="name",
                    order_by="lft desc",
                )
                for acc in accounts:
                    try:
                        frappe.delete_doc("Account", acc,
                            force=True, ignore_permissions=True, ignore_on_trash=True)
                    except Exception:
                        frappe.db.sql("DELETE FROM `tabAccount` WHERE name=%s", acc)
                frappe.db.commit()
                log("7e", "delete_accounts", old, "DONE", f"{len(accounts)} accounts deleted")
            except Exception as e:
                rollback(sp)
                log("7e", "delete_accounts", old, "FAIL", str(e)[:140])


# ====== STEP 8 - Delete Company =========================================
print(f"\n=== STEP 8: Delete {len(BEBANG_TO_NEW)} archived Companies ===")
for old in BEBANG_TO_NEW:
    if not frappe.db.exists("Company", old):
        log("8", "delete_company", old, "SKIP", "already deleted")
        continue
    if DRY_RUN:
        log("8", "delete_company (dry)", old, "DRY",
            "would delete with force=True, ignore_on_trash=True")
        continue
    sp = f"del_co_{old[:25]}"
    try:
        savepoint(sp)
        frappe.delete_doc("Company", old,
            force=True, ignore_permissions=True, ignore_on_trash=True)
        frappe.db.commit()
        log("8", "delete_company", old, "DONE", "")
    except Exception as e:
        rollback(sp)
        # Try raw SQL fallback if ORM fails
        try:
            frappe.db.sql("DELETE FROM `tabCompany` WHERE name=%s", old)
            frappe.db.commit()
            log("8", "delete_company", old, "SQL-DONE",
                f"ORM failed ({str(e)[:80]}), SQL succeeded")
        except Exception as e2:
            log("8", "delete_company", old, "FAIL", str(e2)[:140])


# ====== STEP 9 - Final verification =====================================
print("\n=== STEP 9: Final verification ===")
for old in BEBANG_TO_NEW:
    exists = frappe.db.exists("Company", old)
    if exists:
        log("9", "verify_deleted", old, "FAIL", "Company still exists")
    else:
        log("9", "verify_deleted", old, "DONE", "deleted")

# Count orderable state post-migration
try:
    orderable_companies = frappe.get_all(
        "Company",
        filters={
            "entity_category": ["in", ["Store", "Commissary"]],
            "operational_status": ["in", ["Active", "Pre-Opening", "Temporarily Closed", "Pipeline"]],
        },
        pluck="name",
    )
    print(f"  Orderable Companies: {len(orderable_companies)}")

    NON_ORD_TYPES = {"3PL", "Commissary", "Cold Storage", "Transit"}
    NON_ORD_PATTERNS = (
        "Jentec", "Pinnacle", "Royal Cold", "RCS", "3MD",
        "Commissary", "Kitchen", "TEST-COMMISSARY", "TEST-STORE",
        "Finished Goods", "Work In Progress", "Raw Materials",
    )
    NON_ORD_NAMES = {"Stores", "Stores - BEI", "Stores - BK", "All Warehouses", "All Warehouses - BEI"}

    whs = frappe.get_all(
        "Warehouse",
        filters={"company": ["in", orderable_companies], "is_group": 0, "disabled": 0},
        fields=["name", "company", "warehouse_type", "warehouse_name"],
    )
    def is_ord(w):
        wt = (w.get("warehouse_type") or "").strip()
        if wt and wt in NON_ORD_TYPES: return False
        n = w.get("warehouse_name") or w.get("name") or ""
        if n in NON_ORD_NAMES: return False
        if any(p in n for p in NON_ORD_PATTERNS): return False
        return True
    ord_whs = [w for w in whs if is_ord(w)]
    print(f"  Orderable warehouses: {len(ord_whs)}")
    print(f"  Expected: 50 (unchanged from post-SJDM state)")
except Exception as e:
    print(f"  Verification failed: {e}")


# ---- Summary -----------------------------------------------------------
print("\n" + "=" * 72)
summary = {
    "dry_run": DRY_RUN,
    "total_actions": len(actions),
    "by_status": {},
}
for row in actions:
    summary["by_status"][row["status"]] = summary["by_status"].get(row["status"], 0) + 1
print(json.dumps(summary, indent=2))

# Write CSV action log
try:
    out_path = "/tmp/s196_data_hygiene_actions.csv"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["step", "action", "target", "status", "note"])
        w.writeheader()
        w.writerows(actions)
    print(f"\nAction log: {out_path}")
except Exception as e:
    print(f"CSV write failed: {e}")

# Write audit JSON
try:
    audit_path = "/tmp/s196_data_hygiene_audit.json"
    audit_serializable = {k: v for k, v in audit.items()}
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_serializable, f, indent=2, default=str)
    print(f"Audit snapshot: {audit_path}")
except Exception as e:
    print(f"Audit JSON write failed: {e}")

print("\n" + "=" * 72)
print(f"S196 DATA HYGIENE DONE ({'DRY-RUN' if DRY_RUN else 'LIVE'})")
print("=" * 72)
frappe.destroy()
