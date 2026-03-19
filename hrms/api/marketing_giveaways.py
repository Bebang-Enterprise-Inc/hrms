from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

import requests

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from hrms.utils.bei_config import get_company
from hrms.utils.sales_location_mapping import load_sales_location_mapping
from hrms.utils.sentry import capture_backend_message, set_backend_observability_context
from hrms.utils.supply_chain_contracts import resolve_warehouse_company

MANILA_TZ = ZoneInfo("Asia/Manila")
FEATURE_FLAG_KEY = "marketing_giveaways_enabled"
CAMPAIGN_DT = "BEI Campaign Giveaway"
ISSUE_DT = "BEI Campaign Giveaway Issue"
EXCEPTION_DT = "BEI Campaign Giveaway Exception"
POLICY_VERSION = "S075-2026-03-18"
DEFAULT_EXPENSE_ACCOUNT_NUMBER = "6005001"
DEFAULT_EXPENSE_ACCOUNT_NAME = "MARKETING GIVEAWAYS"
FINISHED_GOODS_ITEM_GROUPS = {"Finished Goods"}
LEAKAGE_LOOKBACK_DAYS = 16
LEAKAGE_CANDIDATE_ORDER_LIMIT = 600
APPROVED_STATES = {"Approved / Active", "Partially Fulfilled"}
OPS_REVIEW_ROLES = {"Area Supervisor", "Supply Chain Manager", "HQ User", "System Manager", "Administrator"}
FINANCE_REVIEW_ROLES = {"HQ Finance", "Accounts Manager", "HQ User", "System Manager", "Administrator"}
REQUEST_ROLES = {"Marketing User", "Marketing Manager", "HQ User", "System Manager", "Administrator"}
FULFILLMENT_ROLES = {"Store Supervisor", "Area Supervisor", "Supply Chain Manager", "System Manager", "Administrator"}
EXCEPTION_ROLES = {
	"HQ Finance",
	"Accounts Manager",
	"HQ User",
	"Area Supervisor",
	"Supply Chain Manager",
	"System Manager",
	"Administrator",
}
DASHBOARD_ROLES = REQUEST_ROLES | FULFILLMENT_ROLES | EXCEPTION_ROLES
RECONCILIATION_ROLES = {"HQ Finance", "Accounts Manager", "HQ User", "System Manager", "Administrator"}
ADMIN_OVERRIDE_ROLES = {"System Manager", "Administrator"}
STATUS_FLOW = {
	"Draft": {"Pending Ops Review", "Cancelled"},
	"Pending Ops Review": {"Pending Finance Approval", "Rejected", "Cancelled"},
	"Pending Finance Approval": {"Approved / Active", "Rejected", "Cancelled"},
	"Approved / Active": {"Partially Fulfilled", "Fully Fulfilled", "Expired"},
	"Partially Fulfilled": {"Fully Fulfilled", "Expired"},
}


def _conf_get(key: str, default: Any = None) -> Any:
	conf = getattr(frappe, "conf", {}) or {}
	if hasattr(conf, "get"):
		return conf.get(key, default)
	return default


def _permission_error_class():
	return getattr(frappe, "PermissionError", Exception)


def _require_enabled() -> None:
	raw_value = os.environ.get(FEATURE_FLAG_KEY.upper()) or _conf_get(FEATURE_FLAG_KEY, "1")
	if str(raw_value).strip().lower() in {"0", "false", "off", "no"}:
		frappe.throw(_("Campaign Giveaways is currently disabled."), _permission_error_class())


def _roles() -> set[str]:
	return set(frappe.get_roles() or [])


def _require_roles(allowed_roles: set[str], message: str) -> set[str]:
	roles = _roles()
	if not roles.intersection(allowed_roles):
		frappe.throw(_(message), _permission_error_class())
	return roles


def _observe(
	action: str,
	*,
	phase: str,
	mutation_type: str,
	extras: dict[str, Any] | None = None,
) -> None:
	set_backend_observability_context(
		module="campaign_giveaways",
		action=action,
		route_action=action,
		mutation_type=mutation_type,
		endpoint_or_job=f"hrms.api.marketing_giveaways.{action}",
		phase=phase,
		extras=extras,
	)


def _capture(
	action: str,
	message: str,
	*,
	level: str = "warning",
	phase: str,
	mutation_type: str,
	extras: dict[str, Any] | None = None,
) -> None:
	capture_backend_message(
		message,
		level=level,
		module="campaign_giveaways",
		action=action,
		route_action=action,
		mutation_type=mutation_type,
		endpoint_or_job=f"hrms.api.marketing_giveaways.{action}",
		phase=phase,
		extras=extras,
	)


def _safe_json(value: Any, default: Any):
	if value in (None, ""):
		return default
	if isinstance(value, (dict, list)):
		return value
	try:
		return json.loads(value)
	except Exception:
		return default


def _normalize_text(value: Any) -> str:
	return " ".join(str(value or "").strip().lower().split())


def _normalize_list(values: list[Any] | None) -> list[str]:
	normalized: list[str] = []
	for value in values or []:
		candidate = str(value or "").strip()
		if candidate and candidate not in normalized:
			normalized.append(candidate)
	return normalized


def _finished_goods_item(item_code: str) -> dict[str, Any]:
	item = frappe.db.get_value(
		"Item",
		item_code,
		["name", "item_name", "stock_uom", "valuation_rate", "item_group", "is_stock_item", "disabled"],
		as_dict=True,
	)
	if not item:
		frappe.throw(_("Item {0} does not exist.").format(item_code))

	item_group = str(item.get("item_group") or "").strip()
	is_finished_goods = item_group in FINISHED_GOODS_ITEM_GROUPS or str(item.get("name") or "").upper().startswith("FG")
	if cint(item.get("disabled") or 0):
		frappe.throw(_("Item {0} is disabled.").format(item_code))
	if not cint(item.get("is_stock_item") or 0):
		frappe.throw(_("Item {0} is not a stock item.").format(item_code))
	if not is_finished_goods:
		frappe.throw(_("Item {0} is not an approved finished-goods SKU.").format(item_code))
	return item


def _require_master_record(
	doctype: str,
	value: str | None,
	label: str,
	*,
	filters: dict[str, Any] | None = None,
	allow_blank: bool = False,
) -> str:
	candidate = str(value or "").strip()
	if not candidate:
		if allow_blank:
			return ""
		frappe.throw(_("{0} is required.").format(label))

	query_filters = {"name": candidate}
	if filters:
		query_filters.update(filters)
	if not frappe.db.exists(doctype, query_filters):
		frappe.throw(_("{0} is not a valid {1}.").format(candidate, label))
	return candidate


def _source_supports_item(source_location: str, item_code: str) -> bool:
	return bool(frappe.db.exists("Bin", {"warehouse": source_location, "item_code": item_code}))


def _require_request_owner(campaign_doc, action: str) -> None:
	if _roles().intersection(ADMIN_OVERRIDE_ROLES):
		return
	requester = str(campaign_doc.requester_user or "").strip()
	if requester and requester != frappe.session.user:
		_capture(
			action,
			f"Requester ownership mismatch for campaign {campaign_doc.name}",
			phase="authorization",
			mutation_type="mutation",
			extras={"campaign": campaign_doc.name, "requester_user": requester},
		)
		frappe.throw(_("Only the original requester can perform this action."), _permission_error_class())


def _require_assigned_reviewer(campaign_doc, action: str) -> None:
	if _roles().intersection(ADMIN_OVERRIDE_ROLES):
		return
	queue_name = str(campaign_doc.active_queue_name or "").strip()
	if not queue_name or not frappe.db.exists("BEI Approval Queue", queue_name):
		return
	assigned_approver = str(frappe.db.get_value("BEI Approval Queue", queue_name, "assigned_approver") or "").strip()
	if assigned_approver and assigned_approver != frappe.session.user:
		_capture(
			action,
			f"Assigned reviewer mismatch for queue {queue_name}",
			phase="authorization",
			mutation_type="mutation",
			extras={
				"campaign": campaign_doc.name,
				"queue_name": queue_name,
				"assigned_approver": assigned_approver,
			},
		)
		frappe.throw(_("This review step is assigned to another approver."), _permission_error_class())


