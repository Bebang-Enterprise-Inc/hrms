"""
BEI Billing API - Delivery Rates, Billing Approval, and Monthly Billing

This module centralizes all billing operations for the BEI ERP system:
- Phase 2a: Delivery rate management (set, review, approve)
- Phase 3: Billing approval workflow
- Phase 4: Monthly billing generation (migrated from procurement.py)
"""

from hrms.utils.bei_config import get_company

import re
import calendar
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, get_first_day, get_last_day, nowdate, getdate

# P0-10: Import centralized RBAC role sets
from hrms.utils.scm_roles import RATE_MANAGEMENT_ROLES, SCM_BILLING_ROLES, check_scm_permission


def _check_rate_permission():
    """Verify the caller has Finance or Supply Chain manager role."""
    check_scm_permission(RATE_MANAGEMENT_ROLES, "manage delivery rates")


def on_billing_schedule_validate(doc, method=None):
    """Doc-event hardening for BEI Billing Schedule validation.

    Backstops monthly records so automation always has a billing_period key.
    """
    if getattr(doc, "billing_type", None) != "Monthly Fees":
        return
    if getattr(doc, "billing_period", None):
        return

    source_date = getattr(doc, "generated_on", None) or nowdate()
    doc.billing_period = getdate(source_date).strftime("%Y-%m")


def on_billing_schedule_update(doc, method=None):
    """Doc-event hardening for update lifecycle.

    Ensures sent_on is populated when status is moved to Sent by custom flows.
    """
    if getattr(doc, "status", None) != "Sent":
        return
    if getattr(doc, "sent_on", None):
        return
    if not getattr(doc, "name", None):
        return

    frappe.db.set_value("BEI Billing Schedule", doc.name, "sent_on", now_datetime())


