"""Drop the unique_store_date_type index on BEI Cycle Count.

The DB-level unique constraint on (store, count_date, count_type, docstatus) blocks
resubmission of rejected cycle counts because Rejected records still have docstatus=1.

Application-level duplicate detection in before_submit() and submit_cycle_count_v2()
now properly excludes Rejected/Resubmitted records, making the DB index redundant.
"""
import frappe


def execute():
    try:
        frappe.db.sql("""
            ALTER TABLE `tabBEI Cycle Count`
            DROP INDEX `unique_store_date_type`
        """)
        frappe.db.commit()
    except Exception:
        # Index may not exist or already dropped
        pass
