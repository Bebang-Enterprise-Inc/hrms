"""S225 v6 — seed ALL PM00x items (PM001-PM030 if they exist) at both hubs.
Each sweep picks a different PM item per store, so partial coverage = whack-a-mole."""
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
HUBS = [PCS_BKI, HUB_3MD]
TARGET_QTY = 2000
SEED_LABEL = "S229 v6 full PM coverage (2026-04-30)"

# Stock Settings
frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
frappe.db.set_single_value("Stock Settings", "allow_negative_stock_for_batch", 1)
frappe.db.commit()

# All PM* items in master that are stock items
pm_items = frappe.get_all("Item",
    filters=[["item_code","like","PM%"],["is_stock_item","=",1],["disabled","=",0]],
    fields=["item_code","stock_uom"], limit_page_length=200)

result = {"created": [], "skipped": [], "errors": []}

for item in pm_items:
    code = item["item_code"]
    uom = item["stock_uom"] or "Nos"
    for hub in HUBS:
        try:
            cur = float(frappe.db.get_value("Bin", {"item_code": code, "warehouse": hub}, "actual_qty") or 0)
            if cur >= TARGET_QTY:
                result["skipped"].append({"item": code, "hub": hub})
                continue
            qty = TARGET_QTY - cur
            company = frappe.db.get_value("Warehouse", hub, "company")
            se = frappe.new_doc("Stock Entry")
            se.stock_entry_type = "Material Receipt"
            se.purpose = "Material Receipt"
            se.posting_date = nowdate()
            se.posting_time = now_datetime().strftime("%H:%M:%S")
            se.set_posting_time = 1
            se.company = company
            se.append("items", {
                "item_code": code, "qty": qty,
                "uom": uom, "stock_uom": uom, "conversion_factor": 1,
                "t_warehouse": hub, "basic_rate": 1.0,
                "allow_zero_valuation_rate": 1,
            })
            se.remarks = SEED_LABEL
            se.insert(ignore_permissions=True)
            se.submit()
            frappe.db.commit()
            result["created"].append({"name": se.name, "item": code, "hub": hub, "qty": qty})
        except Exception as e:
            frappe.db.rollback()
            result["errors"].append({"item": code, "hub": hub, "error": str(e)[:150]})

result["pm_items_in_master"] = len(pm_items)
result["summary"] = {"created": len(result["created"]), "skipped": len(result["skipped"]), "errors": len(result["errors"])}
print(json.dumps(result, indent=2, default=str))
