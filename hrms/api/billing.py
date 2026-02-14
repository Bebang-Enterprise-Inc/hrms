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


# ================================
# PHASE 5 — BILLING LIST, DETAIL, SUMMARY, PAYMENT, SOA, CANCEL
# ================================

@frappe.whitelist()
def get_billing_list(status=None, billing_type=None, store=None, billing_period=None,
                     limit_page_length=20, limit_start=0, order_by="modified desc"):
    """List billings with flexible filters."""
    filters = {}
    if status:
        filters["status"] = status
    if billing_type:
        filters["billing_type"] = billing_type
    if store:
        filters["store"] = store
    if billing_period:
        filters["billing_period"] = billing_period

    return frappe.get_all("BEI Billing Schedule",
        filters=filters,
        fields=["name", "billing_type", "billing_period", "store", "store_type",
                "status", "total_amount", "amount_paid", "balance_due",
                "generated_on", "sent_on", "paid_on"],
        order_by=order_by,
        limit_page_length=int(limit_page_length),
        limit_start=int(limit_start),
    )


@frappe.whitelist()
def get_billing_detail(name):
    """Get full billing details including line items and payment info."""
    billing = frappe.get_doc("BEI Billing Schedule", name)
    return {
        "name": billing.name,
        "billing_type": billing.billing_type,
        "billing_period": billing.billing_period,
        "store": billing.store,
        "store_type": billing.store_type,
        "status": billing.status,
        # Sales data
        "gross_sales": billing.gross_sales,
        "net_sales": billing.net_sales,
        "online_sales": billing.online_sales,
        "website_sales": billing.website_sales,
        # Fee breakdown
        "royalty_fee": billing.royalty_fee,
        "management_fee": billing.management_fee,
        "marketing_fee": billing.marketing_fee,
        "ecommerce_fee": billing.ecommerce_fee,
        "delivery_fee": billing.delivery_fee,
        "logistics_fee": billing.logistics_fee,
        "repairs_maintenance": billing.repairs_maintenance,
        "preventive_maintenance": billing.preventive_maintenance,
        # Totals
        "subtotal": billing.subtotal,
        "vat_amount": billing.vat_amount,
        "total_amount": billing.total_amount,
        "amount_paid": billing.amount_paid,
        "balance_due": billing.balance_due,
        # Payment info
        "payment_reference": billing.payment_reference,
        "payment_proof": billing.payment_proof,
        # Delivery-specific
        "trip_reference": billing.trip_reference,
        "cargo_type": billing.cargo_type,
        "goods_value": billing.goods_value,
        "handling_fee": billing.handling_fee,
        "delivery_cost": billing.delivery_cost,
        "logistics_cost": billing.logistics_cost,
        # Timestamps
        "generated_on": billing.generated_on,
        "sent_on": billing.sent_on,
        "paid_on": billing.paid_on,
        # Line items
        "line_items": [
            {"fee_type": li.fee_type, "description": li.description,
             "rate": li.rate, "amount": li.amount}
            for li in (billing.line_items or [])
        ],
    }


@frappe.whitelist()
def get_billing_summary(billing_period=None, store=None):
    """Get aggregated billing summary by status."""
    conditions = ["1=1"]
    params = []
    if billing_period:
        conditions.append("billing_period = %s")
        params.append(billing_period)
    if store:
        conditions.append("store = %s")
        params.append(store)

    where = " AND ".join(conditions)

    summary = frappe.db.sql(f"""
        SELECT
            status,
            COUNT(*) as count,
            COALESCE(SUM(total_amount), 0) as total_amount,
            COALESCE(SUM(amount_paid), 0) as total_paid,
            COALESCE(SUM(balance_due), 0) as total_balance
        FROM `tabBEI Billing Schedule`
        WHERE {where}
        GROUP BY status
    """, params, as_dict=True)

    totals = frappe.db.sql(f"""
        SELECT
            COUNT(*) as total_billings,
            COALESCE(SUM(total_amount), 0) as grand_total,
            COALESCE(SUM(amount_paid), 0) as total_collected,
            COALESCE(SUM(balance_due), 0) as total_outstanding
        FROM `tabBEI Billing Schedule`
        WHERE {where}
    """, params, as_dict=True)[0]

    return {
        "by_status": summary,
        "totals": totals,
        "billing_period": billing_period,
        "store": store,
    }


@frappe.whitelist()
def record_payment(name, amount, payment_reference=None, payment_proof=None):
    """Record a payment against a billing."""
    if not amount or flt(amount) <= 0:
        frappe.throw(_("Payment amount must be greater than zero"), frappe.ValidationError)

    billing = frappe.get_doc("BEI Billing Schedule", name)
    if billing.status not in ("Sent", "Approved"):
        frappe.throw(_("Payments can only be recorded for Sent or Approved billings"))

    new_paid = flt(billing.amount_paid) + flt(amount)
    if new_paid > flt(billing.total_amount):
        frappe.throw(_("Payment of {0} would exceed total amount of {1}").format(
            frappe.format_value(flt(amount), "Currency"),
            frappe.format_value(billing.total_amount, "Currency"),
        ))

    billing.amount_paid = new_paid
    billing.balance_due = flt(billing.total_amount) - new_paid
    if payment_reference:
        billing.payment_reference = payment_reference
    if payment_proof:
        billing.payment_proof = payment_proof

    # Auto-transition to Paid when fully paid
    if flt(billing.balance_due) <= 0:
        billing.status = "Paid"
        billing.paid_on = now_datetime()

    billing.save()
    return {
        "success": True,
        "amount_paid": billing.amount_paid,
        "balance_due": billing.balance_due,
        "status": billing.status,
    }


@frappe.whitelist()
def get_soa(name):
    """Generate Statement of Account for a billing."""
    billing = frappe.get_doc("BEI Billing Schedule", name)

    return {
        "billing_name": billing.name,
        "store": billing.store,
        "store_type": billing.store_type,
        "billing_period": billing.billing_period,
        "billing_type": billing.billing_type,
        "status": billing.status,
        # Fee breakdown
        "line_items": [
            {"fee_type": li.fee_type, "description": li.description,
             "rate": li.rate, "amount": li.amount}
            for li in (billing.line_items or [])
        ],
        "subtotal": billing.subtotal,
        "vat_amount": billing.vat_amount,
        "total_amount": billing.total_amount,
        "amount_paid": billing.amount_paid,
        "balance_due": billing.balance_due,
        "payment_reference": billing.payment_reference,
        "generated_on": str(billing.generated_on) if billing.generated_on else None,
        "sent_on": str(billing.sent_on) if billing.sent_on else None,
        "paid_on": str(billing.paid_on) if billing.paid_on else None,
    }


@frappe.whitelist()
def cancel_billing(name, reason=None):
    """Cancel a billing. Only Draft, Pending, or Sent billings can be cancelled."""
    billing = frappe.get_doc("BEI Billing Schedule", name)
    if billing.status in ("Cancelled", "Paid"):
        frappe.throw(_("Cannot cancel a {0} billing").format(billing.status))

    billing.status = "Cancelled"
    if reason:
        billing.add_comment("Comment", f"Cancelled: {reason}")
    billing.save()
    return {"success": True, "status": "Cancelled"}


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
