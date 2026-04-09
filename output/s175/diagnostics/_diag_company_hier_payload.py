
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

out = {}
# Show all companies with parent_company
out["companies_full"] = frappe.db.sql("""
    SELECT name, abbr, parent_company, is_group, lft, rgt
    FROM `tabCompany` ORDER BY lft
""", as_dict=True)

# For BKI specifically, what's its parent/ancestors?
out["bki_row"] = frappe.db.sql("SELECT * FROM `tabCompany` WHERE name='Bebang Kitchen Inc.'", as_dict=True)
out["bei_row"] = frappe.db.sql("SELECT * FROM `tabCompany` WHERE name='Bebang Enterprise Inc.'", as_dict=True)
out["bfc_row"] = frappe.db.sql("SELECT * FROM `tabCompany` WHERE name='BEBANG FRANCHISE CORP.'", as_dict=True)

print("DIAG_START")
print(json.dumps(out, default=str))
print("DIAG_END")
frappe.destroy()
