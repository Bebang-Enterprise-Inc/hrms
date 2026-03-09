"""Discount identity monitoring APIs for Accounting and Audit."""

from __future__ import annotations

import io
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from itertools import pairwise
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


def _supabase_get(
	resource: str,
	params: dict[str, Any] | list[tuple[str, Any]] | None = None,
) -> list[dict[str, Any]]:
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


def _supabase_merge_params(
	params: dict[str, Any] | list[tuple[str, Any]] | None,
	extra: list[tuple[str, Any]],
) -> dict[str, Any] | list[tuple[str, Any]]:
	if params is None:
		return list(extra)
	if isinstance(params, dict):
		merged = dict(params)
		for key, value in extra:
			merged[key] = value
		return merged
	merged = [(key, value) for key, value in params if key not in {"limit", "offset"}]
	merged.extend(extra)
	return merged


def _supabase_get_all(
	resource: str,
	params: dict[str, Any] | list[tuple[str, Any]] | None = None,
	page_size: int = 1000,
) -> list[dict[str, Any]]:
	all_rows: list[dict[str, Any]] = []
	offset = 0
	while True:
		page_params = _supabase_merge_params(
			params,
			[("limit", str(page_size)), ("offset", str(offset))],
		)
		rows = _supabase_get(resource, page_params)
		all_rows.extend(rows)
		if len(rows) < page_size:
			break
		offset += page_size
	return all_rows


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


def _normalize_text(value: Any) -> str:
	if value is None:
		return ""
	return " ".join(str(value).strip().upper().split())


def _split_pipe_values(value: Any) -> list[str]:
	if value is None:
		return []
	if isinstance(value, list | tuple | set):
		values: list[str] = []
		for entry in value:
			values.extend(_split_pipe_values(entry))
		return values
	text = str(value).strip()
	if not text:
		return []
	return [part.strip() for part in text.split("|") if part.strip()]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
	seen: set[str] = set()
	result: list[str] = []
	for value in values:
		key = _normalize_text(value)
		if not key or key in seen:
			continue
		seen.add(key)
		result.append(key)
	return result


def _canonical_discount_category(
	category: Any,
	discount_name_normalized: Any = None,
	discount_name: Any = None,
) -> str:
	category_text = _normalize_text(category)
	if category_text in {"SC", "PWD"}:
		return category_text
	name_text = _normalize_text(discount_name_normalized or discount_name)
	if "PWD" in name_text:
		return "PWD"
	if "SENIOR" in name_text or "SC" == name_text:
		return "SC"
	return ""


def _parse_iso_datetime(value: Any) -> datetime | None:
	if not value:
		return None
	text = str(value).strip()
	if not text:
		return None
	try:
		return datetime.fromisoformat(text.replace("Z", "+00:00"))
	except ValueError:
		return None


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


def _format_display_window(start_day: date, end_day: date) -> str:
	if start_day == end_day:
		return _format_display_date(start_day)
	return f"{_format_display_date(start_day)} to {_format_display_date(end_day)}"


def _parse_store_names(value: str | None) -> list[str]:
	if not value:
		return []
	return [part.strip() for part in str(value).split(",") if part.strip()]


def _parse_category_filter(value: str | None) -> set[str] | None:
	text = _normalize_text(value)
	if not text or text == "ALL":
		return None
	return {part.strip() for part in text.split(",") if part.strip() in {"SC", "PWD"}}


def _get_store_directory() -> dict[int, str]:
	rows = _supabase_get_all(
		"stores",
		{
			"select": "location_id,store_name",
			"order": "store_name.asc",
		},
		page_size=200,
	)
	return {int(row["location_id"]): str(row["store_name"]) for row in rows if row.get("location_id")}


def _resolve_selected_stores(store_names: list[str]) -> tuple[list[int], dict[int, str]]:
	store_directory = _get_store_directory()
	if not store_names:
		return [], {}
	normalized_to_id = {
		_normalize_text(store_name): location_id for location_id, store_name in store_directory.items()
	}
	selected_location_ids: list[int] = []
	selected_store_map: dict[int, str] = {}
	for store_name in store_names:
		location_id = normalized_to_id.get(_normalize_text(store_name))
		if location_id is None:
			continue
		if location_id in selected_store_map:
			continue
		selected_location_ids.append(location_id)
		selected_store_map[location_id] = store_directory[location_id]
	return selected_location_ids, selected_store_map


