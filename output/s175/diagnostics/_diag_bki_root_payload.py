
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

out = {}
# For BKI, BEI, BFC, TIH, MF — show lft/rgt of top 10 accounts by lft
for c in ["Bebang Kitchen Inc.","Bebang Enterprise Inc.","BEBANG FRANCHISE CORP.","Triple I Holdings","Managed Franchise"]:
    rows = frappe.db.sql("""
        SELECT name, account_name, is_group, root_type, parent_account, lft, rgt
        FROM `tabAccount` WHERE company=%s
        ORDER BY lft LIMIT 8
    """, c, as_dict=True)
    out[c] = {"first_8_by_lft": rows}
    # min and max lft/rgt
    mm = frappe.db.sql("""
        SELECT MIN(lft), MAX(rgt), COUNT(*) FROM `tabAccount` WHERE company=%s
    """, c)[0]
    out[c]["min_lft"] = mm[0]
    out[c]["max_rgt"] = mm[1]
    out[c]["count"] = mm[2]

# BKI's 4000000 ancestors via recursive parent walk
a = frappe.db.get_value("Account", {"company":"Bebang Kitchen Inc.","account_number":"4000000"}, "name")
ancestors = []
cur = a
for _ in range(20):
    if not cur: break
    row = frappe.db.sql("SELECT name, parent_account, lft, rgt, root_type, is_group FROM `tabAccount` WHERE name=%s", cur, as_dict=True)
    if not row: break
    ancestors.append(row[0])
    cur = row[0]["parent_account"]
out["bki_4000000_ancestors"] = ancestors

# Check multi-company ancestor chain via lft/rgt
if a:
    bki_4000000_lft = frappe.db.sql("SELECT lft, rgt FROM `tabAccount` WHERE name=%s", a, as_dict=True)[0]
    # Find all accounts whose lft < this.lft AND rgt > this.rgt
    containing = frappe.db.sql("""
        SELECT name, company, account_name, is_group, lft, rgt
        FROM `tabAccount`
        WHERE lft < %s AND rgt > %s
        ORDER BY lft
    """, (bki_4000000_lft["lft"], bki_4000000_lft["rgt"]), as_dict=True)
    out["bki_4000000_containing_by_lftrgt"] = containing

print("DIAG_START")
print(json.dumps(out, default=str))
print("DIAG_END")
frappe.destroy()
