"""Probe why SM MARIKINA isn't in _get_allowed_target_companies()."""
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

# Direct call
from hrms.api.warehouse import _get_allowed_target_companies
allowed = _get_allowed_target_companies()
result["allowed_count"] = len(allowed)
result["sm_marikina_in_allowed"] = "SM MARIKINA - BEBANG SM MARIKINA INC." in allowed
result["sample_allowed"] = sorted(allowed)[:30]

# Direct SQL
rows = frappe.db.sql("""
    SELECT name, is_group, parent_company FROM `tabCompany`
    WHERE name = 'SM MARIKINA - BEBANG SM MARIKINA INC.'
""", as_dict=True)
result["sm_marikina_company_record"] = [dict(r) for r in rows]

# Check if BEI Settings has any allow-list config
try:
    val = frappe.db.get_single_value("BEI Settings", "allowed_target_companies")
    result["bei_settings_allowed_csv"] = val[:500] if val else None
except Exception as e:
    result["bei_settings_error"] = str(e)[:200]

# Show DEFAULT fallback list
try:
    from hrms.api.warehouse import _ALLOWED_TARGET_COMPANIES_DEFAULT
    result["default_fallback"] = list(_ALLOWED_TARGET_COMPANIES_DEFAULT)
except Exception as e:
    result["default_fallback_err"] = str(e)[:200]

# Other 5 fail stores — check membership
fail_stores = [
    "STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC.",
    "THE GRID ROCKWELL - TASTECARTEL CORP.",
    "THE TERMINAL - BEBANG STARMALL ALABANG INC.",
    "UP TOWN MALL BGC - DMD HOLDINGS INC.",
    "VISTA MALL TAGUIG - TRICERN FOOD CORP.",
]
result["fail_stores_in_allowed"] = {s: (s in allowed) for s in fail_stores}

# What about parent_company entries?
parent_cos = ["BEBANG ENTERPRISE INC.", "BEBANG SM MARIKINA INC.", "TASTECARTEL CORP.", "BEBANG STARMALL ALABANG INC.", "DMD HOLDINGS INC.", "TRICERN FOOD CORP."]
result["parent_companies_in_allowed"] = {c: (c in allowed) for c in parent_cos}

print(json.dumps(result, indent=2, default=str))
