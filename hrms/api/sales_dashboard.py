"""Sales intelligence dashboard APIs for my.bebang.ph."""

from __future__ import annotations

import csv
import io
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

import frappe
from frappe import _

MANILA_TZ = ZoneInfo("Asia/Manila")
ROLE_SALES_STAKEHOLDER = "Sales Stakeholder"
ROLE_AREA_SUPERVISOR = "Area Supervisor"
ROLE_STORE_SUPERVISOR = "Store Supervisor"
ROLE_HQ_USER = "HQ User"
ROLE_HQ_FINANCE = "HQ Finance"
ROLE_ACCOUNTS_MANAGER = "Accounts Manager"
ROLE_SYSTEM_MANAGER = "System Manager"
ROLE_ADMINISTRATOR = "Administrator"

ALL_STORE_ROLES = {
	ROLE_ADMINISTRATOR,
	ROLE_SYSTEM_MANAGER,
	ROLE_HQ_USER,
	ROLE_HQ_FINANCE,
	ROLE_ACCOUNTS_MANAGER,
}
OPS_ALLOWED_ROLES = {
	ROLE_ADMINISTRATOR,
	ROLE_SYSTEM_MANAGER,
	ROLE_HQ_USER,
	ROLE_HQ_FINANCE,
	ROLE_ACCOUNTS_MANAGER,
	ROLE_AREA_SUPERVISOR,
}
ALLOWED_ROLES = ALL_STORE_ROLES | {ROLE_AREA_SUPERVISOR, ROLE_STORE_SUPERVISOR, ROLE_SALES_STAKEHOLDER}
CALENDAR_SOURCE = "Company.default_holiday_list"
MAPPING_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "sales_dashboard_store_mapping.csv"
SUPABASE_DAILY_VIEW = "sales_dashboard_daily_store_metrics"

DAILY_METRIC_SELECT = ",".join(
	[
		"location_id",
		"business_date",
		"store_name",
		"legal_entity",
		"store_type",
		"pos_orders",
		"web_orders",
		"foodpanda_orders",
		"transactions",
		"pos_gross_sales",
		"pos_net_sales_without_vat",
		"web_gross_sales",
		"web_net_sales_without_vat",
		"web_cod_orders",
		"web_cod_gross_sales",
		"web_cod_net_sales_without_vat",
		"foodpanda_subtotal",
		"foodpanda_vat_deducted_sales",
		"website_non_cod_gross_sales",
		"website_non_cod_net_sales_without_vat",
		"pos_cups_sold",
		"web_cups_sold",
		"foodpanda_cups_sold",
		"cups_sold",
		"total_gross_sales",
		"total_net_sales_without_vat",
	]
)
WEATHER_SELECT = ",".join(
	[
		"location_id",
		"business_date",
		"max_temperature",
		"min_temperature",
		"avg_temperature",
		"total_precipitation",
		"weather_description",
		"weather_code",
		"is_rainy",
		"business_impact",
	]
)

OPS_WW10_REFERENCE = {
	"start_date": "2026-03-02",
	"end_date": "2026-03-08",
	"gross_sales": 23_963_905.0,
	"net_sales": 20_262_953.0,
	"pickup_sales": 13_565_270.0,
	"foodpanda_sales": 4_288_747.0,
	"website_sales": 2_408_936.0,
	"cups_sold": 119_411,
	"transactions": 55_901,
	"source": ".agents/skills/sales/references/ww10-team-truth.md",
}


def _permission_error_class():
	return getattr(frappe, "PermissionError", Exception)


def _validation_error_class():
	return getattr(frappe, "ValidationError", Exception)


def _guest_user() -> bool:
	return getattr(getattr(frappe, "session", None), "user", "Guest") == "Guest"


def _current_user() -> str:
	return getattr(getattr(frappe, "session", None), "user", "Guest")


def _get_roles(user: str | None = None) -> set[str]:
	try:
		roles = frappe.get_roles(user) if user else frappe.get_roles()
	except TypeError:
		roles = frappe.get_roles()
	return set(roles or [])


def _conf_get(key: str, default: Any = None) -> Any:
	conf = getattr(frappe, "conf", {}) or {}
	if hasattr(conf, "get"):
		return conf.get(key, default)
	return default


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
		or _conf_get("SUPABASE_SERVICE_ROLE_KEY")
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
		timeout=60,
	)
	if not response.ok:
		raise RuntimeError(
			f"Supabase GET failed for {resource}: {response.status_code} {response.text[:300]}"
		)
	payload = response.json()
	if isinstance(payload, list):
		return payload
	raise RuntimeError(f"Unexpected Supabase payload for {resource}")