def _validate_campaign_payload(payload: dict[str, Any], *, existing_name: str | None = None) -> dict[str, Any]:
	data = dict(payload or {})
	existing = None
	if existing_name:
		existing = _campaign_doc(existing_name)
		_require_request_owner(existing, "save_campaign_giveaway")

	data["requester_user"] = str(existing.requester_user if existing and existing.requester_user else frappe.session.user).strip()
	data["owning_department"] = _require_master_record("Department", data.get("owning_department") or "Marketing", "Department")
	data["budget_owner"] = _require_master_record(
		"User",
		data.get("budget_owner"),
		"Budget Owner",
		filters={"enabled": 1},
		allow_blank=True,
	)
	data["cost_center"] = _require_master_record(
		"Cost Center",
		data.get("cost_center"),
		"Cost Center",
		filters={"is_group": 0},
		allow_blank=True,
	)

	source_locations = _normalize_list(data.get("source_locations") or data.get("source_locations_json") or [])
	if not source_locations:
		frappe.throw(_("At least one approved source location is required."))
	for source_location in source_locations:
		_require_master_record("Warehouse", source_location, "Source Location", filters={"is_group": 0})
	data["source_locations"] = source_locations

	items_payload = data.get("items") or []
	if not isinstance(items_payload, list) or not items_payload:
		frappe.throw(_("At least one giveaway item is required."))

	normalized_items: list[dict[str, Any]] = []
	for raw_item in items_payload:
		if not isinstance(raw_item, dict):
			continue
		item_code = _require_master_record("Item", raw_item.get("item_code"), "Item")
		item_meta = _finished_goods_item(item_code)
		approved_quantity = flt(raw_item.get("approved_quantity") or 0, 3)
		if approved_quantity <= 0:
			frappe.throw(_("Approved quantity for {0} must be greater than 0.").format(item_code))
		if source_locations and not any(_source_supports_item(source_location, item_code) for source_location in source_locations):
			frappe.throw(_("Item {0} is not stocked in any approved source location.").format(item_code))
		normalized_items.append(
			{
				"item_code": item_code,
				"item_name": item_meta.get("item_name"),
				"uom": item_meta.get("stock_uom"),
				"approved_quantity": approved_quantity,
				"estimated_unit_cost": flt(item_meta.get("valuation_rate") or 0, 4),
			}
		)
	if not normalized_items:
		frappe.throw(_("At least one valid giveaway item is required."))
	data["items"] = normalized_items

	schedule_rows = data.get("schedule_rows") or data.get("schedule_json") or []
	normalized_schedule: list[dict[str, Any]] = []
	approved_item_codes = {row["item_code"] for row in normalized_items}
	approved_qty_by_item = {row["item_code"]: flt(row["approved_quantity"] or 0, 3) for row in normalized_items}
	start_date = getdate(data.get("start_date")) if data.get("start_date") else None
	end_date = getdate(data.get("end_date")) if data.get("end_date") else None
	for row in schedule_rows if isinstance(schedule_rows, list) else []:
		if not isinstance(row, dict):
			continue
		row_date = str(row.get("date") or row.get("issue_date") or "").strip()
		item_code = str(row.get("item_code") or "").strip()
		source_location = str(row.get("source_location") or row.get("warehouse") or "").strip()
		quantity = flt(row.get("quantity") or row.get("approved_quantity") or 0, 3)
		if not row_date or not item_code or not source_location or quantity <= 0:
			continue
		if item_code not in approved_item_codes:
			frappe.throw(_("Schedule row item {0} is not in the approved campaign item list.").format(item_code))
		if source_location not in source_locations:
			frappe.throw(_("Schedule row source {0} is not in the approved source list.").format(source_location))
		if start_date and end_date:
			schedule_day = getdate(row_date[:10])
			if schedule_day < start_date or schedule_day > end_date:
				frappe.throw(_("Schedule row {0} is outside the campaign window.").format(row_date[:10]))
		normalized_schedule.append(
			{
				"date": row_date[:10],
				"item_code": item_code,
				"source_location": source_location,
				"quantity": quantity,
			}
		)
	if normalized_schedule:
		scheduled_qty_by_item: dict[str, float] = {}
		for row in normalized_schedule:
			item_code = row["item_code"]
			scheduled_qty_by_item[item_code] = scheduled_qty_by_item.get(item_code, 0.0) + flt(row["quantity"] or 0, 3)
		for item_code, scheduled_qty in scheduled_qty_by_item.items():
			if scheduled_qty > flt(approved_qty_by_item.get(item_code) or 0, 3):
				frappe.throw(_("Scheduled quantity for {0} exceeds the approved quantity.").format(item_code))
	data["schedule_rows"] = normalized_schedule
	return data


def _manila_today() -> date:
	return datetime.now(timezone.utc).astimezone(MANILA_TZ).date()


def _campaign_doc(name: str):
	return frappe.get_doc(CAMPAIGN_DT, name)


def _issue_doc(name: str):
	return frappe.get_doc(ISSUE_DT, name)


def _approved_sources(campaign) -> list[str]:
	if hasattr(campaign, "approved_sources"):
		return campaign.approved_sources()
	payload = _safe_json(campaign.source_locations_json, [])
	result: list[str] = []
	for entry in payload if isinstance(payload, list) else []:
		candidate = (
			str(entry.get("warehouse") or entry.get("source_location") or "").strip()
			if isinstance(entry, dict)
			else str(entry or "").strip()
		)
		if candidate and candidate not in result:
			result.append(candidate)
	return result


def _schedule_rows(campaign) -> list[dict[str, Any]]:
	if hasattr(campaign, "fulfillment_schedule"):
		return campaign.fulfillment_schedule()
	payload = _safe_json(campaign.schedule_json, [])
	return [row for row in payload if isinstance(row, dict)]


def _find_item_row(campaign, item_code: str):
	for row in campaign.items or []:
		if row.item_code == item_code:
			return row
	return None


def _ensure_transition(current: str, target: str) -> None:
	allowed = STATUS_FLOW.get(current, set())
	if target not in allowed:
		frappe.throw(_("Invalid state transition: {0} → {1}").format(current, target))


def _resolve_marketing_expense_account(company: str | None = None) -> str:
	company_name = company or get_company()
	account = frappe.db.get_value(
		"Account",
		{"company": company_name, "account_number": DEFAULT_EXPENSE_ACCOUNT_NUMBER, "is_group": 0},
		"name",
	)
	if account:
		return account
	like_name = f"{DEFAULT_EXPENSE_ACCOUNT_NUMBER} - {DEFAULT_EXPENSE_ACCOUNT_NAME}%"
	return frappe.db.get_value(
		"Account",
		{"company": company_name, "name": ["like", like_name], "is_group": 0},
		"name",
	) or f"{DEFAULT_EXPENSE_ACCOUNT_NUMBER} - {DEFAULT_EXPENSE_ACCOUNT_NAME} - {company_name}"


def _resolve_item_cost(item_code: str) -> float:
	valuation_rate = frappe.db.get_value("Item", item_code, "valuation_rate")
	return flt(valuation_rate or 0, 4)


def _resolve_available_qty(source_location: str, item_code: str) -> float:
	return flt(
		frappe.db.get_value("Bin", {"warehouse": source_location, "item_code": item_code}, "actual_qty") or 0,
		3,
	)


def _sum_issued_quantity(campaign: str, issue_date: str, item_code: str | None = None) -> float:
	filters: dict[str, Any] = {"campaign": campaign, "issue_date": issue_date, "status": ["!=", "Cancelled"]}
	if item_code:
		filters["item_code"] = item_code
	rows = frappe.get_all(ISSUE_DT, filters=filters, fields=["quantity"], limit_page_length=500)
	return sum(flt(row.get("quantity") or 0, 3) for row in rows)


