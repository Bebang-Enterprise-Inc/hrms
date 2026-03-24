"""Import BOMs from cleanroom CSV data into Frappe production.

Sprint S108 — fixes empty commissary production item dropdown.

Usage (via bench execute on EC2):
    bench execute scripts.data.import_bom_from_cleanroom.run

Or standalone (with frappe initialized):
    python -c "import frappe; frappe.connect('hq.bebang.ph'); exec(open('scripts/data/import_bom_from_cleanroom.py').read()); run()"
"""

import csv
from pathlib import Path

import frappe
from frappe.utils import flt

# ============================================================================
# HARDCODED CROSSWALK — fact-checked 2026-03-24 against live Frappe production
# BOM CSV uses FGRM## codes that DO NOT exist in Frappe.
# Frappe uses MN### codes for menu products (Finished Goods).
# ============================================================================
FGRM_TO_MN = {
    "FGRM01": "MN001",  # Presidential
    "FGRM02": "MN003",  # Halukay Ube (Frappe: HALOKAY UBE)
    "FGRM03": "MN002",  # Mango Graham Caramel
    # FGRM04 SKIPPED — no MN item for Banana Cinnamon (FG002 is ingredient only)
    "FGRM06": "MN005",  # Buko Fruit Salad
    "FGRM07": "MN006",  # Melon
    "FGRM08": "MN007",  # Buko Pandan
    "FGRM09": "MN008",  # Strawberry Pistachio
    "FGRM10": "MN009",  # Blueberry Pistachio
    "FGRM11": "MN010",  # Matcharap
    "FGRM12": "MN011",  # Cookie Crumble
    "FGRM13": "MN012",  # So Corny
    "FGRM14": "MN013",  # Mango Classic
    "FGRM15": "MN014",  # Special
    "FGRM21": "MN015",  # Choco Brownie
}

# RM codes confirmed MISSING from Frappe — skip BOM lines using these
MISSING_RM_CODES = {"FG006-B", "M006-A", "PM004-B", "RM007-A"}

COMPANY = "Bebang Kitchen Inc."

# File paths relative to bench root (F:\Dropbox\Projects\BEI-ERP)
MAIN_BOM_CSV = "data/_CLEANROOM/batch_2026-02-28_cleanroom_v1/cleaned/ready/com_g07_bom_fg_final_clean_READY.csv"
POP_LAMIG_CSV = "data/_CLEANROOM/agent_runs/2026-03-10_pop_lamig_bom/POP_LAMIG_BOM_CANONICAL_MAPPING.csv"


def _bom_exists(item_code):
    """Check if any non-cancelled BOM exists for this item."""
    return frappe.db.exists("BOM", {"item": item_code, "docstatus": ["!=", 2]})


def _item_exists(item_code):
    """Check if item exists in Frappe."""
    return frappe.db.exists("Item", item_code)


def _get_item_uom(item_code):
    """Get the stock UOM for an item."""
    return frappe.db.get_value("Item", item_code, "stock_uom") or "KG"


def _create_bom(item_code, item_name, rm_lines):
    """Create and submit a BOM for a finished goods item."""
    if _bom_exists(item_code):
        print(f"  SKIP {item_code} ({item_name}) — BOM already exists")
        return "skipped"

    if not _item_exists(item_code):
        print(f"  SKIP {item_code} ({item_name}) — item not in Frappe")
        return "skipped"

    bom = frappe.new_doc("BOM")
    bom.item = item_code
    bom.quantity = 1
    bom.is_active = 1
    bom.is_default = 1
    bom.company = COMPANY

    added = 0
    skipped_rms = []
    for rm in rm_lines:
        rm_code = rm["rm_code"]
        if rm_code in MISSING_RM_CODES:
            skipped_rms.append(rm_code)
            continue
        if not _item_exists(rm_code):
            skipped_rms.append(rm_code)
            continue

        qty = flt(rm["qty"])
        if qty <= 0:
            continue

        uom = rm.get("uom") or _get_item_uom(rm_code)
        bom.append(
            "items",
            {
                "item_code": rm_code,
                "qty": qty,
                "uom": uom,
                "stock_uom": _get_item_uom(rm_code),
                "conversion_factor": 1,
            },
        )
        added += 1

    if added == 0:
        print(f"  SKIP {item_code} ({item_name}) — no valid RM lines")
        return "skipped"

    try:
        bom.insert(ignore_permissions=True)
        bom.submit()
        frappe.db.commit()
        msg = f"  OK {item_code} ({item_name}) — BOM {bom.name} created with {added} items"
        if skipped_rms:
            msg += f" (skipped RMs: {skipped_rms})"
        print(msg)
        return "created"
    except Exception as e:
        frappe.db.rollback()
        print(f"  FAIL {item_code} ({item_name}) — {e}")
        return "failed"