def _row_mentions_store(row: dict[str, Any], store_name: str) -> bool:
	names = _split_pipe_values(row.get("store_name"))
	if not names and row.get("store_name"):
		names = [str(row["store_name"])]
	needle = _normalize_text(store_name)
	return any(_normalize_text(name) == needle for name in names)


def _query_same_day_rows_range(
	start_day: date,
	end_day: date,
	categories: set[str] | None = None,
) -> list[dict[str, Any]]:
	params: list[tuple[str, Any]] = [
		("select", "*"),
		("queue_bucket", "eq.same_day"),
		("event_date", f"gte.{start_day.isoformat()}"),
		("event_date", f"lte.{end_day.isoformat()}"),
		("order", SAME_DAY_QUEUE_ORDER),
	]
	rows = [_normalize_queue_row(row) for row in _supabase_get_all("v_discount_identity_audit_queue", params)]
	if categories:
		rows = [row for row in rows if _normalize_text(row.get("discount_bir_category")) in categories]
	return rows


def _query_paid_orders_for_range(
	start_day: date, end_day: date, location_ids: list[int]
) -> list[dict[str, Any]]:
	if not location_ids:
		return []
	location_list = ",".join(str(location_id) for location_id in location_ids)
	params: list[tuple[str, Any]] = [
		(
			"select",
			"id,location_id,business_date,bill_number,receipt_number,billed_at,paid_at,payment_status,original_gross_sales,gross_sales,net_sales,total_discounts",
		),
		("business_date", f"gte.{start_day.isoformat()}"),
		("business_date", f"lte.{end_day.isoformat()}"),
		("location_id", f"in.({location_list})"),
		("payment_status", "eq.PAID"),
		("order", "business_date.asc,id.asc"),
	]
	return _supabase_get_all("pos_orders", params)


def _chunk_values(values: list[int], size: int = 200) -> list[list[int]]:
	if not values:
		return []
	return [values[index : index + size] for index in range(0, len(values), size)]


def _query_discount_item_rows_for_orders(
	paid_order_rows: list[dict[str, Any]],
	categories: set[str] | None = None,
) -> list[dict[str, Any]]:
	if not paid_order_rows:
		return []
	order_lookup: dict[int, dict[str, Any]] = {}
	for row in paid_order_rows:
		order_id = int(row.get("id") or 0)
		if order_id:
			order_lookup[order_id] = row
	order_ids = sorted(order_lookup)
	if not order_ids:
		return []
	select_fields = ",".join(
		[
			"order_id",
			"line_number",
			"product_name",
			"quantity",
			"discount_amount",
			"discount_name",
			"discount_name_normalized",
			"discount_bir_category",
			"discount_customer_full_name",
			"discount_customer_full_name_normalized",
			"discount_reference_number",
			"discount_reference_number_normalized",
		]
	)
	result: list[dict[str, Any]] = []
	for chunk in _chunk_values(order_ids):
		params: list[tuple[str, Any]] = [
			("select", select_fields),
			("discount_amount", "gt.0"),
			("order_id", f"in.({','.join(str(order_id) for order_id in chunk)})"),
			("order", "order_id.asc,line_number.asc"),
		]
		if categories:
			params.append(("discount_bir_category", f"in.({','.join(sorted(categories))})"))
		rows = _supabase_get_all("pos_order_items", params)
		for row in rows:
			order_id = int(row.get("order_id") or 0)
			order = order_lookup.get(order_id)
			if not order:
				continue
			location_id = int(order.get("location_id") or 0)
			category = _canonical_discount_category(
				row.get("discount_bir_category"),
				row.get("discount_name_normalized"),
				row.get("discount_name"),
			)
			if not category:
				continue
			if categories and category not in categories:
				continue
			result.append(
				{
					"location_id": location_id,
					"store_name": str(order.get("store_name") or location_id),
					"business_date": str(order.get("business_date") or ""),
					"order_id": order_id,
					"bill_number": str(order.get("bill_number") or ""),
					"receipt_number": str(order.get("receipt_number") or ""),
					"billed_at": order.get("billed_at"),
					"paid_at": order.get("paid_at"),
					"order_gross_sales": _to_number(order.get("original_gross_sales")),
					"order_net_sales_w_vat": _to_number(order.get("gross_sales")),
					"order_net_sales_wo_vat": _to_number(order.get("net_sales")),
					"order_total_discounts": _to_number(order.get("total_discounts")),
					"line_number": int(row.get("line_number") or 0),
					"product_name": str(row.get("product_name") or ""),
					"quantity": int(row.get("quantity") or 0),
					"discount_amount": _to_number(row.get("discount_amount")),
					"discount_name": str(row.get("discount_name") or ""),
					"discount_name_normalized": str(row.get("discount_name_normalized") or ""),
					"discount_bir_category": category,
					"discount_customer_full_name": str(row.get("discount_customer_full_name") or ""),
					"discount_customer_full_name_normalized": _normalize_text(
						row.get("discount_customer_full_name_normalized")
						or row.get("discount_customer_full_name")
					),
					"discount_reference_number": str(row.get("discount_reference_number") or ""),
					"discount_reference_number_normalized": _normalize_text(
						row.get("discount_reference_number_normalized")
						or row.get("discount_reference_number")
					),
				}
			)
	return result