def _scheduled_day_cap(campaign, issue_day: date, item_code: str, source_location: str) -> float | None:
	rows = _schedule_rows(campaign)
	if not rows:
		return None
	total = 0.0
	for row in rows:
		row_date = str(row.get("date") or row.get("issue_date") or "")[:10]
		if row_date != issue_day.isoformat():
			continue
		row_item_code = str(row.get("item_code") or "").strip()
		row_source = str(row.get("source_location") or row.get("warehouse") or "").strip()
		if row_item_code and row_item_code != item_code:
			continue
		if row_source and row_source != source_location:
			continue
		total += flt(row.get("quantity") or row.get("approved_quantity") or 0, 3)
	return round(total, 3) if total > 0 else None


def _update_campaign_tracking(campaign) -> float:
	issues = frappe.get_all(
		ISSUE_DT,
		filters={"campaign": campaign.name, "status": ["in", ["Posted", "Exception"]]},
		fields=["name", "issue_date", "item_code", "quantity", "actual_total_cost"],
		limit_page_length=1000,
	)
	served_map: dict[str, float] = {}
	total_value = 0.0
	latest_issue_date = ""
	for issue in issues:
		item_code = str(issue.get("item_code") or "").strip()
		served_map[item_code] = served_map.get(item_code, 0.0) + flt(issue.get("quantity") or 0, 3)
		total_value += flt(issue.get("actual_total_cost") or 0, 2)
		issue_date = str(issue.get("issue_date") or "")
		if issue_date and issue_date > latest_issue_date:
			latest_issue_date = issue_date

	for row in campaign.items or []:
		row.served_quantity = round(served_map.get(row.item_code, 0.0), 3)
		row.remaining_quantity = max(round(flt(row.approved_quantity or 0, 3) - row.served_quantity, 3), 0.0)

	campaign.latest_issue_date = latest_issue_date or None
	campaign.quantity_served = round(sum(served_map.values()), 3)
	campaign.remaining_quantity = max(
		round(campaign.total_approved_quantity - campaign.quantity_served, 3),
		0.0,
	)
	if campaign.status in APPROVED_STATES:
		if campaign.remaining_quantity <= 0:
			campaign.status = "Fully Fulfilled"
		elif campaign.quantity_served > 0:
			campaign.status = "Partially Fulfilled"
		elif getdate(campaign.end_date) < _manila_today():
			campaign.status = "Expired"
	campaign.workflow_state = campaign.status
	if getdate(campaign.end_date) >= _manila_today():
		campaign.remaining_days = max((getdate(campaign.end_date) - _manila_today()).days + 1, 0)
	else:
		campaign.remaining_days = 0
	campaign.required_daily_pace = (
		round(campaign.remaining_quantity / campaign.remaining_days, 3)
		if campaign.remaining_days > 0
		else 0
	)
	return max(round(flt(campaign.estimated_peso_value or 0, 2) - total_value, 2), 0.0)


def _serialize_campaign_row(campaign) -> dict[str, Any]:
	remaining_value = max(
		round(
			flt(campaign.estimated_peso_value or 0, 2)
			- sum(
				flt(row.get("actual_total_cost") or 0, 2)
				for row in frappe.get_all(
					ISSUE_DT,
					filters={"campaign": campaign.name, "status": "Posted"},
					fields=["actual_total_cost"],
					limit_page_length=1000,
				)
			),
			2,
		),
		0.0,
	)
	return {
		"name": campaign.name,
		"campaign_name": campaign.campaign_name,
		"campaign_code": campaign.campaign_code,
		"status": campaign.status,
		"workflow_state": campaign.workflow_state,
		"requester_user": campaign.requester_user,
		"owning_department": campaign.owning_department,
		"request_date": str(campaign.request_date or ""),
		"purpose_event": campaign.purpose_event,
		"start_date": str(campaign.start_date or ""),
		"end_date": str(campaign.end_date or ""),
		"daily_cap_quantity": flt(campaign.daily_cap_quantity or 0, 3),
		"budget_owner": campaign.budget_owner,
		"cost_center": campaign.cost_center,
		"approved_value_tolerance_pct": flt(campaign.approved_value_tolerance_pct or 0, 2),
		"finance_expense_account": campaign.finance_expense_account,
		"policy_version": campaign.policy_version,
		"estimated_peso_value": flt(campaign.estimated_peso_value or 0, 2),
		"total_approved_quantity": flt(campaign.total_approved_quantity or 0, 3),
		"quantity_served": flt(campaign.quantity_served or 0, 3),
		"remaining_quantity": flt(campaign.remaining_quantity or 0, 3),
		"remaining_days": cint(campaign.remaining_days or 0),
		"required_daily_pace": flt(campaign.required_daily_pace or 0, 3),
		"remaining_value": remaining_value,
		"latest_issue_date": str(campaign.latest_issue_date or ""),
		"active_queue_name": campaign.active_queue_name,
		"ops_reviewed_by": campaign.ops_reviewed_by,
		"ops_reviewed_at": str(campaign.ops_reviewed_at or ""),
		"ops_review_notes": campaign.ops_review_notes,
		"finance_reviewed_by": campaign.finance_reviewed_by,
		"finance_reviewed_at": str(campaign.finance_reviewed_at or ""),
		"finance_review_notes": campaign.finance_review_notes,
		"rejection_reason": campaign.rejection_reason,
		"cancel_reason": campaign.cancel_reason,
		"source_locations": _approved_sources(campaign),
		"schedule_rows": _schedule_rows(campaign),
		"items": [
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"uom": row.uom,
				"approved_quantity": flt(row.approved_quantity or 0, 3),
				"served_quantity": flt(row.served_quantity or 0, 3),
				"remaining_quantity": flt(row.remaining_quantity or 0, 3),
				"estimated_unit_cost": flt(row.estimated_unit_cost or 0, 4),
				"estimated_total_cost": flt(row.estimated_total_cost or 0, 2),
			}
			for row in campaign.items or []
		],
	}


def _serialize_issue_row(row: dict[str, Any]) -> dict[str, Any]:
	row = dict(row or {})
	row["quantity"] = flt(row.get("quantity") or 0, 3)
	row["actual_unit_cost"] = flt(row.get("actual_unit_cost") or 0, 4)
	row["actual_total_cost"] = flt(row.get("actual_total_cost") or 0, 2)
	return row


def _serialize_exception_row(row: dict[str, Any]) -> dict[str, Any]:
	row = dict(row or {})
	row["requested_quantity"] = flt(row.get("requested_quantity") or 0, 3)
	row["attempted_value"] = flt(row.get("attempted_value") or 0, 2)
	row["linked_alert_payload"] = _safe_json(row.get("linked_alert_payload_json"), [])
	return row


def _campaign_filters(status: str | None = None) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	if status:
		filters["status"] = status
	return filters


def _exception_doc(payload: dict[str, Any]):
	doc = frappe.new_doc(EXCEPTION_DT)
	for key, value in payload.items():
		if key == "doctype":
			continue
		if hasattr(doc, key):
			setattr(doc, key, value)
	doc.insert(ignore_permissions=True)
	return doc


def _create_exception(
	*,
	campaign: str,
	exception_type: str,
	message: str,
	campaign_issue: str | None = None,
	source_location: str | None = None,
	item_code: str | None = None,
	issue_date: str | None = None,
	requested_quantity: float | None = None,
	attempted_value: float | None = None,
	linked_alert_reference: str | None = None,
	linked_alert_payload_json: Any = None,
	status: str = "Open",
	severity: str = "High",
) -> str:
	doc = _exception_doc(
		{
			"campaign": campaign,
			"campaign_issue": campaign_issue,
			"status": status,
			"severity": severity,
			"exception_type": exception_type,
			"source_location": source_location,
			"item_code": item_code,
			"issue_date": issue_date,
			"requested_quantity": requested_quantity,
			"attempted_value": attempted_value,
			"message": message,
			"linked_alert_reference": linked_alert_reference,
			"linked_alert_payload_json": json.dumps(linked_alert_payload_json or []),
		}
	)
	return doc.name


