"""Fuzzy search for SM MARIKINA Company + check warehouse linkage."""
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

# Find any company matching MARIKINA
companies = frappe.db.sql("""
    SELECT name, abbr, default_currency, default_receivable_account, default_income_account, parent_company
    FROM `tabCompany`
    WHERE UPPER(name) LIKE '%MARIKINA%' OR UPPER(name) LIKE '%SM%MARIKIN%'
""", as_dict=True)
result["companies_with_marikina"] = companies

# All companies for reference (count)
total_co = frappe.db.count("Company")
result["total_companies"] = total_co

# Warehouse SM MARIKINA - what company does it reference?
sm_mar_wh_name = "SM MARIKINA - BEBANG SM MARIKINA INC."
if frappe.db.exists("Warehouse", sm_mar_wh_name):
    wh = frappe.db.get_value("Warehouse", sm_mar_wh_name,
        ["name","warehouse_name","company","disabled","is_group","parent_warehouse"], as_dict=True)
    result["sm_marikina_warehouse"] = wh
    # Check if its `company` field references an existing Company
    if wh and wh.get("company"):
        co_exists = frappe.db.exists("Company", wh["company"])
        result["sm_marikina_warehouse_company_exists"] = bool(co_exists)
        if co_exists:
            co = frappe.db.get_value("Company", wh["company"],
                ["name","default_currency","default_receivable_account","default_income_account",
                 "default_inventory_account","cost_center","stock_received_but_not_billed","parent_company"], as_dict=True)
            result["sm_marikina_actual_company"] = co

# Customer SM MARIKINA
sm_mar_cust = "SM MARIKINA - BEBANG SM MARIKINA INC."
if frappe.db.exists("Customer", sm_mar_cust):
    cust = frappe.db.get_value("Customer", sm_mar_cust,
        ["name","customer_type","customer_group","territory","tax_id",
         "is_internal_customer","represents_company"], as_dict=True)
    result["sm_marikina_customer"] = cust

# Compare AYALA VERMOSA setup (also failing — find its company)
av_wh = "AYALA VERMOSA - BEBANG MEGA INC."
if frappe.db.exists("Warehouse", av_wh):
    avwh = frappe.db.get_value("Warehouse", av_wh, ["name","company"], as_dict=True)
    result["ayala_vermosa_warehouse"] = avwh
    if avwh and avwh.get("company") and frappe.db.exists("Company", avwh["company"]):
        avco = frappe.db.get_value("Company", avwh["company"],
            ["name","default_receivable_account","default_income_account","default_inventory_account"], as_dict=True)
        result["ayala_vermosa_company"] = avco

# Compare with a working store: AYALA EVO
ae_wh = "AYALA EVO - BEBANG MEGA INC."
if frappe.db.exists("Warehouse", ae_wh):
    aewh = frappe.db.get_value("Warehouse", ae_wh, ["name","company"], as_dict=True)
    result["ayala_evo_warehouse"] = aewh
    if aewh and aewh.get("company") and frappe.db.exists("Company", aewh["company"]):
        aeco = frappe.db.get_value("Company", aewh["company"],
            ["name","default_receivable_account","default_income_account","default_inventory_account"], as_dict=True)
        result["ayala_evo_company"] = aeco

print(json.dumps(result, indent=2, default=str))