def _merge_params(
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


def _get_param_value(params: dict[str, Any] | list[tuple[str, Any]] | None, key: str) -> Any:
	if params is None:
		return None
	if isinstance(params, dict):
		return params.get(key)
	for existing_key, value in reversed(params):
		if existing_key == key:
			return value
	return None


def _supabase_get_all(
	resource: str,
	params: dict[str, Any] | list[tuple[str, Any]] | None = None,
	page_size: int = 1000,
) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	offset = int(_get_param_value(params, "offset") or 0)
	requested_limit_value = _get_param_value(params, "limit")
	requested_limit = int(requested_limit_value) if requested_limit_value is not None else None
	while True:
		remaining = requested_limit - len(rows) if requested_limit is not None else page_size
		if remaining <= 0:
			break
		current_page_size = min(page_size, remaining)
		page_params = _merge_params(
			params,
			[("limit", str(current_page_size)), ("offset", str(offset))],
		)
		page = _supabase_get(resource, page_params)
		rows.extend(page)
		if len(page) < current_page_size:
			break
		offset += current_page_size
	return rows


def _normalize_store_key(value: str | None) -> str:
	text = str(value or "").strip().lower().replace("’", "'")
	text = " ".join(text.split())
	return text


@lru_cache(maxsize=1)
def _load_store_mapping() -> dict[str, dict[str, Any]]:
	mapping: dict[str, dict[str, Any]] = {}
	with MAPPING_PATH.open("r", encoding="utf-8", newline="") as handle:
		reader = csv.DictReader(handle)
		for row in reader:
			row["location_id"] = int(row["location_id"])
			for key in (
				_normalize_store_key(row.get("warehouse_name")),
				_normalize_store_key(row.get("warehouse_record_name")),
			):
				if key:
					mapping[key] = row
	return mapping


def _lookup_location_id(warehouse_name: str | None, warehouse_record_name: str | None = None) -> int | None:
	mapping = _load_store_mapping()
	for key in (_normalize_store_key(warehouse_record_name), _normalize_store_key(warehouse_name)):
		if key and key in mapping:
			return int(mapping[key]["location_id"])
	return None


def _to_float(value: Any) -> float:
	try:
		return float(value or 0)
	except (TypeError, ValueError):
		return 0.0


def _to_int(value: Any) -> int:
	try:
		return int(float(value or 0))
	except (TypeError, ValueError):
		return 0


def _to_bool(value: Any) -> bool:
	if isinstance(value, bool):
		return value
	return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _coerce_date(value: str | date | datetime | None, default: date | None = None) -> date:
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date):
		return value
	if isinstance(value, str) and value.strip():
		return date.fromisoformat(value[:10])
	if default is not None:
		return default
	raise ValueError("Date is required")


def _default_date_range() -> tuple[date, date]:
	today_manila = datetime.now(timezone.utc).astimezone(MANILA_TZ).date()
	end_day = today_manila - timedelta(days=1)
	start_day = end_day - timedelta(days=13)
	return start_day, end_day


def _resolve_date_range(start_date: str | None, end_date: str | None) -> tuple[date, date]:
	default_start, default_end = _default_date_range()
	start_day = _coerce_date(start_date, default_start)
	end_day = _coerce_date(end_date, default_end)
	if start_day > end_day:
		raise _validation_error_class()("start_date cannot be after end_date")
	return start_day, end_day


def _parse_stores_param(stores: list[str] | str | None) -> list[str]:
	if stores is None:
		return []
	if isinstance(stores, list):
		return [str(item).strip() for item in stores if str(item).strip()]
	if isinstance(stores, str):
		text = stores.strip()
		if not text:
			return []
		try:
			payload = json.loads(text)
			if isinstance(payload, list):
				return [str(item).strip() for item in payload if str(item).strip()]
		except json.JSONDecodeError:
			pass
		return [part.strip() for part in text.split(",") if part.strip()]
	return []


def _get_warehouse_rows(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
	return frappe.get_all(
		"Warehouse",
		filters=filters or {},
		fields=["name", "warehouse_name", "company", "custom_area_supervisor"],
		order_by="warehouse_name",
	)


def _filter_sales_warehouses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	filtered = []
	for row in rows:
		location_id = _lookup_location_id(row.get("warehouse_name"), row.get("name"))
		if not location_id:
			continue
		filtered.append(
			{
				"warehouse": row.get("name"),
				"warehouse_name": row.get("warehouse_name") or row.get("name"),
				"company": row.get("company"),
				"location_id": location_id,
			}
		)
	return filtered


def _find_store_supervisor_warehouse(user: str) -> list[dict[str, Any]]:
	branch = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "branch")
	if not branch:
		return []
	rows = _get_warehouse_rows({"warehouse_name": branch, "is_group": 0, "disabled": 0})
	if not rows:
		rows = _get_warehouse_rows({"name": branch, "is_group": 0, "disabled": 0})
	return _filter_sales_warehouses(rows)


