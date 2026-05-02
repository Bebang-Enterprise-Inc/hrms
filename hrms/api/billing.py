"""
BEI Billing API - Delivery Rates, Billing Approval, and Monthly Billing

This module centralizes all billing operations for the BEI ERP system:
- Phase 2a: Delivery rate management (set, review, approve)
- Phase 3: Billing approval workflow
- Phase 4: Monthly billing generation (migrated from procurement.py)
"""

import calendar
import re
from decimal import Decimal
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, get_last_day, getdate, now_datetime, nowdate

from hrms.hr.doctype.bei_store_type.bei_store_type import resolve_store_type
from hrms.utils.bei_config import get_company

# P0-10: Import centralized RBAC role sets
from hrms.utils.scm_roles import RATE_MANAGEMENT_ROLES, SCM_BILLING_ROLES, check_scm_permission
from hrms.utils.sentry import set_backend_observability_context
from hrms.utils.supply_chain_contracts import resolve_store_buyer_entity


def _check_rate_permission():
	"""Verify the caller has Finance or Supply Chain manager role."""
	check_scm_permission(RATE_MANAGEMENT_ROLES, "manage delivery rates")


def _get_rate_actor_role(user: str | None = None) -> str | None:
	"""Map runtime roles to the billing rate workflow department label."""
	user_roles = set(frappe.get_roles(user or frappe.session.user) or [])
	if "Accounts Manager" in user_roles:
		return "Finance"
	if user_roles.intersection({"Supply Chain Manager", "Warehouse Manager", "Warehouse User"}):
		return "Supply Chain"
	return None


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


def _get_record_value(record, fieldname):
	"""Read field from dict-like or object record."""
	if isinstance(record, dict):
		return record.get(fieldname)
	return getattr(record, fieldname, None)


def _set_record_value(record, fieldname, value):
	"""Write field to dict-like or object record."""
	if isinstance(record, dict):
		record[fieldname] = value
	else:
		setattr(record, fieldname, value)


def _has_column(doctype: str, fieldname: str) -> bool:
	"""Return True when the runtime table really has the requested column."""
	has_column = getattr(frappe.db, "has_column", None)
	if not callable(has_column):
		return False
	try:
		return bool(has_column(doctype, fieldname))
	except Exception:
		return False


def _trip_partner_field_sql(trip_alias: str = "dt", vehicle_alias: str = "veh") -> str:
	"""Resolve the live 3PL partner field across legacy and current trip schemas."""
	if _has_column("BEI Distribution Trip", "vehicle_owner"):
		return f"{trip_alias}.vehicle_owner"
	return f"{vehicle_alias}.threepl_partner"


def _trip_vehicle_join_sql(trip_alias: str = "dt", vehicle_alias: str = "veh") -> str:
	"""Join BEI Vehicle only when partner data moved off the trip record."""
	if _has_column("BEI Distribution Trip", "vehicle_owner"):
		return ""
	return f" LEFT JOIN `tabBEI Vehicle` {vehicle_alias} ON {vehicle_alias}.name = {trip_alias}.vehicle"


def _trip_optional_field_sql(fieldname: str, trip_alias: str = "dt", default: str = "0") -> str:
	"""Select optional trip columns safely across schema revisions."""
	if _has_column("BEI Distribution Trip", fieldname):
		return f"{trip_alias}.{fieldname}"
	return default


def _trip_stop_store_sql(stop_alias: str = "ds", default: str = "''") -> str:
	"""Resolve the live trip-stop label column across schema variants."""
	if _has_column("BEI Trip Stop", "store"):
		return f"{stop_alias}.store"
	if _has_column("BEI Trip Stop", "department"):
		return f"{stop_alias}.department"
	return default


def _normalize_3pl_partner_label(partner: str | None) -> str:
	"""Collapse legacy/live 3PL partner labels into the portal-facing canonical set."""
	label = (partner or "").strip()
	if not label:
		return ""

	canonical = label.upper()
	aliases = {
		"FOUR COOLITZ": "COOLITZ",
	}
	return aliases.get(canonical, canonical)


def _get_3pl_trip_query():
	"""Return a static SQL query for all active 3PL-partner-tagged trips in the period."""
	overtime_sql = _trip_optional_field_sql("overtime_hours")
	holiday_sql = _trip_optional_field_sql("is_holiday_trip")
	weekend_sql = _trip_optional_field_sql("is_weekend_trip")
	store_sql = _trip_stop_store_sql()

	if _has_column("BEI Distribution Trip", "vehicle_owner"):
		return f"""
        SELECT
            dt.name AS trip_name,
            dt.trip_date AS date,
            dt.route AS zone,
            dt.cargo_type,
            dt.vehicle_owner AS partner,
            {overtime_sql} AS overtime_hours,
            {holiday_sql} AS is_holiday_trip,
            {weekend_sql} AS is_weekend_trip,
            GROUP_CONCAT(DISTINCT {store_sql} SEPARATOR ', ') AS stores
        FROM `tabBEI Distribution Trip` dt
        LEFT JOIN `tabBEI Trip Stop` ds ON ds.parent = dt.name
        WHERE dt.trip_date BETWEEN %(start_date)s AND %(end_date)s
          AND COALESCE(dt.vehicle_owner, '') != ''
          AND dt.docstatus < 2
        GROUP BY dt.name
        ORDER BY dt.trip_date ASC
        """

	return f"""
    SELECT
        dt.name AS trip_name,
        dt.trip_date AS date,
        dt.route AS zone,
        dt.cargo_type,
        veh.threepl_partner AS partner,
        {overtime_sql} AS overtime_hours,
        {holiday_sql} AS is_holiday_trip,
        {weekend_sql} AS is_weekend_trip,
        GROUP_CONCAT(DISTINCT {store_sql} SEPARATOR ', ') AS stores
    FROM `tabBEI Distribution Trip` dt
    LEFT JOIN `tabBEI Vehicle` veh ON veh.name = dt.vehicle
    LEFT JOIN `tabBEI Trip Stop` ds ON ds.parent = dt.name
    WHERE dt.trip_date BETWEEN %(start_date)s AND %(end_date)s
      AND COALESCE(veh.threepl_partner, '') != ''
      AND dt.docstatus < 2
    GROUP BY dt.name
    ORDER BY dt.trip_date ASC
    """


def _get_3pl_trip_count_query():
	"""Return a static SQL query for partner trip counts across schema variants."""
	if _has_column("BEI Distribution Trip", "vehicle_owner"):
		return """
        SELECT dt.vehicle_owner AS partner, COUNT(*) AS cnt
        FROM `tabBEI Distribution Trip` dt
        WHERE dt.trip_date BETWEEN %s AND %s
          AND dt.docstatus < 2
          AND COALESCE(dt.vehicle_owner, '') != ''
        GROUP BY dt.vehicle_owner
        """

	return """
    SELECT veh.threepl_partner AS partner, COUNT(*) AS cnt
    FROM `tabBEI Distribution Trip` dt
    LEFT JOIN `tabBEI Vehicle` veh ON veh.name = dt.vehicle
    WHERE dt.trip_date BETWEEN %s AND %s
      AND dt.docstatus < 2
      AND COALESCE(veh.threepl_partner, '') != ''
    GROUP BY veh.threepl_partner
    """


def _normalized_store_type(store_type=None, legacy_store_type_category=None):
	"""Return canonical store_type from canonical or legacy value."""
	return resolve_store_type(
		store_type=store_type,
		store_type_category=legacy_store_type_category,
	)


