
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

out = {}

# Check rebuild_tree function signature
import inspect
from frappe.utils.nestedset import rebuild_tree
try:
    out["rebuild_tree_source"] = inspect.getsource(rebuild_tree)[:2500]
except:
    out["rebuild_tree_source"] = "unavailable"

print("DIAG_START")
print(json.dumps(out, default=str))
print("DIAG_END")
frappe.destroy()
