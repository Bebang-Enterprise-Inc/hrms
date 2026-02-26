"""Item A-Suffix Cleanup — Phase 1: Q-Independent Frappe Production Operations

Operations (all confirmed, no Q-answer dependencies):
  1. Backup production item data (21 target items)
  2. Add CASE UOM to KL001-KL004 (1 CASE = 4 GAL, confirmed by price ratios)
  3. Rename RM008-A → RM008 (orphan item, no parent exists)
  4. Add CAN UOM to RM008 (1 BOX = 24 CAN, confirmed from description)
  5. Safety check: which disable candidates have open transactions

Usage:
    /home/frappe/frappe-bench/env/bin/python /tmp/item_a_cleanup_phase1.py --dry-run
    /home/frappe/frappe-bench/env/bin/python /tmp/item_a_cleanup_phase1.py --execute
"""
import argparse
import json
import sys
import traceback

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()


# ── Target items ────────────────────────────────────────────────────
BACKUP_ITEMS = [
    'FG002', 'FG002-A', 'KL001', 'KL001-A', 'KL002', 'KL002-A',
    'KL003', 'KL003-A', 'KL004', 'KL004-A', 'CS011', 'CS011-A',
    'CS012-A', 'CS012-A1', 'CS012-A2', 'PM008', 'PM008-A',
    'FG001-A', 'A011-A', 'A033-A', 'RM004-A', 'RM008-A', 'RM001-A',
]

KL_ITEMS = ['KL001', 'KL002', 'KL003', 'KL004']

DISABLE_CANDIDATES = [
    'FG002-A', 'KL001-A', 'KL002-A', 'KL003-A', 'KL004-A',
    'CS011-A', 'CS012-A', 'PM008-A',
]


def step1_backup(dry_run):
    """Backup production item data for all 21 target items."""
    print("\n" + "=" * 60)
    print("STEP 1: BACKUP PRODUCTION ITEM DATA")
    print("=" * 60)

    # Item master
    items = frappe.db.sql("""
        SELECT name, item_name, stock_uom, disabled, custom_counting_location,
               custom_counting_uom, custom_packaging_desc, valuation_rate
        FROM `tabItem`
        WHERE name IN %(codes)s
        ORDER BY name
    """, {"codes": BACKUP_ITEMS}, as_dict=True)
    print(f"\n  Items found: {len(items)}")
    for item in items:
        print(f"    {item.name}: {item.item_name} | UOM={item.stock_uom} | "
              f"disabled={item.disabled} | loc={item.custom_counting_location} | "
              f"rate={item.valuation_rate}")

    # UOM conversions
    uoms = frappe.db.sql("""
        SELECT parent, uom, conversion_factor
        FROM `tabUOM Conversion Detail`
        WHERE parent IN %(codes)s
        ORDER BY parent, uom
    """, {"codes": BACKUP_ITEMS}, as_dict=True)
    print(f"\n  UOM conversions: {len(uoms)}")
    for u in uoms:
        print(f"    {u.parent}: {u.uom} = {u.conversion_factor}")

    # Stock balances
    bins = frappe.db.sql("""
        SELECT item_code, warehouse, actual_qty, valuation_rate
        FROM `tabBin`
        WHERE item_code IN %(codes)s AND actual_qty != 0
        ORDER BY item_code, warehouse
    """, {"codes": BACKUP_ITEMS}, as_dict=True)
    print(f"\n  Non-zero stock balances: {len(bins)}")
    for b in bins:
        print(f"    {b.item_code} @ {b.warehouse}: qty={b.actual_qty}, rate={b.valuation_rate}")

    backup = {
        "timestamp": str(frappe.utils.now()),
        "items": [dict(r) for r in items],
        "uom_conversions": [dict(r) for r in uoms],
        "stock_balances": [dict(r) for r in bins],
    }
    if not dry_run:
        backup_path = "/tmp/ITEM_A_CLEANUP_BACKUP_2026-02-25.json"
        with open(backup_path, "w") as f:
            json.dump(backup, f, indent=2, default=str)
        print(f"\n  Backup saved to {backup_path}")
    else:
        print("\n  [DRY-RUN] Would save backup to /tmp/ITEM_A_CLEANUP_BACKUP_2026-02-25.json")

    return backup