def _find_existing_3pl_journal_entry(partner, period_label):
    cheque_no = f"3PL-{partner}-{period_label}"
    return frappe.db.get_value(
        "Journal Entry",
        {"cheque_no": cheque_no, "docstatus": ["!=", 2]},
        ["name", "total_debit", "docstatus"],
        as_dict=True,
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
        for cargo in ["FC", "DRY", "FM", "Mixed"]:
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
    _check_billing_permission("approve billings")
    billing = frappe.get_doc("BEI Billing Schedule", billing_name)
    if billing.status != "Pending":
        frappe.throw(_("Only Pending billings can be approved"))

    billing.status = "Approved"
    billing.save()
    return {"success": True, "status": "Approved"}


@frappe.whitelist()
def reject_billing(billing_name, reason=None):
    """Finance rejects a pending billing."""
    _check_billing_permission("reject billings")
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
    _check_billing_permission("send billings to store")
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
                  AND docstatus IN (0, 1)
            """, (store_rec.store, period_start, period_end), as_dict=True)[0]

            draft_count = frappe.db.count("BEI Store Closing Report", {
                "store": store_rec.store,
                "report_date": ["between", [period_start, period_end]],
                "docstatus": 0
            })
            if draft_count:
                frappe.logger().warning(
                    f"Billing for {store_rec.store}: {draft_count} DRAFT closing report(s) included in period {period_start} to {period_end}"
                )

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

            # Aggregate maintenance charges for franchise stores only
            maintenance_charges = 0.0
            maintenance_request_names = []
            if store_rec.store_type in ("Full Franchise", "Managed Franchise"):
                maint_rows = frappe.db.sql("""
                    SELECT name, total_cost
                    FROM `tabBEI Maintenance Request`
                    WHERE store = %s
                      AND status = 'Completed'
                      AND (billing_status IS NULL OR billing_status = 'Not Billed')
                      AND charge_to_store = 1
                      AND resolved_date BETWEEN %s AND %s
                """, (store_rec.store, period_start, period_end), as_dict=True)

                for row in maint_rows:
                    maintenance_charges += flt(row.total_cost)
                    maintenance_request_names.append(row.name)

            if maintenance_charges > 0:
                billing.repairs_maintenance = maintenance_charges
                billing.append("line_items", {
                    "fee_type": "Maintenance",
                    "description": f"Maintenance charges - {billing_period}",
                    "rate": maintenance_charges,
                    "amount": maintenance_charges,
                })

            billing.insert()

            # Mark maintenance requests as Billed
            if maintenance_request_names:
                for mr_name in maintenance_request_names:
                    frappe.db.set_value(
                        "BEI Maintenance Request",
                        mr_name,
                        {
                            "billing_status": "Billed",
                            "billing_reference": billing.name,
                        }
                    )

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


@frappe.whitelist()
def trigger_monthly_billing_service(billing_period=None, store=None):
    """Manual service endpoint used by portal trigger surfaces.

    This wraps generate_monthly_billing with explicit service metadata so UI
    and automation can consume a stable response contract.
    """
    result = generate_monthly_billing(billing_period=billing_period, store=store)
    return {
        "success": bool(result.get("success")),
        "service": "monthly_billing_trigger",
        "billing_period": result.get("billing_period"),
        "generated": result.get("generated", 0),
        "skipped": result.get("skipped", 0),
        "errors": result.get("errors", []),
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
    # conditions are all string constants, not user input
    conditions = ["1=1"]
    params = []
    if billing_period:
        conditions.append("billing_period = %s")
        params.append(billing_period)
    if store:
        conditions.append("store = %s")
        params.append(store)

    where = " AND ".join(conditions)

    summary = frappe.db.sql(
        "SELECT"
        " status,"
        " COUNT(*) as count,"
        " COALESCE(SUM(total_amount), 0) as total_amount,"
        " COALESCE(SUM(amount_paid), 0) as total_paid,"
        " COALESCE(SUM(balance_due), 0) as total_balance"
        " FROM `tabBEI Billing Schedule`"
        " WHERE " + where +
        " GROUP BY status",
        params, as_dict=True)

    totals = frappe.db.sql(
        "SELECT"
        " COUNT(*) as total_billings,"
        " COALESCE(SUM(total_amount), 0) as grand_total,"
        " COALESCE(SUM(amount_paid), 0) as total_collected,"
        " COALESCE(SUM(balance_due), 0) as total_outstanding"
        " FROM `tabBEI Billing Schedule`"
        " WHERE " + where,
        params, as_dict=True)[0]

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
    _check_billing_permission("cancel billings")
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


# ================================
# PHASE 4B — 3PL BILLING RECONCILIATION
# ================================
# Partners: RCS, 3MD/COOLITZ, PINNACLE
# Billing is per-trip flat rate (NOT per-km or per-kg)
# BIR RR 2-98: 2% EWT on hauling/freight services

# GL accounts for 3PL logistics costs and payment
# DM-1: party_type/party ONLY on AP row (2101101), NEVER on EWT Payable (2102202)
GL_LOGISTICS_COMMISSARY = "6003001"   # Logistics Cost - Commissary
GL_LOGISTICS_PCF        = "6003002"   # Logistics Cost - PCF
GL_LOGISTICS_WAREHOUSE  = "6003003"   # Logistics Cost - Warehouse

def _check_billing_permission(action="access billing records"):
    """Check if current user has any of the allowed 3PL billing roles."""
    check_scm_permission(SCM_BILLING_ROLES, action)


def _get_month_date_range(month, year):
    """Return (start_date, end_date) strings for a given month/year."""
    month = int(month)
    year = int(year)
    last_day = calendar.monthrange(year, month)[1]
    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{last_day:02d}"
    return start_date, end_date


def _get_gl_account_for_partner(partner):
    """Map 3PL partner to appropriate GL logistics cost account."""
    mapping = {
        "RCS":      GL_LOGISTICS_COMMISSARY,
        "3MD":      GL_LOGISTICS_COMMISSARY,
        "COOLITZ":  GL_LOGISTICS_PCF,
        "PINNACLE": GL_LOGISTICS_WAREHOUSE,
    }
    return mapping.get(partner, GL_LOGISTICS_COMMISSARY)


@frappe.whitelist()
def get_3pl_rates(partner=None, cargo_type=None):
    """
    GET active 3PL rate master lookup.
    Returns rates where effective_to is null or >= today.
    Filter by partner and/or cargo_type.
    """
    _check_billing_permission("view 3PL rates")

    today = nowdate()
    conditions = ["(effective_to IS NULL OR effective_to = '' OR effective_to >= %(today)s)"]
    params = {"today": today}

    if partner:
        conditions.append("threepl_partner = %(partner)s")
        params["partner"] = partner

    if cargo_type:
        conditions.append("cargo_type = %(cargo_type)s")
        params["cargo_type"] = cargo_type

    conditions.append("effective_from <= %(today)s")

    where_clause = " AND ".join(conditions)

    rates = frappe.db.sql(
        f"""
        SELECT
            name, rate_name, threepl_partner, cargo_type, zone,
            rate_per_trip, overtime_rate, surcharge_rate,
            COALESCE(ewt_atc, 'WC110') AS ewt_atc,
            COALESCE(ewt_rate, 1.0) AS ewt_rate,
            effective_from, effective_to, notes
        FROM `tabBEI 3PL Rate`
        WHERE {where_clause}
        ORDER BY threepl_partner, cargo_type, effective_from DESC
        """,
        params,
        as_dict=True
    )

    # Contract hardening for portal billing pages:
    # always include EWT fields even if legacy rows/migrations omit them.
    for rate in rates:
        rate["ewt_atc"] = rate.get("ewt_atc") or "WC110"
        rate["ewt_rate"] = flt(rate.get("ewt_rate") or 1.0)

    return {"rates": rates, "count": len(rates)}


@frappe.whitelist()
def generate_3pl_reconciliation(month, year, partner):
    """
    POST: Generate monthly 3PL reconciliation report.
    Steps:
      a. Get all BEI Distribution Trips for the month using a 3PL vehicle
      b. Match each trip to BEI 3PL Rate by zone + cargo_type + partner
      c. Calculate expected cost = rate_per_trip * trip_count + overtime + surcharges
      d. Return structured reconciliation data
    """
    _check_billing_permission("generate 3PL reconciliation")

    month = int(month)
    year = int(year)
    start_date, end_date = _get_month_date_range(month, year)

    # Fetch 3PL trips for the month (vehicle_owner matches the 3PL partner)
    trips_raw = frappe.db.sql(
        """
        SELECT
            dt.name AS trip_name,
            dt.trip_date AS date,
            dt.route AS zone,
            dt.cargo_type,
            dt.vehicle_owner,
            dt.overtime_hours,
            dt.is_holiday_trip,
            dt.is_weekend_trip,
            GROUP_CONCAT(DISTINCT ds.department SEPARATOR ', ') AS stores
        FROM `tabBEI Distribution Trip` dt
        LEFT JOIN `tabBEI Trip Stop` ds ON ds.parent = dt.name
        WHERE dt.trip_date BETWEEN %(start_date)s AND %(end_date)s
          AND dt.vehicle_owner = %(partner)s
          AND dt.docstatus = 1
        GROUP BY dt.name
        ORDER BY dt.trip_date ASC
        """,
        {"start_date": start_date, "end_date": end_date, "partner": partner},
        as_dict=True
    )

    # Fetch applicable rates for this partner active during the month
    rates = frappe.db.sql(
        """
        SELECT name, cargo_type, zone, rate_per_trip, overtime_rate, surcharge_rate,
               COALESCE(ewt_atc, 'WC110') AS ewt_atc,
               COALESCE(ewt_rate, 1.0) AS ewt_rate
        FROM `tabBEI 3PL Rate`
        WHERE threepl_partner = %(partner)s
          AND effective_from <= %(end_date)s
          AND (effective_to IS NULL OR effective_to = '' OR effective_to >= %(start_date)s)
        ORDER BY effective_from DESC
        """,
        {"partner": partner, "start_date": start_date, "end_date": end_date},
        as_dict=True
    )

    # Build rate lookup: (zone, cargo_type) -> rate (most-recent per key)
    rate_lookup = {}
    for r in rates:
        key = (r.get("zone") or "", r.get("cargo_type") or "")
        if key not in rate_lookup:
            rate_lookup[key] = r

    trip_lines = []
    total_expected = 0.0
    discrepancies = []

    for trip in trips_raw:
        zone = trip.get("zone") or ""
        cargo = trip.get("cargo_type") or ""

        # Try exact match, then zone-only, cargo-only, then wildcard
        rate = (
            rate_lookup.get((zone, cargo))
            or rate_lookup.get((zone, ""))
            or rate_lookup.get(("", cargo))
            or rate_lookup.get(("", ""))
        )

        if not rate:
            discrepancies.append({
                "trip_name": trip.trip_name,
                "date": str(trip.date),
                "reason": f"No matching rate for partner={partner}, zone={zone}, cargo_type={cargo}",
                "amount": 0
            })
            trip_lines.append({
                "trip_name": trip.trip_name,
                "date": str(trip.date),
                "zone": zone,
                "stores": trip.get("stores") or "",
                "cargo_type": cargo,
                "rate_name": None,
                "rate_per_trip": 0,
                "overtime_cost": 0,
                "surcharge_cost": 0,
                "cost": 0,
                "has_discrepancy": True
            })
            continue

        base_cost = flt(rate.rate_per_trip)
        overtime_hours = flt(trip.get("overtime_hours") or 0)
        overtime_cost = overtime_hours * flt(rate.get("overtime_rate") or 0)
        surcharge_cost = 0.0
        if trip.get("is_holiday_trip") or trip.get("is_weekend_trip"):
            surcharge_cost = flt(rate.get("surcharge_rate") or 0)

        trip_cost = base_cost + overtime_cost + surcharge_cost
        total_expected += trip_cost

        ewt_atc = rate.get("ewt_atc") or "WC110"
        ewt_rate_pct = flt(rate.get("ewt_rate") or 1.0)
        ewt_amount = round(trip_cost * (ewt_rate_pct / 100), 2)
        net_payment = round(trip_cost - ewt_amount, 2)

        trip_lines.append({
            "trip_name": trip.trip_name,
            "date": str(trip.date),
            "zone": zone,
            "stores": trip.get("stores") or "",
            "cargo_type": cargo,
            "rate_name": rate.get("name"),
            "rate_per_trip": base_cost,
            "overtime_cost": overtime_cost,
            "surcharge_cost": surcharge_cost,
            "cost": trip_cost,
            "ewt_atc": ewt_atc,
            "ewt_rate": ewt_rate_pct,
            "ewt_amount": ewt_amount,
            "net_payment": net_payment,
            "has_discrepancy": False
        })

    total_ewt = round(sum(t["ewt_amount"] for t in trip_lines if not t["has_discrepancy"]), 2)
    total_net = round(total_expected - total_ewt, 2)

    # Determine dominant EWT ATC for this partner (most recent rate)
    dominant_ewt_atc = "WC110"
    dominant_ewt_rate = 1.0
    if rates:
        dominant_ewt_atc = rates[0].get("ewt_atc") or "WC110"
        dominant_ewt_rate = flt(rates[0].get("ewt_rate") or 1.0)

    return {
        "partner": partner,
        "month": month,
        "year": year,
        "period": f"{year:04d}-{month:02d}",
        "trip_count": len(trips_raw),
        "trips": trip_lines,
        "total_expected": round(total_expected, 2),
        "total_ewt": total_ewt,
        "total_net": total_net,
        "ewt_atc": dominant_ewt_atc,
        "ewt_rate": dominant_ewt_rate,
        "discrepancies": discrepancies
    }


@frappe.whitelist()
def create_3pl_payment_request(month, year, partner, invoice_amount):
    """
    POST: Create a Journal Entry payment request for a 3PL invoice.
    - Gross = invoice_amount
    - EWT = gross * ewt_rate% (default WC110 1% per BEI 3PL Rate record)
    - Net payable = gross - EWT
    - GL: DR logistics cost (per partner), CR AP-Trade (net, with party), CR EWT Payable
    - DM-1: party ONLY on AP row, NOT on expense or EWT rows
    - DM-2: frappe.db.savepoint() wraps multi-doc operation
    """
    _check_billing_permission("create 3PL payment requests")

    invoice_amount = flt(invoice_amount)
    if invoice_amount <= 0:
        frappe.throw(_("Invoice amount must be greater than zero"))

    # Fetch EWT rate from active BEI 3PL Rate record for this partner
    today = nowdate()
    rate_doc = frappe.db.sql(
        """
        SELECT ewt_atc, ewt_rate
        FROM `tabBEI 3PL Rate`
        WHERE threepl_partner = %(partner)s
          AND effective_from <= %(today)s
          AND (effective_to IS NULL OR effective_to = '' OR effective_to >= %(today)s)
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        {"partner": partner, "today": today},
        as_dict=True
    )
    ewt_atc = (rate_doc[0].get("ewt_atc") or "WC110") if rate_doc else "WC110"
    ewt_rate_pct = flt((rate_doc[0].get("ewt_rate") or 1.0)) if rate_doc else 1.0

    # Validate EWT rate is within sane range (0.5% to 15%)
    if ewt_rate_pct < 0.5 or ewt_rate_pct > 15:
        frappe.throw(_("EWT rate {0}% is outside valid range (0.5-15%). Check BEI 3PL Rate record.").format(ewt_rate_pct))

    gross = invoice_amount
    ewt_amount = round(gross * (ewt_rate_pct / 100), 2)
    net_payable = round(gross - ewt_amount, 2)

    gl_debit_account = _get_gl_account_for_partner(partner)
    period_label = f"{int(year):04d}-{int(month):02d}"
    remarks = f"3PL Hauling - {partner} - {period_label}"

    company = get_company()

    # GAP-089: strong idempotency guard to prevent duplicate JEs for the same
    # partner/month. The cheque_no key is deterministic: 3PL-{partner}-{period}.
    existing = _find_existing_3pl_journal_entry(partner, period_label)
    if existing:
        existing_total = flt(existing.get("total_debit"))
        if abs(existing_total - gross) > 0.01:
            frappe.throw(
                _(
                    "Existing 3PL Journal Entry {0} already exists for {1} with amount {2}. "
                    "Cancel or adjust it before creating a new request."
                ).format(
                    existing.get("name"),
                    period_label,
                    frappe.format_value(existing_total, "Currency"),
                ),
                frappe.ValidationError,
            )

        return {
            "success": True,
            "journal_entry": existing.get("name"),
            "partner": partner,
            "period": period_label,
            "gross": existing_total,
            "ewt_atc": ewt_atc,
            "ewt_rate": ewt_rate_pct,
            "ewt_amount": ewt_amount,
            "net_payable": net_payable,
            "idempotent": True,
            "message": _("Existing 3PL payment request reused; duplicate JE prevented."),
        }

    sp_name = f"3pl_payment_{partner}_{period_label}".replace("-", "_")
    frappe.db.savepoint(sp_name)

    try:
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.company = company
        je.posting_date = nowdate()
        je.user_remark = remarks
        je.cheque_no = f"3PL-{partner}-{period_label}"
        je.cheque_date = nowdate()

        # DR: Logistics Cost (full gross) — NO party (expense account per DM-1)
        je.append("accounts", {
            "account": gl_debit_account,
            "debit_in_account_currency": gross,
            "credit_in_account_currency": 0,
            "user_remark": remarks
        })

        # CR: Accounts Payable - Trade (net payment) — DM-1: party ONLY on AP row
        je.append("accounts", {
            "account": "2101101 - ACCOUNTS PAYABLE - TRADE - BEI",
            "debit_in_account_currency": 0,
            "credit_in_account_currency": net_payable,
            "party_type": "Supplier",
            "party": partner,
            "user_remark": f"Net payable after EWT {ewt_atc} {ewt_rate_pct}% - {remarks}"
        })

        # CR: EWT Payable (ATC per rate record) — DM-1: NO party on EWT row
        je.append("accounts", {
            "account": "2102202 - EWT PAYABLE - BEI",
            "debit_in_account_currency": 0,
            "credit_in_account_currency": ewt_amount,
            "user_remark": f"EWT {ewt_atc} {ewt_rate_pct}% - {remarks}"
        })

        je.flags.ignore_permissions = True
        je.insert(ignore_permissions=True)
        je.submit()

        frappe.db.release_savepoint(sp_name)

        return {
            "success": True,
            "journal_entry": je.name,
            "partner": partner,
            "period": period_label,
            "gross": gross,
            "ewt_atc": ewt_atc,
            "ewt_rate": ewt_rate_pct,
            "ewt_amount": ewt_amount,
            "net_payable": net_payable,
            "gl_entries": [
                {"account": gl_debit_account, "debit": gross, "credit": 0},
                {"account": "2101101 - ACCOUNTS PAYABLE - TRADE - BEI", "debit": 0, "credit": net_payable},
                {"account": "2102202 - EWT PAYABLE - BEI", "debit": 0, "credit": ewt_amount},
            ]
        }

    except Exception as e:
        frappe.db.rollback(save_point=sp_name)
        frappe.log_error(frappe.get_traceback(), "3PL Payment Request Creation Failed")
        frappe.throw(_("Failed to create payment request: {0}").format(str(e)))


