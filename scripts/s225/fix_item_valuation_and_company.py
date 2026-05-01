"""Fix:
  1. Set valuation_rate=1.0 on all PM/FG/KL items currently missing it
     (so SI creation can price line items)
  2. Investigate AYALA VERMOSA Company default_inventory_account gap;
     copy from BEBANG MEGA INC. parent if missing
  3. Audit SM MARIKINA Stock In Hand - BSMI account exists / is set up
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

result = {}

# ==== Step 1: Set valuation_rate on PM/FG/KL items missing it ====
items_to_fix = frappe.db.sql("""
    SELECT name, item_code, item_name FROM `tabItem`
    WHERE (item_code LIKE 'PM%' OR item_code LIKE 'FG%' OR item_code LIKE 'KL%')
      AND is_stock_item = 1
      AND disabled = 0
      AND (valuation_rate IS NULL OR valuation_rate <= 0)
    ORDER BY item_code
""", as_dict=True)

result["items_fixed"] = []
for item in items_to_fix:
    try:
        frappe.db.set_value("Item", item["item_code"], "valuation_rate", 1.0)
        result["items_fixed"].append(item["item_code"])
    except Exception as e:
        result.setdefault("item_errors", []).append({"item": item["item_code"], "error": str(e)[:200]})
frappe.db.commit()
result["items_fixed_count"] = len(result["items_fixed"])
result["items_fixed_first_15"] = result["items_fixed"][:15]
del result["items_fixed"]  # too long for SSM stdout

# Verify
verify_count = frappe.db.sql("""
    SELECT COUNT(*) AS cnt FROM `tabItem`
    WHERE (item_code LIKE 'PM%' OR item_code LIKE 'FG%' OR item_code LIKE 'KL%')
      AND is_stock_item=1 AND disabled=0
      AND (valuation_rate IS NULL OR valuation_rate <= 0)
""", as_dict=True)
result["items_still_missing_valuation_rate"] = verify_count[0]["cnt"]

# ==== Step 2: AYALA VERMOSA Company audit + fix ====
av_co = "AYALA VERMOSA - BEBANG MEGA INC."
parent_co = "BEBANG MEGA INC."

if frappe.db.exists("Company", av_co):
    av_inv = frappe.db.get_value("Company", av_co, "default_inventory_account")
    parent_inv = frappe.db.get_value("Company", parent_co, "default_inventory_account") if frappe.db.exists("Company", parent_co) else None
    result["AV_BEFORE"] = {
        "company": av_co,
        "default_inventory_account": av_inv,
        "parent_inventory_account": parent_inv,
    }
    if not av_inv and parent_inv:
        # Copy from parent
        try:
            frappe.db.set_value("Company", av_co, "default_inventory_account", parent_inv)
            frappe.db.commit()
            result["AV_FIX"] = "copied default_inventory_account from parent"
        except Exception as e:
            result["AV_FIX_ERROR"] = str(e)[:200]
    av_inv_after = frappe.db.get_value("Company", av_co, "default_inventory_account")
    result["AV_AFTER"] = {"default_inventory_account": av_inv_after}

# ==== Step 3: Audit ALL per-store Companies for similar gaps ====
all_per_store_cos = frappe.db.sql("""
    SELECT name, abbr, default_receivable_account, default_income_account, default_inventory_account, parent_company, cost_center
    FROM `tabCompany`
    WHERE name LIKE '%BEBANG%' OR name LIKE '%TUNGSTEN%' OR name LIKE '%FOOD CORP%' OR name LIKE '%FOOD OPC%' OR name LIKE '%HOLDINGS%'
""", as_dict=True)

result["per_store_company_gaps"] = []
for co in all_per_store_cos:
    gaps = []
    if not co.get("default_receivable_account"): gaps.append("default_receivable_account")
    if not co.get("default_income_account"): gaps.append("default_income_account")
    if not co.get("default_inventory_account"): gaps.append("default_inventory_account")
    if not co.get("cost_center"): gaps.append("cost_center")
    if gaps:
        result["per_store_company_gaps"].append({
            "company": co["name"], "abbr": co["abbr"],
            "parent": co["parent_company"], "missing": gaps,
        })
result["per_store_company_gap_count"] = len(result["per_store_company_gaps"])

# ==== Step 4: Account existence check for SM MARIKINA's BSMI accounts ====
sm_mar_accounts = ["Stock In Hand - BSMI", "Stock Received But Not Billed - BSMI", "Debtors - SMK", "Sales - SMK", "Main - SMK"]
result["sm_marikina_accounts"] = {}
for acc in sm_mar_accounts:
    exists = frappe.db.exists("Account", acc) or frappe.db.exists("Cost Center", acc)
    result["sm_marikina_accounts"][acc] = bool(exists)

print(json.dumps(result, indent=2, default=str))
