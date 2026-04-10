#!/usr/bin/env python3
"""Direct fix: create missing parent groups for the 3 BEI orphans + fix ASSETS circular ref."""
import json, os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

BEI = "Bebang Enterprise Inc."
frappe.local.flags.ignore_root_company_validation = True
r = {"steps": [], "errors": []}

try:
    # Step 1: Fix ASSETS circular reference
    # "ASSETS - BEI" has parent = "PROPERTY, PLANT AND EQUIPMENT - BEI"
    # But PPE should be UNDER Assets, not the other way around
    # Fix: make ASSETS a root (parent_account = NULL)
    assets_acct = frappe.db.get_value("Account",
        {"company": BEI, "account_name": "ASSETS"}, "name")
    if assets_acct:
        frappe.db.set_value("Account", assets_acct, "parent_account", None)
        r["steps"].append(f"Fixed ASSETS circular: {assets_acct} parent set to NULL (root)")

    # Step 2: Create NON-CURRENT ASSETS group under ASSETS
    nca_name = f"NON-CURRENT ASSETS - {BEI}"
    if not frappe.db.exists("Account", nca_name):
        nca = frappe.new_doc("Account")
        nca.company = BEI
        nca.account_name = "NON-CURRENT ASSETS"
        nca.parent_account = assets_acct
        nca.is_group = 1
        nca.root_type = "Asset"
        nca.report_type = "Balance Sheet"
        nca.insert(ignore_permissions=True, ignore_mandatory=True)
        r["steps"].append(f"Created {nca.name} under {assets_acct}")
    else:
        r["steps"].append(f"{nca_name} already exists")

    # Step 3: Create INVENTORY group under ASSETS
    inv_name = f"INVENTORY - {BEI}"
    if not frappe.db.exists("Account", inv_name):
        inv = frappe.new_doc("Account")
        inv.company = BEI
        inv.account_name = "INVENTORY"
        inv.parent_account = assets_acct
        inv.is_group = 1
        inv.root_type = "Asset"
        inv.report_type = "Balance Sheet"
        inv.insert(ignore_permissions=True, ignore_mandatory=True)
        r["steps"].append(f"Created {inv.name} under {assets_acct}")
    else:
        r["steps"].append(f"{inv_name} already exists")

    # Step 4: Create NON-TRADE RECEIVABLES group under ASSETS
    ntr_name = f"NON-TRADE RECEIVABLES - {BEI}"
    if not frappe.db.exists("Account", ntr_name):
        ntr = frappe.new_doc("Account")
        ntr.company = BEI
        ntr.account_name = "NON-TRADE RECEIVABLES"
        ntr.parent_account = assets_acct
        ntr.is_group = 1
        ntr.root_type = "Asset"
        ntr.report_type = "Balance Sheet"
        ntr.insert(ignore_permissions=True, ignore_mandatory=True)
        r["steps"].append(f"Created {ntr.name} under {assets_acct}")
    else:
        r["steps"].append(f"{ntr_name} already exists")

    frappe.db.commit()

    # Step 5: Verify orphans now resolve
    for orphan, expected_parent in [
        ("ADVANCES TO SSS - BEI", ntr_name),
        ("GR/IR CLEARING - BEI", inv_name),
        ("PROPERTY, PLANT AND EQUIPMENT - BEI", nca_name),
    ]:
        current_parent = frappe.db.get_value("Account", orphan, "parent_account")
        parent_exists = bool(frappe.db.exists("Account", current_parent)) if current_parent else False
        r["steps"].append(f"{orphan}: parent={current_parent}, valid={parent_exists}")

    # Final orphan count
    remaining = frappe.db.sql("""
        SELECT a.name FROM `tabAccount` a
        LEFT JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE a.company = %s
          AND a.parent_account IS NOT NULL AND a.parent_account != ''
          AND p.name IS NULL
    """, BEI, as_dict=True)
    r["remaining_orphans"] = len(remaining)
    r["all_pass"] = len(remaining) == 0

except Exception as e:
    import traceback
    r["errors"].append(f"{e}\n{traceback.format_exc()}")

print("R_BEGIN")
print(json.dumps(r, default=str, indent=2))
print("R_END")
