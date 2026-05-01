"""S225 narrow seeding — only the 10 items Sentry flagged as failing.

Avoids the v2 mistake of seeding all 80+ FG/PM/KL items (which didn't bloat the
dropdown — that was wrong analysis — but also wasted time and created teardown
mass).

Seeded items (from Sentry historical evidence + OrderBuilder defaults):
  PM001 — 16OZ cup with logo (packaging, every order needs it)
  FG001, FG002, FG010, FG023 — OrderBuilder default DRY items
  FG002-A, FG004 — batch-tracked variants Sentry showed failing
  KL001, KL004 — kit items Sentry showed failing
  GRP-FRESH-RIPE-MANGO — group item from defaults

Seed at PCS-BKI and 3MD-CAMANGYANAN (the two main hubs). 500 units each = enough
for 25 stores routed to each hub × 20 units max per order.

Also toggles Stock Settings allow_negative_stock + allow_negative_stock_for_batch
= 1 to handle the BACKFILL-20260421-* batches that are intentionally negative
from S225 Phase 3 cleanup.
"""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
from frappe.utils import nowdate, now_datetime
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

PCS_BKI = "PINNACLE COLD STORAGE SOLUTIONS - BKI"
HUB_3MD = "3MD Logistics - Camangyanan - BKI"
SEED_QTY = 500
SEED_LABEL = "S229 narrow seed (2026-04-29 v3)"

ITEMS_TO_SEED = [
    "PM001",
    "FG001", "FG002", "FG010", "FG023",
    "FG002-A", "FG004",
    "KL001", "KL004",
    "GRP-FRESH-RIPE-MANGO",
]
HUBS = [PCS_BKI, HUB_3MD]

result = {
    "stock_settings_pre": {
        "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
        "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
    },
    "stock_entries_created": [],
    "errors": [],
}

# Toggle ON
frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
frappe.db.set_single_value("Stock Settings", "allow_negative_stock_for_batch", 1)
frappe.db.commit()
result["stock_settings_post"] = {
    "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
    "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
}

for item_code in ITEMS_TO_SEED:
    if not frappe.db.exists("Item", item_code):
        result["errors"].append({"item": item_code, "error": "ITEM_NOT_IN_MASTER"})
        continue
    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
    for hub in HUBS:
        try:
            cur = float(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": hub}, "actual_qty") or 0)
            if cur >= SEED_QTY:
                continue
            qty_to_add = SEED_QTY - cur if cur > 0 else SEED_QTY
            company = frappe.db.get_value("Warehouse", hub, "company")
            se = frappe.new_doc("Stock Entry")
            se.stock_entry_type = "Material Receipt"
            se.purpose = "Material Receipt"
            se.posting_date = nowdate()
            se.posting_time = now_datetime().strftime("%H:%M:%S")
            se.set_posting_time = 1
            se.company = company
            se.append("items", {
                "item_code": item_code,
                "qty": qty_to_add,
                "uom": stock_uom,
                "stock_uom": stock_uom,
                "conversion_factor": 1,
                "t_warehouse": hub,
                "basic_rate": 1.0,
                "allow_zero_valuation_rate": 1,
            })
            se.remarks = SEED_LABEL
            se.insert(ignore_permissions=True)
            se.submit()
            frappe.db.commit()
            result["stock_entries_created"].append({
                "name": se.name,
                "item": item_code,
                "qty": qty_to_add,
                "warehouse": hub,
            })
        except Exception as e:
            frappe.db.rollback()
            result["errors"].append({"item": item_code, "warehouse": hub, "error": str(e)[:200]})

result["summary"] = {
    "items_attempted": len(ITEMS_TO_SEED),
    "ses_created": len(result["stock_entries_created"]),
    "errors": len(result["errors"]),
}

print(json.dumps(result, indent=2, default=str))
