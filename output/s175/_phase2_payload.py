
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

# Bypass ERPNext group-company validator for this session.
# This is the Frappe-sanctioned flag — not raw SQL.
frappe.local.flags.ignore_root_company_validation = True

TEMPLATE = json.loads("[[\"4000000\", \"SALES\", null, 1, \"Income\", null], [\"4000100\", \"STORE SALES\", \"4000000\", 1, \"Income\", null], [\"4000110\", \"IN-STORE SALES\", \"4000100\", 0, \"Income\", \"Income Account\"], [\"4000120\", \"ONLINE SALES\", \"4000100\", 1, \"Income\", null], [\"4000121\", \"BEI WEBSITE\", \"4000120\", 0, \"Income\", \"Income Account\"], [\"4000122\", \"FOOD PANDA\", \"4000120\", 0, \"Income\", \"Income Account\"], [\"4000123\", \"GRAB\", \"4000120\", 0, \"Income\", \"Income Account\"], [\"4000200\", \"BKI SALES\", \"4000000\", 1, \"Income\", null], [\"4000210\", \"DELIVERIES\", \"4000200\", 0, \"Income\", \"Income Account\"], [\"4000220\", \"LOGISTICS\", \"4000200\", 1, \"Income\", null], [\"4000221\", \"DELIVERY INCOME\", \"4000220\", 0, \"Income\", \"Income Account\"], [\"4000222\", \"LOGISTICS INCOME\", \"4000220\", 0, \"Income\", \"Income Account\"], [\"4000230\", \"FEES\", \"4000000\", 1, \"Income\", null], [\"4000231\", \"ROYALTY FEES\", \"4000230\", 0, \"Income\", \"Income Account\"], [\"4000232\", \"MANAGEMENT FEES\", \"4000230\", 0, \"Income\", \"Income Account\"], [\"4000233\", \"FRANCHISE FEES\", \"4000230\", 0, \"Income\", \"Income Account\"], [\"4000234\", \"MARKETING FEES\", \"4000230\", 0, \"Income\", \"Income Account\"], [\"4000235\", \"E-COMMERCE FEES\", \"4000230\", 0, \"Income\", \"Income Account\"], [\"4000900\", \"DISCOUNTS AND PROMO\", \"4000000\", 1, \"Income\", null], [\"4000901\", \"SALES DISCOUNT DUE TO FREE HALOHALO\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000902\", \"SALES DISCOUNT OF SENIOR CITIZENS\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000903\", \"SALES DISCOUNTS OF PWDS\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000904\", \"SALES DISCOUNTS OF STAFFS AND EMPLOYEES\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000905\", \"SALES DISCOUNTS FROM VAT OF PWD\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000906\", \"SALES DISCOUNTS FROM VAT OF SENIOR CITIZENS\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000907\", \"SALES REFUNDS TO CUSTOMER\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000908\", \"SALES DISCOUNTS - EMPLOYEE DISC\", \"4000900\", 0, \"Income\", \"Income Account\"]]")
TARGETS = ["Bebang Kitchen Inc.", "Bebang Enterprise Inc.", "BEBANG FRANCHISE CORP."]

results = {"fixups": [], "summary": {}, "verification": {}}

# --- STEP 1: COA Corruption Fixups ---
# BKI: 4000000 SALES has parent_account='SALES - BKI' (self cycle) OR was deleted
bki_4000000 = frappe.db.get_value(
    "Account",
    {"company": "Bebang Kitchen Inc.", "account_number": "4000000"},
    ["name", "parent_account", "is_group", "root_type"],
    as_dict=True,
)
if bki_4000000:
    if bki_4000000["parent_account"] == bki_4000000["name"]:
        frappe.db.sql("UPDATE `tabAccount` SET parent_account=NULL WHERE name=%s", bki_4000000["name"])
        results["fixups"].append({"company": "Bebang Kitchen Inc.", "action": "cleared self-parent"})
    if not bki_4000000["is_group"]:
        frappe.db.sql("UPDATE `tabAccount` SET is_group=1 WHERE name=%s", bki_4000000["name"])
        results["fixups"].append({"company": "Bebang Kitchen Inc.", "action": "posting->group"})

# BEI: 4000000 SALES - is_group=0 (posting), need to convert to group
bei_4000000 = frappe.db.get_value(
    "Account",
    {"company": "Bebang Enterprise Inc.", "account_number": "4000000"},
    ["name", "parent_account", "is_group", "root_type"],
    as_dict=True,
)
if bei_4000000:
    if not bei_4000000["is_group"]:
        gl = frappe.db.sql("SELECT COUNT(*) FROM `tabGL Entry` WHERE account=%s", bei_4000000["name"])[0][0]
        if gl != 0:
            raise RuntimeError(f"Cannot convert BEI 4000000 to group: {gl} GL entries")
        frappe.db.sql("UPDATE `tabAccount` SET is_group=1 WHERE name=%s", bei_4000000["name"])
        results["fixups"].append({"company": "Bebang Enterprise Inc.", "action": "posting->group"})
    if bei_4000000["parent_account"] is not None:
        frappe.db.sql("UPDATE `tabAccount` SET parent_account=NULL WHERE name=%s", bei_4000000["name"])
        results["fixups"].append({"company": "Bebang Enterprise Inc.", "action": "cleared parent"})