def _normalize_store_type_records(records):
	"""Normalize store_type field in list responses."""
	for record in records or []:
		canonical = _normalized_store_type(
			store_type=_get_record_value(record, "store_type"),
			legacy_store_type_category=_get_record_value(record, "store_type_category"),
		)
		_set_record_value(record, "store_type", canonical)
	return records


def _get_store_type_records(store_filters=None):
	"""Fetch BEI Store Type rows with schema-safe canonical store_type normalization."""
	columns = set()
	column_lookup_candidates = ("BEI Store Type", "tabBEI Store Type")
	for table_name in column_lookup_candidates:
		try:
			candidate_columns = set(frappe.db.get_table_columns(table_name) or [])
		except Exception:
			continue
		if candidate_columns:
			columns = candidate_columns
			break

	if not columns:
		frappe.logger().warning("Billing store-type schema lookup failed; skipping BEI Store Type scan")
		return []

	has_store_type = "store_type" in columns
	has_legacy_store_type = "store_type_category" in columns

	if not has_store_type and not has_legacy_store_type:
		return []

	fields = ["store"]
	if has_store_type:
		fields.append("store_type")
	if has_legacy_store_type:
		fields.append("store_type_category")

	rows = frappe.get_all("BEI Store Type", filters=store_filters or {}, fields=fields)
	return _normalize_store_type_records(rows)


# ================================
# PHASE 2a — RATE MANAGEMENT
# ================================


@frappe.whitelist()
def get_delivery_rates(
	store: str | None = None,
	cargo_type: str | None = None,
	status: str | None = None,
):
	"""List delivery rates with optional filters."""
	_check_rate_permission()

	filters = {}
	if store:
		filters["store"] = store
	if cargo_type:
		filters["cargo_type"] = cargo_type
	if status:
		filters["status"] = status

	rates = frappe.get_all(
		"BEI Delivery Rate",
		filters=filters,
		fields=[
			"name",
			"store",
			"cargo_type",
			"delivery_fee",
			"logistics_fee",
			"effective_from",
			"status",
			"set_by",
			"set_by_role",
			"reviewed_by",
			"reviewed_by_role",
			"reviewed_at",
		],
		order_by="store asc, cargo_type asc, modified desc",
	)
	return rates


@frappe.whitelist()
def set_delivery_rate(
	store: str,
	cargo_type: str,
	delivery_fee: Any,
	logistics_fee: Any,
	effective_from: str,
	notes: str | None = None,
):
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
def submit_rate_for_review(rate_name: str):
	"""Move rate from Draft to Pending Review."""
	rate = frappe.get_doc("BEI Delivery Rate", rate_name)
	if rate.status != "Draft":
		frappe.throw(_("Only Draft rates can be submitted for review"))
	rate.status = "Pending Review"
	rate.save()
	return {"success": True, "status": rate.status}


@frappe.whitelist()
def approve_rate(rate_name: str):
	"""Approve a rate: Pending Review -> Active. Expires any existing active rate."""
	_check_rate_permission()

	rate = frappe.get_doc("BEI Delivery Rate", rate_name)
	if rate.status != "Pending Review":
		frappe.throw(_("Only rates with 'Pending Review' status can be approved"))

	reviewer = frappe.session.user
	reviewer_role = _get_rate_actor_role(reviewer)
	if rate.set_by and rate.set_by == reviewer:
		frappe.throw(_("Cannot approve your own rate"))

	if reviewer_role and rate.set_by_role and reviewer_role == rate.set_by_role:
		frappe.throw(_("Delivery rates must be approved by the other department"))

	# Expire existing active rate for same store+cargo_type
	existing_active = frappe.get_all(
		"BEI Delivery Rate",
		filters={
			"store": rate.store,
			"cargo_type": rate.cargo_type,
			"status": "Active",
			"name": ["!=", rate.name],
		},
	)
	for old in existing_active:
		frappe.db.set_value("BEI Delivery Rate", old.name, "status", "Expired")

	# Activate new rate
	rate.status = "Active"
	rate.reviewed_by = reviewer
	if reviewer_role:
		rate.reviewed_by_role = reviewer_role
	rate.reviewed_at = now_datetime()
	rate.save()
	return {"success": True, "status": rate.status}


@frappe.whitelist()
def get_stores_without_rates():
	"""Get stores that are missing active delivery rates."""
	_check_rate_permission()

	# All stores from BEI Store Type
	all_stores = _get_store_type_records()

	# Build set of (store, cargo_type) with active rates
	stores_with_rates = frappe.db.sql(
		"""
        SELECT DISTINCT store, cargo_type FROM `tabBEI Delivery Rate`
        WHERE status = 'Active'
    """,
		as_dict=True,
	)
	active_set = {(r.store, r.cargo_type) for r in stores_with_rates}

	missing = []
	for st in all_stores:
		for cargo in ["FC", "DRY", "FM", "Mixed"]:
			if (st.store, cargo) not in active_set:
				missing.append(
					{
						"store": st.store,
						"store_type": _normalized_store_type(st.store_type),
						"cargo_type": cargo,
					}
				)

	return missing


# ================================
# PHASE 3 — BILLING APPROVAL
# ================================


@frappe.whitelist()
def get_pending_billings(store: str | None = None, billing_type: str | None = None):
	"""List billings pending Finance approval."""
	_check_billing_permission("view pending billings")

	filters = {"status": "Pending"}
	if store:
		filters["store"] = store
	if billing_type:
		filters["billing_type"] = billing_type

	billings = frappe.get_all(
		"BEI Billing Schedule",
		filters=filters,
		fields=[
			"name",
			"billing_type",
			"store",
			"store_type",
			"total_amount",
			"trip_reference",
			"cargo_type",
			"goods_value",
			"handling_fee",
			"delivery_fee",
			"logistics_fee",
			"generated_on",
		],
		order_by="generated_on asc",
	)
	return _normalize_store_type_records(billings)


@frappe.whitelist()
def approve_billing(billing_name: str):
	"""Finance approves a pending billing. Pending → Approved.

	S168 Phase 10 (R2-C10): On approval, also auto-create a VAT-applied
	Sales Invoice on the BKI side for the delivery/logistics fees and
	link it back to the Billing Schedule via custom_bei_store_billing /
	sales_invoice (custom fields per Phase 1 schema).
	"""
	set_backend_observability_context(
		module="logistics",
		action="approve_billing",
		mutation_type="update",
	)
	_check_billing_permission("approve billings")
	billing = frappe.get_doc("BEI Billing Schedule", billing_name)
	if billing.status != "Pending":
		frappe.throw(_("Only Pending billings can be approved"))

	billing.status = "Approved"
	billing.save()

	# S168 Phase 10: auto-create fee Sales Invoice (VAT applied) on approval
	si_name = None
	try:
		frappe.db.savepoint("s168_approve_billing_si")
		si_name = _create_fee_sales_invoice_for_billing(billing)
		if si_name:
			# Reverse link via BEI Billing Schedule-sales_invoice custom field
			try:
				frappe.db.savepoint("s168_billing_rollup")
				frappe.db.set_value(
					"BEI Billing Schedule", billing.name, "sales_invoice", si_name
				)
				frappe.db.release_savepoint("s168_billing_rollup")
			except Exception:
				try:
					frappe.db.sql("ROLLBACK TO SAVEPOINT s168_billing_rollup")
				except Exception:
					pass
				frappe.log_error(
					f"S168 Phase 10: rollup link failed for {billing.name}: {frappe.get_traceback()}",
					"S168 Approve Billing Rollup",
				)
		frappe.db.release_savepoint("s168_approve_billing_si")
	except Exception:
		try:
			frappe.db.sql("ROLLBACK TO SAVEPOINT s168_approve_billing_si")
		except Exception:
			pass
		frappe.log_error(
			f"S168 Phase 10: fee SI creation failed for {billing.name}: {frappe.get_traceback()}",
			"S168 Approve Billing SI",
		)

	return {"success": True, "status": "Approved", "fee_sales_invoice": si_name}


