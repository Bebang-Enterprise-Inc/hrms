"""
BEI Billing API - Delivery Rates, Billing Approval, and Monthly Billing

This module centralizes all billing operations for the BEI ERP system:
- Phase 2a: Delivery rate management (set, review, approve)
- Phase 3: Billing approval workflow
- Phase 4: Monthly billing generation (migrated from procurement.py)
"""

import re

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, get_first_day, get_last_day

RATE_MANAGEMENT_ROLES = {"Accounts Manager", "Supply Chain Manager", "System Manager"}


def _check_rate_permission():
    """Verify the caller has Finance or Supply Chain manager role."""
    if not RATE_MANAGEMENT_ROLES.intersection(set(frappe.get_roles())):
        frappe.throw(
            _("Only Finance or Supply Chain managers can manage delivery rates"),
            frappe.PermissionError,
        )


# ================================
# PHASE 2a — RATE MANAGEMENT
# ================================

@frappe.whitelist()
def get_delivery_rates(store=None, cargo_type=None, status=None):
    """List delivery rates with optional filters."""
    filters = {}
    if store:
        filters["store"] = store
    if cargo_type:
        filters["cargo_type"] = cargo_type
    if status:
        filters["status"] = status

    rates = frappe.get_all("BEI Delivery Rate",
        filters=filters,
        fields=["name", "store", "cargo_type", "delivery_fee", "logistics_fee",
                "effective_from", "status", "set_by", "set_by_role",
                "reviewed_by", "reviewed_by_role", "reviewed_at"],
        order_by="store asc, cargo_type asc, modified desc"
    )
    return rates


@frappe.whitelist()
def set_delivery_rate(store, cargo_type, delivery_fee, logistics_fee, effective_from, notes=None):
    """Create or update a delivery rate. Auto-detects caller role."""
    _check_rate_permission()

    rate = frappe.new_doc("BEI Delivery Rate")
    rate.store = store
    rate.cargo_type = cargo_type
    rate.delivery_fee = flt(delivery_fee)
    rate.logistics_fee = flt(logistics_fee)
    rate.effective_from = effective_from
    rate.status = "Draft"
    rate.notes = notes
    # set_by and set_by_role auto-populated by before_save in controller
    rate.insert()
    return {"success": True, "name": rate.name}


@frappe.whitelist()
def submit_rate_for_review(rate_name):
    """Move rate from Draft to Pending Review."""
    rate = frappe.get_doc("BEI Delivery Rate", rate_name)
    if rate.status != "Draft":
        frappe.throw(_("Only Draft rates can be submitted for review"))
    rate.status = "Pending Review"
    rate.save()
    return {"success": True, "status": rate.status}


@frappe.whitelist()
def approve_rate(rate_name):
    """Approve a rate: Pending Review -> Active. Expires any existing active rate."""
    _check_rate_permission()

    rate = frappe.get_doc("BEI Delivery Rate", rate_name)
    if rate.status != "Pending Review":
        frappe.throw(_("Only rates with 'Pending Review' status can be approved"))

    # Expire existing active rate for same store+cargo_type
    existing_active = frappe.get_all("BEI Delivery Rate", filters={
        "store": rate.store,
        "cargo_type": rate.cargo_type,
        "status": "Active",
        "name": ["!=", rate.name]
    })
    for old in existing_active:
        frappe.db.set_value("BEI Delivery Rate", old.name, "status", "Expired")

    # Activate new rate
    rate.status = "Active"
    rate.reviewed_by = frappe.session.user
    user_roles = frappe.get_roles(frappe.session.user)
    if "Accounts Manager" in user_roles:
        rate.reviewed_by_role = "Finance"
    elif "Supply Chain Manager" in user_roles:
        rate.reviewed_by_role = "Supply Chain"
    rate.reviewed_at = now_datetime()
    rate.save()
    return {"success": True, "status": rate.status}


@frappe.whitelist()
def get_stores_without_rates():
    """Get stores that are missing active delivery rates."""
    # All stores from BEI Store Type
    all_stores = frappe.get_all("BEI Store Type", fields=["store", "store_type"])

    # Build set of (store, cargo_type) with active rates
    stores_with_rates = frappe.db.sql("""
        SELECT DISTINCT store, cargo_type FROM `tabBEI Delivery Rate`
        WHERE status = 'Active'
    """, as_dict=True)
    active_set = {(r.store, r.cargo_type) for r in stores_with_rates}

    missing = []
    for st in all_stores:
        for cargo in ["Dry Goods", "Frozen Goods"]:
            if (st.store, cargo) not in active_set:
                missing.append({
                    "store": st.store,
                    "store_type": st.store_type,
                    "cargo_type": cargo
                })

    return missing


# ================================
# PHASE 3 — BILLING APPROVAL
# ================================

@frappe.whitelist()
def get_pending_billings(store=None, billing_type=None):
    """List billings pending Finance approval."""
    filters = {"status": "Pending"}
    if store:
        filters["store"] = store
    if billing_type:
        filters["billing_type"] = billing_type

    return frappe.get_all("BEI Billing Schedule",
        filters=filters,
        fields=["name", "billing_type", "store", "store_type", "total_amount",
                "trip_reference", "cargo_type", "goods_value", "handling_fee",
                "delivery_fee", "logistics_fee", "generated_on"],
        order_by="generated_on asc"
    )