def _queue_assignee_for_roles(candidate_roles: set[str]) -> str | None:
	role_rows = frappe.get_all(
		"Has Role",
		filters={"role": ["in", sorted(candidate_roles)]},
		fields=["parent"],
		limit_page_length=500,
	)
	candidates = sorted({str(row.get("parent") or "").strip() for row in role_rows if row.get("parent")})
	if not candidates:
		return None
	enabled_rows = frappe.get_all(
		"User",
		filters={"name": ["in", candidates], "enabled": 1},
		fields=["name"],
		limit_page_length=max(50, len(candidates)),
	)
	enabled = {str(row.get("name") or "").strip() for row in enabled_rows if row.get("name")}
	for candidate in candidates:
		if candidate in enabled:
			return candidate
	return None


def _close_queue(queue_name: str | None, status: str, rejection_reason: str | None = None) -> None:
	if not queue_name or not frappe.db.exists("BEI Approval Queue", queue_name):
		return
	queue_doc = frappe.get_doc("BEI Approval Queue", queue_name)
	queue_doc.status = status
	queue_doc.approved_by = frappe.session.user
	queue_doc.approved_at = now_datetime()
	if rejection_reason:
		queue_doc.rejection_reason = rejection_reason
	queue_doc.save(ignore_permissions=True)


def _open_queue(campaign, assigned_approver: str | None, priority: str = "Normal") -> str | None:
	approved_sources = _approved_sources(campaign)
	if not assigned_approver or not approved_sources:
		return None
	queue_entry = frappe.new_doc("BEI Approval Queue")
	queue_entry.reference_doctype = CAMPAIGN_DT
	queue_entry.reference_name = campaign.name
	queue_entry.assigned_approver = assigned_approver
	queue_entry.status = "Pending"
	queue_entry.priority = priority
	queue_entry.store = approved_sources[0]
	queue_entry.submitted_by = campaign.requester_user or frappe.session.user
	queue_entry.submitted_at = now_datetime()
	queue_entry.insert(ignore_permissions=True)
	return queue_entry.name


def _create_or_update_campaign(payload: dict[str, Any], *, existing_name: str | None = None):
	doc = _campaign_doc(existing_name) if existing_name else frappe.new_doc(CAMPAIGN_DT)
	for fieldname in (
		"campaign_name",
		"campaign_code",
		"purpose_event",
		"request_date",
		"start_date",
		"end_date",
		"daily_cap_quantity",
		"budget_owner",
		"cost_center",
		"approved_value_tolerance_pct",
		"owning_department",
		"ops_review_notes",
		"finance_review_notes",
		):
		if fieldname in payload:
			setattr(doc, fieldname, payload.get(fieldname))
	doc.requester_user = str(payload.get("requester_user") or doc.requester_user or frappe.session.user).strip()
	doc.source_locations_json = json.dumps(payload.get("source_locations") or payload.get("source_locations_json") or [])
	doc.schedule_json = json.dumps(payload.get("schedule_rows") or payload.get("schedule_json") or [])
	doc.supporting_attachments_json = json.dumps(
		payload.get("supporting_attachments") or payload.get("supporting_attachments_json") or []
	)
	items = payload.get("items") or []
	doc.set("items", [])
	for item in items:
		doc.append(
			"items",
			{
				"item_code": item.get("item_code"),
				"item_name": item.get("item_name"),
				"uom": item.get("uom"),
				"approved_quantity": item.get("approved_quantity"),
				"estimated_unit_cost": item.get("estimated_unit_cost") or _resolve_item_cost(item.get("item_code")),
			},
		)
	doc.save(ignore_permissions=True)
	return doc


@contextmanager
def _run_as_system_user(user: str = "Administrator"):
	session = getattr(frappe, "session", None)
	if session is None:
		session = getattr(getattr(frappe, "local", None), "session", None)
	original_user = getattr(session, "user", None)
	try:
		if session and user:
			session.user = user
		yield
	finally:
		if session and original_user:
			session.user = original_user


def _current_time_string() -> str:
	return now_datetime().strftime("%H:%M:%S")


def _post_stock_entry_for_issue(campaign, issue_doc) -> str:
	source_company = resolve_warehouse_company(issue_doc.source_location) or get_company()
	expense_account = campaign.finance_expense_account or _resolve_marketing_expense_account(source_company)
	item_meta = frappe.db.get_value(
		"Item",
		issue_doc.item_code,
		["item_name", "description", "stock_uom"],
		as_dict=True,
	) or {}
	stock_entry = frappe.new_doc("Stock Entry")
	stock_entry.stock_entry_type = "Material Issue"
	stock_entry.company = source_company
	stock_entry.posting_date = issue_doc.issue_date or nowdate()
	stock_entry.posting_time = _current_time_string()
	stock_entry.from_warehouse = issue_doc.source_location
	stock_entry.remarks = (
		f"Campaign Giveaway {campaign.campaign_code or campaign.name}"
		f" | {campaign.campaign_name}"
		f" | Issue {issue_doc.name}"
	)
	stock_entry.append(
		"items",
		{
			"item_code": issue_doc.item_code,
			"item_name": item_meta.get("item_name") or issue_doc.item_name,
			"description": item_meta.get("description") or issue_doc.item_name,
			"qty": issue_doc.quantity,
			"uom": item_meta.get("stock_uom") or issue_doc.uom,
			"stock_uom": item_meta.get("stock_uom") or issue_doc.uom,
			"conversion_factor": 1,
			"s_warehouse": issue_doc.source_location,
			"basic_rate": issue_doc.actual_unit_cost,
			"expense_account": expense_account,
			"cost_center": campaign.cost_center,
		},
	)
	with _run_as_system_user():
		stock_entry.insert(ignore_permissions=True)
		stock_entry.flags.ignore_permissions = True
		stock_entry.submit()
	return stock_entry.name


