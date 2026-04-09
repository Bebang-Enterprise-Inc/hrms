
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
