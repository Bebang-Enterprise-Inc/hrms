"""Discount identity monitoring APIs for Accounting and Audit."""

from __future__ import annotations

import io
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

import frappe

MANILA_TZ = ZoneInfo("Asia/Manila")
DEFAULT_NOTIFICATION_GO_LIVE_DATE = date(2026, 3, 10)
REPORT_FILENAME_PREFIX = "Discount_Identity_Audit_Report_"
PORTAL_QUEUE_URL = "https://my.bebang.ph/dashboard/accounting/discount-abuse"
ALLOWED_ROLES = {
	"HQ User",
	"HQ Finance",
	"Accounts User",
	"Accounts Manager",
	"System Manager",
	"Administrator",
}
SAME_DAY_QUEUE_ORDER = (
	"severity_rank.asc,rapid_rank.asc,min_gap_minutes.asc.nullslast,"
	"discount_amount_total.desc,order_count.desc,store_name.asc"
)
ROLLING_QUEUE_ORDER = (
	"severity.asc,order_count.desc,active_day_count.desc,distinct_counterparty_count.desc,store_name.asc"
)


def _conf_get(key: str, default: Any = None) -> Any:
	conf = getattr(frappe, "conf", {}) or {}
	if hasattr(conf, "get"):
		return conf.get(key, default)
	return default


def _permission_error_class():
	return getattr(frappe, "PermissionError", Exception)


def _is_guest() -> bool:
	return getattr(getattr(frappe, "session", None), "user", "Guest") == "Guest"


def _check_discount_audit_role() -> None:
	roles = set(frappe.get_roles() or [])
	if not roles.intersection(ALLOWED_ROLES):
		frappe.throw(
			frappe._("Only Accounting / Audit users can access discount monitoring."),
			_permission_error_class(),
		)


def _manila_now() -> datetime:
	return datetime.now(timezone.utc).astimezone(MANILA_TZ)


def _default_business_date() -> date:
	return _manila_now().date() - timedelta(days=1)


def _coerce_date(value: Any, default: date | None = None) -> date:
	if isinstance(value, date):
		return value
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, str) and value.strip():
		return date.fromisoformat(value.strip()[:10])
	if default is not None:
		return default
	raise ValueError("Business date is required")


def _format_display_date(value: date) -> str:
	return value.strftime("%B %d, %Y")


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


