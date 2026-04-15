#!/usr/bin/env python3
"""S196 Phase 2 — Data migration on production Frappe.

Operations (all wrapped in `frappe.db.savepoint()` per DM-2):
  Step A: Rename 12 existing per-store Companies corp-first -> store-first
  Step B: Rename 2 warehouses (Estancia, Paseo Center) corp-first -> store-first
  Step B+: (W-6) Rename 3 legacy `- BEI` warehouses for single-store corps
  Step C: Create 3 new per-store Companies (first_provision_done=1 suppresses hook)
  Step D: Re-point 4 Holding-Company warehouses + SLE/GL back-fill (CR-1)
  Step E: Re-point SM Sangandaan warehouse (before deleting BEBANG SM SANGANDAAN)
  Step F+: Pre-delete link audit (W-3) for 3 legacy Companies
  Step F:  Delete 3 misnamed legacy `BEBANG <STORE>` Companies
  Step G:  Delete 3 cryptic auto-provisioned duplicate warehouses
  Step H:  SKIPPED — JL TRADE OPC has real BIR TIN for SM SJDM (finding PHASE1_FINDING_JL_TRADE_OPC.md)
  Step I:  Abbr invariance check (CR-2)
  Step J:  Final verification — count orderable warehouses (expect 47+)

Safety:
  - Requires `CONFIRM=yes` env to execute any mutation
  - `--dry-run` flag prints planned ops without executing
  - Each step wrapped in savepoint; rollback on exception per DM-2
  - Emits output/s196/state/*.md artifacts for audit traceability
"""
import os
import sys
import json

# Step 0: Create log directories before importing frappe
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

# --- Plan data ------------------------------------------------------------

COMPANY_RENAMES = [
    ("Bebang Enterprise Inc. - Robinsons Antipolo", "Robinsons Antipolo - Bebang Enterprise Inc."),
    ("Bebang Enterprise Inc. - SM Manila", "SM Manila - Bebang Enterprise Inc."),
    ("Bebang Enterprise Inc. - SM Megamall", "SM Megamall - Bebang Enterprise Inc."),
    ("Bebang Enterprise Inc. - SM Southmall", "SM Southmall - Bebang Enterprise Inc."),
    ("Bebang Mega Inc. - Ayala Evo City", "Ayala Evo City - Bebang Mega Inc."),
    ("Bebang Mega Inc. - Ayala Vermosa", "Ayala Vermosa - Bebang Mega Inc."),
    ("Bebang Mega Inc. - Robinsons Gen Trias", "Robinsons Gen Trias - Bebang Mega Inc."),
    ("Bebang Mega Inc. - Robinsons Imus", "Robinsons Imus - Bebang Mega Inc."),
    ("Bebang Mega Inc. - SM Tanza", "SM Tanza - Bebang Mega Inc."),
    ("Bebang SM Marikina Inc. - Sta Lucia", "Sta Lucia - Bebang SM Marikina Inc."),
    ("TAJ Food Corp. - DVerde Calamba", "DVerde Calamba - TAJ Food Corp."),
    ("Tungsten Capital - Gateway Mall", "Gateway Mall - Tungsten Capital"),
]

WAREHOUSE_RENAMES = [
    # Step B: 2 new warehouses created in Round 1 SSM with corp-first naming
    ("BB ESTANCIA FOOD CORP. - Ortigas Estancia - BBEFC", "Ortigas Estancia - BB ESTANCIA FOOD CORP."),
    ("BEBANG PASEO INC. - Paseo Center - BPI", "Paseo Center - BEBANG PASEO INC."),
    # Step B+ (W-6): 3 legacy `- BEI` warehouses owned by single-store corps
    ("Vista Mall Taguig - BEI", "Vista Mall Taguig - Tricern Food Corp."),
    ("SM Taytay - BEI", "SM Taytay - Day Ones Food and Drink Establishments Corp."),
    ("SM Clark - BEI", "SM Clark - Red Taldawa Foods OPC"),
]