@frappe.whitelist()
def get_reconciliation_summary(month, year):
    """
    GET: Summary across all 3PL partners for a given month.
    Returns: [{partner, trip_count, expected_cost, invoice_amount, variance, variance_pct}]
    """
    _check_billing_permission("view reconciliation summary")

    month = int(month)
    year = int(year)
    start_date, end_date = _get_month_date_range(month, year)
    period_label = f"{year:04d}-{month:02d}"

    partners = ["RCS", "3MD", "COOLITZ", "PINNACLE"]
    summary = []

    # Batch trip counts for all partners in a single query (avoids N+1)
    trip_count_rows = frappe.db.sql(
        "SELECT vehicle_owner, COUNT(*) as cnt"
        " FROM `tabBEI Distribution Trip`"
        " WHERE trip_date BETWEEN %s AND %s AND docstatus = 1"
        " GROUP BY vehicle_owner",
        [start_date, end_date], as_dict=True)
    trip_counts = {r.vehicle_owner: r.cnt for r in trip_count_rows}

    # Batch JE lookups for all partners in a single query (avoids N+1)
    je_cheque_nos = [f"3PL-{p}-{period_label}" for p in partners]
    placeholders = ", ".join(["%s"] * len(je_cheque_nos))
    je_rows = frappe.db.sql(
        "SELECT cheque_no, total_debit FROM `tabJournal Entry`"
        " WHERE cheque_no IN (" + placeholders + ") AND docstatus != 2",  # conditions are string constants
        je_cheque_nos, as_dict=True)
    je_by_cheque = {r.cheque_no: flt(r.total_debit) for r in je_rows}

    for partner in partners:
        trip_count = trip_counts.get(partner, 0)

        if trip_count == 0:
            continue

        recon = generate_3pl_reconciliation(month, year, partner)
        expected_cost = flt(recon.get("total_expected") or 0)

        # Look up pre-fetched JE amount
        invoice_amount = je_by_cheque.get(f"3PL-{partner}-{period_label}", 0.0)

        variance = invoice_amount - expected_cost
        variance_pct = round((variance / expected_cost * 100), 2) if expected_cost else 0

        summary.append({
            "partner": partner,
            "period": period_label,
            "trip_count": trip_count,
            "expected_cost": round(expected_cost, 2),
            "invoice_amount": round(invoice_amount, 2),
            "variance": round(variance, 2),
            "variance_pct": variance_pct,
            "discrepancy_count": len(recon.get("discrepancies") or [])
        })

    return {
        "month": month,
        "year": year,
        "period": period_label,
        "partners": summary,
        "total_expected": round(sum(r["expected_cost"] for r in summary), 2),
        "total_invoiced": round(sum(r["invoice_amount"] for r in summary), 2)
    }


