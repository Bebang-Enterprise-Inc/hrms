
import os, json, inspect
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from erpnext.accounts.doctype.account.account import Account
src = inspect.getsource(Account.validate_root_company_and_sync_account_to_children)
print("SRC_START")
print(src)
print("SRC_END")

# Also try this: find_ancestors or similar
try:
    from erpnext.accounts.doctype.account.account import get_ancestors_of
    print("GET_ANCESTORS_OF SRC:")
    print(inspect.getsource(get_ancestors_of))
except Exception as e:
    print(f"no get_ancestors_of: {e}")

# Frappe's get_ancestors_of
try:
    src2 = inspect.getsource(frappe.db.get_ancestors)
    print("frappe.db.get_ancestors:")
    print(src2)
except:
    pass

frappe.destroy()
