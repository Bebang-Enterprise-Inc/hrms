"""
Seed BOM (Bill of Materials) data for Commissary Finished Goods.
Source: COMMISSARY_CRITICAL_MISSING_INFO_2026-02-03.docx (Arnold / R&D)

Usage:
    # Via Frappe bench console on production:
    bench --site hq.bebang.ph execute scripts.seed_commissary_bom.seed_all_boms

    # Or via the commissary API:
    curl -X POST https://hq.bebang.ph/api/method/hrms.api.commissary.create_bom \
        -H "Authorization: token <key>:<secret>" \
        -d '{"item_code": "FG007", "materials": [...], "quantity": 0.465}'

Author: Claude Code
Date: 2026-02-06
"""

# BOM definitions from Arnold's questionnaire responses
BOMS = [
    {
        "item_code": "FG007",
        "item_name": "Coconut Syrup",
        "quantity": 0.465,
        "uom": "Kg",
        "materials": [
            {"item_code": "Coconut Milk", "qty": 0.400, "uom": "Kg"},
            {"item_code": "Refined Sugar", "qty": 0.065, "uom": "Kg"},
            {"item_code": "Cornstarch", "qty": 0.010, "uom": "Kg"},
        ]
    },
    {
        "item_code": "FG009",
        "item_name": "Sago",
        "quantity": 41.414,
        "uom": "Kg",
        "materials": [
            {"item_code": "Filtered Water", "qty": 42.722, "uom": "Kg"},
            {"item_code": "Sago", "qty": 6.000, "uom": "Kg"},
            {"item_code": "Refined Sugar", "qty": 1.496, "uom": "Kg"},
            {"item_code": "Guar", "qty": 0.037, "uom": "Kg"},
            {"item_code": "Strawberry Red Color", "qty": 0.003, "uom": "Kg"},
            {"item_code": "Sodium Benzoate", "qty": 0.001, "uom": "Kg"},
            {"item_code": "Potassium Sorbate", "qty": 0.001, "uom": "Kg"},
        ]
    },
    {
        "item_code": "FG004",
        "item_name": "Buko Pandan Jelly",
        "quantity": 12.5,
        "uom": "Kg",
        "materials": [
            {"item_code": "Filtered Water", "qty": 14.000, "uom": "Kg"},
            {"item_code": "Crystal Gulaman Pandan", "qty": 0.720, "uom": "Kg"},
        ]
    },
    {
        "item_code": "FG012",
        "item_name": "Melted Ube/Spread",
        "quantity": 13.0,
        "uom": "Kg",
        "materials": [
            {"item_code": "Ube Halaya", "qty": 10.000, "uom": "Kg"},
            {"item_code": "Filtered Water", "qty": 4.000, "uom": "Kg"},
            {"item_code": "Sodium Benzoate", "qty": 0.004, "uom": "Kg"},
            {"item_code": "Potassium Sorbate", "qty": 0.004, "uom": "Kg"},
        ]
    },
    {
        "item_code": "FG014",
        "item_name": "Pistachio/Cashew Mix",
        "quantity": 2.94,
        "uom": "Kg",
        "materials": [
            {"item_code": "Cashew", "qty": 2.000, "uom": "Kg"},
            {"item_code": "Pistachio", "qty": 1.000, "uom": "Kg"},
        ]
    },
    {
        "item_code": "FG003",
        "item_name": "Rice Crispies",
        "quantity": 15.0,  # 30 pcs x 500g
        "uom": "Kg",
        "materials": [
            {"item_code": "Rice Crispies", "qty": 15.000, "uom": "Kg"},
        ]
    },
    {
        "item_code": "FG020-ORIGINAL",
        "item_name": "Frozen Ice Milk (Traditional)",
        "quantity": 15.68,  # 6.27 barrels
        "uom": "Kg",
        "materials": [
            {"item_code": "Nestle Cream", "qty": 2.000, "uom": "Kg"},
            {"item_code": "Condensed Milk", "qty": 3.000, "uom": "Kg"},
            {"item_code": "Evaporated Milk", "qty": 3.000, "uom": "Kg"},
            {"item_code": "Filtered Water", "qty": 8.000, "uom": "Kg"},
        ]
    },
    {
        "item_code": "FG020-GRIFFITH",
        "item_name": "Frozen Ice Milk (Griffith Powder)",
        "quantity": 15.68,  # 6.27 barrels
        "uom": "Kg",
        "materials": [
            {"item_code": "Griffith Ice Milk Powder", "qty": 4.000, "uom": "Kg"},
            {"item_code": "Filtered Water", "qty": 12.000, "uom": "Kg"},
        ]
    },
]


def seed_all_boms():
    """Create BOMs for all FG items. Run via bench console."""
    import frappe
    from frappe.utils import flt

    results = []

    for bom_data in BOMS:
        item_code = bom_data["item_code"]

        # Check if item exists
        if not frappe.db.exists("Item", item_code):
            results.append({"item": item_code, "status": "SKIP", "reason": "Item not found"})
            continue

        # Check if active BOM already exists
        existing = frappe.db.get_value(
            "BOM",
            {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
            "name"
        )
        if existing:
            results.append({"item": item_code, "status": "SKIP", "reason": f"BOM exists: {existing}"})
            continue

        # Check all materials exist
        missing_materials = []
        for mat in bom_data["materials"]:
            if not frappe.db.exists("Item", mat["item_code"]):
                missing_materials.append(mat["item_code"])

        if missing_materials:
            results.append({
                "item": item_code,
                "status": "SKIP",
                "reason": f"Missing materials: {', '.join(missing_materials)}"
            })
            continue

        # Create BOM
        bom = frappe.new_doc("BOM")
        bom.item = item_code
        bom.quantity = flt(bom_data["quantity"])
        bom.uom = bom_data["uom"]
        bom.is_active = 1
        bom.is_default = 1
        bom.company = "Bebang Enterprise Inc."
        bom.with_operations = 0
        bom.remarks = f"Seeded from COMMISSARY_CRITICAL_MISSING_INFO_2026-02-03.docx"

        for mat in bom_data["materials"]:
            mat_item = frappe.db.get_value(
                "Item", mat["item_code"],
                ["item_name", "stock_uom", "valuation_rate"],
                as_dict=True
            )
            bom.append("items", {
                "item_code": mat["item_code"],
                "item_name": mat_item.item_name,
                "qty": flt(mat["qty"]),
                "uom": mat.get("uom") or mat_item.stock_uom,
                "stock_uom": mat_item.stock_uom,
                "rate": mat_item.valuation_rate or 0,
            })

        bom.insert()
        bom.submit()

        results.append({"item": item_code, "status": "CREATED", "bom": bom.name})

    frappe.db.commit()

    print("\n=== BOM Seed Results ===")
    for r in results:
        print(f"  {r['item']}: {r['status']} - {r.get('bom') or r.get('reason', '')}")

    created = sum(1 for r in results if r["status"] == "CREATED")
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    print(f"\nTotal: {created} created, {skipped} skipped")

    return results


if __name__ == "__main__":
    print("Run via: bench --site hq.bebang.ph execute scripts.seed_commissary_bom.seed_all_boms")
    print(f"\nDefined {len(BOMS)} BOMs:")
    for b in BOMS:
        print(f"  {b['item_code']}: {b['item_name']} ({b['quantity']} {b['uom']}, {len(b['materials'])} materials)")