def step2_kl_uom(dry_run):
    """Add CASE UOM conversion to KL001-KL004 (1 CASE = 4 GAL)."""
    print("\n" + "=" * 60)
    print("STEP 2: ADD CASE UOM TO KL001-KL004")
    print("=" * 60)

    for item_code in KL_ITEMS:
        # Check item exists and get current UOMs
        if not frappe.db.exists("Item", item_code):
            print(f"\n  WARNING: {item_code} does not exist in Frappe — skipping")
            continue

        item = frappe.get_doc("Item", item_code)
        existing_case = [r for r in item.uoms if r.uom == "Case"]

        if existing_case:
            print(f"\n  {item_code}: CASE conversion already exists "
                  f"(factor={existing_case[0].conversion_factor}) — skipping")
            continue

        # Check if "Case" UOM exists in the system
        if not frappe.db.exists("UOM", "Case"):
            print(f"\n  WARNING: UOM 'Case' does not exist in Frappe!")
            # Try alternate names
            for alt in ["CASE", "case", "Cse"]:
                if frappe.db.exists("UOM", alt):
                    print(f"  Found alternate: '{alt}'")
                    break
            else:
                print("  No Case UOM found — listing available UOMs with 'case' in name:")
                results = frappe.db.sql(
                    "SELECT name FROM `tabUOM` WHERE LOWER(name) LIKE '%case%'",
                    as_dict=True)
                for r in results:
                    print(f"    '{r.name}'")
                if not results:
                    print("    (none found)")
                continue

        if dry_run:
            print(f"\n  [DRY-RUN] {item_code}: Would add UOM 'Case' with conversion_factor=4.0")
            print(f"    Current UOMs: {[(r.uom, r.conversion_factor) for r in item.uoms]}")
        else:
            item.append("uoms", {"uom": "Case", "conversion_factor": 4.0})
            item.flags.ignore_validate = True
            item.save(ignore_permissions=True)
            print(f"\n  {item_code}: Added Case UOM (1 Case = 4 {item.stock_uom})")
            print(f"    All UOMs now: {[(r.uom, r.conversion_factor) for r in item.uoms]}")

    if not dry_run:
        frappe.db.commit()
        print("\n  Changes committed.")


def step3_rename_rm008a(dry_run):
    """Rename RM008-A → RM008 (orphan item, no parent exists)."""
    print("\n" + "=" * 60)
    print("STEP 3: RENAME RM008-A → RM008")
    print("=" * 60)

    # Pre-checks
    if not frappe.db.exists("Item", "RM008-A"):
        print("\n  ERROR: RM008-A does not exist in Frappe — cannot rename")
        return False

    if frappe.db.exists("Item", "RM008"):
        print("\n  ERROR: RM008 already exists — cannot rename RM008-A to RM008")
        return False

    # Show current state
    item = frappe.get_doc("Item", "RM008-A")
    print(f"\n  Current: {item.name} = {item.item_name}")
    print(f"  Stock UOM: {item.stock_uom}")
    print(f"  Disabled: {item.disabled}")
    print(f"  UOMs: {[(r.uom, r.conversion_factor) for r in item.uoms]}")

    # Check linked records
    sle_count = frappe.db.count("Stock Ledger Entry", {"item_code": "RM008-A"})
    bin_count = frappe.db.count("Bin", {"item_code": "RM008-A"})
    po_count = frappe.db.sql("""
        SELECT COUNT(DISTINCT poi.parent)
        FROM `tabPurchase Order Item` poi
        WHERE poi.item_code = 'RM008-A'
    """)[0][0]
    bom_count = frappe.db.sql("""
        SELECT COUNT(DISTINCT bi.parent)
        FROM `tabBOM Item` bi
        WHERE bi.item_code = 'RM008-A'
    """)[0][0]

    print(f"\n  Linked records that will be updated:")
    print(f"    Stock Ledger Entries: {sle_count}")
    print(f"    Bins (warehouse balances): {bin_count}")
    print(f"    Purchase Orders: {po_count}")
    print(f"    BOMs: {bom_count}")

    if dry_run:
        print(f"\n  [DRY-RUN] Would rename RM008-A → RM008")
        return True

    # Execute with savepoint
    frappe.db.savepoint("rename_rm008a")
    try:
        frappe.rename_doc("Item", "RM008-A", "RM008", merge=False)
        frappe.db.commit()
        print(f"\n  SUCCESS: RM008-A renamed to RM008")

        # Verify
        new_item = frappe.get_doc("Item", "RM008")
        print(f"  Verified: {new_item.name} = {new_item.item_name}")
        return True
    except Exception as e:
        frappe.db.rollback(save_point="rename_rm008a")
        print(f"\n  ERROR: Rename failed — rolled back: {e}")
        traceback.print_exc()
        return False


