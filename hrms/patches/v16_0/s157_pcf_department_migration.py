"""
S157: PCF Department Migration
- Set fund_type='Store' on all existing BEI Petty Cash Fund records
- Generate fund_label from store name
- Set threshold_percentage=60, auto_submit_enabled=0 (notify-only)
- Backfill pcf_fund on BEI Expense Request records
- Backfill pcf_fund on BEI PCF Batch records
- Set expense_type='PCF' on expenses that have a pcf_batch
"""
import frappe


def execute():
    # Step 1: Update existing PCF funds
    _update_existing_funds()

    # Step 2: Backfill pcf_fund on expenses
    _backfill_expense_pcf_fund()

    # Step 3: Backfill pcf_fund on batches
    _backfill_batch_pcf_fund()

    # Step 4: Set expense_type on expenses
    _set_expense_type()

    frappe.db.commit()


def _update_existing_funds():
    """Set fund_type, fund_label, threshold on all existing PCF funds."""
    funds = frappe.get_all(
        "BEI Petty Cash Fund",
        filters={"fund_type": ["in", [None, ""]]},
        fields=["name", "store"],
    )

    for fund in funds:
        # Generate label by stripping company suffix
        label = fund.store or ""
        for suffix in [" - Bebang Enterprise Inc.", " - BEI"]:
            if label.endswith(suffix):
                label = label[: -len(suffix)]
                break

        frappe.db.set_value(
            "BEI Petty Cash Fund",
            fund.name,
            {
                "fund_type": "Store",
                "fund_label": label,
                "threshold_percentage": 60,
                "auto_submit_enabled": 0,
            },
            update_modified=False,
        )

    if funds:
        frappe.log_error(f"S157: Updated {len(funds)} PCF funds with fund_type=Store", "S157 Migration")


def _backfill_expense_pcf_fund():
    """Set pcf_fund on existing BEI Expense Request records by matching store."""
    # Build store→pcf_fund mapping
    funds = frappe.get_all(
        "BEI Petty Cash Fund",
        filters={"fund_type": "Store", "store": ["is", "set"]},
        fields=["name", "store"],
    )
    store_to_fund = {f.store: f.name for f in funds}

    if not store_to_fund:
        return

    updated = 0
    for store, pcf_name in store_to_fund.items():
        count = frappe.db.sql(
            """
            UPDATE `tabBEI Expense Request`
            SET pcf_fund = %s
            WHERE store = %s AND (pcf_fund IS NULL OR pcf_fund = '')
            """,
            (pcf_name, store),
        )
        updated += frappe.db.sql("SELECT ROW_COUNT()")[0][0]

    if updated:
        frappe.log_error(f"S157: Backfilled pcf_fund on {updated} expense requests", "S157 Migration")


def _backfill_batch_pcf_fund():
    """Set pcf_fund on existing BEI PCF Batch records by matching store."""
    funds = frappe.get_all(
        "BEI Petty Cash Fund",
        filters={"fund_type": "Store", "store": ["is", "set"]},
        fields=["name", "store"],
    )
    store_to_fund = {f.store: f.name for f in funds}

    if not store_to_fund:
        return

    updated = 0
    for store, pcf_name in store_to_fund.items():
        frappe.db.sql(
            """
            UPDATE `tabBEI PCF Batch`
            SET pcf_fund = %s
            WHERE store = %s AND (pcf_fund IS NULL OR pcf_fund = '')
            """,
            (pcf_name, store),
        )
        updated += frappe.db.sql("SELECT ROW_COUNT()")[0][0]

    if updated:
        frappe.log_error(f"S157: Backfilled pcf_fund on {updated} PCF batches", "S157 Migration")


def _set_expense_type():
    """Set expense_type='PCF' on expenses that have a pcf_batch."""
    frappe.db.sql(
        """
        UPDATE `tabBEI Expense Request`
        SET expense_type = 'PCF'
        WHERE pcf_batch IS NOT NULL AND pcf_batch != ''
        AND (expense_type IS NULL OR expense_type = '')
        """
    )
    count = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
    if count:
        frappe.log_error(f"S157: Set expense_type=PCF on {count} expense requests", "S157 Migration")
