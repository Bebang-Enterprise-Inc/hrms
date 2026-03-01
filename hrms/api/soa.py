from __future__ import annotations

from typing import Any

from markupsafe import escape as html_escape

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, get_last_day, now_datetime


@frappe.whitelist()
def generate_soa(store: str, period: str) -> dict[str, Any]:
	"""Generate Statement of Account for a store and period.

	Aggregates all non-cancelled billings for the store in the given period.

	Args:
	    store: Department name
	    period: Format "YYYY-MM"
	"""
	if not store or not period:
		frappe.throw(_("Store and period are required"))

	# Check for existing SOA
	existing = frappe.db.exists(
		"BEI Statement of Account",
		{
			"store": store,
			"soa_period": period,
			"status": ["not in", ["Cancelled"]],
		},
	)
	if existing:
		frappe.throw(_("SOA already exists for {0} period {1}: {2}").format(store, period, existing))

	# Parse period
	try:
		period_start = get_first_day(period + "-01")
		period_end = get_last_day(period + "-01")
	except Exception:
		frappe.throw(_("Invalid period format. Use YYYY-MM"))

	# Get all billings for this store in period
	# Monthly billings: match by billing_period
	monthly_billings = frappe.get_all(
		"BEI Billing Schedule",
		filters={
			"store": store,
			"billing_type": "Monthly Fees",
			"billing_period": period,
			"status": ["not in", ["Cancelled"]],
		},
		fields=[
			"name",
			"billing_type",
			"total_amount",
			"generated_on",
			"royalty_fee",
			"management_fee",
			"marketing_fee",
			"ecommerce_fee",
		],
	)

	# Delivery billings: match by date range (generated_on)
	delivery_billings = frappe.get_all(
		"BEI Billing Schedule",
		filters={
			"store": store,
			"billing_type": "Delivery",
			"generated_on": ["between", [period_start, period_end]],
			"status": ["not in", ["Cancelled"]],
		},
		fields=[
			"name",
			"billing_type",
			"total_amount",
			"generated_on",
			"delivery_fee",
			"logistics_fee",
			"goods_value",
			"handling_fee",
			"cargo_type",
			"trip_reference",
		],
	)

	if not monthly_billings and not delivery_billings:
		frappe.throw(_("No billings found for {0} in period {1}").format(store, period))

	# Create SOA
	soa = frappe.new_doc("BEI Statement of Account")
	soa.store = store
	soa.soa_period = period

	# Add monthly billing line items
	for bill in monthly_billings:
		# Break down monthly fees into separate line items
		fee_items = [
			("Royalty Fee", bill.royalty_fee),
			("Management Fee", bill.management_fee),
			("Marketing Fee", bill.marketing_fee),
			("eCommerce Fee", bill.ecommerce_fee),
		]
		for desc, amount in fee_items:
			if flt(amount) > 0:
				soa.append(
					"line_items",
					{
						"billing_reference": bill.name,
						"billing_type": "Monthly Fees",
						"billing_date": bill.generated_on,
						"description": desc,
						"amount": amount,
					},
				)

	# Add delivery billing line items
	for bill in delivery_billings:
		desc_parts = [f"Delivery - {bill.cargo_type or ''}"]
		if bill.trip_reference:
			desc_parts.append(f"Trip: {bill.trip_reference}")
		soa.append(
			"line_items",
			{
				"billing_reference": bill.name,
				"billing_type": "Delivery",
				"billing_date": bill.generated_on,
				"description": " | ".join(desc_parts),
				"amount": bill.total_amount,
			},
		)

	soa.insert()
	return {"success": True, "name": soa.name, "total": soa.total_billings}


@frappe.whitelist()
def get_soa_list(
	store: str | None = None, period: str | None = None, status: str | None = None
) -> list[dict[str, Any]]:
	"""List Statements of Account with optional filters."""
	filters = {}
	if store:
		filters["store"] = store
	if period:
		filters["soa_period"] = period
	if status:
		filters["status"] = status

	return frappe.get_all(
		"BEI Statement of Account",
		filters=filters,
		fields=[
			"name",
			"store",
			"store_type",
			"soa_period",
			"status",
			"total_billings",
			"total_payments",
			"balance_due",
			"generated_on",
			"sent_on",
		],
		order_by="soa_period desc, store asc",
	)


@frappe.whitelist()
def get_soa_detail(soa_name: str) -> dict[str, Any]:
	"""Get SOA header and line-items detail for a single record."""
	if not soa_name:
		frappe.throw(_("SOA name is required"))

	soa = frappe.get_doc("BEI Statement of Account", soa_name)
	if not frappe.has_permission("BEI Statement of Account", "read", doc=soa):
		frappe.throw(_("Not permitted to read this SOA"), frappe.PermissionError)

	line_items = []
	for item in soa.get("line_items", []):
		line_items.append(
			{
				"name": item.get("name"),
				"billing_reference": item.get("billing_reference"),
				"billing_type": item.get("billing_type"),
				"billing_date": item.get("billing_date"),
				"description": item.get("description"),
				"amount": flt(item.get("amount")),
			}
		)

	return {
		"name": soa.name,
		"store": soa.store,
		"store_type": soa.store_type,
		"soa_period": soa.soa_period,
		"status": soa.status,
		"total_billings": flt(soa.total_billings),
		"total_payments": flt(soa.total_payments),
		"balance_due": flt(soa.balance_due),
		"generated_on": soa.generated_on,
		"sent_on": soa.sent_on,
		"line_items": line_items,
	}