def _supabase_get(resource: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
	response = requests.get(
		f"{_get_supabase_url()}/rest/v1/{resource}",
		headers=_supabase_headers(),
		params=params or {},
		timeout=30,
	)
	if not response.ok:
		raise RuntimeError(
			f"Supabase GET failed for {resource}: {response.status_code} {response.text[:300]}"
		)
	payload = response.json()
	if isinstance(payload, list):
		return payload
	raise RuntimeError(f"Unexpected Supabase payload for {resource}")


def _supabase_patch(
	resource: str,
	filters: dict[str, str],
	payload: dict[str, Any],
) -> list[dict[str, Any]]:
	headers = _supabase_headers()
	headers["Prefer"] = "return=representation"
	response = requests.patch(
		f"{_get_supabase_url()}/rest/v1/{resource}",
		headers=headers,
		params=filters,
		json=payload,
		timeout=30,
	)
	if not response.ok:
		raise RuntimeError(
			f"Supabase PATCH failed for {resource}: {response.status_code} {response.text[:300]}"
		)
	result = response.json()
	return result if isinstance(result, list) else []


def _parse_email_recipients() -> list[str]:
	raw = os.environ.get("DISCOUNT_ALERT_EMAIL_RECIPIENTS") or _conf_get(
		"discount_alert_email_recipients", ""
	)
	if not raw:
		return []
	if isinstance(raw, list | tuple):
		return [str(item).strip() for item in raw if str(item).strip()]
	return [item.strip() for item in str(raw).split(",") if item.strip()]


def _get_report_owner(default_user: str | None = None) -> str:
	explicit = os.environ.get("DISCOUNT_ALERT_REPORT_OWNER") or _conf_get("discount_alert_report_owner")
	if explicit:
		return explicit
	if default_user and default_user != "Guest":
		return default_user
	return "Administrator"


def _get_notification_go_live_date() -> date:
	raw = os.environ.get("DISCOUNT_ALERT_NOTIFY_ENABLE_FROM") or _conf_get(
		"discount_alert_notify_enable_from"
	)
	if not raw:
		return DEFAULT_NOTIFICATION_GO_LIVE_DATE
	try:
		return _coerce_date(raw)
	except Exception:
		return DEFAULT_NOTIFICATION_GO_LIVE_DATE


def _notifications_enabled_for_day(target_day: date) -> bool:
	return target_day >= _get_notification_go_live_date()


def _to_number(value: Any) -> float:
	if value in (None, "", False):
		return 0.0
	try:
		return float(value)
	except (TypeError, ValueError):
		return 0.0


def _safe_json(value: Any) -> dict[str, Any]:
	if isinstance(value, dict):
		return value
	if isinstance(value, str) and value.strip():
		try:
			parsed = json.loads(value)
			return parsed if isinstance(parsed, dict) else {}
		except json.JSONDecodeError:
			return {}
	return {}


def _normalize_queue_row(row: dict[str, Any]) -> dict[str, Any]:
	normalized = dict(row)
	normalized["discount_amount_total"] = _to_number(row.get("discount_amount_total"))
	normalized["min_gap_minutes"] = (
		None if row.get("min_gap_minutes") in (None, "") else _to_number(row.get("min_gap_minutes"))
	)
	normalized["order_count"] = int(row.get("order_count") or 0)
	normalized["store_count"] = int(row.get("store_count") or 0)
	normalized["active_day_count"] = int(row.get("active_day_count") or 0)
	normalized["distinct_counterparty_count"] = int(row.get("distinct_counterparty_count") or 0)
	normalized["rapid_within_4h"] = bool(row.get("rapid_within_4h"))
	normalized["details"] = _safe_json(row.get("details"))
	normalized["event_date"] = str(row.get("event_date") or "")
	normalized["window_start"] = str(row.get("window_start") or "")
	normalized["window_end"] = str(row.get("window_end") or "")
	return normalized


def _sort_same_day_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	severity_rank = {"critical": 1, "high": 2, "medium": 3, "review": 4}
	return sorted(
		rows,
		key=lambda row: (
			severity_rank.get(str(row.get("severity") or ""), 9),
			0 if row.get("rapid_within_4h") else 1,
			row.get("min_gap_minutes") if row.get("min_gap_minutes") is not None else 999999,
			-_to_number(row.get("discount_amount_total")),
			-(int(row.get("order_count") or 0)),
			str(row.get("store_name") or ""),
			str(row.get("identity_key") or ""),
		),
	)


def _sort_rolling_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	severity_rank = {"high": 1, "review": 2}
	return sorted(
		rows,
		key=lambda row: (
			severity_rank.get(str(row.get("severity") or ""), 9),
			-(int(row.get("order_count") or 0)),
			-(int(row.get("active_day_count") or 0)),
			-(int(row.get("distinct_counterparty_count") or 0)),
			str(row.get("store_name") or ""),
			str(row.get("identity_key") or ""),
		),
	)


def _query_same_day_rows(business_date: date, severity: str | None = None) -> list[dict[str, Any]]:
	params: dict[str, Any] = {
		"select": "*",
		"queue_bucket": "eq.same_day",
		"event_date": f"eq.{business_date.isoformat()}",
		"order": SAME_DAY_QUEUE_ORDER,
		"limit": "1000",
	}
	if severity and severity != "all":
		params["severity"] = f"eq.{severity}"
	return [_normalize_queue_row(row) for row in _supabase_get("v_discount_identity_audit_queue", params)]


def _query_rolling_rows(business_date: date, severity: str | None = None) -> list[dict[str, Any]]:
	queue_params: dict[str, Any] = {
		"select": "*",
		"queue_bucket": "eq.rolling_30d",
		"event_date": f"eq.{business_date.isoformat()}",
		"order": "severity_rank.asc,discount_amount_total.desc,order_count.desc,store_name.asc",
		"limit": "1000",
	}
	if severity and severity != "all":
		queue_params["severity"] = f"eq.{severity}"
	rows = _supabase_get("v_discount_identity_audit_queue", queue_params)
	if rows:
		return [_normalize_queue_row(row) for row in rows]

	snapshot_params: dict[str, Any] = {
		"select": (
			"id,as_of_date,window_start,window_end,scope,scope_key,location_id,store_name,"
			"discount_name,discount_bir_category,identity_type,identity_key,customer_name,"
			"reference_number,order_count,active_day_count,distinct_counterparty_count,"
			"detection_type,severity,details,created_at,updated_at"
		),
		"as_of_date": f"eq.{business_date.isoformat()}",
		"order": ROLLING_QUEUE_ORDER,
		"limit": "1000",
	}
	if severity and severity != "all":
		snapshot_params["severity"] = f"eq.{severity}"
	snapshot_rows = _supabase_get("discount_identity_30d_snapshots", snapshot_params)
	normalized_rows: list[dict[str, Any]] = []
	for row in snapshot_rows:
		details = _safe_json(row.get("details"))
		normalized_rows.append(
			_normalize_queue_row(
				{
					"queue_bucket": "rolling_30d",
					"queue_bucket_rank": 2,
					"severity_rank": 4 if row.get("severity") == "review" else 2,
					"rapid_rank": 1,
					"event_date": row.get("as_of_date"),
					"window_start": row.get("window_start"),
					"window_end": row.get("window_end"),
					"scope": row.get("scope"),
					"scope_key": row.get("scope_key"),
					"location_id": row.get("location_id"),
					"store_name": row.get("store_name"),
					"discount_name": row.get("discount_name"),
					"discount_bir_category": row.get("discount_bir_category"),
					"identity_type": row.get("identity_type"),
					"identity_key": row.get("identity_key"),
					"customer_name": row.get("customer_name"),
					"reference_number": row.get("reference_number"),
					"order_count": row.get("order_count"),
					"store_count": 1,
					"active_day_count": row.get("active_day_count"),
					"distinct_counterparty_count": row.get("distinct_counterparty_count"),
					"detection_type": row.get("detection_type"),
					"severity": row.get("severity"),
					"rapid_within_4h": False,
					"min_gap_minutes": None,
					"discount_amount_total": details.get("discount_amount_total"),
					"resolved": False,
					"notified_at": None,
					"created_at": row.get("created_at"),
					"updated_at": row.get("updated_at"),
					"details": details,
				}
			)
		)
	return normalized_rows


def _filter_rows(
	rows: list[dict[str, Any]],
	search: str | None = None,
	severity: str | None = None,
	store_name: str | None = None,
	category: str | None = None,
) -> list[dict[str, Any]]:
	filtered = list(rows)
	if severity and severity != "all":
		filtered = [row for row in filtered if str(row.get("severity") or "") == severity]
	if store_name and store_name != "all":
		filtered = [row for row in filtered if str(row.get("store_name") or "") == store_name]
	if category and category != "all":
		filtered = [
			row for row in filtered if str(row.get("discount_bir_category") or "").upper() == category.upper()
		]
	if search:
		needle = search.strip().lower()
		filtered = [
			row
			for row in filtered
			if needle
			in " | ".join(
				[
					str(row.get("store_name") or ""),
					str(row.get("discount_name") or ""),
					str(row.get("identity_key") or ""),
					str(row.get("customer_name") or ""),
					str(row.get("reference_number") or ""),
					str(row.get("detection_type") or ""),
				]
			).lower()
		]
	return filtered


def _make_summary(same_day_rows: list[dict[str, Any]], rolling_rows: list[dict[str, Any]]) -> dict[str, int]:
	same_day_counts = Counter(row.get("severity") for row in same_day_rows)
	rolling_counts = Counter(row.get("severity") for row in rolling_rows)
	return {
		"same_day_critical": int(same_day_counts.get("critical", 0)),
		"same_day_high": int(same_day_counts.get("high", 0)),
		"same_day_medium": int(same_day_counts.get("medium", 0)),
		"rolling_high": int(rolling_counts.get("high", 0)),
		"rolling_review": int(rolling_counts.get("review", 0)),
	}


def _build_critical_notification_message(
	business_date: date,
	rows: list[dict[str, Any]],
) -> str:
	line_count = len(rows)
	store_names = sorted(
		{str(row.get("store_name") or "Unknown Store") for row in rows if row.get("store_name")}
	)
	header = [
		"Senior/PWD discount alert digest",
		f"Business date: {_format_display_date(business_date)}",
		f"{line_count} critical clusters require audit review",
	]
	if store_names:
		header.append("Stores: " + ", ".join(store_names))

	body = []
	for row in rows[:12]:
		amount = _to_number(row.get("discount_amount_total"))
		body.append(
			"- {store} | {detection} | {identity} | orders {orders} | amount PHP {amount:,.2f}".format(
				store=row.get("store_name") or "Unknown Store",
				detection=row.get("detection_type") or "unknown_detection",
				identity=row.get("identity_key") or "-",
				orders=int(row.get("order_count") or 0),
				amount=amount,
			)
		)

	footer = [
		"",
		f"Review queue: {PORTAL_QUEUE_URL}",
	]
	return "\n".join(header + body + footer)


def _set_header_style(worksheet, row_number: int = 1) -> None:
	from openpyxl.styles import Alignment, Font, PatternFill

	fill = PatternFill("solid", fgColor="1F4E78")
	font = Font(color="FFFFFF", bold=True)
	alignment = Alignment(vertical="center")
	for cell in worksheet[row_number]:
		cell.fill = fill
		cell.font = font
		cell.alignment = alignment


def _auto_size_columns(worksheet) -> None:
	for column_cells in worksheet.columns:
		max_length = 0
		column_letter = column_cells[0].column_letter
		for cell in column_cells:
			value = "" if cell.value is None else str(cell.value)
			max_length = max(max_length, len(value))
		worksheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 42)