def _resolve_fee_recipient_company(ownership_type: str) -> str | None:
	"""S231 D-4: per-ownership-type SI.company target for franchise fee SIs.

	Reads from BEI Settings so Finance can rotate recipients without code
	deploys. Per CEO 2026-05-02:
	  - JV → BEI revenue PERMANENTLY (NOT BFC); per Collection Agent Letter
	    §"What this letter does NOT cover" item 4.
	  - Managed/Full Franchise → BFC revenue (collected by BEI as agent
	    during interim, then remitted; ratified by Collection Agent Letter).
	  - Company Owned → no franchise fees; returns None and caller skips.
	"""
	if ownership_type == "Company Owned":
		return None
	if ownership_type == "JV":
		recipient = frappe.db.get_single_value("BEI Settings", "jv_revenue_company")
		if not recipient:
			frappe.throw(
				_("S231 D-4: BEI Settings.jv_revenue_company is not set; cannot route JV fee SI.")
			)
		return recipient
	if ownership_type in ("Managed Franchise", "Full Franchise"):
		recipient = frappe.db.get_single_value("BEI Settings", "bfc_revenue_company")
		if not recipient:
			frappe.throw(
				_(
					"S231 D-4: BEI Settings.bfc_revenue_company is not set; cannot route "
					"{0} fee SI."
				).format(ownership_type)
			)
		return recipient
	raise ValueError(f"S231 D-4: unknown ownership_type {ownership_type!r}")


def _assert_bfc_billing_ready() -> None:
	"""S231 D-3-10: precondition for BFC franchise SI creation.

	Throws when ANY of the BFC operating prerequisites are not yet
	configured. Defense against generating SIs before BFC has an OR
	booklet, VAT registration, or naming series.
	"""
	if not frappe.db.get_single_value("BEI Settings", "bfc_or_active"):
		frappe.throw(
			_(
				"S231 D-3-10: BFC OR booklet not active. Finance must flip "
				"`BEI Settings.bfc_or_active` to 1 before BFC franchise fee SIs "
				"can be created."
			)
		)
	if not frappe.db.get_single_value("BEI Settings", "bfc_vat_registration_active"):
		frappe.throw(
			_(
				"S231 D-3-10: BFC VAT registration not active. Finance must flip "
				"`BEI Settings.bfc_vat_registration_active` to 1 once BIR confirms "
				"BFC VAT registration."
			)
		)
	if not frappe.db.get_single_value("BEI Settings", "bfc_sales_naming_series"):
		frappe.throw(
			_(
				"S231 D-3-10: BFC sales naming series not set. Finance must set "
				"`BEI Settings.bfc_sales_naming_series` (e.g. \"BFC-SI-.YYYY.-.####\")."
			)
		)


def _create_monthly_fee_sales_invoice(billing) -> str | None:
	"""S231 D-3-6: SI builder for `billing_type='Monthly Fees'` rows.

	Routes to BEI vs BFC per `_resolve_fee_recipient_company`, applies
	the recipient's VAT template, line-items each non-zero fee field,
	and tacks on an EWT line if the franchisee Customer is flagged as a
	Top 20,000 Corporation (BIR Form 2307 withholding agent).

	Returns SI name on success, None when there's nothing billable
	(zero fees) or recipient is None (Company Owned).
	"""
	ownership_type = getattr(billing, "store_type", None)
	recipient = _resolve_fee_recipient_company(ownership_type)
	if not recipient:
		return None

	is_bfc = recipient == frappe.db.get_single_value("BEI Settings", "bfc_revenue_company")
	if is_bfc:
		_assert_bfc_billing_ready()

	# Aggregate fees that have a non-zero amount.
	fee_fields = (
		("royalty_fee", "Royalty"),
		("marketing_fee", "Marketing"),
		("management_fee", "Management"),
		("ecommerce_fee", "E-commerce"),
	)
	non_zero = [
		(field, label, flt(getattr(billing, field, 0) or 0))
		for field, label in fee_fields
		if flt(getattr(billing, field, 0) or 0) > 0
	]
	if not non_zero:
		return None

	# Resolve the franchisee Customer via the canonical resolver.
	store_name = getattr(billing, "store", None)
	if not store_name:
		frappe.throw(
			_("S231 D-3-6: Billing {0} has no store; cannot create Monthly Fees SI").format(billing.name)
		)
	entity_row = resolve_store_buyer_entity(warehouse_docname=store_name, store_name=store_name)
	buyer_entity_name = (entity_row or {}).get("buyer_entity_name") or ""
	if not buyer_entity_name:
		frappe.throw(
			_(
				"S231 D-3-6: No buyer entity resolved for store {0}; cannot create "
				"Monthly Fees SI. Check Warehouse.company canonical state."
			).format(store_name)
		)
	customer = frappe.db.get_value("Customer", {"customer_name": buyer_entity_name}, "name")
	if not customer:
		frappe.throw(
			_("S231 D-3-6: No Customer record for buyer entity '{0}' (store: {1}).").format(
				buyer_entity_name, store_name
			)
		)

	settings = frappe.get_single("BEI Settings")
	vat_template = (
		(getattr(settings, "bfc_sales_vat_template", "") or "").strip()
		if is_bfc
		else (getattr(settings, "jv_sales_vat_template", "") or "").strip()
	)
	if not vat_template:
		recipient_field = "bfc_sales_vat_template" if is_bfc else "jv_sales_vat_template"
		frappe.throw(
			_(
				"S231 D-3-6: BEI Settings.{0} not set. Cannot create Monthly Fees SI "
				"without 12% VAT template."
			).format(recipient_field)
		)
	naming_series = (
		(getattr(settings, "bfc_sales_naming_series", "") or "").strip()
		if is_bfc
		else None
	)

	currency = frappe.db.get_value("Company", recipient, "default_currency") or "PHP"
	cost_center = frappe.db.get_value("Company", recipient, "cost_center")

	si = frappe.new_doc("Sales Invoice")
	si.company = recipient
	si.customer = customer
	si.is_internal_customer = 0
	si.posting_date = nowdate()
	si.set_posting_time = 1
	si.currency = currency
	si.taxes_and_charges = vat_template
	if naming_series:
		si.naming_series = naming_series
	si.custom_bei_store_billing = billing.name
	si.remarks = (
		f"S231 D-3-6: Monthly franchise fees for {store_name} "
		f"(period {getattr(billing, 'billing_period', '') or ''}). "
		f"Recipient={recipient}. Source: BEI Billing Schedule {billing.name}."
	)

	# Per-fee line items. The fee `label` becomes the description so the SI is
	# self-documenting at print time without needing a separate Item per fee.
	for field, label, amount in non_zero:
		si.append(
			"items",
			{
				"item_code": _resolve_fee_item_code(label),
				"qty": 1,
				"rate": amount,
				"description": f"{label} fee — {store_name} ({billing.name})",
				"cost_center": cost_center,
			},
		)

	# Apply the VAT template's tax rows.
	try:
		from erpnext.controllers.accounts_controller import get_taxes_and_charges

		taxes = get_taxes_and_charges("Sales Taxes and Charges Template", vat_template) or []
		for tax in taxes:
			si.append("taxes", tax)
	except Exception:
		frappe.log_error(
			f"S231 D-3-6: failed to load taxes from template {vat_template}: {frappe.get_traceback()}",
			"S231 Monthly Fee SI",
		)
		raise

	# EWT line per BIR Form 2307 if franchisee is a Top 20,000 corporation
	# (mandatory withholding agent). Defensive `has_field` guard so we don't
	# break if the custom Customer field hasn't been provisioned yet.
	customer_meta = frappe.get_meta("Customer")
	is_top_20000 = False
	for candidate in ("is_top_20000_corp", "custom_is_top_20000_corp"):
		if customer_meta.has_field(candidate):
			is_top_20000 = bool(frappe.db.get_value("Customer", customer, candidate))
			break
	if is_top_20000:
		ewt_rate = flt(frappe.db.get_single_value("BEI Settings", "default_ewt_rate") or 0)
		ewt_account = (
			frappe.db.get_single_value("BEI Settings", "ewt_payable_account") or ""
		).strip()
		if ewt_rate > 0 and ewt_account:
			si.append(
				"taxes",
				{
					"charge_type": "Actual",
					"account_head": ewt_account,
					"description": f"EWT {ewt_rate}% (BIR Form 2307)",
					"rate": -abs(ewt_rate),
				},
			)

	si.insert(ignore_permissions=True)
	si.submit()
	return si.name