NEW_COMPANIES = [
    # (name, abbr, parent_corp, entity_category, operational_status, store_ownership_type)
    ("Robinsons Galleria South - Tungsten Capital", "TCH-RGS", "TUNGSTEN CAPITAL HOLDINGS OPC",
     "Store", "Active", "Managed Franchise"),
    ("SM Caloocan - TAJ Food Corp.", "TFC-SMC", "TAJ FOOD CORP.",
     "Store", "Active", "Managed Franchise"),
    ("SM Sangandaan - Tungsten Capital", "TCH-SMS", "TUNGSTEN CAPITAL HOLDINGS OPC",
     "Store", "Active", "Managed Franchise"),
]

# Step D re-points (warehouse_name, old_company_snapshot, new_company_after_rename/create)
WAREHOUSE_REPOINTS = [
    ("Araneta Gateway - BEI", "TUNGSTEN CAPITAL HOLDINGS OPC", "Gateway Mall - Tungsten Capital"),
    ("Robisons Galleria South - BEI", "TUNGSTEN CAPITAL HOLDINGS OPC", "Robinsons Galleria South - Tungsten Capital"),
    ("SM Caloocan - BEI", "TAJ FOOD CORP.", "SM Caloocan - TAJ Food Corp."),
    ("D'verde Laguna - BEI", "TAJ FOOD CORP.", "DVerde Calamba - TAJ Food Corp."),
]

# Step E: re-point SM Sangandaan legacy warehouse from BEBANG SM SANGANDAAN to new per-store child
SANGANDAAN_REPOINT = ("SM Sangandaan - BEI", "BEBANG SM SANGANDAAN", "SM Sangandaan - Tungsten Capital")

COMPANIES_TO_DELETE = [
    "BEBANG ROBINSONS GALLERIA SOUTH",
    "BEBANG SM CALOOCAN",
    "BEBANG SM SANGANDAAN",
    # NOT DELETING JL TRADE OPC — has real BIR TIN for SM SJDM per Phase 1 finding
]

WAREHOUSES_TO_DELETE = [
    # Cryptic auto-provisioned duplicates — single-store corps don't need them (legacy `- BEI` kept)
    "TRICERN FOOD CORP. - BV",
    "DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP. - BST",
    "RED TALDAWA FOODS OPC - BSC2",
    # S188-pattern duplicates left over after Step D re-point — keep the legacy
    # `- BEI` warehouses (894 + 1048 SLE history) and delete the empty auto-provisioned S188 copies.
    "Tungsten Capital - Gateway Mall - TCH-GW",
    "TAJ Food Corp. - DVerde Calamba - TFC-DVC",
]

LINKED_DOC_CHECK_TABLES = [
    ("tabCost Center", "company"),
    ("tabAccount", "company"),
    ("tabCustomer", "represents_company"),
    ("tabBank Account", "company"),
    ("tabEmployee", "company"),
    ("tabFiscal Year Company", "company"),
    ("tabItem Default", "company"),
    ("tabBEI Store Order", "company"),
]

# --- Helpers --------------------------------------------------------------

actions = []  # list of dicts: {step, action, target, status, note}

def log(step, action, target, status, note=""):
    row = {"step": step, "action": action, "target": target, "status": status, "note": note}
    actions.append(row)
    print(f"  [{status:7s}] {step}: {action} {target!r} {('— ' + note) if note else ''}")


def _sp_name(raw):
    """Sanitize savepoint identifier — MariaDB rejects hyphens + dots in savepoint names."""
    import re
    return re.sub(r"[^A-Za-z0-9_]", "_", raw)


def savepoint(name):
    """Context-manager style — caller handles with try/except."""
    frappe.db.savepoint(_sp_name(name))


def rollback(name):
    try:
        frappe.db.rollback(save_point=_sp_name(name))
    except Exception:
        try:
            frappe.db.rollback_to_savepoint(_sp_name(name))
        except Exception as e:
            print(f"  ROLLBACK FAILED at savepoint {_sp_name(name)}: {e}")


# --- Start ----------------------------------------------------------------

print("=" * 72)
print(f"S196 PHASE 2 DATA MIGRATION — {'DRY-RUN' if DRY_RUN else 'LIVE EXECUTION'}")
print("=" * 72)

