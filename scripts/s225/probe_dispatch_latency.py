"""Probe get_ready_for_dispatch API latency.

For each newly-Ordered MR (created within the last 30 min), check whether it
appears in get_ready_for_dispatch() output. Then for any MR that's NOT
appearing yet, measure how long it takes to surface.

Specifically focus on SM MARIKINA's recent MRs (MAT-MR-2026-008xx-009xx).

This tells us: does the API have lag between MR.docstatus=1+status=Ordered
and the API returning it? If yes, that's a backend cache/latency issue.
"""
import os, time, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {}

# 1. Recent MRs in Ordered state for SM MARIKINA destination
recent_mrs = frappe.db.sql("""
    SELECT name, status, docstatus, creation, modified,
           custom_destination_warehouse, custom_target_company
    FROM `tabMaterial Request`
    WHERE creation > NOW() - INTERVAL 60 MINUTE
      AND custom_destination_warehouse = 'SM MARIKINA - BEBANG SM MARIKINA INC.'
      AND material_request_type IN ('Material Transfer', 'Material Issue')
    ORDER BY creation DESC
    LIMIT 10
""", as_dict=True)
result["recent_marikina_mrs"] = [dict(r) for r in recent_mrs]

# 2. Call get_ready_for_dispatch directly and time it
from hrms.api.warehouse import get_ready_for_dispatch

t0 = time.time()
api = get_ready_for_dispatch()
t_elapsed = time.time() - t0
result["api_call_seconds"] = round(t_elapsed, 3)
result["api_total_stores_returned"] = len(api.get("data", []))

# 3. Find SM MARIKINA in API output
marikina_in_api = [s for s in api.get("data", []) if "SM MARIKINA" in s.get("store", "").upper()]
result["sm_marikina_in_api"] = bool(marikina_in_api)
if marikina_in_api:
    result["sm_marikina_request_names"] = [r["name"] for r in marikina_in_api[0].get("requests", [])]

# 4. Cross-check: any MRs in `Ordered` state that are NOT in API
ordered_mrs = frappe.db.sql("""
    SELECT name, status, docstatus, custom_destination_warehouse, creation
    FROM `tabMaterial Request`
    WHERE status IN ('Ordered', 'Partially Ordered')
      AND docstatus = 1
      AND material_request_type IN ('Material Transfer', 'Material Issue')
      AND creation > NOW() - INTERVAL 60 MINUTE
""", as_dict=True)
api_mr_names = set()
for s in api.get("data", []):
    for r in s.get("requests", []):
        api_mr_names.add(r["name"])

mrs_missing_from_api = [m for m in ordered_mrs if m["name"] not in api_mr_names]
result["mrs_missing_from_api"] = [dict(m) for m in mrs_missing_from_api]
result["mrs_missing_count"] = len(mrs_missing_from_api)
result["mrs_in_db_ordered_60m"] = len(ordered_mrs)

print(json.dumps(result, indent=2, default=str))