def _resolve_fee_item_code(fee_label: str) -> str:
	"""Pick the Item code for a Monthly Fees SI line. Falls back to a
	configurable default Item if specific fee Items aren't provisioned.
	"""
	# Future enhancement: per-fee Items in BEI Settings (e.g.
	# bfc_royalty_fee_item). For now reuse the generic logistics fee
	# Item to avoid a brittle hard requirement at first deploy.
	settings = frappe.get_single("BEI Settings")
	candidate = (
		getattr(settings, "bki_logistics_fee_item", None)
		or getattr(settings, "logistics_fee_item", None)
		or "LOGISTICS-FEE"
	)
	if frappe.db.exists("Item", candidate):
		return candidate
	alt = frappe.db.get_value(
		"Item", {"item_name": ["like", "Logistics Fee%"], "disabled": 0}, "name"
	)
	if alt:
		return alt
	frappe.throw(
		_(
			"S231 D-3-6: No Item found for franchise fee SI line. Finance must "
			"create a service Item before Monthly Fees billings can be approved."
		)
	)


def _create_fee_sales_invoice_for_billing(billing) -> str | None:
	"""Create + submit a VAT-applied Sales Invoice for delivery/logistics
	fees on a BEI Billing Schedule. Returns SI name or None if nothing
	billable. Mirrors hrms/api/commissary.py::build_bki_store_sale_invoice
	but for service fees instead of goods. Per CFO Q1: 12% VAT MUST apply.

	S231 D-3-6: Monthly Fees billings are routed to
	`_create_monthly_fee_sales_invoice` which handles BFC/BEI recipient
	splitting, the per-ownership-type fee schedule line items, EWT, and
	the BFC operating-readiness precondition.
	"""
	# S231 D-3-11: tag SI creation runs for Sentry grouping.
	set_backend_observability_context(
		module="billing",
		action="create_fee_si",
		mutation_type="create",
		extras={
			"billing": getattr(billing, "name", None),
			"billing_type": getattr(billing, "billing_type", None),
			"store": getattr(billing, "store", None),
		},
	)

	# S231 D-3-6: Monthly Fees branch — different recipient, fee structure,
	# and tax template. Co-Owned billings end here too because
	# `_resolve_fee_recipient_company` returns None for them.
	if getattr(billing, "billing_type", None) == "Monthly Fees":
		return _create_monthly_fee_sales_invoice(billing)

	delivery_fee = flt(getattr(billing, "delivery_fee", 0) or 0)
	logistics_fee = flt(getattr(billing, "logistics_fee", 0) or 0)
	if delivery_fee <= 0 and logistics_fee <= 0:
		return None

	store_name = getattr(billing, "store", None)
	if not store_name:
		frappe.throw(_("Billing {0} has no store; cannot create fee SI").format(billing.name))
	# S190: resolve_store_buyer_entity now tries Company-first, then CSV fallback
	entity_row = resolve_store_buyer_entity(
		warehouse_docname=store_name, store_name=store_name
	)
	buyer_entity_name = (entity_row or {}).get("buyer_entity_name") or ""
	if not buyer_entity_name:
		frappe.throw(
			_(
				"No buyer entity resolved for store {0}; cannot create fee SI. "
				"Check Warehouse.company or buyer entity register."
			).format(store_name)
		)
	# S190: Look up Customer by customer_name (not by name) for robustness
	customer = frappe.db.get_value("Customer", {"customer_name": buyer_entity_name}, "name")
	if not customer:
		frappe.throw(
			_("No Customer record for buyer entity '{0}' (store: {1}).").format(
				buyer_entity_name, store_name
			)
		)

	settings = frappe.get_single("BEI Settings")
	vat_template = (getattr(settings, "bki_sales_vat_template", "") or "").strip()
	if not vat_template:
		frappe.throw(
			_("BEI Settings.bki_sales_vat_template is not set. Cannot create fee SI without 12% VAT (CFO Q1).")
		)
	income_account = (getattr(settings, "bki_sales_income_account", "") or "").strip()
	if not income_account:
		frappe.throw(_("BEI Settings.bki_sales_income_account is not set. Cannot create fee SI."))
	debit_to = (getattr(settings, "bki_sales_debit_to_account", "") or "").strip()

	bki_company = get_company("BKI") or get_company()

	fee_item = (
		getattr(settings, "bki_logistics_fee_item", None)
		or getattr(settings, "logistics_fee_item", None)
		or "LOGISTICS-FEE"
	)
	if not frappe.db.exists("Item", fee_item):
		alt = frappe.db.get_value(
			"Item", {"item_name": ["like", "Logistics Fee%"], "disabled": 0}, "name"
		)
		if alt:
			fee_item = alt
		else:
			frappe.throw(
				_(
					"S168 Phase 10: No Item found for logistics/delivery fees. "
					"Finance must create a service Item before approving billing."
				)
			)

	si = frappe.new_doc("Sales Invoice")
	si.company = bki_company
	si.customer = customer
	si.is_internal_customer = 0
	si.posting_date = nowdate()
	si.set_posting_time = 1
	si.currency = frappe.db.get_value("Company", bki_company, "default_currency") or "PHP"
	si.taxes_and_charges = vat_template
	if debit_to:
		si.debit_to = debit_to
	si.custom_bei_store_billing = billing.name
	si.remarks = (
		f"S168 Phase 10: Logistics/Delivery fee billing for {store_name} "
		f"({getattr(billing, 'billing_type', '')} {getattr(billing, 'billing_period', '') or ''}). "
		f"Source: BEI Billing Schedule {billing.name}."
	)

	cost_center = frappe.db.get_value("Company", bki_company, "cost_center")

	if delivery_fee > 0:
		si.append(
			"items",
			{
				"item_code": fee_item,
				"qty": 1,
				"rate": delivery_fee,
				"description": f"Delivery fee — {store_name} ({billing.name})",
				"income_account": income_account,
				"cost_center": cost_center,
			},
		)
	if logistics_fee > 0:
		si.append(
			"items",
			{
				"item_code": fee_item,
				"qty": 1,
				"rate": logistics_fee,
				"description": f"Logistics fee — {store_name} ({billing.name})",
				"income_account": income_account,
				"cost_center": cost_center,
			},
		)

	try:
		from erpnext.controllers.accounts_controller import get_taxes_and_charges

		taxes = get_taxes_and_charges("Sales Taxes and Charges Template", vat_template) or []
		for tax in taxes:
			si.append("taxes", tax)
	except Exception:
		frappe.log_error(
			f"S168 Phase 10: failed to load taxes from template {vat_template}: {frappe.get_traceback()}",
			"S168 Approve Billing SI",
		)
		raise

	si.insert(ignore_permissions=True)
	si.submit()
	return si.name


