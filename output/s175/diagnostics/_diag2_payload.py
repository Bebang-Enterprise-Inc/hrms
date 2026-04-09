
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

out = {}
for c in ["Bebang Enterprise Inc.", "Bebang Kitchen Inc.", "Triple I Holdings", "JV", "Managed Franchise"]:
    out[c] = {}
    # Top-level accounts (parent_account IS NULL) — only count + first 15
    out[c]["root_level_count"] = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabAccount` WHERE company=%s AND parent_account IS NULL
    """, c)[0][0]
    out[c]["root_level"] = frappe.db.sql("""
        SELECT account_name, account_number, root_type, is_group
        FROM `tabAccount` WHERE company=%s AND parent_account IS NULL AND is_group=1
        ORDER BY lft
    """, c, as_dict=True)
    # Does company have any "Income" group?
    out[c]["income_groups_count"] = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabAccount` WHERE company=%s AND root_type='Income' AND is_group=1", c
    )[0][0]
    out[c]["total_accounts"] = frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE company=%s", c)[0][0]
    # 4000000 specific
    r = frappe.db.sql("""
        SELECT name, account_name, account_number, parent_account, is_group, root_type, lft, rgt
        FROM `tabAccount` WHERE company=%s AND account_number='4000000'
    """, c, as_dict=True)
    out[c]["4000000"] = r
    # If 4000000 is a group, what are its children?
    if r and r[0]["is_group"]:
        out[c]["4000000_children"] = frappe.db.sql("""
            SELECT name, account_number, account_name, is_group, root_type FROM `tabAccount` WHERE parent_account=%s
        """, r[0]["name"], as_dict=True)
    # GL entries on 4000000 (safety for BEI posting case)
    if r:
        gl = frappe.db.sql("SELECT COUNT(*) FROM `tabGL Entry` WHERE account=%s", r[0]["name"])[0][0]
        out[c]["4000000_gl_entries"] = gl
print("DIAG_START")
print(json.dumps(out, default=str))
print("DIAG_END")
frappe.destroy()