def _validate_issue_request(campaign, source_location: str, item_code: str, quantity: float, issue_day: date) -> tuple[Any, float]:
	if campaign.status not in APPROVED_STATES:
		frappe.throw(_("Only approved or active campaigns can issue stock."))
	_finished_goods_item(item_code)
	if issue_day < getdate(campaign.start_date) or issue_day > getdate(campaign.end_date):
		exception_name = _create_exception(
			campaign=campaign.name,
			exception_type="Outside Campaign Window",
			message="Issue date is outside the approved campaign window.",
			source_location=source_location,
			item_code=item_code,
			issue_date=issue_day.isoformat(),
			requested_quantity=quantity,
		)
		frappe.throw(_("Issue blocked: outside campaign window ({0}).").format(exception_name))
	if source_location not in _approved_sources(campaign):
		exception_name = _create_exception(
			campaign=campaign.name,
			exception_type="Source Not Approved",
			message="Source location is not in the approved campaign source list.",
			source_location=source_location,
			item_code=item_code,
			issue_date=issue_day.isoformat(),
			requested_quantity=quantity,
		)
		frappe.throw(_("Issue blocked: source not approved ({0}).").format(exception_name))
	item_row = _find_item_row(campaign, item_code)
	if not item_row:
		frappe.throw(_("Item is not approved for this campaign."))
	remaining_qty = flt(item_row.remaining_quantity or item_row.approved_quantity or 0, 3)
	if quantity > remaining_qty:
		exception_name = _create_exception(
			campaign=campaign.name,
			exception_type="Quantity Overrun",
			message="Requested quantity exceeds remaining campaign balance.",
			source_location=source_location,
			item_code=item_code,
			issue_date=issue_day.isoformat(),
			requested_quantity=quantity,
		)
		frappe.throw(_("Issue blocked: quantity exceeds remaining balance ({0}).").format(exception_name))
	day_cap = _scheduled_day_cap(campaign, issue_day, item_code, source_location)
	if day_cap is None and flt(campaign.daily_cap_quantity or 0, 3) > 0:
		day_cap = flt(campaign.daily_cap_quantity or 0, 3)
	if day_cap is not None:
		already_issued = _sum_issued_quantity(campaign.name, issue_day.isoformat(), item_code)
		if already_issued + quantity > day_cap:
			exception_name = _create_exception(
				campaign=campaign.name,
				exception_type="Daily Cap Exceeded",
				message="Requested quantity exceeds the approved daily cap.",
				source_location=source_location,
				item_code=item_code,
				issue_date=issue_day.isoformat(),
				requested_quantity=quantity,
			)
			frappe.throw(_("Issue blocked: daily cap exceeded ({0}).").format(exception_name))
	available_qty = _resolve_available_qty(source_location, item_code)
	if quantity > available_qty:
		exception_name = _create_exception(
			campaign=campaign.name,
			exception_type="Insufficient Stock",
			message="Requested quantity exceeds available stock.",
			source_location=source_location,
			item_code=item_code,
			issue_date=issue_day.isoformat(),
			requested_quantity=quantity,
		)
		frappe.throw(_("Issue blocked: insufficient stock ({0}).").format(exception_name))
	unit_cost = _resolve_item_cost(item_code) or flt(item_row.estimated_unit_cost or 0, 4)
	total_value_after = sum(
		flt(row.get("actual_total_cost") or 0, 2)
		for row in frappe.get_all(
			ISSUE_DT,
			filters={"campaign": campaign.name, "status": "Posted"},
			fields=["actual_total_cost"],
			limit_page_length=1000,
		)
	) + round(quantity * unit_cost, 2)
	allowed_ceiling = flt(campaign.estimated_peso_value or 0, 2) * (
		1 + (flt(campaign.approved_value_tolerance_pct or 0, 2) / 100)
	)
	if allowed_ceiling and total_value_after > round(allowed_ceiling, 2):
		exception_name = _create_exception(
			campaign=campaign.name,
			exception_type="Value Tolerance Breach",
			message="Requested issue would breach the approved value tolerance.",
			source_location=source_location,
			item_code=item_code,
			issue_date=issue_day.isoformat(),
			requested_quantity=quantity,
			attempted_value=round(quantity * unit_cost, 2),
		)
		frappe.throw(_("Issue blocked: value tolerance breached ({0}).").format(exception_name))
	return item_row, unit_cost


def _get_supabase_url() -> str:
	return (
		os.environ.get("SUPABASE_URL")
		or _conf_get("supabase_url")
		or "https://csnniykjrychgajfrgua.supabase.co"
	).rstrip("/")


def _get_supabase_service_key() -> str:
	return (
		os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
		or _conf_get("supabase_service_role_key")
		or _conf_get("supabase_service_role_key".upper())
		or ""
	)


def _supabase_headers() -> dict[str, str]:
	key = _get_supabase_service_key()
	if not key:
		raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured")
	return {
		"apikey": key,
		"Authorization": f"Bearer {key}",
		"Content-Type": "application/json",
	}


def _supabase_get(resource: str, params: list[tuple[str, Any]] | dict[str, Any] | None = None) -> list[dict[str, Any]]:
	response = requests.get(
		f"{_get_supabase_url()}/rest/v1/{resource}",
		headers=_supabase_headers(),
		params=params or {},
		timeout=30,
	)
	if not response.ok:
		raise RuntimeError(f"Supabase GET failed for {resource}: {response.status_code} {response.text[:250]}")
	payload = response.json()
	return payload if isinstance(payload, list) else []


def _supabase_get_all(
	resource: str,
	params: list[tuple[str, Any]] | dict[str, Any] | None = None,
	page_size: int = 1000,
) -> list[dict[str, Any]]:
	all_rows: list[dict[str, Any]] = []
	offset = 0
	while True:
		page_params = list(params) if isinstance(params, list) else list((params or {}).items())
		page_params = [(key, value) for key, value in page_params if key not in {"limit", "offset"}]
		page_params.extend([("limit", str(page_size)), ("offset", str(offset))])
		rows = _supabase_get(resource, page_params)
		all_rows.extend(rows)
		if len(rows) < page_size:
			break
		offset += page_size
	return all_rows


def _query_probable_giveaway_leakage(start_day: date, end_day: date) -> list[dict[str, Any]]:
	params: list[tuple[str, Any]] = [
		(
			"select",
			"id,location_id,business_date,bill_number,original_gross_sales,total_discounts,payment_status",
		),
		("business_date", f"gte.{start_day.isoformat()}"),
		("business_date", f"lte.{end_day.isoformat()}"),
		("payment_status", "eq.PAID"),
		("total_discounts", "gt.0"),
		("order", "business_date.desc,id.desc"),
		("limit", str(LEAKAGE_CANDIDATE_ORDER_LIMIT)),
	]
	order_rows = _supabase_get("pos_orders", params)
	if not order_rows:
		return []
	order_ids = [int(row.get("id") or 0) for row in order_rows if int(row.get("id") or 0)]
	if not order_ids:
		return []
	order_lookup = {int(row["id"]): row for row in order_rows if int(row.get("id") or 0)}
	result: list[dict[str, Any]] = []
	for index in range(0, len(order_ids), 200):
		chunk = order_ids[index : index + 200]
		item_params: list[tuple[str, Any]] = [
			("select", "order_id,product_name,quantity,discount_amount,discount_name,discount_name_normalized"),
			("discount_amount", "gt.0"),
			("order_id", f"in.({','.join(str(order_id) for order_id in chunk)})"),
			("order", "order_id.asc"),
		]
		item_rows = _supabase_get_all("pos_order_items", item_params)
		per_order: dict[int, list[dict[str, Any]]] = {}
		for row in item_rows:
			order_id = int(row.get("order_id") or 0)
			if order_id:
				per_order.setdefault(order_id, []).append(row)
		for order_id, rows in per_order.items():
			order = order_lookup.get(order_id)
			if not order:
				continue
			order_gross = flt(order.get("original_gross_sales") or 0, 2)
			total_discounts = flt(order.get("total_discounts") or 0, 2)
			discount_names = sorted(
				{
					str(row.get("discount_name") or "").strip()
					for row in rows
					if str(row.get("discount_name") or "").strip()
				}
			)
			normalized_names = {_normalize_text(row.get("discount_name_normalized") or row.get("discount_name")) for row in rows}
			is_marketing = any("marketing" in name for name in normalized_names)
			is_effectively_free = bool(order_gross and total_discounts >= round(order_gross * 0.95, 2))
			if not (is_marketing or is_effectively_free):
				continue
			item_summary = [
				{
					"product_name": str(row.get("product_name") or ""),
					"quantity": cint(row.get("quantity") or 0),
					"discount_amount": flt(row.get("discount_amount") or 0, 2),
				}
				for row in rows
			]
			result.append(
				{
					"alert_reference": f"pos-order:{order_id}",
					"order_id": order_id,
					"business_date": str(order.get("business_date") or ""),
					"store_name": _store_label_for_location(cint(order.get("location_id") or 0)),
					"location_id": cint(order.get("location_id") or 0),
					"bill_number": str(order.get("bill_number") or ""),
					"order_gross_sales": order_gross,
					"total_discounts": total_discounts,
					"discount_names": discount_names,
					"is_marketing_discount": is_marketing,
					"is_effectively_free": is_effectively_free,
					"item_summary": item_summary,
					"linked_campaigns": frappe.get_all(
						EXCEPTION_DT,
						filters={"linked_alert_reference": f"pos-order:{order_id}"},
						fields=["campaign", "status"],
						limit_page_length=20,
					),
				}
			)
	return result