# ================================
# PHASE 11 — POST-SUBMISSION CREDIT NOTES (S168 R1 Amendment 3)
# ================================


@frappe.whitelist()
def create_store_sale_credit_note(
	sales_invoice: str,
	reason: str,
	credit_lines: list | str | None = None,
	attachments: list | str | None = None,
):
	"""S168 Phase 11: Create a Return Sales Invoice (credit note) against
	an already-submitted store sale SI. Used for post-delivery amendments
	(short delivery, item defects, etc.)."""
	set_backend_observability_context(
		module="store",
		action="create_store_sale_credit_note",
		mutation_type="create",
	)
	check_scm_permission(SCM_BILLING_ROLES, "create store sale credit notes")

	if not sales_invoice:
		frappe.throw(_("sales_invoice is required"))
	if not reason or not str(reason).strip():
		frappe.throw(_("reason is required for credit notes"))

	if isinstance(credit_lines, str):
		import json as _json
		try:
			credit_lines = _json.loads(credit_lines)
		except Exception:
			frappe.throw(_("credit_lines must be a JSON list"))
	if not credit_lines or not isinstance(credit_lines, list):
		frappe.throw(_("credit_lines must be a non-empty list"))

	original = frappe.get_doc("Sales Invoice", sales_invoice)
	if original.docstatus != 1:
		frappe.throw(_("Can only credit submitted Sales Invoices"))

	credit_note_name = None
	try:
		frappe.db.savepoint("s168_credit_note")

		cn = frappe.new_doc("Sales Invoice")
		cn.is_return = 1
		cn.return_against = original.name
		cn.company = original.company
		cn.customer = original.customer
		cn.currency = original.currency
		cn.posting_date = nowdate()
		cn.set_posting_time = 1
		cn.taxes_and_charges = original.taxes_and_charges
		if getattr(original, "debit_to", None):
			cn.debit_to = original.debit_to
		for fld in (
			"custom_bei_receiving",
			"custom_bei_store_order",
			"custom_bei_store_billing",
			"custom_stock_entry",
			"custom_delivery_receipt_no",
		):
			val = getattr(original, fld, None)
			if val:
				try:
					setattr(cn, fld, val)
				except Exception:
					pass
		cn.remarks = f"S168 Phase 11 credit note vs {original.name}. Reason: {reason}"

		original_items = {row.item_code: row for row in original.items}

		for line in credit_lines:
			item_code = (line or {}).get("item_code")
			qty = flt((line or {}).get("qty"))
			if not item_code or qty <= 0:
				continue
			if item_code not in original_items:
				frappe.throw(
					_("Item {0} is not on original Sales Invoice {1}").format(item_code, original.name)
				)
			src = original_items[item_code]
			rate = flt((line or {}).get("rate") or src.rate)
			cn.append(
				"items",
				{
					"item_code": item_code,
					"qty": -qty,
					"uom": src.uom,
					"rate": rate,
					"income_account": src.income_account,
					"warehouse": src.warehouse,
					"cost_center": src.cost_center,
				},
			)

		if not cn.items:
			frappe.throw(_("No valid credit lines provided"))

		if cn.taxes_and_charges:
			try:
				from erpnext.controllers.accounts_controller import get_taxes_and_charges

				taxes = (
					get_taxes_and_charges("Sales Taxes and Charges Template", cn.taxes_and_charges) or []
				)
				for tax in taxes:
					cn.append("taxes", tax)
			except Exception:
				frappe.log_error(
					f"S168 Phase 11: failed to load taxes for credit note vs {original.name}: {frappe.get_traceback()}",
					"S168 Credit Note",
				)

		cn.insert(ignore_permissions=True)
		cn.submit()
		credit_note_name = cn.name

		if attachments:
			frappe.logger().info(
				f"S168 Phase 11 credit note {credit_note_name} declared {len(attachments)} attachment(s)."
			)

		frappe.db.release_savepoint("s168_credit_note")
	except Exception:
		try:
			frappe.db.sql("ROLLBACK TO SAVEPOINT s168_credit_note")
		except Exception:
			pass
		frappe.log_error(
			f"S168 Phase 11: credit note creation failed for {sales_invoice}: {frappe.get_traceback()}",
			"S168 Credit Note",
		)
		raise

	return {
		"success": True,
		"credit_note": credit_note_name,
		"original_sales_invoice": sales_invoice,
		"reason": reason,
	}


# ================================
# PHASE 14 — BILLING HOLDS DASHBOARD (S168 R1 Amendment 2)
# ================================


@frappe.whitelist()
def get_billing_holds():
	"""S168 Phase 14: Return draft Sales Invoices that are linked to a
	BEI Store Receiving but failed to auto-submit."""
	set_backend_observability_context(
		module="store",
		action="get_billing_holds",
		mutation_type="read",
	)
	check_scm_permission(SCM_BILLING_ROLES, "view billing holds")

	rows = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 0, "custom_bei_receiving": ["is", "set"]},
		fields=[
			"name",
			"customer",
			"custom_bei_receiving",
			"custom_bei_store_order",
			"custom_bei_store_billing",
			"grand_total",
			"posting_date",
			"creation",
		],
		order_by="creation desc",
		limit_page_length=500,
	)
	return rows


@frappe.whitelist()
def release_billing_hold(sales_invoice: str):
	"""S168 Phase 14: Submit a held draft Sales Invoice."""
	set_backend_observability_context(
		module="store",
		action="release_billing_hold",
		mutation_type="update",
	)
	check_scm_permission(SCM_BILLING_ROLES, "release billing holds")
	if not sales_invoice:
		frappe.throw(_("sales_invoice is required"))

	try:
		frappe.db.savepoint("s168_release_hold")
		si = frappe.get_doc("Sales Invoice", sales_invoice)
		if si.docstatus != 0:
			frappe.throw(_("Sales Invoice {0} is not a draft").format(sales_invoice))
		si.submit()
		frappe.db.release_savepoint("s168_release_hold")
	except Exception:
		try:
			frappe.db.sql("ROLLBACK TO SAVEPOINT s168_release_hold")
		except Exception:
			pass
		frappe.log_error(
			f"S168 Phase 14: release_billing_hold failed for {sales_invoice}: {frappe.get_traceback()}",
			"S168 Billing Holds",
		)
		raise

	return {"success": True, "sales_invoice": sales_invoice, "status": "Submitted"}