def _resolve_allowed_store_scope(user: str | None = None) -> dict[str, Any]:
	if _guest_user():
		frappe.throw(_("Not authenticated"), _permission_error_class())

	user = user or _current_user()
	roles = _get_roles(user)
	if not roles.intersection(ALLOWED_ROLES):
		frappe.throw(_("You do not have access to the Sales Dashboard."), _permission_error_class())

	role_label = None
	warehouse_rows: list[dict[str, Any]] = []

	if roles.intersection({ROLE_ADMINISTRATOR, ROLE_SYSTEM_MANAGER}):
		role_label = ROLE_SYSTEM_MANAGER if ROLE_SYSTEM_MANAGER in roles else ROLE_ADMINISTRATOR
		warehouse_rows = _get_warehouse_rows({"is_group": 0, "disabled": 0})
	elif roles.intersection({ROLE_HQ_USER, ROLE_HQ_FINANCE, ROLE_ACCOUNTS_MANAGER}):
		role_label = (
			ROLE_HQ_FINANCE
			if ROLE_HQ_FINANCE in roles
			else ROLE_ACCOUNTS_MANAGER
			if ROLE_ACCOUNTS_MANAGER in roles
			else ROLE_HQ_USER
		)
		warehouse_rows = _get_warehouse_rows({"is_group": 0, "disabled": 0})
	elif ROLE_AREA_SUPERVISOR in roles:
		role_label = ROLE_AREA_SUPERVISOR
		warehouse_rows = _get_warehouse_rows({"custom_area_supervisor": user, "is_group": 0, "disabled": 0})
	elif ROLE_STORE_SUPERVISOR in roles:
		role_label = ROLE_STORE_SUPERVISOR
		warehouse_rows = _find_store_supervisor_warehouse(user)
		return {
			"user": user,
			"role": role_label,
			"roles": sorted(roles),
			"stores": warehouse_rows,
		}
	elif ROLE_SALES_STAKEHOLDER in roles:
		role_label = ROLE_SALES_STAKEHOLDER
		assigned = frappe.get_all(
			"BEI Sales Dashboard Store Access",
			filters={"user": user},
			fields=["warehouse"],
		)
		assigned_names = [row["warehouse"] for row in assigned if row.get("warehouse")]
		if assigned_names:
			warehouse_rows = _get_warehouse_rows(
				{"name": ["in", assigned_names], "is_group": 0, "disabled": 0}
			)
		else:
			warehouse_rows = []

	if role_label != ROLE_STORE_SUPERVISOR:
		warehouse_rows = _filter_sales_warehouses(warehouse_rows)

	unique: dict[str, dict[str, Any]] = {}
	for row in warehouse_rows:
		unique[row["warehouse"]] = row

	return {
		"user": user,
		"role": role_label,
		"roles": sorted(roles),
		"stores": sorted(unique.values(), key=lambda row: row["warehouse_name"]),
	}


def _selected_scope(requested_stores: list[str], user: str | None = None) -> dict[str, Any]:
	scope = _resolve_allowed_store_scope(user=user)
	allowed_stores = scope["stores"]
	allowed_keys: dict[str, dict[str, Any]] = {}
	for store in allowed_stores:
		for key in (store["warehouse"], store["warehouse_name"], str(store["location_id"])):
			allowed_keys[_normalize_store_key(key)] = store

	if requested_stores:
		selected: list[dict[str, Any]] = []
		seen: set[str] = set()
		for requested in requested_stores:
			match = allowed_keys.get(_normalize_store_key(requested))
			if not match:
				frappe.throw(
					f"Store selection '{requested}' is outside your allowed scope.",
					_permission_error_class(),
				)
			if match["warehouse"] in seen:
				continue
			selected.append(match)
			seen.add(match["warehouse"])
	else:
		selected = allowed_stores

	scope["selected_stores"] = selected
	return scope


def _allowed_view_modes(roles: set[str]) -> list[str]:
	modes = ["canonical"]
	if roles.intersection(OPS_ALLOWED_ROLES):
		modes.append("ops_matched")
	return modes


def _get_weather_max_business_date(location_ids: list[int]) -> str | None:
	if not location_ids:
		return None
	location_filter = ",".join(str(location_id) for location_id in sorted(set(location_ids)))
	rows = _supabase_get_all(
		"daily_weather",
		[
			("select", "business_date"),
			("location_id", f"in.({location_filter})"),
			("order", "business_date.desc"),
			("limit", "1"),
		],
		page_size=1,
	)
	return str(rows[0]["business_date"]) if rows else None


def _get_foodpanda_cups_max_business_date(location_ids: list[int]) -> str | None:
	if not location_ids:
		return None
	location_filter = ",".join(str(location_id) for location_id in sorted(set(location_ids)))
	rows = _supabase_get_all(
		"foodpanda_daily_item_metrics",
		[
			("select", "business_date"),
			("location_id", f"in.({location_filter})"),
			("order", "business_date.desc"),
			("limit", "1"),
		],
		page_size=1,
	)
	return str(rows[0]["business_date"]) if rows else None


def _get_resource_max_business_date(resource: str, filter_key: str, filter_value: str) -> str | None:
	rows = _supabase_get_all(
		resource,
		[
			("select", "business_date"),
			(filter_key, filter_value),
			("order", "business_date.desc"),
			("limit", "1"),
		],
		page_size=1,
	)
	return str(rows[0]["business_date"]) if rows else None


def _build_freshness(location_ids: list[int]) -> dict[str, Any]:
	return {
		"pos_max_business_date": _get_resource_max_business_date("pos_orders", "payment_status", "eq.PAID"),
		"web_max_business_date": _get_resource_max_business_date(
			"web_orders", "order_status_raw", "eq.Completed"
		),
		"foodpanda_max_business_date": _get_resource_max_business_date(
			"foodpanda_orders", "order_status", "ilike.delivered"
		),
		"foodpanda_cups_max_business_date": _get_foodpanda_cups_max_business_date(location_ids),
		"weather_max_business_date": _get_weather_max_business_date(location_ids),
	}


