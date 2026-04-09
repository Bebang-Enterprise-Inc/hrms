
#!/usr/bin/env python3
import os, json, sys, traceback
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
frappe.local.flags.ignore_root_company_validation = True

result = {"phase3": {}, "phase4": {}}

# ===== PHASE 3: S168 legacy check =====
BKI = "Bebang Kitchen Inc."
p3 = result["phase3"]
p3["4000100_absent"] = not frappe.db.get_value(
    "Account", {"company": BKI, "account_number": "4000100", "account_name": "WHOLESALE / B2B SALES"}, "name"
)
p3["4000101_absent"] = not frappe.db.get_value(
    "Account", {"company": BKI, "account_number": "4000101"}, "name"
)
p3["4000200_BKI_SALES_exists"] = bool(frappe.db.sql(
    "SELECT name FROM `tabAccount` WHERE company=%s AND account_number='4000200' AND account_name='BKI SALES' AND is_group=1",
    BKI
))
p3["4000210_DELIVERIES_exists"] = bool(frappe.db.sql(
    "SELECT name FROM `tabAccount` WHERE company=%s AND account_number='4000210' AND account_name='DELIVERIES' AND is_group=0",
    BKI
))

# ===== PHASE 4: Create 2104200 DUE TO BFC on BEI =====
BEI = "Bebang Enterprise Inc."
p4 = result["phase4"]

# Check if already exists
existing = frappe.db.get_value("Account", {"company": BEI, "account_number": "2104200"}, "name")
if existing:
    p4["2104200_status"] = "exists"
    p4["2104200_name"] = existing
else:
    # Find any parent:
    #  1. Prefer a liability group
    #  2. Fall back to 2104100 SHORT TERM DEBT's parent (if any)
    #  3. Fall back to 2104100's parent's neighbor
    #  4. Create 2104200 at root level (parent=None)
    parent = None
    liab_groups = frappe.db.sql("""
        SELECT name, account_name FROM `tabAccount`
        WHERE company=%s AND root_type='Liability' AND is_group=1
        ORDER BY lft
    """, BEI, as_dict=True)
    p4["liability_groups_count"] = len(liab_groups)
    for g in liab_groups:
        nm = (g["account_name"] or "").lower()
        if "current liabilit" in nm or "duties and taxes" in nm:
            parent = g["name"]
            break
    if not parent and liab_groups:
        parent = liab_groups[0]["name"]

    # Try 2104100 SHORT TERM DEBT's parent (from Phase A data)
    if not parent:
        sibling = frappe.db.get_value(
            "Account",
            {"company": BEI, "account_number": "2104100"},
            "parent_account",
        )
        if sibling:
            parent = sibling
            p4["resolved_parent_source"] = "2104100 sibling"

    # If still no parent, create an INTERCOMPANY PAYABLES group at root level
    if not parent:
        try:
            grp = frappe.new_doc("Account")
            grp.company = BEI
            grp.account_number = "2104000"
            grp.account_name = "INTERCOMPANY PAYABLES"
            grp.parent_account = None
            grp.is_group = 1
            grp.root_type = "Liability"
            grp.flags.ignore_root_company_validation = True
            grp.flags.ignore_mandatory = True
            grp.insert(ignore_permissions=True, ignore_mandatory=True)
            frappe.db.commit()
            parent = grp.name
            p4["created_parent_group"] = grp.name
            p4["resolved_parent_source"] = "new 2104000 INTERCOMPANY PAYABLES group"
        except Exception as e:
            p4["_parent_group_error"] = str(e)[:400]

    p4["resolved_parent"] = parent

    try:
        acct = frappe.new_doc("Account")
        acct.company = BEI
        acct.account_number = "2104200"
        acct.account_name = "DUE TO BFC"
        acct.parent_account = parent
        acct.is_group = 0
        acct.root_type = "Liability"
        acct.account_type = "Payable"
        acct.flags.ignore_root_company_validation = True
        acct.flags.ignore_mandatory = True
        acct.insert(ignore_permissions=True, ignore_mandatory=True)
        frappe.db.commit()
        p4["2104200_status"] = "created"
        p4["2104200_name"] = acct.name
    except Exception as e:
        p4["2104200_status"] = f"error: {str(e)[:500]}"
        p4["traceback"] = traceback.format_exc()

# Verify the 3 intercompany accounts from Phase 1 + Phase 4 exist
p4["bei_2104200"] = frappe.db.get_value("Account", {"company": BEI, "account_number": "2104200"}, "name")
p4["bfc_1104200"] = frappe.db.get_value("Account", {"company": "BEBANG FRANCHISE CORP.", "account_number": "1104200"}, "name")
p4["bfc_2102205"] = frappe.db.get_value("Account", {"company": "BEBANG FRANCHISE CORP.", "account_number": "2102205"}, "name")

print("S175_P34_JSON_START")
print(json.dumps(result, default=str))
print("S175_P34_JSON_END")
frappe.destroy()
