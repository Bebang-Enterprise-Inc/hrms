"""Real config audit:
  1. AYALA VERMOSA failure ('SI not created' due to PM006 valuation_rate=null)
     → audit ALL PM* items: which ones have valuation_rate? which don't?
  2. SM MARIKINA failure ('No BEI Warehouse Receiving') — silent dispatch failure
     → compare BEBANG SM MARIKINA INC. config to a working store
       (e.g., BEBANG ENTERPRISE INC. which routes to PCS-BKI and works)

Output: full diff per store + actionable fix list.
"""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {}

# ============ AUDIT 1: PM* item valuation_rate gaps ============
pm_items = frappe.db.sql("""
    SELECT i.item_code, i.item_name, i.valuation_rate, i.is_stock_item, i.disabled
    FROM `tabItem` i
    WHERE i.item_code LIKE 'PM%'
      AND i.is_stock_item = 1
      AND i.disabled = 0
    ORDER BY i.item_code
""", as_dict=True)
result["pm_items_audit"] = {
    "total": len(pm_items),
    "missing_valuation_rate": [r for r in pm_items if not r.get("valuation_rate") or float(r.get("valuation_rate") or 0) <= 0],
    "with_valuation_rate": [r for r in pm_items if r.get("valuation_rate") and float(r.get("valuation_rate") or 0) > 0],
}
result["pm_items_audit"]["count_missing"] = len(result["pm_items_audit"]["missing_valuation_rate"])
result["pm_items_audit"]["count_present"] = len(result["pm_items_audit"]["with_valuation_rate"])

# Sample 5 of each
result["pm_items_audit"]["missing_sample"] = result["pm_items_audit"]["missing_valuation_rate"][:5]
result["pm_items_audit"]["present_sample"] = result["pm_items_audit"]["with_valuation_rate"][:5]
# Drop full lists from response to fit SSM
result["pm_items_audit"]["missing_codes"] = [r["item_code"] for r in result["pm_items_audit"]["missing_valuation_rate"]]
del result["pm_items_audit"]["missing_valuation_rate"]
del result["pm_items_audit"]["with_valuation_rate"]

# Also FG and KL items
for prefix in ["FG", "KL"]:
    items = frappe.db.sql(f"""
        SELECT item_code, valuation_rate FROM `tabItem`
        WHERE item_code LIKE '{prefix}%' AND is_stock_item=1 AND disabled=0
    """, as_dict=True)
    missing = [r["item_code"] for r in items if not r.get("valuation_rate") or float(r.get("valuation_rate") or 0) <= 0]
    result[f"{prefix.lower()}_items_audit"] = {
        "total": len(items),
        "missing_count": len(missing),
        "missing_codes": missing[:30],
    }

# ============ AUDIT 2: SM MARIKINA vs working store config ============
SM_MARIKINA_CO = "BEBANG SM MARIKINA INC."
SM_MARIKINA_WH = "SM MARIKINA - BEBANG SM MARIKINA INC."
SM_MARIKINA_CUST = "SM MARIKINA - BEBANG SM MARIKINA INC."

# Working stores: AYALA EVO and SM TANZA both pass
WORKING_CO = "BEBANG ENTERPRISE INC."  # Used by Robinsons Antipolo etc
WORKING_WH = "AYALA EVO - BEBANG MEGA INC."
WORKING_CUST = "AYALA EVO - BEBANG MEGA INC."

config_audit = {}

for label, co_name in [("MARIKINA", SM_MARIKINA_CO), ("WORKING_BEBANG_ENTERPRISE", WORKING_CO)]:
    if not frappe.db.exists("Company", co_name):
        config_audit[f"{label}_company"] = "NOT_FOUND"
        continue
    co = frappe.db.get_value("Company", co_name,
        ["name","abbr","default_currency","default_letter_head","country",
         "default_payable_account","default_receivable_account",
         "default_employee_advance_account","default_payroll_payable_account",
         "default_expense_account","default_income_account",
         "default_inventory_account","stock_received_but_not_billed",
         "expenses_included_in_valuation","cost_center","round_off_account",
         "round_off_cost_center","write_off_account","exchange_gain_loss_account",
         "unrealized_exchange_gain_loss_account","accumulated_depreciation_account",
         "depreciation_expense_account","disposal_account","capital_work_in_progress_account",
         "default_holiday_list","tax_id","parent_company"], as_dict=True)
    config_audit[f"{label}_company"] = co

# Check warehouses
for label, wh_name in [("MARIKINA", SM_MARIKINA_WH), ("WORKING", WORKING_WH)]:
    if not frappe.db.exists("Warehouse", wh_name):
        config_audit[f"{label}_warehouse"] = "NOT_FOUND"
        continue
    wh = frappe.db.get_value("Warehouse", wh_name,
        ["name","warehouse_name","company","disabled","is_group","parent_warehouse",
         "default_in_transit_warehouse","custom_area_supervisor"], as_dict=True)
    config_audit[f"{label}_warehouse"] = wh

# Check customers
for label, cust_name in [("MARIKINA", SM_MARIKINA_CUST), ("WORKING", WORKING_CUST)]:
    if not frappe.db.exists("Customer", cust_name):
        config_audit[f"{label}_customer"] = "NOT_FOUND"
        continue
    cust = frappe.db.get_value("Customer", cust_name,
        ["name","customer_name","customer_type","customer_group","territory","tax_id",
         "is_internal_customer","represents_company","default_currency",
         "default_price_list"], as_dict=True)
    config_audit[f"{label}_customer"] = cust

result["config_audit"] = config_audit

print(json.dumps(result, indent=2, default=str))