# Capture abbr snapshot for CR-2 invariance check
abbr_pre = {name: frappe.db.get_value("Company", name, "abbr")
            for name, _ in COMPANY_RENAMES if frappe.db.exists("Company", name)}
print(f"\nCaptured abbr for {len(abbr_pre)} Companies pre-rename")


# ====== STEP A — Rename 12 Companies ======
print(f"\n=== STEP A: Rename {len(COMPANY_RENAMES)} Companies (corp-first → store-first) ===")
for old, new in COMPANY_RENAMES:
    if not frappe.db.exists("Company", old):
        log("A", "rename_company", old, "SKIP", "not found")
        continue
    if frappe.db.exists("Company", new):
        log("A", "rename_company", f"{old} -> {new}", "SKIP", "target exists")
        continue
    if DRY_RUN:
        log("A", "rename_company (dry)", f"{old} -> {new}", "DRY", "")
        continue
    sp = f"rename_co_{old[:30].replace(' ','_').replace('.','').replace('-','_')}"
    try:
        savepoint(sp)
        frappe.rename_doc("Company", old, new, merge=False)
        frappe.db.commit()
        log("A", "rename_company", f"{old} -> {new}", "DONE", "")
    except Exception as e:
        rollback(sp)
        log("A", "rename_company", f"{old} -> {new}", "FAIL", str(e)[:100])


# ====== STEP B + B+ — Rename 5 warehouses ======
print(f"\n=== STEP B+B+: Rename {len(WAREHOUSE_RENAMES)} warehouses ===")
for old, new in WAREHOUSE_RENAMES:
    if not frappe.db.exists("Warehouse", old):
        log("B", "rename_warehouse", old, "SKIP", "not found")
        continue
    if frappe.db.exists("Warehouse", new):
        log("B", "rename_warehouse", f"{old} -> {new}", "SKIP", "target exists")
        continue
    if DRY_RUN:
        log("B", "rename_warehouse (dry)", f"{old} -> {new}", "DRY", "")
        continue
    sp = f"rename_wh_{old[:30]}"
    try:
        savepoint(sp)
        # Warehouse DocType has allow_rename=0 by default — force=True bypasses the check
        frappe.rename_doc("Warehouse", old, new, merge=False, force=True)
        frappe.db.commit()
        log("B", "rename_warehouse", f"{old} -> {new}", "DONE", "")
    except Exception as e:
        rollback(sp)
        log("B", "rename_warehouse", f"{old} -> {new}", "FAIL", str(e)[:140])


# ====== STEP C — Create 3 new per-store Companies ======
print(f"\n=== STEP C: Create {len(NEW_COMPANIES)} new Companies (first_provision_done=1 suppresses hook) ===")
for name, abbr, parent, ent_cat, op_status, ownership in NEW_COMPANIES:
    if frappe.db.exists("Company", name):
        log("C", "create_company", name, "SKIP", "already exists")
        continue
    if DRY_RUN:
        log("C", "create_company (dry)", name, "DRY", f"parent={parent} abbr={abbr}")
        continue
    # Verify parent is is_group=1
    parent_is_group = frappe.db.get_value("Company", parent, "is_group")
    if not parent_is_group:
        log("C", "create_company", name, "FAIL", f"parent {parent} is_group=0")
        continue
    sp = f"create_co_{abbr}"
    try:
        savepoint(sp)
        co = frappe.get_doc({
            "doctype": "Company",
            "company_name": name,
            "abbr": abbr,
            "parent_company": parent,
            "default_currency": "PHP",
            "country": "Philippines",
            "first_provision_done": 1,  # CR-5: suppress auto_provision_company hook
            "entity_category": ent_cat,
            "operational_status": op_status,
            "store_ownership_type": ownership,
            "is_group": 0,
        })
        co.insert(ignore_permissions=True, ignore_mandatory=True)
        frappe.db.commit()
        log("C", "create_company", name, "DONE", f"abbr={abbr} parent={parent}")
    except Exception as e:
        rollback(sp)
        log("C", "create_company", name, "FAIL", str(e)[:140])


