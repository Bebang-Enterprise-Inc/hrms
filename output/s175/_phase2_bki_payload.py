
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

TEMPLATE = json.loads("[[\"4000000\", \"SALES\", null, 1, \"Income\", null], [\"4000100\", \"STORE SALES\", \"4000000\", 1, \"Income\", null], [\"4000110\", \"IN-STORE SALES\", \"4000100\", 0, \"Income\", \"Income Account\"], [\"4000120\", \"ONLINE SALES\", \"4000100\", 1, \"Income\", null], [\"4000121\", \"BEI WEBSITE\", \"4000120\", 0, \"Income\", \"Income Account\"], [\"4000122\", \"FOOD PANDA\", \"4000120\", 0, \"Income\", \"Income Account\"], [\"4000123\", \"GRAB\", \"4000120\", 0, \"Income\", \"Income Account\"], [\"4000200\", \"BKI SALES\", \"4000000\", 1, \"Income\", null], [\"4000210\", \"DELIVERIES\", \"4000200\", 0, \"Income\", \"Income Account\"], [\"4000220\", \"LOGISTICS\", \"4000200\", 1, \"Income\", null], [\"4000221\", \"DELIVERY INCOME\", \"4000220\", 0, \"Income\", \"Income Account\"], [\"4000222\", \"LOGISTICS INCOME\", \"4000220\", 0, \"Income\", \"Income Account\"], [\"4000230\", \"FEES\", \"4000000\", 1, \"Income\", null], [\"4000231\", \"ROYALTY FEES\", \"4000230\", 0, \"Income\", \"Income Account\"], [\"4000232\", \"MANAGEMENT FEES\", \"4000230\", 0, \"Income\", \"Income Account\"], [\"4000233\", \"FRANCHISE FEES\", \"4000230\", 0, \"Income\", \"Income Account\"], [\"4000234\", \"MARKETING FEES\", \"4000230\", 0, \"Income\", \"Income Account\"], [\"4000235\", \"E-COMMERCE FEES\", \"4000230\", 0, \"Income\", \"Income Account\"], [\"4000900\", \"DISCOUNTS AND PROMO\", \"4000000\", 1, \"Income\", null], [\"4000901\", \"SALES DISCOUNT DUE TO FREE HALOHALO\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000902\", \"SALES DISCOUNT OF SENIOR CITIZENS\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000903\", \"SALES DISCOUNTS OF PWDS\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000904\", \"SALES DISCOUNTS OF STAFFS AND EMPLOYEES\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000905\", \"SALES DISCOUNTS FROM VAT OF PWD\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000906\", \"SALES DISCOUNTS FROM VAT OF SENIOR CITIZENS\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000907\", \"SALES REFUNDS TO CUSTOMER\", \"4000900\", 0, \"Income\", \"Income Account\"], [\"4000908\", \"SALES DISCOUNTS - EMPLOYEE DISC\", \"4000900\", 0, \"Income\", \"Income Account\"]]")
COMPANY = "Bebang Kitchen Inc."

result = {"steps": [], "walk": {"created": [], "matched": [], "errors": []}}