@frappe.whitelist()
def send_soa_to_store(soa_name: str) -> dict[str, Any]:
	"""Send SOA to store via email (Full Franchise only)."""
	soa = frappe.get_doc("BEI Statement of Account", soa_name)

	if soa.status not in ("Draft", "Pending Review"):
		frappe.throw(_("SOA must be in Draft or Pending Review status to send"))

	store_type = soa.store_type or frappe.db.get_value("BEI Store Type", {"store": soa.store}, "store_type")

	if store_type != "Full Franchise":
		# Internal stores — just mark as sent, no email
		soa.status = "Sent"
		soa.sent_on = now_datetime()
		soa.save()
		return {"success": True, "status": "Sent", "emailed": False}

	# Build SOA email content
	rows_html = ""
	for item in soa.line_items:
		rows_html += (
			f"<tr>"
			f"<td>{html_escape(str(item.billing_date or ''))}</td>"
			f"<td>{html_escape(str(item.description or ''))}</td>"
			f"<td>{html_escape(str(item.billing_type or ''))}</td>"
			f"<td style='text-align:right'>₱{flt(item.amount):,.2f}</td>"
			f"</tr>"
		)

	message = f"""
    <h2>Statement of Account</h2>
    <p><strong>Store:</strong> {html_escape(str(soa.store))}</p>
    <p><strong>Period:</strong> {html_escape(str(soa.soa_period))}</p>

    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse; width:100%">
        <thead>
            <tr style="background:#f5f5f5">
                <th>Date</th>
                <th>Description</th>
                <th>Type</th>
                <th style="text-align:right">Amount</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
        <tfoot>
            <tr><td colspan="3"><strong>Total Billings</strong></td>
                <td style="text-align:right"><strong>₱{flt(soa.total_billings):,.2f}</strong></td></tr>
            <tr><td colspan="3">Payments Received</td>
                <td style="text-align:right">₱{flt(soa.total_payments):,.2f}</td></tr>
            <tr style="background:#f5f5f5">
                <td colspan="3"><strong>Balance Due</strong></td>
                <td style="text-align:right"><strong>₱{flt(soa.balance_due):,.2f}</strong></td></tr>
        </tfoot>
    </table>

    <p style="margin-top:16px"><em>This is a system-generated Statement of Account from Bebang ERP.</em></p>
    """

	# Get recipients
	recipients = []
	dept_email = frappe.db.get_value("Department", soa.store, "department_email")
	if dept_email:
		recipients.append(dept_email)

	if recipients:
		try:
			frappe.sendmail(
				recipients=recipients,
				subject=_("Statement of Account: {0} - {1}").format(soa.store, soa.soa_period),
				message=message,
			)
		except Exception:
			frappe.log_error(f"Failed to send SOA email for {soa.name}", "SOA Email Error")

	soa.status = "Sent"
	soa.sent_on = now_datetime()
	soa.save()

	return {"success": True, "status": "Sent", "emailed": bool(recipients)}


@frappe.whitelist()
def get_monthly_billing_service_snapshot(period: str, store: str | None = None) -> dict[str, Any]:
	"""Service snapshot for monthly billing + OR follow-up surfaces."""
	if not period:
		frappe.throw(_("Period is required (YYYY-MM)"), frappe.ValidationError)

	params: dict[str, Any] = {"period": period}
	if store:
		params["store"] = store
		billing_stats = frappe.db.sql(
			"""
			SELECT
				COUNT(*) AS billing_count,
				COALESCE(SUM(bs.total_amount), 0) AS total_billed,
				COALESCE(SUM(bs.balance_due), 0) AS total_outstanding
			FROM `tabBEI Billing Schedule` bs
			WHERE bs.billing_period = %(period)s
			  AND bs.status != 'Cancelled'
			  AND bs.store = %(store)s
			""",
			params,
			as_dict=True,
		)[0]
	else:
		billing_stats = frappe.db.sql(
			"""
			SELECT
				COUNT(*) AS billing_count,
				COALESCE(SUM(bs.total_amount), 0) AS total_billed,
				COALESCE(SUM(bs.balance_due), 0) AS total_outstanding
			FROM `tabBEI Billing Schedule` bs
			WHERE bs.billing_period = %(period)s
			  AND bs.status != 'Cancelled'
			""",
			params,
			as_dict=True,
		)[0]

	followup_stats = frappe.db.sql(
		"""
        SELECT
            COUNT(*) AS overdue_or_count,
            COALESCE(SUM(payment_amount), 0) AS overdue_or_amount
        FROM `tabBEI Payment Request`
        WHERE status = 'Paid - Awaiting OR'
          AND or_status = 'Overdue'
        """,
		as_dict=True,
	)[0]

	return {
		"success": True,
		"period": period,
		"store": store,
		"billing": billing_stats,
		"or_follow_up": followup_stats,
	}