@frappe.whitelist()
def reject_billing_hold(sales_invoice: str, reason: str):
	"""S168 Phase 14: Reject (delete if draft, cancel if submitted) a held SI."""
	set_backend_observability_context(
		module="store",
		action="reject_billing_hold",
		mutation_type="delete",
	)
	check_scm_permission(SCM_BILLING_ROLES, "reject billing holds")
	if not sales_invoice:
		frappe.throw(_("sales_invoice is required"))
	if not reason or not str(reason).strip():
		frappe.throw(_("reason is required when rejecting a billing hold"))

	try:
		frappe.db.savepoint("s168_reject_hold")
		si = frappe.get_doc("Sales Invoice", sales_invoice)
		if si.docstatus == 0:
			si.add_comment("Comment", f"S168 Phase 14 reject reason: {reason}")
			si.delete(ignore_permissions=True)
		elif si.docstatus == 1:
			si.cancel()
			frappe.db.set_value(
				"Sales Invoice",
				sales_invoice,
				"remarks",
				(si.remarks or "") + f"\nS168 Phase 14 reject reason: {reason}",
			)
		else:
			frappe.throw(_("Sales Invoice {0} is already cancelled").format(sales_invoice))
		frappe.db.release_savepoint("s168_reject_hold")
	except Exception:
		try:
			frappe.db.sql("ROLLBACK TO SAVEPOINT s168_reject_hold")
		except Exception:
			pass
		frappe.log_error(
			f"S168 Phase 14: reject_billing_hold failed for {sales_invoice}: {frappe.get_traceback()}",
			"S168 Billing Holds",
		)
		raise

	return {"success": True, "sales_invoice": sales_invoice, "status": "Rejected", "reason": reason}


@frappe.whitelist()
def reassign_billing_hold_customer(sales_invoice: str, new_customer: str):
	"""S168 Phase 14: Change the customer on a held draft Sales Invoice."""
	set_backend_observability_context(
		module="store",
		action="reassign_billing_hold_customer",
		mutation_type="update",
	)
	check_scm_permission(SCM_BILLING_ROLES, "reassign billing hold customer")
	if not sales_invoice:
		frappe.throw(_("sales_invoice is required"))
	if not new_customer:
		frappe.throw(_("new_customer is required"))
	if not frappe.db.exists("Customer", new_customer):
		frappe.throw(_("Customer {0} does not exist").format(new_customer))

	try:
		frappe.db.savepoint("s168_reassign_hold")
		si = frappe.get_doc("Sales Invoice", sales_invoice)
		if si.docstatus != 0:
			frappe.throw(
				_("Cannot reassign customer on submitted Sales Invoice {0}").format(sales_invoice)
			)
		old_customer = si.customer
		si.customer = new_customer
		si.add_comment(
			"Comment",
			f"S168 Phase 14 customer reassigned: {old_customer} → {new_customer}",
		)
		si.save(ignore_permissions=True)
		frappe.db.release_savepoint("s168_reassign_hold")
	except Exception:
		try:
			frappe.db.sql("ROLLBACK TO SAVEPOINT s168_reassign_hold")
		except Exception:
			pass
		frappe.log_error(
			f"S168 Phase 14: reassign_billing_hold_customer failed for {sales_invoice}: {frappe.get_traceback()}",
			"S168 Billing Holds",
		)
		raise

	return {"success": True, "sales_invoice": sales_invoice, "customer": new_customer}


@frappe.whitelist()
def reject_billing(billing_name: str, reason: str | None = None):
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
def send_billing_to_store(billing_name: str):
	"""Send approved billing to store (Full Franchise only)."""
	_check_billing_permission("send billings to store")
	billing = frappe.get_doc("BEI Billing Schedule", billing_name)
	billing_store_type = _normalized_store_type(billing.store_type)
	if billing_store_type and billing_store_type != billing.store_type:
		billing.store_type = billing_store_type

	# I-08 fix: Only Approved or already-Sent billings can be sent
	if billing.status not in ("Approved", "Sent"):
		frappe.throw(_("Billing must be Approved before sending"))

	# Only email Full Franchise stores
	if billing_store_type == "Full Franchise":
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
def generate_monthly_billing(billing_period: str | None = None, store: str | None = None):
	"""Generate monthly franchise fee billing for all stores.

	Creates BEI Billing Schedule with billing_type='Monthly Fees'.
	Data source: Supabase POS data (via Store Closing Reports for now).

	Args:
	    billing_period: Format "YYYY-MM"
	    store: Optional single store name

	Returns:
	    dict with generated count, skipped count, errors list

	S231 D-3-8: per-store savepoint named `s231_bill_<store>` so a single
	store's failure rolls back ONLY that store's BEI Billing Schedule
	insert; the loop continues for the remaining 48 stores. Existing
	`billing_<store>` savepoint pattern (preserved for backward compat
	with logger searches) is now namespaced.

	S231 D-3-9: Redis mutex `s231_billing_lock_<period>` prevents the
	cron + a manual call from racing on the same period. TTL 1 hour;
	released in finally.

	S231 D-3-11: `set_backend_observability_context` tags every cron run
	in Sentry with the period + scope so post-deploy errors are
	groupable.
	"""
	if not billing_period:
		frappe.throw(_("Missing required parameter: billing_period"), frappe.ValidationError)

	if not frappe.has_permission("BEI Billing Schedule", "create"):
		frappe.throw(_("Insufficient permissions to generate billing"), frappe.PermissionError)

	# S231 D-3-11: tag every monthly billing run for Sentry grouping.
	set_backend_observability_context(
		module="billing",
		action="generate_monthly_billing",
		mutation_type="create",
		extras={"billing_period": billing_period, "store_scope": store or "all"},
	)

	# S231 D-3-9: Redis mutex prevents the `0 6 1 * *` cron + a manual
	# `trigger_monthly_billing_service` invocation from racing on the same
	# period (which would silently double-bill every store).
	lock_key = f"s231_billing_lock_{billing_period}"
	if not frappe.cache().setnx(lock_key, 1):
		frappe.log_error(
			f"S231 D-3-9: monthly billing already running for {billing_period}; this call skipped",
			"S231 Monthly Billing Mutex",
		)
		return {
			"success": False,
			"skipped": True,
			"reason": "concurrent_run",
			"billing_period": billing_period,
		}
	# 1-hour TTL — much longer than a normal run but a safety net if a
	# crash leaves the lock orphaned.
	frappe.cache().expire(lock_key, 3600)

	try:
		period_start = get_first_day(billing_period + "-01")
		period_end = get_last_day(billing_period + "-01")
	except Exception:
		frappe.cache().delete_value(lock_key)
		frappe.throw(_("Invalid billing period format. Use YYYY-MM"))

	store_filters = {"store": store} if store else {}
	stores = _get_store_type_records(store_filters=store_filters)

	generated = 0
	skipped = 0
	errors = []

	for store_rec in stores:
		store_name = _get_record_value(store_rec, "store")
		store_type = _normalized_store_type(
			store_type=_get_record_value(store_rec, "store_type"),
			legacy_store_type_category=_get_record_value(store_rec, "store_type_category"),
		)

		# S231 D-3-8: namespaced savepoint so failure on one store doesn't
		# affect the other 48.
		sp_name = "s231_bill_" + re.sub(r"[^a-zA-Z0-9_]", "_", store_name)
		frappe.db.savepoint(sp_name)
		try:
			# Duplicate check
			existing = frappe.db.exists(
				"BEI Billing Schedule",
				{
					"store": store_name,
					"billing_period": billing_period,
					"billing_type": "Monthly Fees",
					"status": ["not in", ["Cancelled"]],
				},
			)
			if existing:
				skipped += 1
				frappe.db.release_savepoint(sp_name)
				continue

			# Aggregate sales from Store Closing Reports
			sales_data = frappe.db.sql(
				"""
                SELECT
                    COALESCE(SUM(gross_sales), 0) as gross_sales,
                    COALESCE(SUM(net_sales), 0) as net_sales,
                    COALESCE(SUM(online_sales), 0) as online_sales,
                    COALESCE(SUM(website_sales), 0) as website_sales
                FROM `tabBEI Store Closing Report`
                WHERE store = %s
                  AND report_date BETWEEN %s AND %s
                  AND docstatus IN (0, 1)
            """,
				(store_name, period_start, period_end),
				as_dict=True,
			)[0]

			draft_count = frappe.db.count(
				"BEI Store Closing Report",
				{"store": store_name, "report_date": ["between", [period_start, period_end]], "docstatus": 0},
			)
			if draft_count:
				frappe.logger().warning(
					f"Billing for {store_name}: {draft_count} DRAFT closing report(s) included in period {period_start} to {period_end}"
				)

			if not sales_data.gross_sales and not sales_data.net_sales:
				skipped += 1
				frappe.db.release_savepoint(sp_name)
				continue

			billing = frappe.get_doc(
				{
					"doctype": "BEI Billing Schedule",
					"billing_type": "Monthly Fees",
					"billing_period": billing_period,
					"store": store_name,
					"store_type": store_type,
					"gross_sales": sales_data.gross_sales,
					"net_sales": sales_data.net_sales,
					"online_sales": sales_data.online_sales,
					"website_sales": sales_data.website_sales,
					"status": "Draft",
				}
			)

			# Aggregate maintenance charges for franchise stores only
			maintenance_charges = 0.0
			maintenance_request_names = []
			if store_type in ("Full Franchise", "Managed Franchise"):
				maint_rows = frappe.db.sql(
					"""
                    SELECT name, total_cost
                    FROM `tabBEI Maintenance Request`
                    WHERE store = %s
                      AND status = 'Completed'
                      AND (billing_status IS NULL OR billing_status = 'Not Billed')
                      AND charge_to_store = 1
                      AND resolved_date BETWEEN %s AND %s
                """,
					(store_name, period_start, period_end),
					as_dict=True,
				)

				for row in maint_rows:
					maintenance_charges += flt(row.total_cost)
					maintenance_request_names.append(row.name)

			if maintenance_charges > 0:
				billing.repairs_maintenance = maintenance_charges
				billing.append(
					"line_items",
					{
						"fee_type": "Maintenance",
						"description": f"Maintenance charges - {billing_period}",
						"rate": maintenance_charges,
						"amount": maintenance_charges,
					},
				)

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
						},
					)

			generated += 1
			frappe.db.release_savepoint(sp_name)

		except Exception as e:
			frappe.db.rollback(save_point=sp_name)
			errors.append({"store": store_name, "error": str(e)})

	# S231 D-3-9: release the period lock so the next run can proceed.
	try:
		frappe.cache().delete_value(lock_key)
	except Exception:
		# Cache failure shouldn't mask a successful billing run; the TTL
		# will reap the lock within an hour.
		frappe.log_error(
			f"S231 D-3-9: failed to release billing lock {lock_key}",
			"S231 Monthly Billing Mutex",
		)

	return {
		"success": True,
		"generated": generated,
		"skipped": skipped,
		"errors": errors,
		"billing_period": billing_period,
	}


