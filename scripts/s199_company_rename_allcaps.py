#!/usr/bin/env python3
"""S199 — Rename 45 store Companies to ALL CAPS store-first pattern.

Pattern: <STORE NAME> - <CORP NAME> in ALL CAPS.
Corp suffix uses full legal name (e.g., TUNGSTEN CAPITAL HOLDINGS OPC).

Also renames the primary leaf warehouse for each Company to match.

Safety:
  - CONFIRM=yes env required for mutations
  - --dry-run flag previews without executing
  - Each rename in frappe.db.savepoint()
"""
import os
import sys
import json
import re
import csv

for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

DRY_RUN = "--dry-run" in sys.argv
CONFIRM = os.environ.get("CONFIRM", "").strip().lower() == "yes"

if not DRY_RUN and not CONFIRM:
    print("ERROR: CONFIRM=yes required. Use --dry-run to preview.")
    sys.exit(2)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

def _sp(raw):
    return re.sub(r"[^A-Za-z0-9_]", "_", raw)[:60]

COMPANY_RENAMES = [
    ("BEBANG PASEO INC.", "MEGAWORLD PASEO CENTER - BEBANG PASEO INC."),
    ("BEBANG PITX INC.", "MEGAWIDE PITX - BEBANG PITX INC."),
    ("BEBANG SMEO INC.", "SM EAST ORTIGAS - BEBANG SMEO INC."),
    ("BEBANG VENICE GRAND CANAL INC.", "MEGAWORLD VENICE GRAND CANAL - BEBANG VENICE GRAND CANAL INC."),
    ("BEBANG BF HOMES INC.", "BF HOMES - BEBANG BF HOMES INC."),
    ("BEBANG GRAND CENTRAL INC.", "SM GRAND CENTRAL - BEBANG GRAND CENTRAL INC."),
    ("BEBANG SMOA INC.", "SM MALL OF ASIA - BEBANG SMOA INC."),
    ("BEBANG FT INC.", "AYALA MALLS FAIRVIEW TERRACES - BEBANG FT INC."),
    ("BEBANG FESTIVAL INC.", "FESTIVAL MALL ALABANG - BEBANG FESTIVAL INC."),
    ("TASTECARTEL CORP.", "THE GRID ROCKWELL - TASTECARTEL CORP."),
    ("DLS Dessert Craft Inc.", "EVER COMMONWEALTH - DLS DESSERT CRAFT INC."),
    ("BEBANG NORTH EDSA INC.", "SM NORTH EDSA - BEBANG NORTH EDSA INC."),
    ("BEBANG MARKET MARKET INC.", "AYALA MARKET MARKET - BEBANG MARKET MARKET INC."),
    ("BEBANG LCT INC.", "LUCKY CHINATOWN - BEBANG LCT INC."),
    ("BEBANG SM MARIKINA INC.", "SM MARIKINA - BEBANG SM MARIKINA INC."),
    ("BEBANG STARMALL ALABANG INC.", "THE TERMINAL - BEBANG STARMALL ALABANG INC."),
    ("SM Megamall - Bebang Enterprise Inc.", "SM MEGAMALL - BEBANG ENTERPRISE INC."),
    ("SM Manila - Bebang Enterprise Inc.", "SM MANILA - BEBANG ENTERPRISE INC."),
    ("SM Southmall - Bebang Enterprise Inc.", "SM SOUTHMALL - BEBANG ENTERPRISE INC."),
    ("BEBANG SMV INC.", "SM VALENZUELA - BEBANG SMV INC."),
    ("Robinsons Antipolo - Bebang Enterprise Inc.", "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC."),
    ("Robinsons Imus - Bebang Mega Inc.", "ROBINSONS IMUS - BEBANG MEGA INC."),
    ("SM Tanza - Bebang Mega Inc.", "SM TANZA - BEBANG MEGA INC."),
    ("BEBANG SM BICUTAN INC.", "SM BICUTAN - BEBANG SM BICUTAN INC."),
    ("BEBANG MARILAO INC.", "SM MARILAO - BEBANG MARILAO INC."),
    ("BEBANG UP TOWN CENTER INC.", "AYALA UP TOWN CENTER - BEBANG UP TOWN CENTER INC."),
    ("Ayala Evo City - Bebang Mega Inc.", "AYALA EVO CITY - BEBANG MEGA INC."),
    ("Ayala Vermosa - Bebang Mega Inc.", "AYALA VERMOSA - BEBANG MEGA INC."),
    ("Robinsons Gen Trias - Bebang Mega Inc.", "ROBINSONS GENERAL TRIAS - BEBANG MEGA INC."),
    ("SM Caloocan - TAJ Food Corp.", "SM CALOOCAN - TAJ FOOD CORP."),
    ("BEBANG SMM INC.", "SM PULILAN - BEBANG SMM INC."),
    ("SM San Jose Del Monte - JL TRADE OPC", "SM SAN JOSE DEL MONTE - JL TRADE OPC"),
    ("SM Sangandaan - Tungsten Capital", "SM SANGANDAAN - TUNGSTEN CAPITAL HOLDINGS OPC"),
    ("Robinsons Galleria South - Tungsten Capital", "ROBINSONS GALLERIA SOUTH - TUNGSTEN CAPITAL HOLDINGS OPC"),
    ("B CUBED VENTURES CORP.", "CTTM TOMAS MORATO - B CUBED VENTURES CORP."),
    ("HFFM SOLENAD FOOD SERVICES INC.", "AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC."),
    ("DMD HOLDINGS INC.", "UP TOWN MALL BGC - DMD HOLDINGS INC."),
    ("TRICERN FOOD CORP.", "VISTA MALL TAGUIG - TRICERN FOOD CORP."),
    ("Gateway Mall - Tungsten Capital", "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC"),
    ("Sta Lucia - Bebang SM Marikina Inc.", "STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC."),
    ("RED TALDAWA FOODS OPC", "SM CLARK - RED TALDAWA FOODS OPC"),
    ("DVerde Calamba - TAJ Food Corp.", "D'VERDE CALAMBA - TAJ FOOD CORP."),
    ("SWEET HARMONY FOOD CORP.", "SM STA. ROSA - SWEET HARMONY FOOD CORP."),
    ("DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP.", "SM TAYTAY - DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP."),
    ("HALO-HALO TERMINAL FOOD CORP.", "NAIA T3 - HALO-HALO TERMINAL FOOD CORP."),
]

