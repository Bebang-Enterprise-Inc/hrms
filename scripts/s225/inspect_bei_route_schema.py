"""Inspect BEI Route + BEI Route Stop schema so we can insert correctly."""
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
for dt in ["BEI Route", "BEI Route Stop"]:
    if not frappe.db.exists("DocType", dt):
        result[dt] = "DOCTYPE_MISSING"
        continue
    meta = frappe.get_meta(dt)
    result[dt] = {
        "is_submittable": meta.is_submittable,
        "autoname": meta.autoname,
        "naming_rule": getattr(meta, "naming_rule", None),
        "fields": [
            {
                "fieldname": f.fieldname,
                "label": f.label,
                "fieldtype": f.fieldtype,
                "options": (f.options or "")[:80],
                "reqd": f.reqd,
                "unique": f.unique,
                "default": f.default,
            }
            for f in meta.fields if f.fieldname not in ("amended_from",)
        ],
    }

# Sample 1 existing route to see actual values
sample_route = frappe.db.sql("""
    SELECT * FROM `tabBEI Route`
    WHERE COALESCE(active,1) = 1
    ORDER BY creation DESC
    LIMIT 1
""", as_dict=True)
result["sample_existing_route"] = sample_route[0] if sample_route else None
if sample_route:
    sample_stops = frappe.db.sql("""
        SELECT * FROM `tabBEI Route Stop`
        WHERE parent = %s
    """, sample_route[0]["name"], as_dict=True)
    result["sample_route_stops"] = sample_stops

print(json.dumps(result, indent=2, default=str))