@frappe.whitelist()
def trigger_monthly_billing_service(billing_period: str | None = None, store: str | None = None):
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
def get_billing_list(
	status: str | None = None,
	billing_type: str | None = None,
	store: str | None = None,
	billing_period: str | None = None,
	limit_page_length: int = 20,
	limit_start: int = 0,
	order_by: str = "modified desc",
):
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

	billings = frappe.get_all(
		"BEI Billing Schedule",
		filters=filters,
		fields=[
			"name",
			"billing_type",
			"billing_period",
			"store",
			"store_type",
			"status",
			"total_amount",
			"amount_paid",
			"balance_due",
			"generated_on",
			"sent_on",
			"paid_on",
		],
		order_by=order_by,
		limit_page_length=int(limit_page_length),
		limit_start=int(limit_start),
	)
	return _normalize_store_type_records(billings)


@frappe.whitelist()
def get_billing_detail(name: str):
	"""Get full billing details including line items and payment info."""
	billing = frappe.get_doc("BEI Billing Schedule", name)
	return {
		"name": billing.name,
		"billing_type": billing.billing_type,
		"billing_period": billing.billing_period,
		"store": billing.store,
		"store_type": _normalized_store_type(billing.store_type),
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
			{"fee_type": li.fee_type, "description": li.description, "rate": li.rate, "amount": li.amount}
			for li in (billing.line_items or [])
		],
	}


@frappe.whitelist()
def get_billing_summary(billing_period: str | None = None, store: str | None = None):
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
		" WHERE " + where + " GROUP BY status",
		params,
		as_dict=True,
	)

	totals = frappe.db.sql(
		"SELECT"
		" COUNT(*) as total_billings,"
		" COALESCE(SUM(total_amount), 0) as grand_total,"
		" COALESCE(SUM(amount_paid), 0) as total_collected,"
		" COALESCE(SUM(balance_due), 0) as total_outstanding"
		" FROM `tabBEI Billing Schedule`"
		" WHERE " + where,
		params,
		as_dict=True,
	)[0]

	return {
		"by_status": summary,
		"totals": totals,
		"billing_period": billing_period,
		"store": store,
	}


