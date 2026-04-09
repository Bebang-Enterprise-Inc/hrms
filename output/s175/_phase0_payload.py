
#!/usr/bin/env python3
"""S175 Phase 0 live re-verify payload — read-only."""
import os, json, sys
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

BKI_DELETE_NUMS = [
    "4000001","4000002","4000100","4000101","4000200","4000201","4000202",
    "4000203","4000204","4000205","4000206","4000207","4000208","4000300",
    "4000301","4000302","4000303","4000304","4000305","4000306",
]
BEI_DELETE_NUMS = [
    "4000001","4000002","4000003","4000004","4000005","4000006","4000200",
    "4000201","4000202","4000203","4000204","4000205","4000206","4000207",
    "4000208","4000300","4000301","4000302","4000303","4000304","4000305","4000306",
]
BEI = "Bebang Enterprise Inc."
BKI = "Bebang Kitchen Inc."

result = {}

# 1. Company count + BFC existence
companies = frappe.get_all("Company", fields=["name","abbr","tax_id","default_currency"])
result["companies_count"] = len(companies)
result["companies"] = sorted([c["name"] for c in companies])
result["bfc_exists_real"] = bool(frappe.db.exists("Company", "BEBANG FRANCHISE CORP."))

# 2. BEI 6xxxxxx breakdown + GL
rows = frappe.db.sql("""
    SELECT root_type, report_type, COUNT(*)
    FROM `tabAccount`
    WHERE company = %s AND account_number LIKE '6%%'
    GROUP BY root_type, report_type
""", BEI, as_dict=False)
bei_6xxx_breakdown = [{"root_type": r[0], "report_type": r[1], "count": r[2]} for r in rows]
bei_6xxx_total = sum(r["count"] for r in bei_6xxx_breakdown)
gl6 = frappe.db.sql("""
    SELECT COUNT(*) FROM `tabGL Entry` ge
    JOIN `tabAccount` a ON ge.account = a.name
    WHERE a.company = %s AND a.account_number LIKE '6%%'
""", BEI)[0][0]
result["bei_6xxx"] = {
    "total": bei_6xxx_total,
    "breakdown": bei_6xxx_breakdown,
    "gl_entries": gl6,
}

def probe(company, number):
    row = frappe.db.sql(
        "SELECT name, account_name, is_group, root_type FROM `tabAccount` WHERE company=%s AND account_number=%s",
        (company, number), as_dict=True,
    )
    if not row:
        return {"exists": False}
    name = row[0]["name"]
    gl = frappe.db.sql("SELECT COUNT(*) FROM `tabGL Entry` WHERE account=%s", name)[0][0]
    children = frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE parent_account=%s", name)[0][0]
    r = row[0]
    r["exists"] = True
    r["gl_entries"] = gl
    r["children_count"] = children
    return r

result["bki_delete_targets"] = {num: probe(BKI, num) for num in BKI_DELETE_NUMS}
result["bei_delete_targets"] = {num: probe(BEI, num) for num in BEI_DELETE_NUMS}

# 3. BEI Settings
bs = frappe.get_single("BEI Settings")
bei_settings_fields = [
    "bki_sales_income_account","bki_output_vat_account",
    "gr_ir_clearing_account","input_vat_goods_account",
    "input_vat_services_account","input_vat_capital_goods_account",
    "advances_to_suppliers_account","ewt_payable_account","ap_trade_account",
]
result["bei_settings"] = {}
for f in bei_settings_fields:
    val = bs.get(f) or ""
    exists = bool(val) and bool(frappe.db.exists("Account", val))
    result["bei_settings"][f] = {"value": val, "linked_account_exists": exists}

# 4. BEI 2104xxx range (collision check for 2104200)
result["bei_2104_range"] = frappe.db.sql(
    "SELECT account_number, account_name, is_group FROM `tabAccount` "
    "WHERE company=%s AND account_number LIKE '2104%%' ORDER BY account_number",
    BEI, as_dict=True,
)
result["bei_2104200_exists"] = bool(
    frappe.db.get_value("Account", {"company": BEI, "account_number": "2104200"}, "name")
)

# 5. BKI Store customer group count (S168 baseline)
result["bki_store_customer_count"] = frappe.db.sql(
    "SELECT COUNT(*) FROM `tabCustomer` WHERE customer_group=%s", "BKI Store"
)[0][0]

print("S175_PHASE0_JSON_START")
print(json.dumps(result, default=str))
print("S175_PHASE0_JSON_END")

frappe.destroy()