actions = []

def log(step, target, status, note=""):
    row = {"step": step, "target": target, "status": status, "note": note}
    actions.append(row)
    tag = "DRY" if DRY_RUN else status
    print(f"  [{tag:7s}] {step}: {target} {('- ' + note) if note else ''}")

# Capture abbr pre-rename
abbr_pre = {}
for old, new in COMPANY_RENAMES:
    if frappe.db.exists("Company", old):
        abbr_pre[old] = frappe.db.get_value("Company", old, "abbr")

print("=" * 72)
print(f"S199 ALL CAPS COMPANY RENAME - {'DRY-RUN' if DRY_RUN else 'LIVE'}")
print(f"Renames: {len(COMPANY_RENAMES)} | Abbr captured: {len(abbr_pre)}")
print("=" * 72)

# === STEP 1: Rename Companies ===
print(f"\n=== STEP 1: Rename {len(COMPANY_RENAMES)} Companies ===")
renamed = 0
for old, new in COMPANY_RENAMES:
    if not frappe.db.exists("Company", old):
        if frappe.db.exists("Company", new):
            log("CO", f"{old} -> {new}", "SKIP", "target already exists")
        else:
            log("CO", old, "SKIP", "not found")
        continue
    if old == new:
        log("CO", old, "SKIP", "old == new")
        continue
    if DRY_RUN:
        log("CO", f"{old} -> {new}", "DRY", "")
        continue
    sp = f"rn_co_{_sp(old[:30])}"
    try:
        frappe.db.savepoint(sp)
        frappe.rename_doc("Company", old, new, merge=False)
        frappe.db.commit()
        log("CO", f"{old} -> {new}", "DONE", "")
        renamed += 1
    except Exception as e:
        try:
            frappe.db.rollback(save_point=sp)
        except Exception:
            pass
        log("CO", f"{old} -> {new}", "FAIL", str(e)[:140])

# === STEP 2: Rename leaf warehouses to match ===
# After Company rename, the leaf warehouse that holds store inventory
# should also be renamed to ALL CAPS. The warehouse docname format is
# typically "<Store> - <Corp>" matching the Company name.
print(f"\n=== STEP 2: Rename leaf warehouses to ALL CAPS ===")
if not DRY_RUN:
    # Get all leaf warehouses for renamed Companies
    new_company_names = [new for _, new in COMPANY_RENAMES]
    for new_co in new_company_names:
        if not frappe.db.exists("Company", new_co):
            continue
        whs = frappe.get_all("Warehouse",
            filters={"company": new_co, "is_group": 0, "disabled": 0},
            fields=["name", "warehouse_name"],
        )
        for wh in whs:
            wh_name = wh["name"]
            wh_upper = wh_name.upper()
            # Skip structural warehouses
            if any(wh["warehouse_name"].startswith(p) for p in
                   ("Stores", "Finished Goods", "Goods In Transit",
                    "Work In Progress", "All Warehouses", "Raw Materials",
                    "In Transit", "TEST-")):
                continue
            if wh_name == wh_upper:
                continue  # already ALL CAPS
            if frappe.db.exists("Warehouse", wh_upper):
                log("WH", f"{wh_name} -> {wh_upper}", "SKIP", "target exists")
                continue
            sp = f"rn_wh_{_sp(wh_name[:25])}"
            try:
                frappe.db.savepoint(sp)
                frappe.rename_doc("Warehouse", wh_name, wh_upper, merge=False, force=True)
                frappe.db.commit()
                log("WH", f"{wh_name} -> {wh_upper}", "DONE", "")
            except Exception as e:
                try:
                    frappe.db.rollback(save_point=sp)
                except Exception:
                    pass
                log("WH", f"{wh_name} -> {wh_upper}", "FAIL", str(e)[:140])
