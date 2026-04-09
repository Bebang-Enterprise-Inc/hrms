#!/usr/bin/env python3
"""S175 Phase 10 — Full verification of all S175 structural outcomes.

12 checks per plan Task 10.1:
 1. Company count = 40
 2. Each of 40 companies has 27-row template (= 1080 assertions)
 3. BKI: 4000100/4000101 absent; 4000200/4000210 present
 4. BEI: deleted legacy accounts absent; 4000005 preserved
 5. BEI Settings.bki_sales_income_account resolves to 4000210 DELIVERIES - BKI
 6. BEI 6xxxxxx: all Expense, zero Income
 7. BFC: company exists with correct tax_id
 8. Intercompany scaffolding: 2104200 BEI, 1104200 BFC, 2102205 BFC
 9. 4000200 is NOT a DISCOUNTS group on any company
10. BKI Store customer group count = 35 (S168 baseline)
11. S168 Custom Fields present (broad match)
12. (optional) BEI input_vat_goods_account — policy, skipped
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s175_ssm_runner import run_on_frappe  # noqa: E402
from s175_master_coa_template import MASTER_SALES_TEMPLATE  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output" / "s175"

TEMPLATE_NUMBERS = [row[0] for row in MASTER_SALES_TEMPLATE]  # 27 numbers
NUMBERS_JSON = json.dumps(TEMPLATE_NUMBERS)

PAYLOAD = r'''
#!/usr/bin/env python3
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

TEMPLATE_NUMS = json.loads(__NUMBERS_JSON__)

checks = {}

# 1. Company count
checks["1_company_count"] = {
    "value": frappe.db.sql("SELECT COUNT(*) FROM `tabCompany`")[0][0],
    "expected": 40,
}
checks["1_company_count"]["pass"] = checks["1_company_count"]["value"] == 40

# 2. Template on all 40
companies = frappe.get_all("Company", pluck="name")
per_company_missing = {}
total_assertions = 0
total_passing = 0
for c in companies:
    total_assertions += 27
    present = frappe.db.sql("""
        SELECT account_number FROM `tabAccount`
        WHERE company=%s AND account_number IN ({})
    """.format(",".join(["%s"] * 27)), [c] + TEMPLATE_NUMS, as_list=True)
    present_set = {r[0] for r in present}
    missing = [n for n in TEMPLATE_NUMS if n not in present_set]
    total_passing += (27 - len(missing))
    if missing:
        per_company_missing[c] = missing
checks["2_template_on_all_companies"] = {
    "total_assertions": total_assertions,
    "passing": total_passing,
    "missing_per_company": per_company_missing,
    "pass": len(per_company_missing) == 0,
}

# 3. BKI legacy
bki_absent_nums = ["4000100", "4000101"]
# 4000100 must NOT exist as "WHOLESALE / B2B SALES" (the legacy content).
# BUT the new template also uses 4000100 (as STORE SALES group).
# So distinguish by account_name.
r3 = {}
r3["4000100_is_legacy_wholesale_absent"] = not bool(frappe.db.sql(
    "SELECT name FROM `tabAccount` WHERE company='Bebang Kitchen Inc.' AND account_number='4000100' AND account_name='WHOLESALE / B2B SALES'"
))
r3["4000101_absent"] = not bool(frappe.db.get_value(
    "Account", {"company": "Bebang Kitchen Inc.", "account_number": "4000101"}, "name"
))
r3["4000200_BKI_SALES_exists"] = bool(frappe.db.sql(
    "SELECT name FROM `tabAccount` WHERE company='Bebang Kitchen Inc.' AND account_number='4000200' AND account_name='BKI SALES' AND is_group=1"
))
r3["4000210_DELIVERIES_exists"] = bool(frappe.db.sql(
    "SELECT name FROM `tabAccount` WHERE company='Bebang Kitchen Inc.' AND account_number='4000210' AND account_name='DELIVERIES' AND is_group=0"
))
r3["pass"] = all([r3["4000100_is_legacy_wholesale_absent"], r3["4000101_absent"],
                  r3["4000200_BKI_SALES_exists"], r3["4000210_DELIVERIES_exists"]])
checks["3_bki_legacy"] = r3

# 4. BEI deletions verified via legacy account names that no longer match template
r4 = {}
# 4000005 BRAND GROWTH FEE INCOME must exist
r4["4000005_preserved"] = bool(frappe.db.sql(
    "SELECT name FROM `tabAccount` WHERE company='Bebang Enterprise Inc.' AND account_number='4000005' AND account_name='BRAND GROWTH FEE INCOME'"
))
# Legacy names that should be absent because they were deleted and template replaced them
legacy_names_gone = ["ROYALTY INCOME", "MANAGEMENT FEE INCOME", "FRANCHISE INCOME"]
for nm in legacy_names_gone:
    present = frappe.db.sql(
        "SELECT name FROM `tabAccount` WHERE company='Bebang Enterprise Inc.' AND account_name=%s",
        nm,
    )
    r4[f"legacy_{nm.replace(' ', '_')}_absent"] = not bool(present)
r4["pass"] = all([r4["4000005_preserved"]] + [r4[f"legacy_{nm.replace(' ', '_')}_absent"] for nm in legacy_names_gone])
checks["4_bei_legacy"] = r4

# 5. BEI Settings bki_sales_income_account
bs = frappe.get_single("BEI Settings")
val = bs.bki_sales_income_account
r5 = {
    "value": val,
    "resolves": bool(frappe.db.exists("Account", val)) if val else False,
    "contains_DELIVERIES": "DELIVERIES" in (val or ""),
    "contains_BKI": "BKI" in (val or ""),
}
r5["pass"] = r5["resolves"] and r5["contains_DELIVERIES"] and r5["contains_BKI"]
checks["5_bei_settings_cutover"] = r5

# 6. BEI 6xxxxxx
r6 = {}
r6["income_count"] = frappe.db.sql(
    "SELECT COUNT(*) FROM `tabAccount` WHERE company='Bebang Enterprise Inc.' AND account_number LIKE '6%%' AND root_type='Income'"
)[0][0]
r6["expense_count"] = frappe.db.sql(
    "SELECT COUNT(*) FROM `tabAccount` WHERE company='Bebang Enterprise Inc.' AND account_number LIKE '6%%' AND root_type='Expense'"
)[0][0]
r6["total"] = frappe.db.sql(
    "SELECT COUNT(*) FROM `tabAccount` WHERE company='Bebang Enterprise Inc.' AND account_number LIKE '6%%'"
)[0][0]
r6["pass"] = r6["income_count"] == 0 and r6["expense_count"] >= 134
checks["6_bei_6xxxxxx"] = r6

# 7. BFC company
bfc = frappe.db.get_value("Company", "BEBANG FRANCHISE CORP.", ["tax_id", "abbr", "default_currency"], as_dict=True)
r7 = {"bfc": bfc, "pass": bfc and bfc.get("tax_id") == "672-618-804-00000" and bfc.get("abbr") == "BFC"}
checks["7_bfc"] = r7

# 8. Intercompany scaffolding
r8 = {
    "2104200_BEI": frappe.db.get_value("Account", {"company": "Bebang Enterprise Inc.", "account_number": "2104200"}, "name"),
    "1104200_BFC": frappe.db.get_value("Account", {"company": "BEBANG FRANCHISE CORP.", "account_number": "1104200"}, "name"),
    "2102205_BFC": frappe.db.get_value("Account", {"company": "BEBANG FRANCHISE CORP.", "account_number": "2102205"}, "name"),
}
r8["pass"] = all([r8["2104200_BEI"], r8["1104200_BFC"], r8["2102205_BFC"]])
checks["8_intercompany"] = r8

# 9. 4000200 is NOT a DISCOUNTS group anywhere
r9 = {}
wrong_4000200 = frappe.db.sql("""
    SELECT company, name, account_name FROM `tabAccount`
    WHERE account_number='4000200' AND account_name LIKE '%%DISCOUNTS%%'
