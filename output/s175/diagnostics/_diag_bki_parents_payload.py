
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

out = {}
out["bki_parent_categories"] = {
    "NULL": frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE company=%s AND parent_account IS NULL", "Bebang Kitchen Inc.")[0][0],
    "empty_string": frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE company=%s AND parent_account=''", "Bebang Kitchen Inc.")[0][0],
    "non_null": frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE company=%s AND parent_account IS NOT NULL AND parent_account != ''", "Bebang Kitchen Inc.")[0][0],
}
# What does BKI's income-type tree look like?
out["bki_income_accounts"] = frappe.db.sql("""
    SELECT name, account_name, is_group, parent_account, lft, rgt
    FROM `tabAccount` WHERE company=%s AND root_type='Income'
    ORDER BY lft LIMIT 20
""", "Bebang Kitchen Inc.", as_dict=True)

# Do BKI and TIH share lft/rgt ranges?
out["bki_lft_range"] = frappe.db.sql("SELECT MIN(lft), MAX(rgt), COUNT(*) FROM `tabAccount` WHERE company=%s", "Bebang Kitchen Inc.")[0]
out["tih_lft_range"] = frappe.db.sql("SELECT MIN(lft), MAX(rgt), COUNT(*) FROM `tabAccount` WHERE company=%s", "Triple I Holdings")[0]

# What's at lft 1-10?
out["global_lft_1_10"] = frappe.db.sql("""
    SELECT name, company, account_name, is_group, parent_account, lft, rgt
    FROM `tabAccount` WHERE lft BETWEEN 1 AND 10 ORDER BY lft
""", as_dict=True)

# What's at the very highest lft/rgt?
out["global_max"] = frappe.db.sql("""
    SELECT name, company, lft, rgt FROM `tabAccount` ORDER BY rgt DESC LIMIT 5
""", as_dict=True)

# Check if normalize UPDATE reaches anything (dry run count)
out["bki_would_normalize"] = frappe.db.sql("""
    SELECT COUNT(*) FROM `tabAccount` WHERE company=%s AND parent_account=''
""", "Bebang Kitchen Inc.")[0][0]

print("DIAG_START")
print(json.dumps(out, default=str))
print("DIAG_END")
frappe.destroy()
