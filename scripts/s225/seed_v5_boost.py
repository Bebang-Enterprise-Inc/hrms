"""S225 v5 boost — top up PM001 to 2000 and seed PM007 + other PM00x items
that the suggested-order picker may select. Also re-seed KL items to compensate
for v4 consumption."""
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
SEED_LABEL = "S229 v5 boost (2026-04-30)"

# Stock Settings ON for batch handling
frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
frappe.db.set_single_value("Stock Settings", "allow_negative_stock_for_batch", 1)
frappe.db.commit()

# Items to top up — both PM and KL series at both hubs
TARGETS = [
    ("PM001", 2000),  # higher buffer
    ("PM007", 2000),  # was missing; SM MARIKINA needed this
    ("PM002", 2000),
    ("PM003", 2000),
    ("PM010", 2000),
    ("KL001", 2000),
    ("KL004", 2000),
    ("KL002", 2000),
    ("KL003", 2000),
]
HUBS = [PCS_BKI, HUB_3MD]
result = {"created": [], "skipped_existing_qty": [], "errors": []}

for item_code, target_qty in TARGETS:
    if not frappe.db.exists("Item", item_code):
        result["errors"].append({"item": item_code, "error": "ITEM_NOT_IN_MASTER"})
        continue
    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
    for hub in HUBS:
        try:
            cur = float(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": hub}, "actual_qty") or 0)
            if cur >= target_qty:
                result["skipped_existing_qty"].append({"item": item_code, "hub": hub, "actual": cur})
                continue
            qty_to_add = target_qty - cur
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
            result["created"].append({"name": se.name, "item": item_code, "qty": qty_to_add, "hub": hub})
        except Exception as e:
            frappe.db.rollback()
            result["errors"].append({"item": item_code, "hub": hub, "error": str(e)[:200]})

result["summary"] = {
    "ses_created": len(result["created"]),
    "skipped_existing": len(result["skipped_existing_qty"]),
    "errors": len(result["errors"]),
}
print(json.dumps(result, indent=2, default=str))