def _min_gap_minutes(rows: list[dict[str, Any]]) -> int | None:
	timestamps = [
		_parse_iso_datetime(row.get("billed_at")) or _parse_iso_datetime(row.get("paid_at")) for row in rows
	]
	parsed = sorted(ts for ts in timestamps if ts is not None)
	if len(parsed) < 2:
		return None
	return min(int((right - left).total_seconds() // 60) for left, right in pairwise(parsed))


def _extract_alert_associations(row: dict[str, Any]) -> dict[str, list[str]]:
	details = _safe_json(row.get("details"))
	names = _dedupe_preserve_order(
		_split_pipe_values(row.get("customer_name"))
		+ _split_pipe_values(row.get("customer_names"))
		+ _split_pipe_values(details.get("customer_name"))
		+ _split_pipe_values(details.get("customer_names"))
	)
	references = _dedupe_preserve_order(
		_split_pipe_values(row.get("reference_number"))
		+ _split_pipe_values(row.get("reference_numbers"))
		+ _split_pipe_values(details.get("reference_number"))
		+ _split_pipe_values(details.get("reference_numbers"))
	)
	bills = _dedupe_preserve_order(
		_split_pipe_values(row.get("bill_numbers")) + _split_pipe_values(details.get("bill_numbers"))
	)
	business_dates = _dedupe_preserve_order(
		_split_pipe_values(row.get("business_dates")) + _split_pipe_values(details.get("business_dates"))
	)
	return {
		"names": names,
		"references": references,
		"bill_numbers": bills,
		"business_dates": business_dates,
	}


def _build_store_sales_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
	active_days = {str(row.get("business_date") or "") for row in rows if row.get("business_date")}
	order_count = len(rows)
	gross_sales = sum(_to_number(row.get("original_gross_sales")) for row in rows)
	net_sales_w_vat = sum(_to_number(row.get("gross_sales")) for row in rows)
	net_sales_wo_vat = sum(_to_number(row.get("net_sales")) for row in rows)
	total_discounts = sum(_to_number(row.get("total_discounts")) for row in rows)
	return {
		"paid_orders": order_count,
		"active_days": len(active_days),
		"gross_sales": round(gross_sales, 2),
		"net_sales_w_vat": round(net_sales_w_vat, 2),
		"net_sales_wo_vat": round(net_sales_wo_vat, 2),
		"total_discounts": round(total_discounts, 2),
		"avg_order_gross": round(gross_sales / order_count, 2) if order_count else 0.0,
	}


def _build_store_item_summary(
	rows: list[dict[str, Any]],
	selected_categories: set[str] | None,
) -> dict[str, Any]:
	order_ids = {int(row["order_id"]) for row in rows if row.get("order_id")}
	rows_with_name = [
		row for row in rows if _normalize_text(row.get("discount_customer_full_name_normalized"))
	]
	rows_with_reference = [
		row for row in rows if _normalize_text(row.get("discount_reference_number_normalized"))
	]
	breakdown_counter: Counter[str] = Counter(
		_normalize_text(row.get("discount_bir_category")) for row in rows if row.get("discount_bir_category")
	)
	label = "ALL" if selected_categories is None else ",".join(sorted(selected_categories))
	return {
		"category_label": label,
		"item_rows": len(rows),
		"orders": len(order_ids),
		"discount_total": round(sum(_to_number(row.get("discount_amount")) for row in rows), 2),
		"rows_with_name": len(rows_with_name),
		"rows_with_reference": len(rows_with_reference),
		"category_breakdown": dict(sorted(breakdown_counter.items())),
	}


def _build_store_contextual_metrics(
	rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
	orders: dict[tuple[str, int], dict[str, Any]] = {}
	for row in rows:
		key = (str(row.get("business_date") or ""), int(row.get("order_id") or 0))
		order_bucket = orders.setdefault(
			key,
			{
				"business_date": key[0],
				"order_id": key[1],
				"store_name": row.get("store_name"),
				"bill_numbers": set(),
				"names": set(),
				"references": set(),
				"discount_amount_total": 0.0,
			},
		)
		if row.get("bill_number"):
			order_bucket["bill_numbers"].add(str(row["bill_number"]))
		name = _normalize_text(row.get("discount_customer_full_name_normalized"))
		ref = _normalize_text(row.get("discount_reference_number_normalized"))
		if name:
			order_bucket["names"].add(name)
		if ref:
			order_bucket["references"].add(ref)
		order_bucket["discount_amount_total"] += _to_number(row.get("discount_amount"))

	name_groups: dict[str, dict[str, set[Any]]] = {}
	ref_groups: dict[str, dict[str, set[Any]]] = {}
	non_four_digit_reference_rows = 0
	for row in rows:
		name = _normalize_text(row.get("discount_customer_full_name_normalized"))
		ref = _normalize_text(row.get("discount_reference_number_normalized"))
		order_id = int(row.get("order_id") or 0)
		if ref and len(ref) != 4:
			non_four_digit_reference_rows += 1
		if name:
			name_bucket = name_groups.setdefault(name, {"references": set(), "orders": set()})
			if ref:
				name_bucket["references"].add(ref)
			name_bucket["orders"].add(order_id)
		if ref:
			ref_bucket = ref_groups.setdefault(ref, {"names": set(), "orders": set()})
			if name:
				ref_bucket["names"].add(name)
			ref_bucket["orders"].add(order_id)

	multi_name_receipts: list[dict[str, Any]] = []
	for order_bucket in orders.values():
		distinct_names = sorted(order_bucket["names"])
		distinct_references = sorted(order_bucket["references"])
		if len(distinct_names) >= 2:
			multi_name_receipts.append(
				{
					"business_date": order_bucket["business_date"],
					"order_id": order_bucket["order_id"],
					"store_name": order_bucket["store_name"],
					"bill_numbers": sorted(order_bucket["bill_numbers"]),
					"names": distinct_names,
					"references": distinct_references,
					"distinct_name_count": len(distinct_names),
					"discount_amount_total": round(order_bucket["discount_amount_total"], 2),
				}
			)

	order_count = len(orders)
	contextual_metrics = {
		"multi_name_receipts": len(multi_name_receipts),
		"multi_name_receipts_3plus": sum(1 for row in multi_name_receipts if row["distinct_name_count"] >= 3),
		"multi_name_receipts_5plus": sum(1 for row in multi_name_receipts if row["distinct_name_count"] >= 5),
		"max_names_on_single_receipt": max(
			(row["distinct_name_count"] for row in multi_name_receipts), default=0
		),
		"multi_name_receipts_pct_of_orders": round((len(multi_name_receipts) / order_count) * 100, 2)
		if order_count
		else 0.0,
		"month_name_multiple_reference_findings": sum(
			1 for bucket in name_groups.values() if len(bucket["references"]) >= 2
		),
		"month_reference_multi_name_findings": sum(
			1 for bucket in ref_groups.values() if len(bucket["names"]) >= 2
		),
		"non_four_digit_reference_rows": non_four_digit_reference_rows,
		"non_four_digit_reference_rate_pct": round((non_four_digit_reference_rows / len(rows)) * 100, 2)
		if rows
		else 0.0,
	}
	return contextual_metrics, multi_name_receipts


def _build_same_day_metrics(
	store_name: str, rows: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
	store_rows = [
		row
		for row in rows
		if _normalize_text(row.get("scope")) == "STORE"
		and _normalize_text(row.get("store_name")) == _normalize_text(store_name)
	]
	chain_rows = [
		row
		for row in rows
		if _normalize_text(row.get("scope")) != "STORE" and _row_mentions_store(row, store_name)
	]
	store_severity = Counter(_normalize_text(row.get("severity")) for row in store_rows)
	chain_severity = Counter(_normalize_text(row.get("severity")) for row in chain_rows)
	store_metrics = {
		"repeat_name_findings": sum(
			1 for row in store_rows if row.get("detection_type") == "same_name_same_day_same_store"
		),
		"repeat_reference_findings": sum(
			1 for row in store_rows if row.get("detection_type") == "same_reference_same_day_same_store"
		),
		"same_reference_different_name_findings": sum(
			1
			for row in store_rows
			if row.get("detection_type") == "same_reference_diff_name_same_day_same_store"
		),
		"same_name_multiple_reference_findings": sum(
			1
			for row in store_rows
			if row.get("detection_type") == "same_name_diff_reference_same_day_same_store"
		),
		"rapid_repeat_name_findings_4h": sum(
			1
			for row in store_rows
			if row.get("detection_type") == "same_name_same_day_same_store" and row.get("rapid_within_4h")
		),
		"rapid_repeat_reference_findings_4h": sum(
			1
			for row in store_rows
			if row.get("detection_type") == "same_reference_same_day_same_store"
			and row.get("rapid_within_4h")
		),
		"same_day_rows_by_severity": {
			"critical": int(store_severity.get("CRITICAL", 0)),
			"high": int(store_severity.get("HIGH", 0)),
			"medium": int(store_severity.get("MEDIUM", 0)),
			"review": int(store_severity.get("REVIEW", 0)),
		},
	}
	chain_metrics = {
		"same_day_chain_rows": len(chain_rows),
		"chain_rows_by_severity": {
			"critical": int(chain_severity.get("CRITICAL", 0)),
			"high": int(chain_severity.get("HIGH", 0)),
			"medium": int(chain_severity.get("MEDIUM", 0)),
			"review": int(chain_severity.get("REVIEW", 0)),
		},
	}
	return store_metrics, chain_metrics


def _build_investigation_summary_payload(
	start_day: date,
	end_day: date,
	selected_store_names: list[str],
	selected_categories: set[str] | None,
	same_day_rows: list[dict[str, Any]],
	item_rows: list[dict[str, Any]],
	paid_order_rows: list[dict[str, Any]],
) -> dict[str, Any]:
	store_summaries: list[dict[str, Any]] = []
	total_repeat_name = 0
	total_same_ref_diff_name = 0
	total_rapid_repeat_name = 0
	total_multi_name_receipts = 0
	for store_name in selected_store_names:
		store_order_rows = [
			row
			for row in paid_order_rows
			if _normalize_text(row.get("store_name")) == _normalize_text(store_name)
		]
		store_item_rows = [
			row for row in item_rows if _normalize_text(row.get("store_name")) == _normalize_text(store_name)
		]
		location_id = int(store_item_rows[0]["location_id"]) if store_item_rows else 0
		sales_summary = _build_store_sales_summary(store_order_rows)
		category_summary = _build_store_item_summary(store_item_rows, selected_categories)
		same_day_metrics, chain_metrics = _build_same_day_metrics(store_name, same_day_rows)
		contextual_metrics, _ = _build_store_contextual_metrics(store_item_rows)
		total_repeat_name += same_day_metrics["repeat_name_findings"]
		total_same_ref_diff_name += same_day_metrics["same_reference_different_name_findings"]
		total_rapid_repeat_name += same_day_metrics["rapid_repeat_name_findings_4h"]
		total_multi_name_receipts += contextual_metrics["multi_name_receipts"]
		store_summaries.append(
			{
				"location_id": location_id,
				"store_name": store_name,
				"sales": sales_summary,
				"category_summary": category_summary,
				"same_day_metrics": same_day_metrics,
				"chain_metrics": chain_metrics,
				"contextual_metrics": contextual_metrics,
			}
		)

	return {
		"start_date": start_day.isoformat(),
		"end_date": end_day.isoformat(),
		"display_window": _format_display_window(start_day, end_day),
		"selected_store_names": selected_store_names,
		"discount_bir_category": ",".join(sorted(selected_categories)) if selected_categories else "ALL",
		"requires_store_selection": False,
		"methodology_notes": [
			"Same-day metrics are alert-derived from validated discount identity alerts.",
			"Multi-name receipt metrics are contextual receipt-level review metrics, not incident counts.",
		],
		"totals": {
			"same_day_repeat_name_findings": total_repeat_name,
			"same_day_same_reference_different_name_findings": total_same_ref_diff_name,
			"same_day_rapid_repeat_name_findings_4h": total_rapid_repeat_name,
			"contextual_multi_name_receipts": total_multi_name_receipts,
		},
		"stores": store_summaries,
	}


def _build_investigation_case_rows(
	selected_store_names: list[str],
	same_day_rows: list[dict[str, Any]],
	item_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
	case_rows: list[dict[str, Any]] = []
	for row in same_day_rows:
		if not any(_row_mentions_store(row, store_name) for store_name in selected_store_names):
			continue
		associations = _extract_alert_associations(row)
		case_rows.append(
			{
				"case_id": (
					f"alert:{row.get('event_date')}:{row.get('scope')}:{row.get('scope_key')}:"
					f"{row.get('identity_key')}:{row.get('detection_type')}"
				),
				"case_bucket": "same_day_alert",
				"detection_type": row.get("detection_type"),
				"scope": row.get("scope"),
				"store_name": row.get("store_name"),
				"business_date": row.get("event_date"),
				"severity": row.get("severity"),
				"identity_key": row.get("identity_key"),
				"names": associations["names"],
				"references": associations["references"],
				"bill_numbers": associations["bill_numbers"],
				"business_dates": associations["business_dates"] or [str(row.get("event_date") or "")],
				"order_count": int(row.get("order_count") or 0),
				"store_count": int(row.get("store_count") or 0),
				"discount_amount_total": round(_to_number(row.get("discount_amount_total")), 2),
				"rapid_within_4h": bool(row.get("rapid_within_4h")),
				"min_gap_minutes": row.get("min_gap_minutes"),
				"context_note": "",
			}
		)

	contextual_metrics_by_store: dict[str, list[dict[str, Any]]] = {}
	for store_name in selected_store_names:
		store_item_rows = [
			row for row in item_rows if _normalize_text(row.get("store_name")) == _normalize_text(store_name)
		]
		_, multi_name_receipts = _build_store_contextual_metrics(store_item_rows)
		contextual_metrics_by_store[store_name] = multi_name_receipts

	for store_name, receipt_rows in contextual_metrics_by_store.items():
		for receipt in receipt_rows:
			if receipt["distinct_name_count"] < 3:
				continue
			case_rows.append(
				{
					"case_id": f"context:{receipt['business_date']}:{receipt['order_id']}",
					"case_bucket": "contextual_receipt",
					"detection_type": "context_multi_name_receipt",
					"scope": "store",
					"store_name": store_name,
					"business_date": receipt["business_date"],
					"severity": "high" if receipt["distinct_name_count"] >= 5 else "review",
					"identity_key": receipt["bill_numbers"][0]
					if receipt["bill_numbers"]
					else str(receipt["order_id"]),
					"names": receipt["names"],
					"references": receipt["references"],
					"bill_numbers": receipt["bill_numbers"],
					"business_dates": [receipt["business_date"]],
					"order_count": 1,
					"store_count": 1,
					"discount_amount_total": receipt["discount_amount_total"],
					"rapid_within_4h": False,
					"min_gap_minutes": None,
					"context_note": "Contextual receipt metric - multiple distinct names on one discounted receipt.",
				}
			)

	severity_rank = {"critical": 1, "high": 2, "medium": 3, "review": 4}
	case_rows.sort(
		key=lambda row: (
			severity_rank.get(str(row.get("severity") or ""), 9),
			str(row.get("business_date") or ""),
			str(row.get("store_name") or ""),
			str(row.get("detection_type") or ""),
			str(row.get("identity_key") or ""),
		)
	)
	return case_rows


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
	stores = sorted(_get_store_directory().values())
	return {
		"success": True,
		"data": {
			"business_date": target_day.isoformat(),
			"rows": data,
			"summary": _make_summary(same_day_rows, rolling_rows),
			"stores": stores,
		},
	}


def _get_investigation_payload(
	start_date: str | None,
	end_date: str | None,
	store_names: str | None,
	discount_bir_category: str | None,
) -> tuple[
	date, date, list[str], set[str] | None, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
	start_day = _coerce_date(start_date)
	end_day = _coerce_date(end_date)
	if end_day < start_day:
		frappe.throw(frappe._("End date cannot be earlier than start date."))
	selected_store_names = _parse_store_names(store_names)
	selected_categories = _parse_category_filter(discount_bir_category)
	location_ids, selected_store_map = _resolve_selected_stores(selected_store_names)
	resolved_store_names = [selected_store_map[location_id] for location_id in location_ids]
	if not resolved_store_names:
		return start_day, end_day, [], selected_categories, [], [], []
	same_day_rows = _query_same_day_rows_range(start_day, end_day, selected_categories)
	paid_order_rows = _query_paid_orders_for_range(start_day, end_day, location_ids)
	store_map = {location_id: store_name for location_id, store_name in selected_store_map.items()}
	for row in paid_order_rows:
		location_id = int(row.get("location_id") or 0)
		row["store_name"] = store_map.get(location_id, str(location_id))
	item_rows = _query_discount_item_rows_for_orders(paid_order_rows, selected_categories)
	return (
		start_day,
		end_day,
		resolved_store_names,
		selected_categories,
		same_day_rows,
		item_rows,
		paid_order_rows,
	)


@frappe.whitelist()
def get_discount_investigation_summary(
	start_date: str,
	end_date: str,
	store_names: str | None = None,
	discount_bir_category: str | None = "SC",
) -> dict[str, Any]:
	_check_discount_audit_role()
	(
		start_day,
		end_day,
		resolved_store_names,
		selected_categories,
		same_day_rows,
		item_rows,
		paid_order_rows,
	) = _get_investigation_payload(start_date, end_date, store_names, discount_bir_category)
	if not resolved_store_names:
		return {
			"success": True,
			"data": {
				"start_date": start_day.isoformat(),
				"end_date": end_day.isoformat(),
				"display_window": _format_display_window(start_day, end_day),
				"discount_bir_category": ",".join(sorted(selected_categories))
				if selected_categories
				else "ALL",
				"selected_store_names": [],
				"requires_store_selection": True,
				"totals": {},
				"stores": [],
				"methodology_notes": [
					"Select at least one store to load investigation analytics.",
				],
			},
		}
	return {
		"success": True,
		"data": _build_investigation_summary_payload(
			start_day,
			end_day,
			resolved_store_names,
			selected_categories,
			same_day_rows,
			item_rows,
			paid_order_rows,
		),
	}


@frappe.whitelist()
def get_discount_investigation_cases(
	start_date: str,
	end_date: str,
	store_names: str | None = None,
	discount_bir_category: str | None = "SC",
) -> dict[str, Any]:
	_check_discount_audit_role()
	(
		start_day,
		end_day,
		resolved_store_names,
		selected_categories,
		same_day_rows,
		item_rows,
		_paid_order_rows,
	) = _get_investigation_payload(start_date, end_date, store_names, discount_bir_category)
	if not resolved_store_names:
		return {
			"success": True,
			"data": {
				"start_date": start_day.isoformat(),
				"end_date": end_day.isoformat(),
				"display_window": _format_display_window(start_day, end_day),
				"discount_bir_category": ",".join(sorted(selected_categories))
				if selected_categories
				else "ALL",
				"selected_store_names": [],
				"requires_store_selection": True,
				"summary": {"same_day_alert_cases": 0, "contextual_cases": 0},
				"rows": [],
			},
		}
	case_rows = _build_investigation_case_rows(resolved_store_names, same_day_rows, item_rows)
	return {
		"success": True,
		"data": {
			"start_date": start_day.isoformat(),
			"end_date": end_day.isoformat(),
			"display_window": _format_display_window(start_day, end_day),
			"discount_bir_category": ",".join(sorted(selected_categories)) if selected_categories else "ALL",
			"selected_store_names": resolved_store_names,
			"requires_store_selection": False,
			"summary": {
				"same_day_alert_cases": sum(1 for row in case_rows if row["case_bucket"] == "same_day_alert"),
				"contextual_cases": sum(1 for row in case_rows if row["case_bucket"] == "contextual_receipt"),
			},
			"rows": case_rows,
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