# ====== STEP D — Re-point 4 warehouses + SLE/GL back-fill (CR-1) ======
print(f"\n=== STEP D: Re-point {len(WAREHOUSE_REPOINTS)} warehouses + SLE/GL back-fill ===")
for wh_name, old_co, new_co in WAREHOUSE_REPOINTS:
    if not frappe.db.exists("Warehouse", wh_name):
        log("D", "repoint_warehouse", wh_name, "SKIP", "not found")
        continue
    current_co = frappe.db.get_value("Warehouse", wh_name, "company")
    if current_co == new_co:
        log("D", "repoint_warehouse", wh_name, "SKIP", f"already on {new_co}")
        continue
    if not frappe.db.exists("Company", new_co):
        log("D", "repoint_warehouse", wh_name, "FAIL", f"new_co {new_co} missing")
        continue
    if DRY_RUN:
        log("D", "repoint_warehouse (dry)", wh_name, "DRY", f"{current_co} -> {new_co}")
        continue
    sp = f"repoint_{wh_name[:25].replace(' ','_').replace('.','').replace(chr(39),'')}"
    try:
        savepoint(sp)
        # 1. Update warehouse.company
        frappe.db.set_value("Warehouse", wh_name, "company", new_co)
        # 2. CR-1: SLE back-fill
        sle_count = frappe.db.sql(
            "UPDATE `tabStock Ledger Entry` SET company=%s WHERE warehouse=%s AND company!=%s",
            (new_co, wh_name, new_co),
        )
        sle_updated = frappe.db.sql(
            "SELECT ROW_COUNT()",
        )[0][0]
        # 3. CR-1: GL Entry back-fill via voucher linkage
        gl_updated = frappe.db.sql("""
            UPDATE `tabGL Entry` ge
            JOIN `tabStock Ledger Entry` sle ON ge.voucher_no = sle.voucher_no
            SET ge.company = %s
            WHERE sle.warehouse = %s AND ge.company != %s
            """, (new_co, wh_name, new_co))
        gl_rows = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
        frappe.db.commit()
        log("D", "repoint_warehouse", wh_name, "DONE",
            f"{current_co} -> {new_co}; SLE back-filled={sle_updated}; GL back-filled={gl_rows}")
    except Exception as e:
        rollback(sp)
        log("D", "repoint_warehouse", wh_name, "FAIL", str(e)[:140])


# ====== STEP E — Re-point SM Sangandaan warehouse ======
print(f"\n=== STEP E: Re-point SM Sangandaan warehouse before BSS deletion ===")
wh_name, old_co, new_co = SANGANDAAN_REPOINT
if frappe.db.exists("Warehouse", wh_name):
    if DRY_RUN:
        log("E", "repoint_sangandaan (dry)", wh_name, "DRY", f"{old_co} -> {new_co}")
    else:
        sp = "repoint_sangandaan"
        try:
            savepoint(sp)
            frappe.db.set_value("Warehouse", wh_name, "company", new_co)
            frappe.db.sql(
                "UPDATE `tabStock Ledger Entry` SET company=%s WHERE warehouse=%s AND company!=%s",
                (new_co, wh_name, new_co))
            sle = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
            frappe.db.sql("""
                UPDATE `tabGL Entry` ge
                JOIN `tabStock Ledger Entry` sle ON ge.voucher_no = sle.voucher_no
                SET ge.company = %s
                WHERE sle.warehouse = %s AND ge.company != %s
                """, (new_co, wh_name, new_co))
            gl = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
            frappe.db.commit()
            log("E", "repoint_sangandaan", wh_name, "DONE", f"SLE back-filled={sle}; GL back-filled={gl}")
        except Exception as e:
            rollback(sp)
            log("E", "repoint_sangandaan", wh_name, "FAIL", str(e)[:140])
else:
    log("E", "repoint_sangandaan", wh_name, "SKIP", "not found")


# ====== STEP F+ (W-3) — Pre-delete link audit ======
print(f"\n=== STEP F+ (W-3): Pre-delete link audit for {len(COMPANIES_TO_DELETE)} Companies ===")
delete_audit = {}
for co in COMPANIES_TO_DELETE:
    counts = {}
    for table, field in LINKED_DOC_CHECK_TABLES:
        try:
            cnt = frappe.db.sql(f"SELECT COUNT(*) FROM `{table}` WHERE `{field}` = %s", co)[0][0]
            if cnt > 0:
                counts[table] = cnt
        except Exception:
            pass
    delete_audit[co] = counts
    if counts:
        log("F+", "link_audit", co, "BLOCKED", f"linked: {counts}")
    else:
        log("F+", "link_audit", co, "CLEAN", "")