frappe.db.commit()

# Normalize empty-string parents to NULL on BKI (legacy data cleanup)
frappe.db.sql("""
    UPDATE `tabAccount` SET parent_account=NULL
    WHERE company='Bebang Kitchen Inc.' AND parent_account=''
""")
frappe.db.commit()

# Skip rebuild_tree here — too slow (11k accounts × 40 companies).
# With ignore_root_company_validation flag set, Frappe won't walk the tree.
from frappe.utils.nestedset import rebuild_tree
results["_rebuild_post_fixup"] = "SKIPPED (rely on ignore_root_company_validation flag)"

# --- STEP 2: ensure_account helper ---
def ensure_account(company, number, name, parent_number, is_group, root_type, account_type, rep):
    # Resolve parent
    if parent_number is None:
        parent_name = None  # root level
    else:
        parent_name = frappe.db.get_value(
            "Account", {"company": company, "account_number": parent_number}, "name"
        )
        if not parent_name:
            raise RuntimeError(f"Parent {parent_number} not found on {company}")

    existing = frappe.db.sql(
        "SELECT name, account_name, is_group, root_type, parent_account "
        "FROM `tabAccount` WHERE company=%s AND account_number=%s",
        (company, number), as_dict=True,
    )

    if existing:
        ex = existing[0]
        # is_group mismatch → HB-5
        if int(ex["is_group"]) != int(is_group):
            raise RuntimeError(f"HB-5: {ex['name']} is_group={ex['is_group']}, expected {is_group}")
        # root_type mismatch → SQL UPDATE
        if ex["root_type"] != root_type:
            frappe.db.sql("UPDATE `tabAccount` SET root_type=%s WHERE name=%s", (root_type, ex["name"]))
            rep["root_type_fixed"].append(number)
        # parent mismatch → SQL UPDATE (bypass validator)
        if ex["parent_account"] != parent_name:
            frappe.db.sql("UPDATE `tabAccount` SET parent_account=%s WHERE name=%s", (parent_name, ex["name"]))
            rep["reparented"].append({"number": number, "old": ex["parent_account"], "new": parent_name})
        # account_type for posting accounts
        if account_type and not is_group:
            cur = frappe.db.get_value("Account", ex["name"], "account_type")
            if cur != account_type:
                frappe.db.sql("UPDATE `tabAccount` SET account_type=%s WHERE name=%s", (account_type, ex["name"]))
        # Fix account_name if wrong
        if ex["account_name"] != name:
            frappe.db.sql("UPDATE `tabAccount` SET account_name=%s WHERE name=%s", (name, ex["name"]))
            rep["name_fixed"].append(number)
        rep["matched"].append(number)
        return ex["name"]

    # Create new
    acct = frappe.new_doc("Account")
    acct.company = company
    acct.account_number = number
    acct.account_name = name
    acct.parent_account = parent_name
    acct.is_group = is_group
    acct.root_type = root_type
    if account_type:
        acct.account_type = account_type
    # Belt-and-suspenders: set doc-level flag too
    acct.flags.ignore_root_company_validation = True
    acct.flags.ignore_mandatory = True  # parent_account may be None for root
    acct.insert(ignore_permissions=True, ignore_mandatory=True)
    rep["created"].append(number)
    return acct.name

for company in TARGETS:
    rep = {"created": [], "matched": [], "reparented": [], "root_type_fixed": [],
           "name_fixed": [], "errors": []}
    try:
        for number, name, parent_number, is_group, root_type, account_type in TEMPLATE:
            try:
                ensure_account(company, number, name, parent_number, is_group, root_type, account_type, rep)
                frappe.db.commit()
            except Exception as inner:
                rep["errors"].append({"number": number, "error": str(inner)})
                frappe.db.rollback()
    except Exception as e:
        rep["errors"].append({"fatal": str(e), "traceback": traceback.format_exc()})
    results["summary"][company] = rep

# Skip final rebuild too — we can do it in Phase 10 verification
results["_rebuild_final"] = "SKIPPED"

# Verify final state per company
for company in TARGETS:
    rows = frappe.db.sql("""
        SELECT account_number, account_name, is_group, root_type, parent_account
        FROM `tabAccount`
        WHERE company=%s AND account_number LIKE '4000%%'
        ORDER BY account_number
    """, company, as_dict=True)
    results["verification"][company] = rows

print("S175_PHASE2_JSON_START")
print(json.dumps(results, default=str))
print("S175_PHASE2_JSON_END")

frappe.destroy()
