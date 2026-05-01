"""Fix SM MARIKINA's Company misconfig: is_group=1 → is_group=0.

Per canonical store/company SSOT, every per-store Company should be a leaf
(is_group=0). SM MARIKINA - BEBANG SM MARIKINA INC. has is_group=1 which makes
`_get_allowed_target_companies()` exclude it (the SQL filters group Companies),
which makes WR auto-creation fail with 'Target warehouse must belong to one of:'.

This is the root cause of SM MARIKINA's reproducible test failure.

Probe + fix + verify in one shot. Idempotent."""
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe, json
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {}

CO_NAME = "SM MARIKINA - BEBANG SM MARIKINA INC."

# 1. Pre-state
pre = frappe.db.get_value("Company", CO_NAME, ["is_group", "parent_company"], as_dict=True)
result["pre"] = dict(pre) if pre else {"NOT_FOUND": True}

# 2. Identify children of SM MARIKINA (need to know who's affected)
children = frappe.db.sql("""
    SELECT name, is_group, parent_company FROM `tabCompany`
    WHERE parent_company = %s
""", (CO_NAME,), as_dict=True)
result["children_before_fix"] = [dict(r) for r in children]

# 3. Apply fix: is_group=0 (idempotent)
if pre and pre.get("is_group") == 1:
    frappe.db.set_value("Company", CO_NAME, "is_group", 0)
    frappe.db.commit()
    result["fix_applied"] = True
else:
    result["fix_applied"] = False
    result["reason"] = "already is_group=0 or company not found"

# 4. Post-state verify
post = frappe.db.get_value("Company", CO_NAME, ["is_group", "parent_company"], as_dict=True)
result["post"] = dict(post) if post else {}

# 5. Verify _get_allowed_target_companies() now includes SM MARIKINA
from hrms.api.warehouse import _get_allowed_target_companies
allowed = _get_allowed_target_companies()
result["sm_marikina_now_in_allowed"] = CO_NAME in allowed
result["allowed_count_after_fix"] = len(allowed)

# 6. Children still resolve correctly (parent_company points to non-group is OK in Frappe)
post_children = frappe.db.sql("""
    SELECT name, is_group, parent_company FROM `tabCompany`
    WHERE parent_company = %s
""", (CO_NAME,), as_dict=True)
result["children_after_fix"] = [dict(r) for r in post_children]

print(json.dumps(result, indent=2, default=str))