def _write_tab(worksheet, rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> None:
	headers = [label for label, _ in columns]
	worksheet.append(headers)
	_set_header_style(worksheet)
	for row in rows:
		worksheet.append([row.get(key) for _, key in columns])
	worksheet.freeze_panes = "A2"
	_auto_size_columns(worksheet)


def _build_audit_workbook_bytes(
	business_date: date,
	same_day_rows: list[dict[str, Any]],
	rolling_rows: list[dict[str, Any]],
	summary: dict[str, int],
) -> bytes:
	import openpyxl

	workbook = openpyxl.Workbook()
	overview = workbook.active
	overview.title = "Overview"
	overview.append(["Metric", "Value"])
	_set_header_style(overview)
	overview_rows = [
		("Business Date", business_date.isoformat()),
		("Generated At PHT", _manila_now().strftime("%Y-%m-%d %H:%M:%S")),
		("Same-Day Critical", summary.get("same_day_critical", 0)),
		("Same-Day High", summary.get("same_day_high", 0)),
		("Same-Day Medium", summary.get("same_day_medium", 0)),
		("Rolling 30D High", summary.get("rolling_high", 0)),
		("Rolling 30D Review", summary.get("rolling_review", 0)),
		("Same-Day Rows", len(same_day_rows)),
		("Rolling Rows", len(rolling_rows)),
	]
	for metric, value in overview_rows:
		overview.append([metric, value])
	overview.freeze_panes = "A2"
	_auto_size_columns(overview)

	columns = [
		("Bucket", "queue_bucket"),
		("Event Date", "event_date"),
		("Store", "store_name"),
		("Severity", "severity"),
		("Category", "discount_bir_category"),
		("Detection", "detection_type"),
		("Identity Type", "identity_type"),
		("Identity Key", "identity_key"),
		("Customer Name", "customer_name"),
		("Reference No.", "reference_number"),
		("Order Count", "order_count"),
		("Store Count", "store_count"),
		("Rapid <4h", "rapid_within_4h"),
		("Min Gap Minutes", "min_gap_minutes"),
		("Discount Amount", "discount_amount_total"),
		("Window Start", "window_start"),
		("Window End", "window_end"),
	]
	rolling_columns = [
		("Bucket", "queue_bucket"),
		("Event Date", "event_date"),
		("Store", "store_name"),
		("Severity", "severity"),
		("Category", "discount_bir_category"),
		("Detection", "detection_type"),
		("Identity Type", "identity_type"),
		("Identity Key", "identity_key"),
		("Customer Name", "customer_name"),
		("Reference No.", "reference_number"),
		("Order Count", "order_count"),
		("Active Days", "active_day_count"),
		("Distinct Counterparties", "distinct_counterparty_count"),
		("Discount Amount", "discount_amount_total"),
		("Window Start", "window_start"),
		("Window End", "window_end"),
	]

	same_day_sheet = workbook.create_sheet("SameDay_All")
	_write_tab(same_day_sheet, same_day_rows, columns)

	same_day_critical = workbook.create_sheet("SameDay_Critical")
	_write_tab(
		same_day_critical,
		[row for row in same_day_rows if str(row.get("severity") or "") == "critical"],
		columns,
	)

	rolling_all = workbook.create_sheet("Rolling30D_All")
	_write_tab(rolling_all, rolling_rows, rolling_columns)

	rolling_high = workbook.create_sheet("Rolling30D_High")
	_write_tab(
		rolling_high,
		[row for row in rolling_rows if str(row.get("severity") or "") == "high"],
		rolling_columns,
	)

	buffer = io.BytesIO()
	workbook.save(buffer)
	return buffer.getvalue()


def _alert_filters(row: dict[str, Any]) -> dict[str, str]:
	return {
		"business_date": f"eq.{row['event_date']}",
		"scope": f"eq.{row['scope']}",
		"scope_key": f"eq.{int(row['scope_key'])}",
		"discount_bir_category": f"eq.{row['discount_bir_category']}",
		"identity_type": f"eq.{row['identity_type']}",
		"identity_key": f"eq.{row['identity_key']}",
		"detection_type": f"eq.{row['detection_type']}",
	}


def _mark_alerts_notified(rows: list[dict[str, Any]]) -> int:
	notified_at = _manila_now().isoformat()
	updated = 0
	for row in rows:
		result = _supabase_patch(
			"discount_abuse_alerts",
			_alert_filters(row),
			{"notified_at": notified_at, "updated_at": notified_at},
		)
		if result:
			updated += 1
	return updated


@frappe.whitelist()
def get_discount_audit_dashboard(business_date: str | None = None) -> dict[str, Any]:
	_check_discount_audit_role()
	target_day = _coerce_date(business_date, default=_default_business_date())
	same_day_rows = _query_same_day_rows(target_day)
	rolling_rows = _query_rolling_rows(target_day)
	summary = _make_summary(same_day_rows, rolling_rows)
	return {
		"success": True,
		"data": {
			"business_date": target_day.isoformat(),
			"display_business_date": _format_display_date(target_day),
			"summary": summary,
			"same_day_total": len(same_day_rows),
			"rolling_total": len(rolling_rows),
			"critical_same_day_rows": same_day_rows[:10],
			"top_rolling_rows": rolling_rows[:10],
			"notifications_enabled": _notifications_enabled_for_day(target_day),
			"notification_go_live_date": _get_notification_go_live_date().isoformat(),
			"latest_reports": list_discount_audit_reports(limit=5).get("data", []),
		},
	}


@frappe.whitelist()
def get_discount_audit_queue(
	business_date: str | None = None,
	queue_bucket: str | None = None,
	severity: str | None = None,
	search: str | None = None,
	store_name: str | None = None,
	discount_bir_category: str | None = None,
) -> dict[str, Any]:
	_check_discount_audit_role()
	target_day = _coerce_date(business_date, default=_default_business_date())
	bucket = (queue_bucket or "all").strip()

	same_day_rows = _query_same_day_rows(target_day) if bucket in ("all", "same_day") else []
	rolling_rows = _query_rolling_rows(target_day) if bucket in ("all", "rolling_30d") else []

	same_day_rows = _filter_rows(
		_sort_same_day_rows(same_day_rows),
		search=search,
		severity=severity if bucket != "rolling_30d" else None,
		store_name=store_name,
		category=discount_bir_category,
	)
	rolling_rows = _filter_rows(
		_sort_rolling_rows(rolling_rows),
		search=search,
		severity=severity if bucket != "same_day" else None,
		store_name=store_name,
		category=discount_bir_category,
	)

	data = same_day_rows + rolling_rows
	stores = sorted({row.get("store_name") for row in data if row.get("store_name")})
	return {
		"success": True,
		"data": {
			"business_date": target_day.isoformat(),
			"rows": data,
			"summary": _make_summary(same_day_rows, rolling_rows),
			"stores": stores,
		},
	}


@frappe.whitelist()
def resolve_discount_audit_alert(
	alert: str | dict[str, Any],
	resolution_code: str,
	resolution_note: str | None = None,
) -> dict[str, Any]:
	_check_discount_audit_role()
	payload = _safe_json(alert) if not isinstance(alert, dict) else alert
	required_keys = [
		"event_date",
		"scope",
		"scope_key",
		"discount_bir_category",
		"identity_type",
		"identity_key",
		"detection_type",
	]
	missing = [key for key in required_keys if payload.get(key) in (None, "")]
	if missing:
		frappe.throw(frappe._("Missing alert identity fields: {0}").format(", ".join(missing)))

	existing_rows = _supabase_get(
		"discount_abuse_alerts",
		{
			"select": "details",
			**_alert_filters(payload),
			"limit": "1",
		},
	)
	existing_details = _safe_json(existing_rows[0].get("details")) if existing_rows else {}
	resolved_at = _manila_now().isoformat()
	merged_details = {
		**existing_details,
		"resolution_code": resolution_code,
		"resolution_note": resolution_note or "",
		"resolved_by": getattr(getattr(frappe, "session", None), "user", "unknown"),
		"resolved_at_pht": resolved_at,
	}

	updated = _supabase_patch(
		"discount_abuse_alerts",
		_alert_filters(payload),
		{
			"resolved": True,
			"resolved_at": resolved_at,
			"updated_at": resolved_at,
			"details": merged_details,
		},
	)
	return {
		"success": True,
		"data": updated[0] if updated else None,
		"message": "Alert resolved",
	}


@frappe.whitelist()
def generate_daily_discount_audit_report(
	business_date: str | None = None,
	attach_to_user: str | None = None,
) -> dict[str, Any]:
	target_day = _coerce_date(business_date, default=_default_business_date())
	return _generate_daily_discount_audit_report_internal(target_day, attach_to_user, check_permissions=True)


def _generate_daily_discount_audit_report_internal(
	target_day: date,
	attach_to_user: str | None = None,
	check_permissions: bool = False,
) -> dict[str, Any]:
	if check_permissions:
		_check_discount_audit_role()

	same_day_rows = _sort_same_day_rows(_query_same_day_rows(target_day))
	rolling_rows = _sort_rolling_rows(_query_rolling_rows(target_day))
	summary = _make_summary(same_day_rows, rolling_rows)
	workbook_bytes = _build_audit_workbook_bytes(target_day, same_day_rows, rolling_rows, summary)

	from frappe.utils.file_manager import save_file

	target_user = _get_report_owner(attach_to_user or getattr(getattr(frappe, "session", None), "user", None))
	filename = f"{REPORT_FILENAME_PREFIX}{target_day.isoformat()}.xlsx"
	file_doc = save_file(filename, workbook_bytes, "User", target_user, is_private=1)
	return {
		"success": True,
		"data": {
			"business_date": target_day.isoformat(),
			"filename": filename,
			"file_url": file_doc.file_url,
			"attached_to_user": target_user,
			"same_day_count": len(same_day_rows),
			"rolling_count": len(rolling_rows),
			"summary": summary,
		},
	}


@frappe.whitelist()
def list_discount_audit_reports(limit: int | str = 10) -> dict[str, Any]:
	_check_discount_audit_role()
	page_length = min(max(int(limit or 10), 1), 50)
	files = frappe.get_all(
		"File",
		filters=[
			["File", "file_name", "like", f"{REPORT_FILENAME_PREFIX}%"],
			["File", "is_private", "=", 1],
		],
		fields=["name", "file_name", "file_url", "creation", "attached_to_name"],
		order_by="creation desc",
		limit_page_length=page_length,
	)
	return {"success": True, "data": files}


@frappe.whitelist()
def send_critical_discount_alert_notifications(
	business_date: str | None = None,
	force: int | str | bool = False,
) -> dict[str, Any]:
	target_day = _coerce_date(business_date, default=_default_business_date())
	force_send = str(force).lower() in {"1", "true", "yes"}
	return _send_critical_discount_alert_notifications_internal(
		target_day,
		force_send=force_send,
		check_permissions=True,
	)


def _send_critical_discount_alert_notifications_internal(
	target_day: date,
	force_send: bool = False,
	check_permissions: bool = False,
) -> dict[str, Any]:
	if check_permissions:
		_check_discount_audit_role()

	if not force_send and not _notifications_enabled_for_day(target_day):
		return {
			"success": True,
			"skipped": True,
			"reason": "Notifications are still in warm-up window",
			"go_live_date": _get_notification_go_live_date().isoformat(),
		}

	rows = _sort_same_day_rows(_query_same_day_rows(target_day, severity="critical"))
	if not rows:
		return {
			"success": True,
			"skipped": True,
			"reason": "No critical same-day rows",
			"business_date": target_day.isoformat(),
		}

	message = _build_critical_notification_message(target_day, rows)
	chat_sent = False
	email_sent = False

	try:
		from hrms.api.google_chat import send_message_to_space
		from hrms.utils.bei_config import SPACE_ACCOUNTING, get_chat_space

		chat_sent = send_message_to_space(get_chat_space(SPACE_ACCOUNTING), message)
	except Exception as exc:
		frappe.log_error(
			title="Discount Alert Chat Notification Failed",
			message=str(exc),
		)

	recipients = _parse_email_recipients()
	if recipients:
		try:
			frappe.sendmail(
				recipients=recipients,
				subject=f"Critical SC/PWD Alert Digest - {target_day.isoformat()}",
				message=f"<pre>{message}</pre>",
			)
			email_sent = True
		except Exception as exc:
			frappe.log_error(
				title="Discount Alert Email Notification Failed",
				message=str(exc),
			)

	marked_count = _mark_alerts_notified(rows) if (chat_sent or email_sent) else 0
	return {
		"success": True,
		"data": {
			"business_date": target_day.isoformat(),
			"critical_count": len(rows),
			"chat_sent": chat_sent,
			"email_sent": email_sent,
			"marked_notified": marked_count,
		},
	}


def scheduled_generate_daily_discount_audit_report() -> dict[str, Any]:
	target_day = _default_business_date()
	report_owner = _get_report_owner()
	try:
		return _generate_daily_discount_audit_report_internal(
			target_day,
			attach_to_user=report_owner,
		)
	except Exception as exc:
		frappe.log_error(
			title="Scheduled Discount Audit Report Failed",
			message=str(exc),
		)
		return {"success": False, "error": str(exc)}


def scheduled_send_critical_discount_alert_notifications() -> dict[str, Any]:
	target_day = _default_business_date()
	try:
		return _send_critical_discount_alert_notifications_internal(target_day)
	except Exception as exc:
		frappe.log_error(
			title="Scheduled Discount Alert Notification Failed",
			message=str(exc),
		)
		return {"success": False, "error": str(exc)}