try:
    from frappe.utils.nestedset import rebuild_tree

    # STEP 1: Rollback broken Phase 2 inserts (raw SQL DELETE)
    # Delete every 4000xxx on BKI + the synthetic "Income - BKI" group
    # (all have 0 GL since Phase 1.5 pre-clean verified + new accounts also 0 GL)
    rows_before = frappe.db.sql("""
        SELECT name, (SELECT COUNT(*) FROM `tabGL Entry` WHERE account=a.name) as gl
        FROM `tabAccount` a
        WHERE a.company=%s AND (a.account_number LIKE '4000%%' OR a.name='Income - BKI')
    """, COMPANY, as_dict=True)
    for r in rows_before:
        if r["gl"] != 0:
            raise RuntimeError(f"Cannot rollback {r['name']}: {r['gl']} GL entries")
    if rows_before:
        frappe.db.sql("""
            DELETE FROM `tabAccount`
            WHERE company=%s AND (account_number LIKE '4000%%' OR name='Income - BKI')
        """, COMPANY)
        frappe.db.commit()
        result["steps"].append(f"rolled back {len(rows_before)} BKI accounts: {[r['name'] for r in rows_before]}")

    # STEP 1.5: Normalize empty-string parent_account to NULL across all BKI
    # accounts. Frappe's rebuild_tree only treats NULL parents as roots; empty
    # strings are orphans, which leaves lft/rgt stale.
    normalized = frappe.db.sql("""
        UPDATE `tabAccount` SET parent_account=NULL
        WHERE company=%s AND (parent_account='' OR parent_account IS NULL)
    """, COMPANY)
    frappe.db.commit()
    result["steps"].append(f"normalized BKI empty-string parents to NULL: rowcount={frappe.db._cursor.rowcount if hasattr(frappe.db, '_cursor') else 'unknown'}")

    # STEP 1.6: Also normalize any BKI account whose parent_account points to a
    # non-existent account (dangling parent refs from legacy).
    dangling = frappe.db.sql("""
        SELECT a.name, a.parent_account FROM `tabAccount` a
        LEFT JOIN `tabAccount` p ON p.name = a.parent_account
        WHERE a.company=%s AND a.parent_account IS NOT NULL AND p.name IS NULL
    """, COMPANY, as_dict=True)
    if dangling:
        frappe.db.sql("""
            UPDATE `tabAccount` a
            LEFT JOIN `tabAccount` p ON p.name = a.parent_account
            SET a.parent_account=NULL
            WHERE a.company=%s AND a.parent_account IS NOT NULL AND p.name IS NULL
        """, COMPANY)
        frappe.db.commit()
        result["steps"].append(f"cleared {len(dangling)} BKI dangling parent refs")

    # STEP 2: Full rebuild_tree to un-corrupt BKI
    rebuild_tree("Account", "parent_account")
    frappe.db.commit()
    result["steps"].append("initial rebuild_tree OK")

    # STEP 3: Inspect BKI's actual root groups (post-rollback) — count only
    roots_count = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabAccount`
        WHERE company=%s AND (parent_account IS NULL OR parent_account='') AND is_group=1
    """, COMPANY)[0][0]
    result["bki_root_groups_count"] = roots_count
    # Just show the Income-type roots
    result["bki_income_root_groups"] = frappe.db.sql("""
        SELECT name, account_name FROM `tabAccount`
        WHERE company=%s AND (parent_account IS NULL OR parent_account='')
          AND is_group=1 AND root_type='Income'
        ORDER BY lft
    """, COMPANY, as_dict=True)

    def resolve_root_parent(company, root_type):
        return frappe.db.get_value("Account", {
            "company": company,
            "root_type": root_type,
            "is_group": 1,
            "parent_account": ["in", ["", None]],
        }, "name")

    # STEP 4: Ensure BKI has an "Income" root group (create if missing)
    income_root_name = resolve_root_parent(COMPANY, "Income")
    if not income_root_name:
        # Create an Income root via new_doc + ignore_mandatory
        root = frappe.new_doc("Account")
        root.company = COMPANY
        root.account_name = "Income"
        root.is_group = 1
        root.root_type = "Income"
        root.report_type = "Profit and Loss"
        # Don't set parent_account — it's a true root
        root.flags.ignore_mandatory = True
        root.insert(ignore_permissions=True, ignore_mandatory=True)
        frappe.db.commit()
        income_root_name = root.name
        result["steps"].append(f"created root group {income_root_name}")
        rebuild_tree("Account", "parent_account")
        frappe.db.commit()
    else:
        result["steps"].append(f"income root exists: {income_root_name}")

    # STEP 5: Walk the 27-row template via frappe.new_doc
    def ensure_account(number, name, parent_number, is_group, root_type, account_type):
        if parent_number is None:
            parent_name = resolve_root_parent(COMPANY, root_type)
            if not parent_name:
                raise RuntimeError(f"No root group on {COMPANY} for {root_type}")
        else:
            parent_name = frappe.db.get_value(
                "Account", {"company": COMPANY, "account_number": parent_number}, "name"
            )
            if not parent_name:
                raise RuntimeError(f"Parent {parent_number} not found on {COMPANY}")

        existing = frappe.db.get_value(
            "Account", {"company": COMPANY, "account_number": number}, "name"
        )
        if existing:
            result["walk"]["matched"].append(number)
            return existing

        acct = frappe.new_doc("Account")
        acct.company = COMPANY
        acct.account_number = number
        acct.account_name = name
        acct.parent_account = parent_name
        acct.is_group = is_group
        acct.root_type = root_type
        if account_type:
            acct.account_type = account_type
        acct.insert(ignore_permissions=True)
        result["walk"]["created"].append(number)
        return acct.name

    for number, name, parent_number, is_group, root_type, account_type in TEMPLATE:
        try:
            ensure_account(number, name, parent_number, is_group, root_type, account_type)
            frappe.db.commit()
        except Exception as e:
            result["walk"]["errors"].append({"number": number, "error": str(e)})
            frappe.db.rollback()

    rebuild_tree("Account", "parent_account")
    frappe.db.commit()
    result["steps"].append("final rebuild_tree OK")

except Exception as e:
    result["top_error"] = str(e)
    result["traceback"] = traceback.format_exc()

# Final verification
result["post_4000xxx"] = frappe.db.sql("""
    SELECT account_number, account_name, is_group, root_type, parent_account
    FROM `tabAccount`
    WHERE company=%s AND account_number LIKE '4000%%'
    ORDER BY account_number
""", COMPANY, as_dict=True)

print("S175_PHASE2BKI_JSON_START")
print(json.dumps(result, default=str))
print("S175_PHASE2BKI_JSON_END")

frappe.destroy()