else:
    # Dry-run: just list candidates
    for old, new in COMPANY_RENAMES:
        co = new if frappe.db.exists("Company", new) else old
        if not frappe.db.exists("Company", co):
            continue
        whs = frappe.get_all("Warehouse",
            filters={"company": co, "is_group": 0, "disabled": 0},
            fields=["name", "warehouse_name"],
        )
        for wh in whs:
            if any(wh["warehouse_name"].startswith(p) for p in
                   ("Stores", "Finished Goods", "Goods In Transit",
                    "Work In Progress", "All Warehouses", "Raw Materials",
                    "In Transit", "TEST-")):
                continue
            wh_upper = wh["name"].upper()
            if wh["name"] != wh_upper:
                log("WH", f"{wh['name']} -> {wh_upper}", "DRY", f"co={co}")

# === STEP 3: Fix Robisons typo in warehouse docname ===
print(f"\n=== STEP 3: Fix Robisons typo in warehouse docname ===")
TYPO_FIX = "Robisons Galleria South"
for wh_row in frappe.get_all("Warehouse", filters={"name": ["like", f"%{TYPO_FIX}%"]}, pluck="name"):
    corrected = wh_row.replace("Robisons", "ROBINSONS").upper()
    if wh_row == corrected:
        continue
    if frappe.db.exists("Warehouse", corrected):
        log("TYPO", f"{wh_row} -> {corrected}", "SKIP", "target exists")
        continue
    if DRY_RUN:
        log("TYPO", f"{wh_row} -> {corrected}", "DRY", "")
        continue
    sp = f"typo_{_sp(wh_row[:25])}"
    try:
        frappe.db.savepoint(sp)
        frappe.rename_doc("Warehouse", wh_row, corrected, merge=False, force=True)
        frappe.db.commit()
        log("TYPO", f"{wh_row} -> {corrected}", "DONE", "")
    except Exception as e:
        try:
            frappe.db.rollback(save_point=sp)
        except Exception:
            pass
        log("TYPO", f"{wh_row} -> {corrected}", "FAIL", str(e)[:140])

# === STEP 4: Abbr invariance check ===
print(f"\n=== STEP 4: Abbr invariance check ===")
if not DRY_RUN:
    violations = 0
    for old, expected in abbr_pre.items():
        new = next((n for o, n in COMPANY_RENAMES if o == old), None)
        if not new or not frappe.db.exists("Company", new):
            continue
        actual = frappe.db.get_value("Company", new, "abbr")
        if actual != expected:
            log("ABBR", new, "FAIL", f"was {expected}, now {actual}")
            violations += 1
        else:
            log("ABBR", new, "OK", f"preserved: {actual}")
    print(f"  Abbr violations: {violations}")

# === STEP 5: Verification ===
print(f"\n=== STEP 5: Final verification ===")
orderable = frappe.get_all("Company",
    filters={
        "entity_category": ["in", ["Store", "Commissary"]],
        "operational_status": ["in", ["Active", "Pre-Opening", "Temporarily Closed", "Pipeline"]],
    },
    pluck="name",
)
print(f"  Orderable Companies: {len(orderable)}")

# Check for mixed case among store Companies
mixed_case = [c for c in orderable if c != c.upper() and
    frappe.db.get_value("Company", c, "entity_category") == "Store" and
    frappe.db.get_value("Company", c, "mosaic_location_id")]
if mixed_case:
    print(f"  WARNING: {len(mixed_case)} store Companies still have mixed case:")
    for c in mixed_case:
        print(f"    {c}")
else:
    print("  All store Companies with mosaic_location_id are ALL CAPS")

# Summary
print("\n" + "=" * 72)
summary = {"dry_run": DRY_RUN, "total": len(actions), "by_status": {}}
for a in actions:
    s = a["status"]
    summary["by_status"][s] = summary["by_status"].get(s, 0) + 1
print(json.dumps(summary, indent=2))

try:
    out = "/tmp/s199_rename_actions.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["step", "target", "status", "note"])
        w.writeheader()
        w.writerows(actions)
    print(f"\nAction log: {out}")
except Exception as e:
    print(f"CSV write failed: {e}")

print(f"\nS199 DONE ({'DRY-RUN' if DRY_RUN else 'LIVE'})")
print("=" * 72)
frappe.destroy()