@frappe.whitelist()
def flag_discrepancy(trip_name, reason, amount):
    """
    POST: Flag a specific trip as discrepant.
    Reasons: extra_trip, wrong_rate, missing_pod, duplicate, other.
    Stores a comment on the BEI Distribution Trip document.
    """
    _check_billing_permission("flag trip discrepancies")

    if not trip_name:
        frappe.throw(_("trip_name is required"))
    if not reason:
        frappe.throw(_("reason is required"))

    amount = flt(amount)

    if not frappe.db.exists("BEI Distribution Trip", trip_name):
        frappe.throw(_("Trip {0} not found").format(trip_name), frappe.DoesNotExistError)

    comment = frappe.new_doc("Comment")
    comment.comment_type = "Comment"
    comment.reference_doctype = "BEI Distribution Trip"
    comment.reference_name = trip_name
    comment.content = (
        f"<b>3PL Billing Discrepancy Flagged</b><br>"
        f"Reason: {reason}<br>"
        f"Disputed Amount: {amount:,.2f}<br>"
        f"Flagged by: {frappe.session.user}"
    )
    comment.insert(ignore_permissions=True)

    # Update discrepancy fields on the trip if they exist
    try:
        frappe.db.set_value(
            "BEI Distribution Trip",
            trip_name,
            {
                "billing_discrepancy": 1,
                "discrepancy_reason": reason,
                "discrepancy_amount": amount
            }
        )
    except Exception as e:
        frappe.log_error(
            f"Could not update discrepancy fields on {trip_name}: {e}",
            "3PL Billing Discrepancy"
        )

    return {
        "success": True,
        "trip_name": trip_name,
        "reason": reason,
        "amount": amount,
        "flagged_by": frappe.session.user,
        "comment_name": comment.name
    }
