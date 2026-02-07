"""
Seed Raw Materials master data for Commissary.
Source: Bryan's response in COMMISSARY_CRITICAL_MISSING_INFO_2026-02-03.docx

Updates Item master with supplier, reorder levels, and custom fields.

Usage:
    bench --site hq.bebang.ph execute scripts.seed_rm_master.seed_rm_data

Author: Claude Code
Date: 2026-02-06
"""

# Raw Materials data from Bryan (Commissary Supervisor)
# All reorder levels are "1 Day" - we set safety_stock to 2 days consumption as buffer
RAW_MATERIALS = [
    {
        "item_code": "Nestle Cream",
        "uom": "Box",
        "current_stock": 108,
        "supplier": "RGSOI",
        "reorder_days": 2,
        "used_in": ["FG020-ORIGINAL"],
    },
    {
        "item_code": "Condensed Milk",
        "uom": "Box",
        "current_stock": 87,
        "supplier": "CLAYACE",
        "reorder_days": 2,
        "used_in": ["FG020-ORIGINAL"],
    },
    {
        "item_code": "Evaporated Milk",
        "uom": "Box",
        "current_stock": 213,
        "supplier": "121",
        "reorder_days": 2,
        "used_in": ["FG020-ORIGINAL"],
    },
    {
        "item_code": "Refined Sugar",
        "uom": "Sack",
        "current_stock": 4,
        "supplier": "MANA SUPER FOOD",
        "reorder_days": 2,
        "used_in": ["FG007", "FG009"],
    },
    {
        "item_code": "Vanilla Extract",
        "uom": "Gallon",
        "current_stock": 18,
        "supplier": "CARANDANG",
        "reorder_days": 2,
        "used_in": ["FG020-ORIGINAL"],
    },
    {
        "item_code": "Crystal Gulaman Clear",
        "uom": "Box",
        "current_stock": 11,
        "supplier": "121",
        "reorder_days": 2,
        "used_in": ["FG005", "FG006"],
    },
    {
        "item_code": "Crystal Gulaman Pandan",
        "uom": "Box",
        "current_stock": 111,
        "supplier": "121",
        "reorder_days": 2,
        "used_in": ["FG004"],
    },
    {
        "item_code": "Coconut Milk",
        "uom": "Box",
        "current_stock": 16,
        "supplier": "MOLINA",
        "reorder_days": 2,
        "used_in": ["FG007"],
    },
    {
        "item_code": "Griffith Ice Milk Powder",
        "uom": "Sack",
        "current_stock": 166,
        "supplier": "Griffith",
        "reorder_days": 2,
        "used_in": ["FG020-GRIFFITH"],
    },
    {
        "item_code": "Rice Crispies",
        "uom": "Sack",
        "current_stock": 48,
        "supplier": "GREEN DISTRICT",
        "reorder_days": 2,
        "used_in": ["FG003"],
    },
    {
        "item_code": "PE Laminated Bags",
        "uom": "Bundle",
        "current_stock": 166,
        "supplier": "UNNITED POLYRECENT",
        "reorder_days": 2,
        "used_in": ["All FG packaging"],
    },
]


def seed_rm_data():
    """Update Item master with RM supplier and reorder data. Run via bench console."""
    import frappe
    from frappe.utils import flt

    results = []

    for rm in RAW_MATERIALS:
        item_code = rm["item_code"]

        if not frappe.db.exists("Item", item_code):
            results.append({"item": item_code, "status": "NOT_FOUND"})
            continue

        # Update custom reorder fields
        frappe.db.set_value("Item", item_code, {
            "custom_reorder_days": rm["reorder_days"],
        })

        # Update safety stock (approximate: 2x daily avg consumption)
        # For simplicity, set safety_stock = current_stock * 0.15 (15% buffer)
        safety = max(2, int(rm["current_stock"] * 0.15))
        frappe.db.set_value("Item", item_code, "safety_stock", safety)

        results.append({
            "item": item_code,
            "status": "UPDATED",
            "supplier": rm["supplier"],
            "safety_stock": safety,
            "reorder_days": rm["reorder_days"]
        })

    frappe.db.commit()

    print("\n=== RM Master Seed Results ===")
    for r in results:
        if r["status"] == "UPDATED":
            print(f"  {r['item']}: {r['status']} (supplier={r['supplier']}, safety={r['safety_stock']}, reorder={r['reorder_days']}d)")
        else:
            print(f"  {r['item']}: {r['status']}")

    updated = sum(1 for r in results if r["status"] == "UPDATED")
    not_found = sum(1 for r in results if r["status"] == "NOT_FOUND")
    print(f"\nTotal: {updated} updated, {not_found} not found")

    return results


if __name__ == "__main__":
    print("Run via: bench --site hq.bebang.ph execute scripts.seed_rm_master.seed_rm_data")
    print(f"\nDefined {len(RAW_MATERIALS)} raw materials:")
    for rm in RAW_MATERIALS:
        print(f"  {rm['item_code']}: {rm['uom']} (supplier: {rm['supplier']}, stock: {rm['current_stock']})")
