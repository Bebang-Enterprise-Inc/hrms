"""SM MARIKINA fix: Company references 'Stock In Hand - BSMI' which doesn't exist.
Find SMK-suffixed Stock accounts (or fall back to parent BEBANG ENTERPRISE INC.) and re-point."""
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

# Find SMK accounts of relevant types
smk_accounts = frappe.db.sql("""
    SELECT name, account_type, root_type, is_group
    FROM `tabAccount`
    WHERE name LIKE '%- SMK%' AND is_group = 0
    ORDER BY name
""", as_dict=True)
result["smk_leaf_accounts"] = smk_accounts

# What about parent company BEBANG ENTERPRISE INC. accounts (BEI)?
parent_inv = frappe.db.get_value("Company", "BEBANG ENTERPRISE INC.", "default_inventory_account")
parent_srbnb = frappe.db.get_value("Company", "BEBANG ENTERPRISE INC.", "stock_received_but_not_billed")
result["parent_BEI_inv"] = parent_inv
result["parent_BEI_srbnb"] = parent_srbnb

# Find the right inventory account for SMK - any "Stock In Hand" or similar
inv_candidates = frappe.db.sql("""
    SELECT name, account_type, root_type
    FROM `tabAccount`
    WHERE (name LIKE 'Stock In Hand%' OR name LIKE 'Inventory%')
      AND is_group = 0
      AND name LIKE '%SMK%'
""", as_dict=True)
result["smk_inv_candidates"] = inv_candidates

# Also fall-back: look at sister stores under SMK that have inventory account set up working
sm_marikina_co = "SM MARIKINA - BEBANG SM MARIKINA INC."
co = frappe.db.get_value("Company", sm_marikina_co,
    ["default_inventory_account","stock_received_but_not_billed","stock_adjustment_account",
     "expenses_included_in_valuation","default_payable_account","default_receivable_account",
     "default_income_account","default_expense_account","cost_center","round_off_account",
     "round_off_cost_center","abbr"], as_dict=True)
result["SM_MAR_BEFORE"] = co

# Determine fix:
# If a SMK-suffixed inventory account exists, use it. Else use parent BEI inventory.
target_inv_account = None
for c in inv_candidates:
    target_inv_account = c["name"]; break

if not target_inv_account:
    # Fallback to parent
    target_inv_account = parent_inv

result["target_inv_account"] = target_inv_account

# Apply fix if account exists
if target_inv_account and frappe.db.exists("Account", target_inv_account):
    try:
        frappe.db.set_value("Company", sm_marikina_co, "default_inventory_account", target_inv_account)
        # Also set stock_received_but_not_billed if it's broken
        if co.get("stock_received_but_not_billed") and not frappe.db.exists("Account", co["stock_received_but_not_billed"]):
            if parent_srbnb and frappe.db.exists("Account", parent_srbnb):
                frappe.db.set_value("Company", sm_marikina_co, "stock_received_but_not_billed", parent_srbnb)
                result["FIX_STOCK_SRBNB"] = parent_srbnb
        frappe.db.commit()
        result["FIX_INV_APPLIED"] = target_inv_account
    except Exception as e:
        result["FIX_ERROR"] = str(e)[:200]

# Verify
co_after = frappe.db.get_value("Company", sm_marikina_co,
    ["default_inventory_account","stock_received_but_not_billed"], as_dict=True)
result["SM_MAR_AFTER"] = co_after

# Verify all referenced accounts exist
for k, v in (co_after or {}).items():
    if v:
        result.setdefault("verify_accounts_exist", {})[v] = bool(frappe.db.exists("Account", v))

print(json.dumps(result, indent=2, default=str))
