"""Find any Company with MARIKINA in name. The verify script reported
company_exists=false for 'BEBANG SM MARIKINA INC.' but handoff §3d says
it was fixed today. Either renamed, abbreviated, or named differently."""
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

# Find any company with MARIKINA
mk_cos = frappe.db.sql("""
    SELECT name, abbr, default_inventory_account, stock_received_but_not_billed,
           stock_adjustment_account, expenses_included_in_valuation, round_off_cost_center,
           parent_company
    FROM `tabCompany`
    WHERE name LIKE '%MARIKINA%' OR abbr LIKE '%SMK%' OR abbr LIKE '%BSMI%'
""", as_dict=True)
result["marikina_companies"] = [dict(r) for r in mk_cos]

# Also Warehouse and Customer
mk_wh = frappe.db.sql("SELECT name, company FROM `tabWarehouse` WHERE name LIKE '%MARIKINA%'", as_dict=True)
result["marikina_warehouses"] = [dict(r) for r in mk_wh]

# Find any account with SMK or BSMI suffix
acc_smk = frappe.db.sql("SELECT name, company FROM `tabAccount` WHERE name LIKE '%- SMK' LIMIT 20", as_dict=True)
acc_bsmi = frappe.db.sql("SELECT name, company FROM `tabAccount` WHERE name LIKE '%- BSMI' LIMIT 20", as_dict=True)
result["accounts_smk_count"] = len(acc_smk)
result["accounts_smk_sample"] = [r["name"] for r in acc_smk][:10]
result["accounts_bsmi_count"] = len(acc_bsmi)
result["accounts_bsmi_sample"] = [r["name"] for r in acc_bsmi][:10]

print(json.dumps(result, indent=2, default=str))