def step4_rm008_can_uom(dry_run):
    """Add CAN UOM to RM008 (1 BOX = 24 CAN)."""
    print("\n" + "=" * 60)
    print("STEP 4: ADD CAN UOM TO RM008 (1 BOX = 24 CAN)")
    print("=" * 60)

    item_code = "RM008"
    if not frappe.db.exists("Item", item_code):
        print(f"\n  ERROR: {item_code} does not exist — was step 3 (rename) skipped?")
        return

    item = frappe.get_doc("Item", item_code)
    existing_can = [r for r in item.uoms if r.uom in ("Can", "CAN", "can")]

    if existing_can:
        print(f"\n  {item_code}: CAN conversion already exists — skipping")
        return

    # Find the correct UOM name
    can_uom = None
    for name in ["Can", "CAN", "Nos"]:
        if frappe.db.exists("UOM", name):
            can_uom = name
            break

    if not can_uom:
        print("\n  WARNING: No 'Can' UOM found in Frappe. Searching...")
        results = frappe.db.sql(
            "SELECT name FROM `tabUOM` WHERE LOWER(name) LIKE '%can%'",
            as_dict=True)
        for r in results:
            print(f"    '{r.name}'")
        if not results:
            print("    (none found — may need to create 'Can' UOM first)")
        return

    if dry_run:
        print(f"\n  [DRY-RUN] {item_code}: Would add UOM '{can_uom}' with conversion_factor=24.0")
        print(f"    Current UOMs: {[(r.uom, r.conversion_factor) for r in item.uoms]}")
    else:
        item.append("uoms", {"uom": can_uom, "conversion_factor": 24.0})
        item.flags.ignore_validate = True
        item.save(ignore_permissions=True)
        frappe.db.commit()
        print(f"\n  {item_code}: Added {can_uom} UOM (1 {item.stock_uom} = 24 {can_uom})")
        print(f"    All UOMs now: {[(r.uom, r.conversion_factor) for r in item.uoms]}")


