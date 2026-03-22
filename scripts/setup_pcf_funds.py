"""
PCF Fund Setup Script
Create PCF fund configurations for all stores.

Usage:
    bench execute scripts.setup_pcf_funds.setup_all
    bench execute scripts.setup_pcf_funds.setup_single --kwargs "{'store': 'Store Name'}"
    bench execute scripts.setup_pcf_funds.enable_store --kwargs "{'store': 'Store Name'}"
    bench execute scripts.setup_pcf_funds.list_funds

Author: Claude Code
Date: 2026-02-03
"""

import frappe

DEFAULT_FUND_AMOUNT = 10000  # PHP 10,000
DEFAULT_THRESHOLD = 50  # 50%


def setup_all():
    """Create PCF fund for each store warehouse (non-group, non-disabled)."""
    stores = frappe.get_all(
        "Warehouse",
        filters={"is_group": 0, "disabled": 0},
        fields=["name", "custom_area_supervisor"],
    )

    created = 0
    skipped = 0

    for store in stores:
        if frappe.db.exists("BEI Petty Cash Fund", {"store": store.name}):
            print(f"Skipping {store.name}: PCF fund already exists")
            skipped += 1
            continue

        # Find area supervisor as default custodian
        custodian = store.custom_area_supervisor

        if not custodian:
            # Try to find any user with System Manager role as fallback
            custodian = frappe.db.get_value(
                "Has Role",
                {"role": "System Manager", "parenttype": "User"},
                "parent",
            )

        if not custodian:
            print(f"Warning: No custodian found for {store.name}, using Administrator")
            custodian = "Administrator"

        doc = frappe.new_doc("BEI Petty Cash Fund")
        doc.store = store.name
        doc.company = "Bebang Enterprise Inc."
        doc.fund_amount = DEFAULT_FUND_AMOUNT
        doc.threshold_percentage = DEFAULT_THRESHOLD
        doc.custodian = custodian
        doc.is_enabled = False  # Enable manually per store
        doc.auto_submit_enabled = True
        doc.month_end_auto_submit = True
        doc.insert(ignore_permissions=True)
        created += 1
        print(f"Created PCF fund for {store.name} (custodian: {custodian})")

    frappe.db.commit()
    print(f"\nSummary: Created {created} PCF funds, skipped {skipped}")


def setup_single(store: str, fund_amount: float = None, custodian: str = None):
    """Create PCF fund for a single store."""
    if frappe.db.exists("BEI Petty Cash Fund", {"store": store}):
        print(f"PCF fund already exists for {store}")
        return

    # Find custodian
    if not custodian:
        custodian = frappe.db.get_value("Warehouse", store, "custom_area_supervisor")
    if not custodian:
        custodian = "Administrator"

    doc = frappe.new_doc("BEI Petty Cash Fund")
    doc.store = store
    doc.company = "Bebang Enterprise Inc."
    doc.fund_amount = fund_amount or DEFAULT_FUND_AMOUNT
    doc.threshold_percentage = DEFAULT_THRESHOLD
    doc.custodian = custodian
    doc.is_enabled = False
    doc.auto_submit_enabled = True
    doc.month_end_auto_submit = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    print(f"Created PCF fund for {store}")
    print(f"  Fund Amount: PHP {doc.fund_amount:,.2f}")
    print(f"  Custodian: {custodian}")
    print(f"  Status: Disabled (enable manually)")


def enable_store(store: str):
    """Enable PCF for a store."""
    pcf_name = frappe.db.get_value("BEI Petty Cash Fund", {"store": store}, "name")
    if not pcf_name:
        print(f"No PCF fund found for {store}. Run setup_single first.")
        return

    frappe.db.set_value("BEI Petty Cash Fund", pcf_name, "is_enabled", 1)
    frappe.db.commit()
    print(f"PCF enabled for {store}")


def disable_store(store: str):
    """Disable PCF for a store."""
    pcf_name = frappe.db.get_value("BEI Petty Cash Fund", {"store": store}, "name")
    if not pcf_name:
        print(f"No PCF fund found for {store}")
        return

    frappe.db.set_value("BEI Petty Cash Fund", pcf_name, "is_enabled", 0)
    frappe.db.commit()
    print(f"PCF disabled for {store}")


def list_funds():
    """List all PCF funds with their status."""
    funds = frappe.get_all(
        "BEI Petty Cash Fund",
        fields=[
            "name",
            "store",
            "is_enabled",
            "fund_amount",
            "pending_total",
            "pending_count",
            "threshold_percentage",
            "custodian",
        ],
        order_by="store asc",
    )

    if not funds:
        print("No PCF funds configured. Run setup_all first.")
        return

    print(f"\n{'Store':<40} {'Enabled':<8} {'Fund':>12} {'Pending':>12} {'Count':>6} {'Custodian':<30}")
    print("-" * 120)

    for f in funds:
        enabled = "Yes" if f.is_enabled else "No"
        print(
            f"{f.store:<40} {enabled:<8} {f.fund_amount:>12,.0f} {f.pending_total or 0:>12,.0f} {f.pending_count or 0:>6} {f.custodian or '-':<30}"
        )

    enabled_count = sum(1 for f in funds if f.is_enabled)
    print(f"\nTotal: {len(funds)} funds ({enabled_count} enabled)")


def update_custodians_from_area_supervisors():
    """Update all PCF custodians to match area supervisors."""
    funds = frappe.get_all(
        "BEI Petty Cash Fund",
        fields=["name", "store"],
    )

    updated = 0
    for fund in funds:
        supervisor = frappe.db.get_value("Warehouse", fund.store, "custom_area_supervisor")
        if supervisor:
            frappe.db.set_value("BEI Petty Cash Fund", fund.name, "custodian", supervisor)
            updated += 1
            print(f"Updated {fund.store} custodian to {supervisor}")

    frappe.db.commit()
    print(f"\nUpdated {updated} PCF custodians")


def recalculate_all_totals():
    """Recalculate pending_total and current_balance for all PCF funds."""
    from hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund import update_pcf_totals

    funds = frappe.get_all("BEI Petty Cash Fund", pluck="store")

    for store in funds:
        update_pcf_totals(store)
        print(f"Recalculated totals for {store}")

    print(f"\nRecalculated totals for {len(funds)} funds")
