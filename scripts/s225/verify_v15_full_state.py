"""Verify v15-era state plus full 49-store canonical readiness post-S231/S232 BD changes.

Checks beyond verify_v7_fixes_still_applied.py:
  - SM MARIKINA Company is_group = 0 (v15 fix)
  - 24 BEI Routes (0633-0656) all exist + active = 1 (15 original + 9 added)
  - Each of the 49 fixture stores has Company + Warehouse + Customer (canonical 3)
  - Each per-store Company is_group = 0 (no other store accidentally flipped)
  - SM MARIKINA in _get_allowed_target_companies() output

Output: JSON. Verdict: READY / DRIFT_DETECTED.
"""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {"checks": {}, "drifts": []}

# Load fixture stores (mounted from /tmp)
with open("/tmp/v16_fixture.json") as f:
    fixture = json.load(f)
fixture_stores = [e["store"] for e in fixture]

# 1. SM MARIKINA is_group=0
sm = frappe.db.get_value("Company", "SM MARIKINA - BEBANG SM MARIKINA INC.", "is_group")
result["checks"]["sm_marikina_is_group_0"] = sm == 0
if sm != 0:
    result["drifts"].append({"type": "sm_marikina_is_group_flipped", "actual": sm})

# 2. 24 BEI Routes (0633-0656) exist + active
expected_routes = [f"BEI-ROUTE-{n:04d}" for n in list(range(633, 648)) + list(range(648, 657))]
existing = frappe.db.sql("""
    SELECT name, route_name, cargo_type, source_warehouse, COALESCE(active,0) AS active
    FROM `tabBEI Route`
    WHERE name IN %(names)s
""", {"names": tuple(expected_routes)}, as_dict=True)
existing_names = {r["name"] for r in existing}
missing_routes = [n for n in expected_routes if n not in existing_names]
inactive_routes = [r["name"] for r in existing if not r.get("active")]
result["checks"]["bei_routes_24"] = {
    "expected": 24, "found": len(existing),
    "missing": missing_routes, "inactive": inactive_routes,
    "ok": not missing_routes and not inactive_routes,
}
if missing_routes:
    result["drifts"].append({"type": "missing_bei_routes", "routes": missing_routes})
if inactive_routes:
    result["drifts"].append({"type": "inactive_bei_routes", "routes": inactive_routes})

# 3. SM MARIKINA in allowed_target_companies
try:
    from hrms.api.warehouse import _get_allowed_target_companies
    allowed = _get_allowed_target_companies()
    in_allowed = "SM MARIKINA - BEBANG SM MARIKINA INC." in allowed
    result["checks"]["sm_marikina_in_allowed_target"] = in_allowed
    result["checks"]["allowed_target_count"] = len(allowed)
    if not in_allowed:
        result["drifts"].append({"type": "sm_marikina_not_in_allowed_target_companies"})
except Exception as e:
    result["checks"]["sm_marikina_in_allowed_target"] = f"ERROR: {str(e)[:200]}"

# 4. All 49 fixture stores have Company + Warehouse + Customer
missing_records = []
for store in fixture_stores:
    co = frappe.db.exists("Company", store)
    wh = frappe.db.exists("Warehouse", store)
    cust = frappe.db.exists("Customer", store)
    if not (co and wh and cust):
        missing_records.append({"store": store, "company": bool(co), "warehouse": bool(wh), "customer": bool(cust)})
result["checks"]["all_49_canonical_records"] = {
    "missing": missing_records, "ok": not missing_records,
}
if missing_records:
    result["drifts"].append({"type": "missing_canonical_records", "stores": missing_records})

# 5. All 49 per-store Companies have is_group = 0
group_stores = []
for store in fixture_stores:
    if frappe.db.exists("Company", store):
        ig = frappe.db.get_value("Company", store, "is_group")
        if ig == 1:
            group_stores.append(store)
result["checks"]["all_49_companies_leaf"] = {
    "is_group_1": group_stores, "ok": not group_stores,
}
if group_stores:
    result["drifts"].append({"type": "stores_with_is_group_1", "stores": group_stores})

# 6. Each store has at least one BEI Route assigned
stores_no_routes = []
for store in fixture_stores:
    has_route = frappe.db.sql("""
        SELECT 1 FROM `tabBEI Route Stop` brs
        INNER JOIN `tabBEI Route` br ON br.name = brs.parent
        WHERE brs.store = %s AND COALESCE(br.active,0) = 1
        LIMIT 1
    """, (store,))
    if not has_route:
        stores_no_routes.append(store)
result["checks"]["all_49_have_routes"] = {
    "no_routes": stores_no_routes, "ok": not stores_no_routes,
}
if stores_no_routes:
    result["drifts"].append({"type": "stores_without_active_routes", "stores": stores_no_routes})

# Final verdict
result["verdict"] = "READY" if not result["drifts"] else "DRIFT_DETECTED"
result["drift_count"] = len(result["drifts"])

print(json.dumps(result, indent=2, default=str))