def _build_data_quality_warnings(end_day: date, freshness: dict[str, Any]) -> list[str]:
	warnings: list[str] = []
	foodpanda_cups_max = freshness.get("foodpanda_cups_max_business_date")
	weather_max = freshness.get("weather_max_business_date")

	if foodpanda_cups_max and str(foodpanda_cups_max) < end_day.isoformat():
		warnings.append(
			f"FoodPanda cups are validated only through {foodpanda_cups_max}; total cups may be understated beyond that date."
		)

	if weather_max and str(weather_max) < end_day.isoformat():
		warnings.append(
			f"Weather context is validated only through {weather_max}; later dates will not have complete weather overlays."
		)

	return warnings


def _build_access_context(scope: dict[str, Any]) -> dict[str, Any]:
	location_ids = [store["location_id"] for store in scope["stores"]]
	roles = set(scope["roles"])
	weather_max = _get_weather_max_business_date(location_ids)
	return {
		"role": scope["role"],
		"allowed_stores": scope["stores"],
		"default_store_ids": [store["warehouse"] for store in scope["stores"]],
		"allowed_view_modes": _allowed_view_modes(roles),
		"can_export": bool(scope["stores"]),
		"can_group_by_area": scope["role"] in ALL_STORE_ROLES | {ROLE_AREA_SUPERVISOR},
		"weather_coverage_summary": {
			"covered_store_count": len(location_ids),
			"uncovered_store_count": 0,
			"weather_max_business_date": weather_max,
		},
		"calendar_source": CALENDAR_SOURCE,
	}


def _query_daily_rows(start_day: date, end_day: date, location_ids: list[int]) -> list[dict[str, Any]]:
	if not location_ids:
		return []
	allowed_location_ids = set(location_ids)
	rows = _supabase_get_all(
		SUPABASE_DAILY_VIEW,
		[
			("select", DAILY_METRIC_SELECT),
			("business_date", f"gte.{start_day.isoformat()}"),
			("business_date", f"lte.{end_day.isoformat()}"),
			("order", "business_date.asc,store_name.asc"),
		],
	)
	return [row for row in rows if _to_int(row.get("location_id")) in allowed_location_ids]


def _query_weather_rows(start_day: date, end_day: date, location_ids: list[int]) -> list[dict[str, Any]]:
	if not location_ids:
		return []
	location_filter = ",".join(str(location_id) for location_id in sorted(set(location_ids)))
	return _supabase_get_all(
		"daily_weather",
		[
			("select", WEATHER_SELECT),
			("business_date", f"gte.{start_day.isoformat()}"),
			("business_date", f"lte.{end_day.isoformat()}"),
			("location_id", f"in.({location_filter})"),
			("order", "business_date.asc"),
		],
	)


def _aggregate_sales(rows: list[dict[str, Any]]) -> dict[str, Any]:
	day_count = len({str(row.get("business_date")) for row in rows})
	totals = {
		"gross_sales": 0.0,
		"net_sales_with_vat": 0.0,
		"net_sales_without_vat": 0.0,
		"cups_sold": 0,
		"transactions": 0,
		"pickup_sales": 0.0,
		"website_sales": 0.0,
		"website_sales_without_vat": 0.0,
		"website_cod_orders": 0,
		"website_cod_sales_with_vat": 0.0,
		"website_cod_sales_without_vat": 0.0,
		"foodpanda_sales": 0.0,
		"foodpanda_sales_without_vat": 0.0,
	}
	for row in rows:
		totals["gross_sales"] += _to_float(row.get("total_gross_sales"))
		totals["net_sales_with_vat"] += _to_float(row.get("total_gross_sales"))
		totals["net_sales_without_vat"] += _to_float(row.get("total_net_sales_without_vat"))
		totals["cups_sold"] += _to_int(row.get("cups_sold"))
		totals["transactions"] += _to_int(row.get("transactions"))
		totals["pickup_sales"] += _to_float(row.get("pos_gross_sales"))
		totals["website_sales"] += _to_float(row.get("website_non_cod_gross_sales"))
		totals["website_sales_without_vat"] += _to_float(row.get("website_non_cod_net_sales_without_vat"))
		totals["website_cod_orders"] += _to_int(row.get("web_cod_orders"))
		totals["website_cod_sales_with_vat"] += _to_float(row.get("web_cod_gross_sales"))
		totals["website_cod_sales_without_vat"] += _to_float(row.get("web_cod_net_sales_without_vat"))
		totals["foodpanda_sales"] += _to_float(row.get("foodpanda_subtotal"))
		totals["foodpanda_sales_without_vat"] += _to_float(row.get("foodpanda_vat_deducted_sales"))

	transactions = totals["transactions"]
	cups = totals["cups_sold"]
	totals["average_daily_sales"] = round(totals["gross_sales"] / day_count, 2) if day_count else 0.0
	totals["average_guest_check"] = round(totals["gross_sales"] / transactions, 2) if transactions else 0.0
	totals["cups_per_transaction"] = round(cups / transactions, 2) if transactions else 0.0
	totals["day_count"] = day_count

	for key, value in list(totals.items()):
		if isinstance(value, float):
			totals[key] = round(value, 2)
	return totals


def _shift_range(start_day: date, end_day: date, delta_days: int) -> tuple[date, date]:
	return start_day - timedelta(days=delta_days), end_day - timedelta(days=delta_days)