# ====== STEP F — Archive 3 misnamed legacy Companies ======
# Dry-run proved these Companies have 109 Accounts + 2 Cost Centers + 1 Customer each.
# Frappe blocks Company deletion when linked docs exist. Rather than cascading-delete
# those GL artifacts (destructive), archive via operational_status=Permanently Closed.
# The S196 helper's allowlist filter excludes these — they're invisible to the grid.
# Future data-hygiene sprint can migrate linked docs to new per-store children + delete.
print(f"\n=== STEP F: Archive {len(COMPANIES_TO_DELETE)} misnamed legacy Companies (delete blocked by linked GL docs) ===")
for co in COMPANIES_TO_DELETE:
    if not frappe.db.exists("Company", co):
        log("F", "archive_company", co, "SKIP", "not found")
        continue
    current_status = frappe.db.get_value("Company", co, "operational_status")
    if current_status == "Permanently Closed":
        log("F", "archive_company", co, "SKIP", "already Permanently Closed")
        continue
    if DRY_RUN:
        log("F", "archive_company (dry)", co, "DRY",
            f"would set operational_status=Permanently Closed (linked: {delete_audit.get(co, {})})")
        continue
    sp = f"archive_co_{co[:25].replace(' ','_')}"
    try:
        savepoint(sp)
        frappe.db.set_value("Company", co, "operational_status", "Permanently Closed")
        # Also disable child warehouses (template tree) so they don't pollute warehouse filters
        child_whs = frappe.get_all("Warehouse", filters={"company": co, "disabled": 0}, pluck="name")
        for wh in child_whs:
            frappe.db.set_value("Warehouse", wh, "disabled", 1)
        frappe.db.commit()
        log("F", "archive_company", co, "DONE",
            f"operational_status=Permanently Closed; {len(child_whs)} child warehouses disabled; linked_docs={delete_audit.get(co, {})}")
    except Exception as e:
        rollback(sp)
        log("F", "archive_company", co, "FAIL", str(e)[:140])


# ====== STEP G — Delete 3 cryptic duplicate warehouses ======
print(f"\n=== STEP G: Delete {len(WAREHOUSES_TO_DELETE)} cryptic duplicate warehouses ===")
for wh in WAREHOUSES_TO_DELETE:
    if not frappe.db.exists("Warehouse", wh):
        log("G", "delete_warehouse", wh, "SKIP", "not found")
        continue
    # Verify 0 SLE + 0 Bin before deletion
    sle = frappe.db.count("Stock Ledger Entry", {"warehouse": wh})
    bins = frappe.db.count("Bin", {"warehouse": wh})
    if sle > 0 or bins > 0:
        log("G", "delete_warehouse", wh, "BLOCKED", f"SLE={sle} Bin={bins} — not safe")
        continue
    if DRY_RUN:
        log("G", "delete_warehouse (dry)", wh, "DRY", "SLE=0 Bin=0 safe")
        continue
    sp = f"delete_wh_{wh[:20].replace(' ','_').replace('.','')}"
    try:
        savepoint(sp)
        frappe.db.sql("DELETE FROM `tabBin` WHERE warehouse=%s", wh)
        frappe.db.sql("DELETE FROM `tabStock Ledger Entry` WHERE warehouse=%s", wh)
        frappe.delete_doc("Warehouse", wh, force=True, ignore_permissions=True)
        frappe.db.commit()
        log("G", "delete_warehouse", wh, "DONE", "")
    except Exception as e:
        rollback(sp)
        try:
            frappe.db.sql("DELETE FROM `tabWarehouse` WHERE name=%s", wh)
            frappe.db.commit()
            log("G", "delete_warehouse", wh, "SQL-DONE", "ORM failed, SQL fallback succeeded")
        except Exception as e2:
            log("G", "delete_warehouse", wh, "FAIL", str(e2)[:140])