@frappe.whitelist()
def record_payment(
	name: str,
	amount: Any,
	payment_reference: str | None = None,
	payment_proof: str | None = None,
):
	"""Record a payment against a billing."""
	if not amount or flt(amount) <= 0:
		frappe.throw(_("Payment amount must be greater than zero"), frappe.ValidationError)

	billing = frappe.get_doc("BEI Billing Schedule", name)
	if billing.status not in ("Sent", "Approved"):
		frappe.throw(_("Payments can only be recorded for Sent or Approved billings"))

	new_paid = flt(billing.amount_paid) + flt(amount)
	if new_paid > flt(billing.total_amount):
		frappe.throw(
			_("Payment of {0} would exceed total amount of {1}").format(
				frappe.format_value(flt(amount), "Currency"),
				frappe.format_value(billing.total_amount, "Currency"),
			)
		)

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
def get_soa(name: str):
	"""Generate Statement of Account for a billing."""
	billing = frappe.get_doc("BEI Billing Schedule", name)

	return {
		"billing_name": billing.name,
		"store": billing.store,
		"store_type": _normalized_store_type(billing.store_type),
		"billing_period": billing.billing_period,
		"billing_type": billing.billing_type,
		"status": billing.status,
		# Fee breakdown
		"line_items": [
			{"fee_type": li.fee_type, "description": li.description, "rate": li.rate, "amount": li.amount}
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
def cancel_billing(name: str, reason: str | None = None):
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

	S231 Pre-Phase-0: gated by `BEI Settings.bki_billing_cron_enabled`.
	Default 0 = cron is no-op. Finance flips to 1 only after ratifying
	dry-run output. Protects 2026-06-01 firing while remaining S231 work
	(BEI Billing Schedule DocType migration, VAT template wiring, fee
	schedule seeding) lands in subsequent PRs.
	"""
	from frappe.utils import add_months, getdate
	from frappe.utils import today as frappe_today

	if not frappe.db.get_single_value("BEI Settings", "bki_billing_cron_enabled"):
		return

	prev_month = add_months(frappe_today(), -1)
	billing_period = getdate(prev_month).strftime("%Y-%m")

	result = generate_monthly_billing(billing_period=billing_period)

	frappe.log_error(
		f"Monthly billing generated for {billing_period}: "
		f"{result.get('generated', 0)} created, {result.get('skipped', 0)} skipped, "
		f"{len(result.get('errors', []))} errors",
		"Scheduled Monthly Billing",
	)


# ================================
# PHASE 4B — 3PL BILLING RECONCILIATION
# ================================
# Partners: RCS, 3MD/COOLITZ, PINNACLE
# Billing is per-trip flat rate (NOT per-km or per-kg)
# BIR RR 2-98: 2% EWT on hauling/freight services

# GL accounts for 3PL logistics costs and payment
# DM-1: party_type/party ONLY on AP row (2101101), NEVER on EWT Payable (2102202)
GL_LOGISTICS_COMMISSARY = "6003001"  # Logistics Cost - Commissary
GL_LOGISTICS_PCF = "6003002"  # Logistics Cost - PCF
GL_LOGISTICS_WAREHOUSE = "6003003"  # Logistics Cost - Warehouse


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
		"RCS": GL_LOGISTICS_COMMISSARY,
		"3MD": GL_LOGISTICS_COMMISSARY,
		"COOLITZ": GL_LOGISTICS_PCF,
		"PINNACLE": GL_LOGISTICS_WAREHOUSE,
	}
	return mapping.get(partner, GL_LOGISTICS_COMMISSARY)


@frappe.whitelist()
def get_3pl_rates(partner: str | None = None, cargo_type: str | None = None):
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

	# where_clause is assembled from fixed query fragments; all user values are bound via `params`.
	rates = frappe.db.sql(  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-sql-format-injection
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
		as_dict=True,
	)

	# Contract hardening for portal billing pages:
	# always include EWT fields even if legacy rows/migrations omit them.
	for rate in rates:
		rate["ewt_atc"] = rate.get("ewt_atc") or "WC110"
		rate["ewt_rate"] = flt(rate.get("ewt_rate") or 1.0)

	return {"rates": rates, "count": len(rates)}


@frappe.whitelist()
def generate_3pl_reconciliation(month: int | str, year: int | str, partner: str):
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
	normalized_partner = _normalize_3pl_partner_label(partner)

	# Fetch all 3PL-tagged trips for the month, then collapse partner aliases in
	# Python so the portal's canonical keys still resolve legacy/live labels.
	trips_all = frappe.db.sql(
		_get_3pl_trip_query(),
		{"start_date": start_date, "end_date": end_date},
		as_dict=True,
	)
	trips_raw = [
		trip for trip in trips_all if _normalize_3pl_partner_label(trip.get("partner")) == normalized_partner
	]

	# Fetch all applicable rates for the period, then normalize partner aliases in
	# Python because live operational labels do not always match the portal keys.
	rates_all = frappe.db.sql(
		"""
        SELECT name, threepl_partner, cargo_type, zone, rate_per_trip, overtime_rate, surcharge_rate,
               COALESCE(ewt_atc, 'WC110') AS ewt_atc,
               COALESCE(ewt_rate, 1.0) AS ewt_rate
        FROM `tabBEI 3PL Rate`
        WHERE effective_from <= %(end_date)s
          AND (effective_to IS NULL OR effective_to = '' OR effective_to >= %(start_date)s)
        ORDER BY effective_from DESC
        """,
		{"start_date": start_date, "end_date": end_date},
		as_dict=True,
	)
	rates = [
		rate
		for rate in rates_all
		if _normalize_3pl_partner_label(rate.get("threepl_partner")) == normalized_partner
	]

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
			discrepancies.append(
				{
					"trip_name": trip.trip_name,
					"date": str(trip.date),
					"reason": f"No matching rate for partner={partner}, zone={zone}, cargo_type={cargo}",
					"amount": 0,
				}
			)
			trip_lines.append(
				{
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
					"has_discrepancy": True,
				}
			)
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

		trip_lines.append(
			{
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
				"has_discrepancy": False,
			}
		)

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
		"discrepancies": discrepancies,
	}


@frappe.whitelist()
def create_3pl_payment_request(month: int | str, year: int | str, partner: str, invoice_amount: Any):
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
		as_dict=True,
	)
	ewt_atc = (rate_doc[0].get("ewt_atc") or "WC110") if rate_doc else "WC110"
	ewt_rate_pct = flt(rate_doc[0].get("ewt_rate") or 1.0) if rate_doc else 1.0

	# Validate EWT rate is within sane range (0.5% to 15%)
	if ewt_rate_pct < 0.5 or ewt_rate_pct > 15:
		frappe.throw(
			_("EWT rate {0}% is outside valid range (0.5-15%). Check BEI 3PL Rate record.").format(
				ewt_rate_pct
			)
		)

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
		je.append(
			"accounts",
			{
				"account": gl_debit_account,
				"debit_in_account_currency": gross,
				"credit_in_account_currency": 0,
				"user_remark": remarks,
			},
		)

		# CR: Accounts Payable - Trade (net payment) — DM-1: party ONLY on AP row
		je.append(
			"accounts",
			{
				"account": "2101101 - ACCOUNTS PAYABLE - TRADE - BEI",
				"debit_in_account_currency": 0,
				"credit_in_account_currency": net_payable,
				"party_type": "Supplier",
				"party": partner,
				"user_remark": f"Net payable after EWT {ewt_atc} {ewt_rate_pct}% - {remarks}",
			},
		)

		# CR: EWT Payable (ATC per rate record) — DM-1: NO party on EWT row
		je.append(
			"accounts",
			{
				"account": "2102202 - EWT PAYABLE - BEI",
				"debit_in_account_currency": 0,
				"credit_in_account_currency": ewt_amount,
				"user_remark": f"EWT {ewt_atc} {ewt_rate_pct}% - {remarks}",
			},
		)

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
			],
		}

	except Exception as e:
		frappe.db.rollback(save_point=sp_name)
		frappe.log_error(frappe.get_traceback(), "3PL Payment Request Creation Failed")
		frappe.throw(_("Failed to create payment request: {0}").format(str(e)))


@frappe.whitelist()
def get_reconciliation_summary(month: int | str, year: int | str):
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
		_get_3pl_trip_count_query(),
		[start_date, end_date],
		as_dict=True,
	)
	trip_counts = {}
	for row in trip_count_rows:
		canonical_partner = _normalize_3pl_partner_label(row.get("partner"))
		if not canonical_partner:
			continue
		trip_counts[canonical_partner] = trip_counts.get(canonical_partner, 0) + row.get("cnt", 0)

	# Batch JE lookups for all partners in a single query (avoids N+1)
	je_cheque_nos = [f"3PL-{p}-{period_label}" for p in partners]
	placeholders = ", ".join(["%s"] * len(je_cheque_nos))
	je_rows = frappe.db.sql(
		"SELECT cheque_no, total_debit FROM `tabJournal Entry`"
		" WHERE cheque_no IN (" + placeholders + ") AND docstatus != 2",  # conditions are string constants
		je_cheque_nos,
		as_dict=True,
	)
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

		summary.append(
			{
				"partner": partner,
				"period": period_label,
				"trip_count": trip_count,
				"expected_cost": round(expected_cost, 2),
				"invoice_amount": round(invoice_amount, 2),
				"variance": round(variance, 2),
				"variance_pct": variance_pct,
				"discrepancy_count": len(recon.get("discrepancies") or []),
			}
		)

	return {
		"month": month,
		"year": year,
		"period": period_label,
		"partners": summary,
		"total_expected": round(sum(r["expected_cost"] for r in summary), 2),
		"total_invoiced": round(sum(r["invoice_amount"] for r in summary), 2),
	}


@frappe.whitelist()
def flag_discrepancy(trip_name: str, reason: str, amount: Any):
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
			{"billing_discrepancy": 1, "discrepancy_reason": reason, "discrepancy_amount": amount},
		)
	except Exception as e:
		frappe.log_error(
			f"Could not update discrepancy fields on {trip_name}: {e}", "3PL Billing Discrepancy"
		)

	return {
		"success": True,
		"trip_name": trip_name,
		"reason": reason,
		"amount": amount,
		"flagged_by": frappe.session.user,
		"comment_name": comment.name,
	}