def _build_comparisons(
	start_day: date,
	end_day: date,
	location_ids: list[int],
	current: dict[str, Any],
) -> dict[str, Any]:
	span_days = (end_day - start_day).days + 1
	prev_start, prev_end = _shift_range(start_day, end_day, span_days)
	prev_rows = _query_daily_rows(prev_start, prev_end, location_ids)
	prev = _aggregate_sales(prev_rows) if prev_rows else {}
	last_year_rows = _query_daily_rows(
		start_day - timedelta(days=365), end_day - timedelta(days=365), location_ids
	)
	last_year = _aggregate_sales(last_year_rows) if last_year_rows else {}

	def delta_payload(baseline: dict[str, Any]) -> dict[str, Any]:
		if not baseline:
			return {"available": False}
		base_sales = _to_float(baseline.get("gross_sales"))
		current_sales = _to_float(current.get("gross_sales"))
		delta = round(current_sales - base_sales, 2)
		pct = round((delta / base_sales) * 100, 2) if base_sales else None
		return {
			"available": True,
			"gross_sales_delta": delta,
			"gross_sales_delta_pct": pct,
			"baseline_gross_sales": base_sales,
		}

	return {
		"previous_period": delta_payload(prev),
		"same_period_last_year": delta_payload(last_year),
	}


def _empty_comparisons() -> dict[str, dict[str, bool]]:
	return {
		"previous_period": {"available": False},
		"same_period_last_year": {"available": False},
	}


def _calendar_map_for_scope(stores: list[dict[str, Any]], dates: set[str]) -> dict[str, dict[str, Any]]:
	company_to_holiday_list: dict[str, str] = {}
	for store in stores:
		company = str(store.get("company") or "").strip()
		if company and company not in company_to_holiday_list:
			holiday_list = frappe.db.get_value("Company", company, "default_holiday_list")
			if holiday_list:
				company_to_holiday_list[company] = holiday_list

	holiday_maps: dict[str, dict[str, str]] = {}
	for holiday_list_name in set(company_to_holiday_list.values()):
		try:
			doc = frappe.get_doc("Holiday List", holiday_list_name)
		except Exception:
			continue
		holiday_maps[holiday_list_name] = {
			str(row.holiday_date): str(row.description or row.weekly_off or "").strip()
			for row in getattr(doc, "holidays", []) or []
			if getattr(row, "holiday_date", None)
		}

	calendar: dict[str, dict[str, Any]] = {}
	for day_text in sorted(dates):
		day_obj = date.fromisoformat(day_text)
		holiday_names: list[str] = []
		holiday_lists: list[str] = []
		for holiday_list_name in set(company_to_holiday_list.values()):
			holiday_name = holiday_maps.get(holiday_list_name, {}).get(day_text)
			if holiday_name:
				holiday_names.append(holiday_name)
				holiday_lists.append(holiday_list_name)
		calendar[day_text] = {
			"business_date": day_text,
			"day_of_week": day_obj.strftime("%A"),
			"is_weekend": day_obj.weekday() >= 5,
			"is_holiday": bool(holiday_names),
			"holiday_name": ", ".join(sorted({name for name in holiday_names if name})) or None,
			"holiday_list_used": ", ".join(sorted(set(holiday_lists))) or None,
		}
	return calendar