""", as_dict=True)
r9["wrong_count"] = len(wrong_4000200)
r9["wrong_entries"] = wrong_4000200
r9["pass"] = len(wrong_4000200) == 0
checks["9_4000200_not_discounts"] = r9

# 10. BKI Store customer group count
r10 = {
    "value": frappe.db.sql("SELECT COUNT(*) FROM `tabCustomer` WHERE customer_group=%s", "BKI Store")[0][0],
    "expected": 35,
}
r10["pass"] = r10["value"] == 35
checks["10_bki_store_customers"] = r10

# 11. S168 custom fields — broad match (S168 added custom fields to Sales Invoice + Payment Entry)
r11 = {
    "count_by_label": frappe.db.sql("""
        SELECT COUNT(*) FROM `tabCustom Field`
        WHERE (label LIKE '%%BKI%%' OR label LIKE '%%BEI%%' OR label LIKE '%%S168%%')
           OR fieldname LIKE '%%bki%%' OR fieldname LIKE '%%bei%%'
    """)[0][0],
    "bki_sales_income_account_setting_present": bool(frappe.db.sql("""
        SELECT fieldname FROM `tabDocField` df
        WHERE df.fieldname='bki_sales_income_account'
    """) or frappe.db.sql("""
        SELECT fieldname FROM `tabCustom Field`
        WHERE fieldname='bki_sales_income_account'
    """)),
}
# S168 regression baseline: any S168/BKI-related custom field or settings field present
r11["pass"] = r11["count_by_label"] >= 1 or r11["bki_sales_income_account_setting_present"]
checks["11_s168_custom_fields"] = r11

# Overall
checks["overall_pass"] = all(v.get("pass", True) for v in checks.values() if isinstance(v, dict))

print("S175_P10_JSON_START")
print(json.dumps(checks, default=str))
print("S175_P10_JSON_END")
frappe.destroy()
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    payload = PAYLOAD.replace("__NUMBERS_JSON__", json.dumps(NUMBERS_JSON))
    payload_path = OUT / "_phase10_payload.py"
    payload_path.write_text(payload, encoding="utf-8")

    stdout, stderr, status = run_on_frappe(payload_path, tag="phase10_final_verify", timeout_seconds=900)
    if status != "Success":
        print(stderr[-3000:]); sys.exit(1)

    raw = stdout.split("S175_P10_JSON_START", 1)[1].split("S175_P10_JSON_END", 1)[0].strip()
    checks = json.loads(raw)

    (OUT / "verification_final.json").write_text(json.dumps(checks, indent=2, default=str), encoding="utf-8")

    print("S175 Phase 10 — Final Verification\n")
    for k, v in checks.items():
        if k == "overall_pass":
            continue
        if isinstance(v, dict):
            p = "PASS" if v.get("pass") else "FAIL"
            print(f"  [{p}] {k}")
            if not v.get("pass"):
                for sub, subv in v.items():
                    if sub != "pass":
                        print(f"         {sub}: {subv}")
    print()
    print(f"OVERALL: {'PASS' if checks['overall_pass'] else 'FAIL'}")
    sys.exit(0 if checks["overall_pass"] else 2)


if __name__ == "__main__":
    main()