def _import_main_bom_csv():
    """Import BOMs from the main cleanroom CSV using FGRM->MN crosswalk."""
    csv_path = Path(frappe.get_app_path("hrms")).parent.parent / MAIN_BOM_CSV
    if not csv_path.exists():
        # Try relative to bench root
        csv_path = Path(MAIN_BOM_CSV)
    if not csv_path.exists():
        print(f"ERROR: Main BOM CSV not found at {csv_path}")
        return {}

    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # Group by fg_itemcode
    from collections import defaultdict

    by_fg = defaultdict(list)
    for r in rows:
        fg_code = r["fg_itemcode"]
        if fg_code not in FGRM_TO_MN:
            continue
        mn_code = FGRM_TO_MN[fg_code]

        # Map CSV UOM to Frappe UOM
        uom_raw = (r.get("rm_uom") or "").strip().upper()
        uom_map = {"G": "KG", "PC": "Nos", "KG": "KG", "ML": "KG", "L": "KG"}
        uom = uom_map.get(uom_raw, "KG")

        qty = flt(r.get("rm_qty", 0))
        # Convert grams to KG for weight-based UOMs
        if uom_raw == "G" and qty > 0:
            qty = qty / 1000.0

        by_fg[mn_code].append(
            {
                "rm_code": r["rm_code"],
                "rm_name": r["rm_name"],
                "qty": qty,
                "uom": uom,
            }
        )

    results = {}
    for mn_code in sorted(by_fg.keys()):
        item_name = frappe.db.get_value("Item", mn_code, "item_name") or mn_code
        result = _create_bom(mn_code, item_name, by_fg[mn_code])
        results[mn_code] = result

    return results


def _import_pop_lamig_bom():
    """Import Pop Lamig BOM from the separate canonical mapping CSV."""
    csv_path = Path(frappe.get_app_path("hrms")).parent.parent / POP_LAMIG_CSV
    if not csv_path.exists():
        csv_path = Path(POP_LAMIG_CSV)
    if not csv_path.exists():
        print(f"WARNING: Pop Lamig CSV not found at {csv_path}")
        return "skipped"

    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    rm_lines = []
    for r in rows:
        status = (r.get("status") or "").strip()
        if status == "CLEANUP_REQUIRED":
            continue  # Skip legacy alias row
        code = r.get("canonical_item_code", "").strip()
        qty = flt(r.get("qty_per_serving", 0))
        if not code or qty <= 0:
            continue

        uom = _get_item_uom(code) if _item_exists(code) else "KG"
        rm_lines.append({"rm_code": code, "rm_name": r.get("canonical_item_name", ""), "qty": qty, "uom": uom})

    item_name = frappe.db.get_value("Item", "MN016", "item_name") or "POP LAMIG"
    return _create_bom("MN016", item_name, rm_lines)


def run():
    """Main entry point for bench execute."""
    print("=" * 60)
    print("S108 BOM Import — Cleanroom to Frappe Production")
    print("=" * 60)

    print("\n--- Main BOM CSV (14 products via FGRM->MN crosswalk) ---")
    main_results = _import_main_bom_csv()

    print("\n--- Pop Lamig BOM (MN016) ---")
    pop_result = _import_pop_lamig_bom()

    # Summary
    created = sum(1 for v in main_results.values() if v == "created") + (1 if pop_result == "created" else 0)
    skipped = sum(1 for v in main_results.values() if v == "skipped") + (1 if pop_result == "skipped" else 0)
    failed = sum(1 for v in main_results.values() if v == "failed") + (1 if pop_result == "failed" else 0)

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {created} created, {skipped} skipped, {failed} failed")
    print(f"{'=' * 60}")

    if failed > 0:
        print("WARNING: Some BOMs failed. Check output above.")
    if created > 0:
        print(f"SUCCESS: {created} BOMs now active in Frappe.")