@frappe.whitelist()
def approve_billing(billing_name):
    """Finance approves a pending billing. Pending → Approved."""
    billing = frappe.get_doc("BEI Billing Schedule", billing_name)
    if billing.status != "Pending":
        frappe.throw(_("Only Pending billings can be approved"))

    billing.status = "Approved"
    billing.save()
    return {"success": True, "status": "Approved"}


@frappe.whitelist()
def reject_billing(billing_name, reason=None):
    """Finance rejects a pending billing."""
    billing = frappe.get_doc("BEI Billing Schedule", billing_name)
    if billing.status != "Pending":
        frappe.throw(_("Only Pending billings can be rejected"))

    billing.status = "Cancelled"
    if reason:
        billing.add_comment("Comment", reason)
    billing.save()
    return {"success": True, "status": "Cancelled"}


@frappe.whitelist()
def send_billing_to_store(billing_name):
    """Send approved billing to store (Full Franchise only)."""
    billing = frappe.get_doc("BEI Billing Schedule", billing_name)
    # I-08 fix: Only Approved or already-Sent billings can be sent
    if billing.status not in ("Approved", "Sent"):
        frappe.throw(_("Billing must be Approved before sending"))

    # Only email Full Franchise stores
    if billing.store_type == "Full Franchise":
        billing.send_to_store()  # Uses existing method
    else:
        # Internal billing — just mark as Sent without email
        billing.status = "Sent"
        billing.sent_on = now_datetime()
        billing.save()

    return {"success": True, "status": billing.status}


# ================================
# PHASE 4 — MONTHLY BILLING
# ================================

@frappe.whitelist()
def generate_monthly_billing(billing_period=None, store=None):
    """Generate monthly franchise fee billing for all stores.

    Creates BEI Billing Schedule with billing_type='Monthly Fees'.
    Data source: Supabase POS data (via Store Closing Reports for now).

    Args:
        billing_period: Format "YYYY-MM"
        store: Optional single store name

    Returns:
        dict with generated count, skipped count, errors list
    """
    if not billing_period:
        frappe.throw(_("Missing required parameter: billing_period"), frappe.ValidationError)

    if not frappe.has_permission("BEI Billing Schedule", "create"):
        frappe.throw(_("Insufficient permissions to generate billing"), frappe.PermissionError)

    try:
        period_start = get_first_day(billing_period + "-01")
        period_end = get_last_day(billing_period + "-01")
    except Exception:
        frappe.throw(_("Invalid billing period format. Use YYYY-MM"))

    store_filters = {"store": store} if store else {}
    stores = frappe.get_all("BEI Store Type", filters=store_filters, fields=["store", "store_type"])

    generated = 0
    skipped = 0
    errors = []

    for store_rec in stores:
        sp_name = "billing_" + re.sub(r'[^a-zA-Z0-9_]', '_', store_rec.store)
        sp = frappe.db.savepoint(sp_name)
        try:
            # Duplicate check
            existing = frappe.db.exists("BEI Billing Schedule", {
                "store": store_rec.store,
                "billing_period": billing_period,
                "billing_type": "Monthly Fees",
                "status": ["not in", ["Cancelled"]],
            })
            if existing:
                skipped += 1
                frappe.db.release_savepoint(sp)
                continue

            # Aggregate sales from Store Closing Reports
            sales_data = frappe.db.sql("""
                SELECT
                    COALESCE(SUM(gross_sales), 0) as gross_sales,
                    COALESCE(SUM(net_sales), 0) as net_sales,
                    COALESCE(SUM(online_sales), 0) as online_sales,
                    COALESCE(SUM(website_sales), 0) as website_sales
                FROM `tabBEI Store Closing Report`
                WHERE store = %s
                  AND report_date BETWEEN %s AND %s
                  AND docstatus = 1
            """, (store_rec.store, period_start, period_end), as_dict=True)[0]

            if not sales_data.gross_sales and not sales_data.net_sales:
                skipped += 1
                frappe.db.release_savepoint(sp)
                continue

            billing = frappe.get_doc({
                "doctype": "BEI Billing Schedule",
                "billing_type": "Monthly Fees",
                "billing_period": billing_period,
                "store": store_rec.store,
                "store_type": store_rec.store_type,
                "gross_sales": sales_data.gross_sales,
                "net_sales": sales_data.net_sales,
                "online_sales": sales_data.online_sales,
                "website_sales": sales_data.website_sales,
                "status": "Draft",
            })
            billing.insert()
            generated += 1
            frappe.db.release_savepoint(sp)

        except Exception as e:
            frappe.db.rollback(save_point=sp)
            errors.append({"store": store_rec.store, "error": str(e)})

    return {
        "success": True,
        "generated": generated,
        "skipped": skipped,
        "errors": errors,
        "billing_period": billing_period,
    }


def scheduled_monthly_billing():
    """Scheduled job: auto-generate monthly billing for the previous month.

    Called by hooks.py cron (6 AM on 1st of each month).
    """
    from frappe.utils import add_months, getdate, today as frappe_today

    prev_month = add_months(frappe_today(), -1)
    billing_period = getdate(prev_month).strftime("%Y-%m")

    result = generate_monthly_billing(billing_period=billing_period)

    frappe.log_error(
        f"Monthly billing generated for {billing_period}: "
        f"{result.get('generated', 0)} created, {result.get('skipped', 0)} skipped, "
        f"{len(result.get('errors', []))} errors",
        "Scheduled Monthly Billing"
    )
