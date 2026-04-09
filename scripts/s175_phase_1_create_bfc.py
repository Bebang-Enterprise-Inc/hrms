#!/usr/bin/env python3
"""S175 Phase 1 — Create BEBANG FRANCHISE CORP. (BFC) Frappe Company.

Creates:
1. Company "BEBANG FRANCHISE CORP." (abbr=BFC, TIN=672-618-804-00000)
2. `2102205 OUTPUT VAT PAYABLE - BFC` under BFC current liabilities
3. `1104200 DUE FROM BEI - BFC` under BFC current assets (receivables)

Runs on hq.bebang.ph via SSM.

Outputs:
- output/s175/phase1_bfc_verification.json
- output/s175/phase1_error.log (if HB-6)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s175_ssm_runner import run_on_frappe  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output" / "s175"

PAYLOAD = r'''
#!/usr/bin/env python3
import os, json, sys, traceback
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

result = {"company_created": False, "accounts": {}, "errors": []}

COMPANY = "BEBANG FRANCHISE CORP."
ABBR = "BFC"

try:
    # 1. Create Company if not exists
    if frappe.db.exists("Company", COMPANY):
        result["company_created"] = False
        result["company_already_existed"] = True
    else:
        c = frappe.new_doc("Company")
        c.company_name = COMPANY
        c.abbr = ABBR
        c.default_currency = "PHP"
        c.country = "Philippines"
        c.tax_id = "672-618-804-00000"
        c.chart_of_accounts = "Standard"
        c.create_chart_of_accounts_based_on = "Standard Template"
        c.date_of_incorporation = "2025-03-27"
        c.enable_perpetual_inventory = 0
        c.insert(ignore_permissions=True)
        frappe.db.commit()
        result["company_created"] = True

    # Refresh
    comp = frappe.get_doc("Company", COMPANY)
    result["company_facts"] = {
        "name": comp.name,
        "abbr": comp.abbr,
        "tax_id": comp.tax_id,
        "default_currency": comp.default_currency,
        "country": comp.country,
    }

    # 2. Find BFC current liability and current asset parents from Standard CoA
    # Standard template produces accounts like "Current Liabilities - BFC", "Accounts Receivable - BFC", etc.
    liab_candidates = frappe.db.sql("""
        SELECT name, account_name, is_group, parent_account
        FROM `tabAccount`
        WHERE company=%s AND root_type='Liability' AND is_group=1
        ORDER BY lft
    """, COMPANY, as_dict=True)
    asset_candidates = frappe.db.sql("""
        SELECT name, account_name, is_group, parent_account
        FROM `tabAccount`
        WHERE company=%s AND root_type='Asset' AND is_group=1
        ORDER BY lft
    """, COMPANY, as_dict=True)

    result["liability_groups"] = liab_candidates
    result["asset_groups"] = asset_candidates

    def pick(groups, keywords):
        for g in groups:
            nm = (g["account_name"] or "").lower()
            for kw in keywords:
                if kw in nm:
                    return g["name"]
        return None

    curr_liab_parent = (pick(liab_candidates, ["current liabilit"])
                        or pick(liab_candidates, ["duties and taxes"])
                        or pick(liab_candidates, ["accounts payable"]))
    curr_asset_parent = (pick(asset_candidates, ["current asset"])
                         or pick(asset_candidates, ["accounts receivable"])
                         or pick(asset_candidates, ["receivable"]))

    result["resolved_parents"] = {
        "current_liabilities": curr_liab_parent,
        "current_assets": curr_asset_parent,
    }

    if not curr_liab_parent or not curr_asset_parent:
        result["errors"].append("Could not resolve BFC current liabilities/assets parent groups")
        print("S175_PHASE1_JSON_START")
        print(json.dumps(result, default=str))
        print("S175_PHASE1_JSON_END")
        sys.exit(3)

    def ensure(number, name, parent, is_group, root_type, account_type):
        existing = frappe.db.get_value(
            "Account",
            {"company": COMPANY, "account_number": number},
            ["name", "account_name"], as_dict=True,
        )
        if existing:
            return existing["name"], "exists"
        acct = frappe.new_doc("Account")
        acct.company = COMPANY
        acct.account_number = number
        acct.account_name = name
        acct.parent_account = parent
        acct.is_group = is_group
        acct.root_type = root_type
        if account_type:
            acct.account_type = account_type
        acct.insert(ignore_permissions=True)
        return acct.name, "created"

    # 3. Create 2102205 OUTPUT VAT PAYABLE - BFC
    name, status = ensure("2102205", "OUTPUT VAT PAYABLE",
                          parent=curr_liab_parent,
                          is_group=0, root_type="Liability", account_type="Tax")
    result["accounts"]["2102205"] = {"name": name, "status": status}

    # 4. Create 1104200 DUE FROM BEI - BFC
    name, status = ensure("1104200", "DUE FROM BEI",
                          parent=curr_asset_parent,
                          is_group=0, root_type="Asset", account_type="Receivable")
    result["accounts"]["1104200"] = {"name": name, "status": status}

    frappe.db.commit()

    # 5. Dump BFC 4/1/2 ranges for visibility
    result["bfc_4xxx_accounts"] = frappe.db.sql("""
        SELECT account_number, account_name, is_group, root_type FROM `tabAccount`
        WHERE company=%s AND account_number LIKE '4%%' ORDER BY account_number
    """, COMPANY, as_dict=True)
    result["bfc_2102xxx_accounts"] = frappe.db.sql("""
        SELECT account_number, account_name, root_type FROM `tabAccount`
        WHERE company=%s AND account_number LIKE '2102%%' ORDER BY account_number
    """, COMPANY, as_dict=True)
    result["bfc_1104xxx_accounts"] = frappe.db.sql("""
        SELECT account_number, account_name, root_type FROM `tabAccount`
        WHERE company=%s AND account_number LIKE '1104%%' ORDER BY account_number
    """, COMPANY, as_dict=True)

except Exception as e:
    result["errors"].append(str(e))
    result["traceback"] = traceback.format_exc()

print("S175_PHASE1_JSON_START")
print(json.dumps(result, default=str))
print("S175_PHASE1_JSON_END")

frappe.destroy()
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    payload_path = OUT / "_phase1_payload.py"
    payload_path.write_text(PAYLOAD, encoding="utf-8")

    stdout, stderr, status = run_on_frappe(payload_path, tag="phase1_create_bfc", timeout_seconds=900)
    if status != "Success":
        (OUT / "phase1_error.log").write_text(f"SSM status: {status}\n\nSTDERR:\n{stderr}\n\nSTDOUT:\n{stdout}", encoding="utf-8")
        print("HB-6: BFC Company creation failed via SSM")
        print(stderr[-2000:])
        sys.exit(6)

    if "S175_PHASE1_JSON_START" not in stdout:
        (OUT / "phase1_error.log").write_text(stdout + "\n\nSTDERR:\n" + stderr, encoding="utf-8")
        print("HB-6: no JSON markers")
        sys.exit(6)

    raw = stdout.split("S175_PHASE1_JSON_START", 1)[1].split("S175_PHASE1_JSON_END", 1)[0].strip()
    result = json.loads(raw)

    (OUT / "phase1_bfc_verification.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    if result.get("errors"):
        (OUT / "phase1_error.log").write_text("\n".join(result["errors"]) + "\n\n" + result.get("traceback", ""), encoding="utf-8")
        print("HB-6: payload errors:")
        for e in result["errors"]:
            print("  " + e)
        sys.exit(6)

    print("PHASE1 OK")
    print(f"  company_created={result.get('company_created')}")
    print(f"  2102205: {result['accounts'].get('2102205')}")
    print(f"  1104200: {result['accounts'].get('1104200')}")


if __name__ == "__main__":
    main()
