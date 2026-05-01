"""Non-mutating audit: confirm v7 production fixes from 2026-04-30 still in place.

Checks:
 1. Zero PM/FG/KL items with valuation_rate IS NULL or <= 0
 2. AYALA VERMOSA Company default_inventory_account == 'Stock In Hand - BMI2'
 3. SM MARIKINA Company has all 5 BSMI->SMK account fields repointed correctly
 4. 15 BEI Routes BEI-ROUTE-0633..0647 still exist + active=1

Output: short JSON summary fitting SSM stdout. all_clear=true means safe to sweep.
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

result = {"checks": {}, "verdict": "PENDING"}

# ===== 1. Item valuation_rate gaps =====
missing_val = frappe.db.sql("""
    SELECT item_code, valuation_rate FROM `tabItem`
    WHERE (item_code LIKE 'PM%' OR item_code LIKE 'FG%' OR item_code LIKE 'KL%')
      AND is_stock_item = 1
      AND disabled = 0
      AND (valuation_rate IS NULL OR valuation_rate <= 0)
""", as_dict=True)
result["checks"]["item_valuation"] = {
    "missing_count": len(missing_val),
    "missing_codes": [r["item_code"] for r in missing_val][:20],
    "ok": len(missing_val) == 0,
}

# ===== 2. AYALA VERMOSA company =====
av_co = "AYALA VERMOSA - BEBANG MEGA INC."
av_exists = bool(frappe.db.exists("Company", av_co))
av_inv = frappe.db.get_value("Company", av_co, "default_inventory_account") if av_exists else None
result["checks"]["ayala_vermosa"] = {
    "company_exists": av_exists,
    "default_inventory_account": av_inv,
    "expected": "Stock In Hand - BMI2",
    "ok": av_inv == "Stock In Hand - BMI2",
}

# ===== 3. SM MARIKINA company (canonical name = STORE - PARENT) =====
sm_co = "SM MARIKINA - BEBANG SM MARIKINA INC."
expected_sm = {
    "default_inventory_account": "Stock In Hand - SMK",
    "stock_received_but_not_billed": "Stock Received But Not Billed - BEI",
    "stock_adjustment_account": "Stock Adjustment - SMK",
    "expenses_included_in_valuation": "Expenses Included In Valuation - SMK",
    "round_off_cost_center": "Main - SMK",
}
sm_exists = bool(frappe.db.exists("Company", sm_co))
if sm_exists:
    actual_sm = frappe.db.get_value("Company", sm_co,
        list(expected_sm.keys()), as_dict=True)
    sm_diffs = {k: {"actual": actual_sm.get(k), "expected": v}
                for k, v in expected_sm.items() if actual_sm.get(k) != v}
    result["checks"]["sm_marikina"] = {
        "company_exists": True,
        "actual": dict(actual_sm),
        "diffs": sm_diffs,
        "ok": len(sm_diffs) == 0,
    }
else:
    result["checks"]["sm_marikina"] = {"company_exists": False, "ok": False}

# ===== 4. BEI Routes 0633..0647 =====
expected_routes = [f"BEI-ROUTE-{n:04d}" for n in range(633, 648)]
existing_routes = frappe.db.sql("""
    SELECT name, route_name, cargo_type, source_warehouse, active
    FROM `tabBEI Route`
    WHERE name IN %(names)s
""", {"names": tuple(expected_routes)}, as_dict=True)
existing_names = {r["name"] for r in existing_routes}
missing_routes = [n for n in expected_routes if n not in existing_names]
inactive_routes = [r["name"] for r in existing_routes if not r.get("active")]
result["checks"]["bei_routes"] = {
    "expected_count": len(expected_routes),
    "found_count": len(existing_routes),
    "missing": missing_routes,
    "inactive": inactive_routes,
    "ok": len(missing_routes) == 0 and len(inactive_routes) == 0,
}

# ===== Final verdict =====
all_ok = all(c.get("ok") for c in result["checks"].values())
result["verdict"] = "ALL_FIXES_INTACT" if all_ok else "REGRESSION_DETECTED"

print(json.dumps(result, indent=2, default=str))
