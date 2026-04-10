#!/usr/bin/env python3
"""Create the 3 missing BEI parent group accounts and re-parent the orphans."""
import json, os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

BEI = "Bebang Enterprise Inc."
r = {"fixes": [], "errors": []}

# The 3 orphans and what parent they need:
# 1. ADVANCES TO SSS - BEI → parent "NON-TRADE RECEIVABLES - BEI" (missing) → create under Asset root
# 2. GR/IR CLEARING - BEI → parent "INVENTORY - BEI" (missing) → create under Asset root
# 3. PROPERTY, PLANT AND EQUIPMENT - BEI → parent "NON-CURRENT ASSETS - BEI" (missing) → create under Asset root

# Find BEI's Asset root group (the top-level parent with root_type=Asset and no parent_account)
asset_root = frappe.db.get_value("Account", {
    "company": BEI, "root_type": "Asset", "is_group": 1,
    "parent_account": ["in", ["", None]]
}, "name")

if not asset_root:
    # BEI might have roots with parent_account = '' vs NULL — try both
    asset_root = frappe.db.sql("""
        SELECT name FROM `tabAccount`
        WHERE company = %s AND root_type = 'Asset' AND is_group = 1
          AND (parent_account IS NULL OR parent_account = '')
        ORDER BY lft LIMIT 1
    """, BEI)
    asset_root = asset_root[0][0] if asset_root else None

r["asset_root"] = asset_root

if not asset_root:
    r["errors"].append("No Asset root group found on BEI — cannot create parent accounts")
    print("R_BEGIN")
    print(json.dumps(r, default=str, indent=2))
    print("R_END")
    import sys; sys.exit(1)

# Bypass the Group Company validator (BEI is a child of Irresistible Infusions Inc.)
frappe.local.flags.ignore_root_company_validation = True

# Create each missing parent group and re-verify the orphan's link
missing_parents = [
    {"name_part": "NON-TRADE RECEIVABLES", "root_type": "Asset", "orphan": "ADVANCES TO SSS - BEI"},
    {"name_part": "INVENTORY", "root_type": "Asset", "orphan": "GR/IR CLEARING - BEI"},
    {"name_part": "NON-CURRENT ASSETS", "root_type": "Asset", "orphan": "PROPERTY, PLANT AND EQUIPMENT - BEI"},
]

for mp in missing_parents:
    expected_name = f"{mp['name_part']} - {BEI}"
    try:
        if frappe.db.exists("Account", expected_name):
            r["fixes"].append({"parent": expected_name, "action": "ALREADY_EXISTS"})
        else:
            acct = frappe.new_doc("Account")
            acct.company = BEI
            acct.account_name = mp["name_part"]
            acct.parent_account = asset_root
            acct.is_group = 1
            acct.root_type = mp["root_type"]
            acct.report_type = "Balance Sheet"
            acct.insert(ignore_permissions=True, ignore_mandatory=True)
            r["fixes"].append({"parent": acct.name, "action": "CREATED", "under": asset_root})

        # Verify the orphan now has a valid parent
        orphan_parent = frappe.db.get_value("Account", mp["orphan"], "parent_account")
        parent_exists = bool(frappe.db.exists("Account", orphan_parent)) if orphan_parent else False
        r["fixes"][-1]["orphan"] = mp["orphan"]
        r["fixes"][-1]["orphan_parent_valid"] = parent_exists

    except Exception as e:
        r["errors"].append(f"{mp['name_part']}: {e}")

frappe.db.commit()

# Final orphan count
remaining = frappe.db.sql("""
    SELECT a.name, a.parent_account FROM `tabAccount` a
    LEFT JOIN `tabAccount` p ON a.parent_account = p.name
    WHERE a.company = %s
      AND a.parent_account IS NOT NULL AND a.parent_account != ''
      AND p.name IS NULL
""", BEI, as_dict=True)
r["remaining_orphans"] = len(remaining)
if remaining:
    r["remaining_details"] = [dict(x) for x in remaining]
r["all_pass"] = len(remaining) == 0

print("R_BEGIN")
print(json.dumps(r, default=str, indent=2))
print("R_END")