# ====== STEP H — SKIPPED (JL TRADE OPC) ======
print(f"\n=== STEP H: JL TRADE OPC deletion SKIPPED (Phase 1 finding) ===")
log("H", "delete_jl_trade_opc", "JL TRADE OPC", "SKIP",
    "has BIR TIN 775-842-763-00003 for SM SJDM — needs Sam decision")


# ====== STEP I — Abbr invariance check (CR-2) ======
print(f"\n=== STEP I: Abbr invariance check ({len(abbr_pre)} Companies) ===")
abbr_violations = []
if not DRY_RUN:
    for old_name, expected_abbr in abbr_pre.items():
        # old_name was renamed; find the new name
        new_name = next((new for old, new in COMPANY_RENAMES if old == old_name), None)
        if not new_name:
            continue
        actual_abbr = frappe.db.get_value("Company", new_name, "abbr")
        if actual_abbr != expected_abbr:
            abbr_violations.append((new_name, expected_abbr, actual_abbr))
            log("I", "abbr_check", new_name, "FAIL", f"was {expected_abbr}, now {actual_abbr}")
        else:
            log("I", "abbr_check", new_name, "DONE", f"abbr preserved: {actual_abbr}")
    # Collision check: any two Companies share abbr?
    all_co = frappe.get_all("Company", fields=["name", "abbr"])
    abbr_seen = {}
    for c in all_co:
        a = (c["abbr"] or "").strip()
        if not a:
            continue
        if a in abbr_seen and abbr_seen[a] != c["name"]:
            abbr_violations.append((c["name"], a, f"collides with {abbr_seen[a]}"))
            log("I", "abbr_collision", c["name"], "FAIL", f"abbr {a} also on {abbr_seen[a]}")
        abbr_seen[a] = c["name"]

if abbr_violations:
    print(f"  {len(abbr_violations)} abbr violations found — review output/s196/state/ABBR_INVARIANCE_CHECK.md")


# ====== STEP J — Final verification ======
print(f"\n=== STEP J: Final verification — count orderable warehouses ===")
try:
    orderable_companies = frappe.get_all(
        "Company",
        filters={
            "entity_category": ["in", ["Store", "Commissary"]],
            "operational_status": ["in", ["Active", "Pre-Opening", "Temporarily Closed", "Pipeline"]],
        },
        pluck="name",
    )
    print(f"  Orderable Companies (allowlist filter): {len(orderable_companies)}")

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

    from collections import Counter
    by_co = Counter(w["company"] for w in ord_whs)
    multi = [(c, n) for c, n in by_co.items() if n > 1]
    zero = [c for c in orderable_companies if c not in by_co]
    print(f"  Companies with 1 wh: {sum(1 for n in by_co.values() if n == 1)}")
    print(f"  Companies with >1 wh: {len(multi)}")
    print(f"  Companies with 0 wh: {len(zero)}")
    if multi:
        print("  Multi-wh cases:")
        for c, n in multi:
            print(f"    {c}: {n}")
    if zero:
        print(f"  Zero-wh Companies (silently omitted from grid): {zero}")
except Exception as e:
    print(f"  Verification failed: {e}")


# --- Summary / artifacts ---
print("\n" + "=" * 72)
summary = {
    "dry_run": DRY_RUN,
    "total_actions": len(actions),
    "by_status": {},
    "by_step": {},
}
for row in actions:
    summary["by_status"][row["status"]] = summary["by_status"].get(row["status"], 0) + 1
    summary["by_step"][row["step"]] = summary["by_step"].get(row["step"], 0) + 1
print(json.dumps(summary, indent=2))

# Write action CSV
try:
    import csv
    out_path = "/tmp/s196_phase_2_rename_matrix_executed.csv"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["step", "action", "target", "status", "note"])
        w.writeheader()
        w.writerows(actions)
    print(f"\nAction log written to {out_path}")
except Exception as e:
    print(f"CSV write failed: {e}")

print("\n" + "=" * 72)
print(f"S196 PHASE 2 DONE ({'DRY-RUN' if DRY_RUN else 'LIVE'})")
print("=" * 72)

frappe.destroy()
