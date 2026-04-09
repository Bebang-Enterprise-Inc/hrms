
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

r = {}
for c in ["Bebang Kitchen Inc.", "Bebang Enterprise Inc.", "BEBANG FRANCHISE CORP.", "Triple I Holdings"]:
    r[c] = {
        "income_roots_no_parent": frappe.db.sql("""
            SELECT name, account_name, is_group, lft, rgt
            FROM `tabAccount`
            WHERE company=%s AND root_type='Income' AND parent_account IS NULL
            ORDER BY lft
        """, c, as_dict=True),
        "all_income_groups": frappe.db.sql("""
            SELECT name, account_name, is_group, parent_account, lft
            FROM `tabAccount`
            WHERE company=%s AND root_type='Income' AND is_group=1
            ORDER BY lft
        """, c, as_dict=True),
        "4000000": frappe.db.sql("""
            SELECT name, account_name, parent_account, root_type, is_group, lft, rgt
            FROM `tabAccount`
            WHERE company=%s AND account_number='4000000'
        """, c, as_dict=True),
    }
print("DIAG_START")
print(json.dumps(r, default=str))
print("DIAG_END")
frappe.destroy()
