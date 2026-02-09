"""Migrate existing 'Paid' BEI Payment Requests to 'Paid - Awaiting OR'.

All existing BEI Payment Requests with status 'Paid' should be migrated to
'Paid - Awaiting OR' so they appear in the OR tracking dashboard.

Sets:
  - status = 'Paid - Awaiting OR'
  - or_status = 'Awaiting OR'
  - or_required = 1
  - or_due_date = modified + 30 days (best estimate since we don't know actual payment date)
"""

import frappe


def execute():
    if not frappe.db.table_exists("tabBEI Payment Request"):
        return

    # Check if the or_status column exists (added by model sync)
    columns = frappe.db.get_table_columns("tabBEI Payment Request")
    if "or_status" not in columns:
        return

    count = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabBEI Payment Request` WHERE status = 'Paid'"
    )[0][0]

    if count == 0:
        return

    frappe.db.sql("""
        UPDATE `tabBEI Payment Request`
        SET status = 'Paid - Awaiting OR',
            or_status = 'Awaiting OR',
            or_required = 1,
            or_due_date = DATE_ADD(COALESCE(payment_date, modified), INTERVAL 30 DAY)
        WHERE status = 'Paid'
    """)

    frappe.db.commit()
    frappe.msgprint(f"Migrated {count} 'Paid' payment requests to 'Paid - Awaiting OR'")
