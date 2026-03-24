"""S104: Set up contracted price infrastructure.

1. Add price_validity_days field to BEI Settings (default 90)
2. Create "Standard Buying" Price List
3. Import 92 items from SKU Master CSV into Frappe Item Price
   - Only imports items that exist in Frappe Item master
   - Only imports items with cost > 0
   - Sets valid_from = today, valid_upto = today + price_validity_days
"""

import csv
import os

import frappe
from frappe.utils import today, add_days, flt


def execute():
    # --- Step 1: Ensure price_validity_days field exists on BEI Settings ---
    if not frappe.db.exists("Custom Field", {"dt": "BEI Settings", "fieldname": "price_validity_days"}):
        # Add directly to the DocType JSON in code; the field is added by the JSON update.
        # For runtime, just set the value on the doc.
        pass

    # Set default price_validity_days if not already set
    try:
        settings = frappe.get_single("BEI Settings")
        if not settings.get("price_validity_days"):
            settings.db_set("price_validity_days", 90, update_modified=False)
    except Exception:
        pass

    # --- Step 2: Create "Standard Buying" Price List ---
    if not frappe.db.exists("Price List", "Standard Buying"):
        pl = frappe.get_doc({
            "doctype": "Price List",
            "price_list_name": "Standard Buying",
            "buying": 1,
            "selling": 0,
            "enabled": 1,
            "currency": "PHP",
        })
        pl.insert(ignore_permissions=True)
        frappe.db.commit()
        print("Created Price List: Standard Buying")
    else:
        print("Price List 'Standard Buying' already exists")

    # --- Step 3: Import SKU Master prices into Item Price ---
    sku_master_path = os.path.join(
        frappe.get_app_path("hrms"),
        "..", "data", "Procurement_Database", "FORENSIC_EXTRACTION",
        "Copy of Compliance App Database__SKU_Master.csv"
    )

    if not os.path.exists(sku_master_path):
        print(f"SKU Master not found at {sku_master_path} — skipping import")
        return

    validity_days = 90
    try:
        validity_days = int(frappe.db.get_single_value("BEI Settings", "price_validity_days") or 90)
    except Exception:
        pass

    valid_from = today()
    valid_upto = add_days(valid_from, validity_days)

    imported = 0
    skipped_no_item = []
    skipped_zero_cost = []
    skipped_existing = []

    with open(sku_master_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_code = (row.get("Item Code") or "").strip()
            cost = flt(row.get("Cost", 0))
            uom = (row.get("UOM") or "Nos").strip()

            if not item_code:
                continue

            if cost <= 0:
                skipped_zero_cost.append(item_code)
                continue

            # Check item exists in Frappe
            if not frappe.db.exists("Item", item_code):
                skipped_no_item.append(item_code)
                continue

            # Check if Item Price already exists for this item + price list
            existing = frappe.db.exists("Item Price", {
                "item_code": item_code,
                "price_list": "Standard Buying",
            })
            if existing:
                skipped_existing.append(item_code)
                continue

            # Ensure UOM exists
            if uom and not frappe.db.exists("UOM", uom):
                uom = "Nos"

            ip = frappe.get_doc({
                "doctype": "Item Price",
                "item_code": item_code,
                "price_list": "Standard Buying",
                "price_list_rate": cost,
                "uom": uom,
                "buying": 1,
                "selling": 0,
                "currency": "PHP",
                "valid_from": valid_from,
                "valid_upto": valid_upto,
            })
            ip.insert(ignore_permissions=True)
            imported += 1

    frappe.db.commit()

    print(f"\nS104 Item Price Import Summary:")
    print(f"  Imported: {imported}")
    print(f"  Skipped (no matching Item): {len(skipped_no_item)} — {skipped_no_item[:10]}")
    print(f"  Skipped (zero cost): {len(skipped_zero_cost)} — {skipped_zero_cost[:10]}")
    print(f"  Skipped (already exists): {len(skipped_existing)} — {skipped_existing[:10]}")