def _leakage_window() -> tuple[date, date]:
	leakage_end = _manila_today()
	return leakage_end - timedelta(days=LEAKAGE_LOOKBACK_DAYS), leakage_end


@lru_cache(maxsize=1)
def _location_store_labels() -> dict[int, str]:
	labels: dict[int, str] = {}
	for row in load_sales_location_mapping().values():
		location_id = cint(row.get("location_id") or 0)
		if not location_id or location_id in labels:
			continue
		labels[location_id] = str(
			row.get("warehouse_record_name") or row.get("warehouse_name") or f"Location {location_id}"
		).strip()
	return labels


def _store_label_for_location(location_id: int) -> str:
	if not location_id:
		return ""
	return _location_store_labels().get(location_id, f"Location {location_id}")


@frappe.whitelist()
def get_campaign_giveaways_dashboard(campaign: str | None = None) -> dict[str, Any]:
	_observe("get_campaign_giveaways_dashboard", phase="read", mutation_type="load", extras={"campaign": campaign})
	_require_enabled()
	_require_roles(DASHBOARD_ROLES, "You do not have access to Campaign Giveaways.")
	campaign_names = frappe.get_all(CAMPAIGN_DT, filters={}, fields=["name"], order_by="modified desc", limit_page_length=200)
	campaign_rows = [_serialize_campaign_row(_campaign_doc(row["name"])) for row in campaign_names]
	selected = next((row for row in campaign_rows if row["name"] == campaign), campaign_rows[0] if campaign_rows else None)
	today = _manila_today().isoformat()
	active_statuses = (*APPROVED_STATES, "Pending Ops Review", "Pending Finance Approval")
	active_campaigns = [row for row in campaign_rows if row["status"] in active_statuses]
	todays_schedule = [
		{
			"campaign": row["name"],
			"campaign_name": row["campaign_name"],
			"campaign_code": row["campaign_code"],
			"rows": [schedule for schedule in row["schedule_rows"] if str(schedule.get("date") or "")[:10] == today],
		}
		for row in active_campaigns
	]
	todays_schedule = [entry for entry in todays_schedule if entry["rows"]]
	exceptions = frappe.get_all(
		EXCEPTION_DT,
		filters={"status": ["not in", ["Resolved", "Ignored"]]},
		fields=["name", "campaign", "exception_type", "status", "severity", "issue_date", "message"],
		order_by="modified desc",
		limit_page_length=20,
	)
	upcoming = [row for row in active_campaigns if row["remaining_days"] > 0 and row["required_daily_pace"] > 0 and row["status"] in APPROVED_STATES]
	return {
		"summary": {
			"total_campaigns": len(campaign_rows),
			"active_campaigns": len([row for row in active_campaigns if row["status"] in APPROVED_STATES]),
			"pending_ops_review": len([row for row in campaign_rows if row["status"] == "Pending Ops Review"]),
			"pending_finance_review": len([row for row in campaign_rows if row["status"] == "Pending Finance Approval"]),
			"open_exceptions": len(exceptions),
			"today_scheduled_issues": sum(len(entry["rows"]) for entry in todays_schedule),
		},
		"selected_campaign": selected,
		"campaigns": campaign_rows,
		"active_campaigns": active_campaigns,
		"todays_schedule": todays_schedule,
		"pace_watch": sorted(upcoming, key=lambda row: (-row["required_daily_pace"], row["campaign_name"]))[:10],
		"open_exceptions": [_serialize_exception_row(row) for row in exceptions],
		"probable_leakage": [],
		"probable_leakage_deferred": True,
	}


@frappe.whitelist()
def list_campaign_giveaways(status: str | None = None) -> dict[str, Any]:
	_observe("list_campaign_giveaways", phase="read", mutation_type="load", extras={"status": status})
	_require_enabled()
	_require_roles(DASHBOARD_ROLES, "You do not have access to Campaign Giveaways.")
	rows = frappe.get_all(CAMPAIGN_DT, filters=_campaign_filters(status), fields=["name"], order_by="modified desc", limit_page_length=200)
	return {"rows": [_serialize_campaign_row(_campaign_doc(row["name"])) for row in rows]}


@frappe.whitelist()
def get_campaign_giveaway_detail(campaign: str) -> dict[str, Any]:
	_observe("get_campaign_giveaway_detail", phase="read", mutation_type="load", extras={"campaign": campaign})
	_require_enabled()
	_require_roles(DASHBOARD_ROLES, "You do not have access to Campaign Giveaways.")
	doc = _campaign_doc(campaign)
	remaining_value = _update_campaign_tracking(doc)
	doc.save(ignore_permissions=True)
	issues = frappe.get_all(
		ISSUE_DT,
		filters={"campaign": campaign},
		fields=["name", "status", "issue_date", "source_location", "item_code", "item_name", "quantity", "actual_unit_cost", "actual_total_cost", "stock_entry", "finance_expense_account", "cost_center", "budget_owner", "notes"],
		order_by="issue_date desc, creation desc",
		limit_page_length=200,
	)
	exceptions = frappe.get_all(
		EXCEPTION_DT,
		filters={"campaign": campaign},
		fields=["name", "status", "severity", "exception_type", "source_location", "item_code", "issue_date", "requested_quantity", "attempted_value", "message", "linked_alert_reference", "linked_alert_payload_json", "resolution_code", "resolution_notes", "resolved_by", "resolved_at"],
		order_by="modified desc",
		limit_page_length=200,
	)
	return {
		"campaign": _serialize_campaign_row(doc),
		"issues": [_serialize_issue_row(row) for row in issues],
		"exceptions": [_serialize_exception_row(row) for row in exceptions],
		"remaining_value": remaining_value,
	}


@frappe.whitelist()
def save_campaign_giveaway(payload: str | dict[str, Any]) -> dict[str, Any]:
	_observe("save_campaign_giveaway", phase="mutation", mutation_type="mutation")
	_require_enabled()
	_require_roles(REQUEST_ROLES, "Only authorized requestors can save campaign giveaway requests.")
	raw_data = _safe_json(payload, {})
	data = _validate_campaign_payload(raw_data, existing_name=raw_data.get("name"))
	doc = _create_or_update_campaign(data, existing_name=data.get("name"))
	return {"success": True, "campaign": _serialize_campaign_row(doc)}


@frappe.whitelist()
def submit_campaign_giveaway_for_ops_review(campaign: str) -> dict[str, Any]:
	_observe("submit_campaign_giveaway_for_ops_review", phase="mutation", mutation_type="mutation", extras={"campaign": campaign})
	_require_enabled()
	_require_roles(REQUEST_ROLES, "Only authorized requestors can submit campaign giveaway requests.")
	doc = _campaign_doc(campaign)
	_require_request_owner(doc, "submit_campaign_giveaway_for_ops_review")
	_ensure_transition(doc.status, "Pending Ops Review")
	doc.status = "Pending Ops Review"
	doc.workflow_state = doc.status
	assigned = _queue_assignee_for_roles(OPS_REVIEW_ROLES)
	if doc.active_queue_name:
		_close_queue(doc.active_queue_name, "Approved")
	doc.active_queue_name = _open_queue(doc, assigned)
	doc.save(ignore_permissions=True)
	return {"success": True, "campaign": _serialize_campaign_row(doc)}