def step5_safety_check():
    """Run open-transaction check on all disable candidates."""
    print("\n" + "=" * 60)
    print("STEP 5: SAFETY CHECK — OPEN TRANSACTIONS")
    print("=" * 60)

    codes = DISABLE_CANDIDATES
    blocked = set()

    def _check(label, query, params):
        try:
            rows = frappe.db.sql(query, params, as_dict=True)
            for r in rows:
                blocked.add(r.item_code)
                print(f"    BLOCKED: {r.item_code} — {label}")
        except Exception as e:
            print(f"    [WARN] {label} check failed: {e}")

    print(f"\n  Checking {len(codes)} disable candidates: {', '.join(codes)}")

    # Draft POs
    _check("Draft PO", """
        SELECT DISTINCT poi.item_code
        FROM `tabPurchase Order Item` poi
        JOIN `tabPurchase Order` po ON po.name = poi.parent
        WHERE poi.item_code IN %(codes)s AND po.docstatus = 0
    """, {"codes": codes})

    # Submitted POs with unfulfilled qty
    _check("Submitted PO (unfulfilled)", """
        SELECT DISTINCT poi.item_code
        FROM `tabPurchase Order Item` poi
        JOIN `tabPurchase Order` po ON po.name = poi.parent
        WHERE poi.item_code IN %(codes)s
          AND po.docstatus = 1
          AND poi.qty > COALESCE(poi.received_qty, 0)
    """, {"codes": codes})

    # Material Requests
    _check("Draft Material Request", """
        SELECT DISTINCT mri.item_code
        FROM `tabMaterial Request Item` mri
        JOIN `tabMaterial Request` mr ON mr.name = mri.parent
        WHERE mri.item_code IN %(codes)s AND mr.docstatus = 0
    """, {"codes": codes})

    # Active BOMs
    _check("Active BOM", """
        SELECT DISTINCT bi.item_code
        FROM `tabBOM Item` bi
        JOIN `tabBOM` b ON b.name = bi.parent
        WHERE bi.item_code IN %(codes)s
          AND b.docstatus IN (0, 1)
          AND COALESCE(b.is_active, 0) = 1
    """, {"codes": codes})

    # Draft Stock Entries
    _check("Draft Stock Entry", """
        SELECT DISTINCT sed.item_code
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE sed.item_code IN %(codes)s AND se.docstatus = 0
    """, {"codes": codes})

    # Draft Stock Reconciliations
    _check("Draft Stock Reconciliation", """
        SELECT DISTINCT sri.item_code
        FROM `tabStock Reconciliation Item` sri
        JOIN `tabStock Reconciliation` sr ON sr.name = sri.parent
        WHERE sri.item_code IN %(codes)s AND sr.docstatus = 0
    """, {"codes": codes})

    safe = [c for c in codes if c not in blocked]
    print(f"\n  SAFE to disable ({len(safe)}): {', '.join(safe) if safe else '(none)'}")
    print(f"  BLOCKED ({len(blocked)}): {', '.join(blocked) if blocked else '(none)'}")

    # Also show stock balances for blocked items
    if blocked:
        print("\n  Stock balances for blocked items:")
        for code in sorted(blocked):
            bins = frappe.db.sql("""
                SELECT warehouse, actual_qty, valuation_rate
                FROM `tabBin` WHERE item_code = %s AND actual_qty != 0
            """, code, as_dict=True)
            if bins:
                for b in bins:
                    print(f"    {code} @ {b.warehouse}: qty={b.actual_qty}, rate={b.valuation_rate}")
            else:
                print(f"    {code}: no stock")

    return safe, list(blocked)


def main():
    parser = argparse.ArgumentParser(description="Item A-Suffix Cleanup Phase 1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview all changes without executing")
    group.add_argument("--execute", action="store_true", help="Execute all changes on production")
    args = parser.parse_args()

    dry_run = args.dry_run

    print("=" * 60)
    print(f"ITEM A-SUFFIX CLEANUP — PHASE 1 ({'DRY RUN' if dry_run else 'EXECUTE'})")
    print(f"Site: hq.bebang.ph")
    print("=" * 60)

    try:
        # Step 1: Backup (always runs)
        step1_backup(dry_run)

        # Step 2: KL001-KL004 CASE UOM
        step2_kl_uom(dry_run)

        # Step 3: Rename RM008-A → RM008
        rename_ok = step3_rename_rm008a(dry_run)

        # Step 4: Add CAN UOM to RM008 (only if rename succeeded or dry-run)
        if rename_ok or dry_run:
            step4_rm008_can_uom(dry_run)
        else:
            print("\n  Skipping step 4 (CAN UOM) because rename in step 3 failed")

        # Step 5: Safety check (always runs, read-only)
        step5_safety_check()

        print("\n" + "=" * 60)
        print(f"ALL STEPS COMPLETE ({'DRY RUN — no changes made' if dry_run else 'CHANGES APPLIED'})")
        print("=" * 60)

    except Exception:
        print("\n\nFATAL ERROR:")
        traceback.print_exc()
        sys.exit(1)
    finally:
        frappe.destroy()


if __name__ == "__main__":
    main()