def _weather_by_store_day(rows: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
	result: dict[tuple[int, str], dict[str, Any]] = {}
	for row in rows:
		key = (_to_int(row.get("location_id")), str(row.get("business_date")))
		result[key] = row
	return result


def _aggregate_daily_series(
	stores: list[dict[str, Any]],
	sales_rows: list[dict[str, Any]],
	weather_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
	weather_map = _weather_by_store_day(weather_rows)
	calendar_map = _calendar_map_for_scope(stores, {str(row.get("business_date")) for row in sales_rows})
	day_buckets: dict[str, dict[str, Any]] = {}
	for row in sales_rows:
		day_key = str(row.get("business_date"))
		bucket = day_buckets.setdefault(
			day_key,
			{
				"business_date": day_key,
				"gross_sales": 0.0,
				"net_sales_with_vat": 0.0,
				"net_sales_without_vat": 0.0,
				"cups_sold": 0,
				"transactions": 0,
				"weather_rows": [],
			},
		)
		bucket["gross_sales"] += _to_float(row.get("total_gross_sales"))
		bucket["net_sales_with_vat"] += _to_float(row.get("total_gross_sales"))
		bucket["net_sales_without_vat"] += _to_float(row.get("total_net_sales_without_vat"))
		bucket["cups_sold"] += _to_int(row.get("cups_sold"))
		bucket["transactions"] += _to_int(row.get("transactions"))
		weather_row = weather_map.get((_to_int(row.get("location_id")), day_key))
		if weather_row:
			bucket["weather_rows"].append(weather_row)

	series: list[dict[str, Any]] = []
	for day_key in sorted(day_buckets):
		bucket = day_buckets[day_key]
		weather_group = bucket.pop("weather_rows")
		calendar = calendar_map.get(day_key, {})
		if weather_group:
			description = Counter(
				str(item.get("weather_description") or "").strip()
				for item in weather_group
				if item.get("weather_description")
			).most_common(1)
			impact = Counter(
				str(item.get("business_impact") or "").strip()
				for item in weather_group
				if item.get("business_impact")
			).most_common(1)
			bucket.update(
				{
					"avg_temperature": round(
						sum(_to_float(item.get("avg_temperature")) for item in weather_group)
						/ len(weather_group),
						2,
					),
					"max_temperature": round(
						max(_to_float(item.get("max_temperature")) for item in weather_group), 2
					),
					"min_temperature": round(
						min(_to_float(item.get("min_temperature")) for item in weather_group), 2
					),
					"total_precipitation": round(
						sum(_to_float(item.get("total_precipitation")) for item in weather_group), 2
					),
					"weather_description": description[0][0] if description else None,
					"business_impact": impact[0][0] if impact else None,
					"is_rainy": any(bool(item.get("is_rainy")) for item in weather_group)
					or sum(_to_float(item.get("total_precipitation")) for item in weather_group) > 0,
					"weather_coverage_count": len(weather_group),
				}
			)
		else:
			bucket.update(
				{
					"avg_temperature": None,
					"max_temperature": None,
					"min_temperature": None,
					"total_precipitation": None,
					"weather_description": None,
					"business_impact": None,
					"is_rainy": False,
					"weather_coverage_count": 0,
				}
			)
		bucket["average_guest_check"] = (
			round(bucket["gross_sales"] / bucket["transactions"], 2) if bucket["transactions"] else 0.0
		)
		bucket["cups_per_transaction"] = (
			round(bucket["cups_sold"] / bucket["transactions"], 2) if bucket["transactions"] else 0.0
		)
		bucket.update(calendar)
		for key in ("gross_sales", "net_sales_with_vat", "net_sales_without_vat"):
			bucket[key] = round(bucket[key], 2)
		series.append(bucket)
	return series


def _build_group_stat(rows: list[dict[str, Any]]) -> dict[str, Any]:
	if not rows:
		return {"sample_size": 0}
	return {
		"sample_size": len(rows),
		"average_gross_sales": round(sum(_to_float(row.get("gross_sales")) for row in rows) / len(rows), 2),
		"average_cups_sold": round(sum(_to_int(row.get("cups_sold")) for row in rows) / len(rows), 2),
		"average_transactions": round(sum(_to_int(row.get("transactions")) for row in rows) / len(rows), 2),
	}


def _build_weather_context(series: list[dict[str, Any]]) -> dict[str, Any]:
	return {
		"not_enough_history": len(series) < 7,
		"groups": {
			"rainy": _build_group_stat([row for row in series if row.get("is_rainy")]),
			"dry": _build_group_stat([row for row in series if not row.get("is_rainy")]),
			"weekend": _build_group_stat([row for row in series if row.get("is_weekend")]),
			"weekday": _build_group_stat([row for row in series if not row.get("is_weekend")]),
			"holiday": _build_group_stat([row for row in series if row.get("is_holiday")]),
			"non_holiday": _build_group_stat([row for row in series if not row.get("is_holiday")]),
			"hot": _build_group_stat(
				[
					row
					for row in series
					if row.get("avg_temperature") is not None and _to_float(row.get("avg_temperature")) >= 32
				]
			),
			"high_precipitation": _build_group_stat(
				[
					row
					for row in series
					if row.get("total_precipitation") is not None
					and _to_float(row.get("total_precipitation")) >= 10
				]
			),
		},
	}


def _is_ops_scope_calibrated(
	view_mode: str,
	start_day: date,
	end_day: date,
	selected_location_ids: list[int],
	allowed_store_count: int,
) -> bool:
	if view_mode != "ops_matched":
		return False
	return (
		start_day.isoformat() == OPS_WW10_REFERENCE["start_date"]
		and end_day.isoformat() == OPS_WW10_REFERENCE["end_date"]
		and len(selected_location_ids) == allowed_store_count
	)


def _build_mode_state(
	view_mode: str, start_day: date, end_day: date, scope: dict[str, Any]
) -> dict[str, Any]:
	selected_location_ids = [store["location_id"] for store in scope["selected_stores"]]
	is_calibrated = _is_ops_scope_calibrated(
		view_mode,
		start_day,
		end_day,
		selected_location_ids,
		len(scope["stores"]),
	)
	if view_mode == "canonical":
		return {"view_mode": view_mode, "supported": True, "label": "Canonical warehouse"}
	if is_calibrated:
		return {
			"view_mode": view_mode,
			"supported": True,
			"label": "Ops-matched",
			"calibration_status": "screenshot_calibrated",
			"source": OPS_WW10_REFERENCE["source"],
		}
	return {
		"view_mode": view_mode,
		"supported": False,
		"label": "Ops-matched",
		"calibration_status": "unsupported_scope",
		"message": "Ops-matched mode is currently certified only for the full-chain WW10 window.",
	}


def _build_ops_summary() -> dict[str, Any]:
	return {
		"gross_sales": OPS_WW10_REFERENCE["gross_sales"],
		"net_sales": OPS_WW10_REFERENCE["net_sales"],
		"pickup_sales": OPS_WW10_REFERENCE["pickup_sales"],
		"website_sales": OPS_WW10_REFERENCE["website_sales"],
		"foodpanda_sales": OPS_WW10_REFERENCE["foodpanda_sales"],
		"cups_sold": OPS_WW10_REFERENCE["cups_sold"],
		"transactions": OPS_WW10_REFERENCE["transactions"],
	}


def _build_store_rankings(
	scope: dict[str, Any],
	sales_rows: list[dict[str, Any]],
	weather_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
	by_location: dict[int, dict[str, Any]] = {}
	weather_map = _weather_by_store_day(weather_rows)
	store_lookup = {store["location_id"]: store for store in scope["selected_stores"]}
	for row in sales_rows:
		location_id = _to_int(row.get("location_id"))
		store_row = by_location.setdefault(
			location_id,
			{
				"location_id": location_id,
				"warehouse": store_lookup.get(location_id, {}).get("warehouse"),
				"warehouse_name": store_lookup.get(location_id, {}).get("warehouse_name")
				or row.get("store_name"),
				"gross_sales": 0.0,
				"net_sales_without_vat": 0.0,
				"cups_sold": 0,
				"transactions": 0,
				"rainy_days": 0,
				"weather_covered_days": 0,
			},
		)
		store_row["gross_sales"] += _to_float(row.get("total_gross_sales"))
		store_row["net_sales_without_vat"] += _to_float(row.get("total_net_sales_without_vat"))
		store_row["cups_sold"] += _to_int(row.get("cups_sold"))
		store_row["transactions"] += _to_int(row.get("transactions"))
		weather_row = weather_map.get((location_id, str(row.get("business_date"))))
		if weather_row:
			store_row["weather_covered_days"] += 1
			if bool(weather_row.get("is_rainy")) or _to_float(weather_row.get("total_precipitation")) > 0:
				store_row["rainy_days"] += 1
	for row in by_location.values():
		row["gross_sales"] = round(row["gross_sales"], 2)
		row["net_sales_without_vat"] = round(row["net_sales_without_vat"], 2)
		row["average_guest_check"] = (
			round(row["gross_sales"] / row["transactions"], 2) if row["transactions"] else 0.0
		)
		row["cups_per_transaction"] = (
			round(row["cups_sold"] / row["transactions"], 2) if row["transactions"] else 0.0
		)
	return sorted(by_location.values(), key=lambda row: row["gross_sales"], reverse=True)


def _build_export_rows(
	scope: dict[str, Any],
	series: list[dict[str, Any]],
	sales_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
	daily_lookup = {row["business_date"]: row for row in series}
	location_lookup = {store["location_id"]: store for store in scope["selected_stores"]}
	rows: list[dict[str, Any]] = []
	for row in sales_rows:
		day_key = str(row.get("business_date"))
		store_meta = location_lookup.get(_to_int(row.get("location_id")), {})
		day_meta = daily_lookup.get(day_key, {})
		rows.append(
			{
				"business_date": day_key,
				"warehouse": store_meta.get("warehouse"),
				"warehouse_name": store_meta.get("warehouse_name") or row.get("store_name"),
				"location_id": _to_int(row.get("location_id")),
				"gross_sales": round(_to_float(row.get("total_gross_sales")), 2),
				"net_sales_without_vat": round(_to_float(row.get("total_net_sales_without_vat")), 2),
				"cups_sold": _to_int(row.get("cups_sold")),
				"transactions": _to_int(row.get("transactions")),
				"avg_temperature": day_meta.get("avg_temperature"),
				"total_precipitation": day_meta.get("total_precipitation"),
				"weather_description": day_meta.get("weather_description"),
				"is_rainy": day_meta.get("is_rainy"),
				"is_weekend": day_meta.get("is_weekend"),
				"is_holiday": day_meta.get("is_holiday"),
				"holiday_name": day_meta.get("holiday_name"),
			}
		)
	return rows


@frappe.whitelist()
def get_sales_dashboard_access_context() -> dict[str, Any]:
	scope = _resolve_allowed_store_scope()
	return _build_access_context(scope)


@frappe.whitelist()
def get_sales_dashboard_summary(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
	include_comparisons: str | int | bool = False,
) -> dict[str, Any]:
	scope = _selected_scope(_parse_stores_param(stores))
	start_day, end_day = _resolve_date_range(start_date, end_date)
	selected_location_ids = [store["location_id"] for store in scope["selected_stores"]]
	sales_rows = _query_daily_rows(start_day, end_day, selected_location_ids)
	summary = _aggregate_sales(sales_rows)
	mode_state = _build_mode_state(view_mode, start_day, end_day, scope)
	freshness = _build_freshness(selected_location_ids)
	freshness["data_quality_warnings"] = _build_data_quality_warnings(end_day, freshness)
	response: dict[str, Any] = {
		"scope": {
			"selected_stores": scope["selected_stores"],
			"selected_location_ids": selected_location_ids,
			"channel": channel,
		},
		"date_window": {"start_date": start_day.isoformat(), "end_date": end_day.isoformat()},
		"mode_state": mode_state,
		"summary": summary,
		"freshness": freshness,
		"comparisons": _build_comparisons(start_day, end_day, selected_location_ids, summary)
		if _to_bool(include_comparisons)
		else _empty_comparisons(),
	}
	if view_mode == "ops_matched" and mode_state.get("supported"):
		response["ops_summary"] = _build_ops_summary()
	return response


@frappe.whitelist()
def get_sales_dashboard_daily_series(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
) -> dict[str, Any]:
	scope = _selected_scope(_parse_stores_param(stores))
	start_day, end_day = _resolve_date_range(start_date, end_date)
	selected_location_ids = [store["location_id"] for store in scope["selected_stores"]]
	sales_rows = _query_daily_rows(start_day, end_day, selected_location_ids)
	weather_rows = _query_weather_rows(start_day, end_day, selected_location_ids)
	series = _aggregate_daily_series(scope["selected_stores"], sales_rows, weather_rows)
	return {
		"scope": {"selected_stores": scope["selected_stores"], "channel": channel},
		"date_window": {"start_date": start_day.isoformat(), "end_date": end_day.isoformat()},
		"mode_state": _build_mode_state(view_mode, start_day, end_day, scope),
		"series": series,
	}


@frappe.whitelist()
def get_sales_dashboard_channel_mix(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
) -> dict[str, Any]:
	scope = _selected_scope(_parse_stores_param(stores))
	start_day, end_day = _resolve_date_range(start_date, end_date)
	selected_location_ids = [store["location_id"] for store in scope["selected_stores"]]
	summary = _aggregate_sales(_query_daily_rows(start_day, end_day, selected_location_ids))
	return {
		"scope": {"selected_stores": scope["selected_stores"], "channel": channel},
		"date_window": {"start_date": start_day.isoformat(), "end_date": end_day.isoformat()},
		"mode_state": _build_mode_state(view_mode, start_day, end_day, scope),
		"channels": [
			{
				"key": "pickup",
				"label": "Pickup Sales",
				"sales_with_vat": summary["pickup_sales"],
				"sales_without_vat": summary["pickup_sales"],
			},
			{
				"key": "website",
				"label": "Website Sales (Non-COD)",
				"sales_with_vat": summary["website_sales"],
				"sales_without_vat": summary["website_sales_without_vat"],
			},
			{
				"key": "website_cod",
				"label": "Website COD",
				"orders": summary["website_cod_orders"],
				"sales_with_vat": summary["website_cod_sales_with_vat"],
				"sales_without_vat": summary["website_cod_sales_without_vat"],
			},
			{
				"key": "foodpanda",
				"label": "FoodPanda",
				"sales_with_vat": summary["foodpanda_sales"],
				"sales_without_vat": summary["foodpanda_sales_without_vat"],
			},
		],
	}


@frappe.whitelist()
def get_sales_dashboard_store_rankings(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
) -> dict[str, Any]:
	scope = _selected_scope(_parse_stores_param(stores))
	start_day, end_day = _resolve_date_range(start_date, end_date)
	selected_location_ids = [store["location_id"] for store in scope["selected_stores"]]
	sales_rows = _query_daily_rows(start_day, end_day, selected_location_ids)
	weather_rows = _query_weather_rows(start_day, end_day, selected_location_ids)
	return {
		"scope": {"selected_stores": scope["selected_stores"], "channel": channel},
		"date_window": {"start_date": start_day.isoformat(), "end_date": end_day.isoformat()},
		"mode_state": _build_mode_state(view_mode, start_day, end_day, scope),
		"stores": _build_store_rankings(scope, sales_rows, weather_rows),
	}


@frappe.whitelist()
def get_sales_dashboard_weather_context(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
) -> dict[str, Any]:
	scope = _selected_scope(_parse_stores_param(stores))
	start_day, end_day = _resolve_date_range(start_date, end_date)
	selected_location_ids = [store["location_id"] for store in scope["selected_stores"]]
	sales_rows = _query_daily_rows(start_day, end_day, selected_location_ids)
	weather_rows = _query_weather_rows(start_day, end_day, selected_location_ids)
	series = _aggregate_daily_series(scope["selected_stores"], sales_rows, weather_rows)
	return {
		"scope": {"selected_stores": scope["selected_stores"], "channel": channel},
		"date_window": {"start_date": start_day.isoformat(), "end_date": end_day.isoformat()},
		"mode_state": _build_mode_state(view_mode, start_day, end_day, scope),
		"daily": series,
		"analysis": _build_weather_context(series),
	}


@frappe.whitelist()
def export_sales_dashboard_detail(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
) -> dict[str, Any]:
	scope = _selected_scope(_parse_stores_param(stores))
	start_day, end_day = _resolve_date_range(start_date, end_date)
	selected_location_ids = [store["location_id"] for store in scope["selected_stores"]]
	sales_rows = _query_daily_rows(start_day, end_day, selected_location_ids)
	weather_rows = _query_weather_rows(start_day, end_day, selected_location_ids)
	series = _aggregate_daily_series(scope["selected_stores"], sales_rows, weather_rows)
	export_rows = _build_export_rows(scope, series, sales_rows)

	buffer = io.StringIO()
	fieldnames = [
		"business_date",
		"warehouse",
		"warehouse_name",
		"location_id",
		"gross_sales",
		"net_sales_without_vat",
		"cups_sold",
		"transactions",
		"avg_temperature",
		"total_precipitation",
		"weather_description",
		"is_rainy",
		"is_weekend",
		"is_holiday",
		"holiday_name",
	]
	writer = csv.DictWriter(buffer, fieldnames=fieldnames)
	writer.writeheader()
	writer.writerows(export_rows)
	filename = f"sales_dashboard_detail_{start_day.isoformat()}_{end_day.isoformat()}.csv"

	return {
		"filename": filename,
		"content_type": "text/csv",
		"content": buffer.getvalue(),
		"row_count": len(export_rows),
		"view_mode": view_mode,
		"channel": channel,
	}