@frappe.whitelist()
def review_campaign_giveaway_ops(
	campaign: str,
	decision: str,
	notes: str | None = None,
	source_locations_json: str | None = None,
	schedule_json: str | None = None,
) -> dict[str, Any]:
	_observe("review_campaign_giveaway_ops", phase="mutation", mutation_type="mutation", extras={"campaign": campaign, "decision": decision})
	_require_enabled()
	_require_roles(OPS_REVIEW_ROLES, "Only Ops reviewers can process this stage.")
	doc = _campaign_doc(campaign)
	_require_assigned_reviewer(doc, "review_campaign_giveaway_ops")
	if doc.status != "Pending Ops Review":
		frappe.throw(_("Campaign is not pending Ops review."))
	decision_normalized = str(decision or "").strip().lower()
	if decision_normalized not in {"approve", "reject"}:
		frappe.throw(_("Decision must be approve or reject."))
	doc.ops_reviewed_by = frappe.session.user
	doc.ops_reviewed_at = now_datetime()
	doc.ops_review_notes = notes or doc.ops_review_notes
	if source_locations_json:
		sources = _normalize_list(_safe_json(source_locations_json, []))
		for source_location in sources:
			_require_master_record("Warehouse", source_location, "Source Location", filters={"is_group": 0})
		doc.source_locations_json = json.dumps(sources)
	if schedule_json:
		doc.schedule_json = json.dumps(_safe_json(schedule_json, []))
	if decision_normalized == "reject":
		doc.status = "Rejected"
		doc.rejection_reason = notes
		_close_queue(doc.active_queue_name, "Rejected", notes)
		doc.active_queue_name = None
	else:
		_ensure_transition(doc.status, "Pending Finance Approval")
		doc.status = "Pending Finance Approval"
		_close_queue(doc.active_queue_name, "Approved")
		doc.active_queue_name = _open_queue(doc, _queue_assignee_for_roles(FINANCE_REVIEW_ROLES))
	doc.workflow_state = doc.status
	doc.save(ignore_permissions=True)
	return {"success": True, "campaign": _serialize_campaign_row(doc)}


@frappe.whitelist()
def review_campaign_giveaway_finance(
	campaign: str,
	decision: str,
	notes: str | None = None,
	cost_center: str | None = None,
	budget_owner: str | None = None,
	approved_value_tolerance_pct: float | str | None = None,
) -> dict[str, Any]:
	_observe("review_campaign_giveaway_finance", phase="mutation", mutation_type="mutation", extras={"campaign": campaign, "decision": decision})
	_require_enabled()
	_require_roles(FINANCE_REVIEW_ROLES, "Only Finance reviewers can process this stage.")
	doc = _campaign_doc(campaign)
	_require_assigned_reviewer(doc, "review_campaign_giveaway_finance")
	if doc.status != "Pending Finance Approval":
		frappe.throw(_("Campaign is not pending Finance approval."))
	decision_normalized = str(decision or "").strip().lower()
	if decision_normalized not in {"approve", "reject"}:
		frappe.throw(_("Decision must be approve or reject."))
	doc.finance_reviewed_by = frappe.session.user
	doc.finance_reviewed_at = now_datetime()
	doc.finance_review_notes = notes or doc.finance_review_notes
	if cost_center:
		doc.cost_center = _require_master_record("Cost Center", cost_center, "Cost Center", filters={"is_group": 0})
	if budget_owner:
		doc.budget_owner = _require_master_record("User", budget_owner, "Budget Owner", filters={"enabled": 1})
	if approved_value_tolerance_pct is not None:
		doc.approved_value_tolerance_pct = flt(approved_value_tolerance_pct, 2)
	if decision_normalized == "reject":
		doc.status = "Rejected"
		doc.rejection_reason = notes
		_close_queue(doc.active_queue_name, "Rejected", notes)
		doc.active_queue_name = None
	else:
		_ensure_transition(doc.status, "Approved / Active")
		doc.status = "Approved / Active"
		doc.policy_version = POLICY_VERSION
		doc.finance_expense_account = _resolve_marketing_expense_account()
		_close_queue(doc.active_queue_name, "Approved")
		doc.active_queue_name = None
	doc.workflow_state = doc.status
	doc.save(ignore_permissions=True)
	return {"success": True, "campaign": _serialize_campaign_row(doc)}


@frappe.whitelist()
def cancel_campaign_giveaway(campaign: str, reason: str | None = None) -> dict[str, Any]:
	_observe("cancel_campaign_giveaway", phase="mutation", mutation_type="mutation", extras={"campaign": campaign})
	_require_enabled()
	_require_roles(REQUEST_ROLES | {"System Manager", "Administrator"}, "Only authorized users can cancel this request.")
	doc = _campaign_doc(campaign)
	_require_request_owner(doc, "cancel_campaign_giveaway")
	if doc.status not in {"Draft", "Pending Ops Review", "Pending Finance Approval"}:
		frappe.throw(_("Only pre-approval campaigns can be cancelled."))
	doc.status = "Cancelled"
	doc.workflow_state = doc.status
	doc.cancel_reason = reason
	_close_queue(doc.active_queue_name, "Rejected", reason)
	doc.active_queue_name = None
	doc.save(ignore_permissions=True)
	return {"success": True, "campaign": _serialize_campaign_row(doc)}


@frappe.whitelist()
def post_campaign_giveaway_issue(
	campaign: str,
	source_location: str,
	item_code: str,
	quantity: float | str,
	issue_date: str | None = None,
	idempotency_key: str | None = None,
	notes: str | None = None,
) -> dict[str, Any]:
	_observe("post_campaign_giveaway_issue", phase="mutation", mutation_type="mutation", extras={"campaign": campaign, "item_code": item_code, "source_location": source_location})
	_require_enabled()
	_require_roles(FULFILLMENT_ROLES, "Only approved fulfillment roles can issue campaign giveaways.")
	quantity_value = flt(quantity or 0, 3)
	if quantity_value <= 0:
		frappe.throw(_("Issued quantity must be greater than 0."))
	key = str(idempotency_key or "").strip()
	if not key:
		frappe.throw(_("Idempotency key is required."))
	existing_issue_name = frappe.db.get_value(ISSUE_DT, {"idempotency_key": key}, "name")
	if existing_issue_name:
		existing = _issue_doc(existing_issue_name)
		return {
			"success": True,
			"idempotent_replay": True,
			"issue": {
				"name": existing.name,
				"status": existing.status,
				"stock_entry": existing.stock_entry,
				"actual_total_cost": flt(existing.actual_total_cost or 0, 2),
			},
		}
	campaign_doc = _campaign_doc(campaign)
	issue_day = getdate(issue_date) if issue_date else _manila_today()
	item_row, unit_cost = _validate_issue_request(campaign_doc, source_location, item_code, quantity_value, issue_day)
	frappe.db.savepoint(f"campaign_issue_{campaign_doc.name.replace('-', '_')}")
	try:
		issue_doc = frappe.new_doc(ISSUE_DT)
		issue_doc.campaign = campaign_doc.name
		issue_doc.status = "Draft"
		issue_doc.issue_date = issue_day.isoformat()
		issue_doc.idempotency_key = key
		issue_doc.source_location = source_location
		issue_doc.item_code = item_code
		issue_doc.item_name = item_row.item_name or frappe.db.get_value("Item", item_code, "item_name")
		issue_doc.uom = item_row.uom or frappe.db.get_value("Item", item_code, "stock_uom")
		issue_doc.quantity = quantity_value
		issue_doc.actual_unit_cost = unit_cost
		issue_doc.actual_total_cost = round(quantity_value * unit_cost, 2)
		issue_doc.finance_expense_account = campaign_doc.finance_expense_account or _resolve_marketing_expense_account()
		issue_doc.cost_center = campaign_doc.cost_center
		issue_doc.budget_owner = campaign_doc.budget_owner
		issue_doc.notes = notes
		issue_doc.insert(ignore_permissions=True)
		stock_entry_name = _post_stock_entry_for_issue(campaign_doc, issue_doc)
		issue_doc.stock_entry = stock_entry_name
		issue_doc.status = "Posted"
		issue_doc.save(ignore_permissions=True)
		remaining_value = _update_campaign_tracking(campaign_doc)
		campaign_doc.save(ignore_permissions=True)
		frappe.db.commit()
		return {
			"success": True,
			"issue": {
				"name": issue_doc.name,
				"status": issue_doc.status,
				"issue_date": issue_doc.issue_date,
				"quantity": flt(issue_doc.quantity or 0, 3),
				"actual_total_cost": flt(issue_doc.actual_total_cost or 0, 2),
				"stock_entry": stock_entry_name,
				"remaining_value": remaining_value,
			},
			"campaign": _serialize_campaign_row(campaign_doc),
		}
	except Exception:
		frappe.db.rollback()
		raise


@frappe.whitelist()
def get_campaign_giveaway_approvals() -> dict[str, Any]:
	_observe("get_campaign_giveaway_approvals", phase="read", mutation_type="load")
	_require_enabled()
	_require_roles(OPS_REVIEW_ROLES | FINANCE_REVIEW_ROLES, "You do not have approval access to Campaign Giveaways.")
	rows = frappe.get_all(
		CAMPAIGN_DT,
		filters={"status": ["in", ["Pending Ops Review", "Pending Finance Approval"]]},
		fields=["name"],
		order_by="modified desc",
		limit_page_length=200,
	)
	return {"rows": [_serialize_campaign_row(_campaign_doc(row["name"])) for row in rows]}


@frappe.whitelist()
def get_campaign_giveaway_fulfillment_queue(campaign: str | None = None) -> dict[str, Any]:
	_observe("get_campaign_giveaway_fulfillment_queue", phase="read", mutation_type="load", extras={"campaign": campaign})
	_require_enabled()
	_require_roles(FULFILLMENT_ROLES, "You do not have fulfillment access to Campaign Giveaways.")
	filters: dict[str, Any] = {"status": ["in", list(APPROVED_STATES)]}
	if campaign:
		filters["name"] = campaign
	rows = frappe.get_all(CAMPAIGN_DT, filters=filters, fields=["name"], order_by="modified desc", limit_page_length=200)
	return {"rows": [_serialize_campaign_row(_campaign_doc(row["name"])) for row in rows]}


@frappe.whitelist()
def get_campaign_giveaway_exceptions(campaign: str | None = None) -> dict[str, Any]:
	_observe("get_campaign_giveaway_exceptions", phase="read", mutation_type="load", extras={"campaign": campaign})
	_require_enabled()
	_require_roles(EXCEPTION_ROLES, "You do not have exception access to Campaign Giveaways.")
	filters: dict[str, Any] = {}
	if campaign:
		filters["campaign"] = campaign
	rows = frappe.get_all(
		EXCEPTION_DT,
		filters=filters,
		fields=["name", "campaign", "campaign_issue", "status", "severity", "exception_type", "source_location", "item_code", "issue_date", "requested_quantity", "attempted_value", "message", "linked_alert_reference", "linked_alert_payload_json", "resolution_code", "resolution_notes", "created_by", "resolved_by", "resolved_at"],
		order_by="modified desc",
		limit_page_length=300,
	)
	return {
		"rows": [_serialize_exception_row(row) for row in rows],
		"probable_leakage": [],
		"probable_leakage_deferred": True,
	}


@frappe.whitelist()
def get_campaign_giveaway_probable_leakage(campaign: str | None = None) -> dict[str, Any]:
	_observe("get_campaign_giveaway_probable_leakage", phase="read", mutation_type="load", extras={"campaign": campaign})
	_require_enabled()
	_require_roles(EXCEPTION_ROLES, "You do not have probable leakage access to Campaign Giveaways.")
	leakage_start, leakage_end = _leakage_window()
	return {
		"rows": _query_probable_giveaway_leakage(leakage_start, leakage_end),
		"window_start": leakage_start.isoformat(),
		"window_end": leakage_end.isoformat(),
	}


@frappe.whitelist()
def resolve_campaign_giveaway_exception(exception_name: str, resolution_code: str, resolution_notes: str | None = None) -> dict[str, Any]:
	_observe("resolve_campaign_giveaway_exception", phase="mutation", mutation_type="mutation", extras={"exception_name": exception_name, "resolution_code": resolution_code})
	_require_enabled()
	_require_roles(EXCEPTION_ROLES, "You do not have exception access to Campaign Giveaways.")
	doc = frappe.get_doc(EXCEPTION_DT, exception_name)
	doc.status = "Resolved"
	doc.resolution_code = resolution_code
	doc.resolution_notes = resolution_notes
	doc.resolved_by = frappe.session.user
	doc.resolved_at = now_datetime()
	doc.save(ignore_permissions=True)
	return {"success": True, "exception": _serialize_exception_row(doc.as_dict())}


@frappe.whitelist()
def link_probable_leakage_to_campaign(
	campaign: str,
	alert_reference: str,
	alert_payload: str | dict[str, Any] | None = None,
	resolution_notes: str | None = None,
) -> dict[str, Any]:
	_observe("link_probable_leakage_to_campaign", phase="mutation", mutation_type="mutation", extras={"campaign": campaign, "alert_reference": alert_reference})
	_require_enabled()
	_require_roles(EXCEPTION_ROLES, "You do not have exception access to Campaign Giveaways.")
	payload = _safe_json(alert_payload, {})
	existing = frappe.db.get_value(EXCEPTION_DT, {"campaign": campaign, "linked_alert_reference": alert_reference}, "name")
	if existing:
		doc = frappe.get_doc(EXCEPTION_DT, existing)
		if resolution_notes:
			doc.resolution_notes = resolution_notes
		doc.status = "Linked"
		doc.save(ignore_permissions=True)
	else:
		doc = _exception_doc(
			{
				"campaign": campaign,
				"status": "Linked",
				"severity": "Medium",
				"exception_type": "Leaked POS Giveaway",
				"message": resolution_notes or "Probable leaked POS giveaway linked to campaign.",
				"linked_alert_reference": alert_reference,
				"linked_alert_payload_json": json.dumps(payload or {}),
			}
		)
	return {"success": True, "exception": _serialize_exception_row(doc.as_dict())}


@frappe.whitelist()
def get_campaign_giveaway_reconciliation(campaign: str | None = None) -> dict[str, Any]:
	_observe("get_campaign_giveaway_reconciliation", phase="read", mutation_type="load", extras={"campaign": campaign})
	_require_enabled()
	_require_roles(RECONCILIATION_ROLES, "You do not have reconciliation access to Campaign Giveaways.")
	rows = frappe.get_all(CAMPAIGN_DT, filters={"name": campaign} if campaign else {}, fields=["name"], order_by="modified desc", limit_page_length=200)
	results = []
	for row in rows:
		doc = _campaign_doc(row["name"])
		issues = frappe.get_all(
			ISSUE_DT,
			filters={"campaign": doc.name, "status": "Posted"},
			fields=["source_location", "quantity", "actual_total_cost"],
			limit_page_length=1000,
		)
		by_store: dict[str, dict[str, Any]] = {}
		for issue in issues:
			source = str(issue.get("source_location") or "Unknown")
			entry = by_store.setdefault(source, {"source_location": source, "quantity": 0.0, "actual_value": 0.0})
			entry["quantity"] += flt(issue.get("quantity") or 0, 3)
			entry["actual_value"] += flt(issue.get("actual_total_cost") or 0, 2)
		exception_count = frappe.db.count(EXCEPTION_DT, {"campaign": doc.name, "status": ["not in", ["Resolved", "Ignored"]]})
		results.append(
			{
				"campaign": _serialize_campaign_row(doc),
				"approved_quantity": flt(doc.total_approved_quantity or 0, 3),
				"issued_quantity": flt(doc.quantity_served or 0, 3),
				"remaining_quantity": flt(doc.remaining_quantity or 0, 3),
				"approved_value": flt(doc.estimated_peso_value or 0, 2),
				"actual_issued_value": round(sum(entry["actual_value"] for entry in by_store.values()), 2),
				"open_exception_count": exception_count,
				"by_store": sorted(by_store.values(), key=lambda entry: (-entry["actual_value"], entry["source_location"])),
			}
		)
	return {"rows": results}
