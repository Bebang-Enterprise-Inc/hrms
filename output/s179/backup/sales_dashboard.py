"""Sales intelligence dashboard APIs for my.bebang.ph."""

from __future__ import annotations

from calendar import monthrange
import csv
import io
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

import requests

import frappe

from hrms.utils.sales_location_mapping import lookup_location_id, normalize_store_key
from hrms.utils.sentry import set_backend_observability_context

MANILA_TZ = ZoneInfo("Asia/Manila")

# S176 DD-19: Mosaic channel tagging regime-shift boundary dates.
# Before these dates, FoodPanda/GrabFood orders exist in pos_orders under legacy
# channel labels ('Delivery', 'Unknown', NULL) - they were not retroactively retagged.
# S176 hotfix #3 2026-04-09: cutover bumped 2026-03-26 -> 2026-03-27 after
# live data inspection showed 2026-03-25 and 2026-03-26 were PARTIAL Mosaic days.
_FOODPANDA_MOSAIC_START = date(2026, 3, 27)
_GRABFOOD_MOSAIC_START = date(2026, 4, 1)
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
ALLOWED_ROLES = ALL_STORE_ROLES | {ROLE_AREA_SUPERVISOR, ROLE_STORE_SUPERVISOR, ROLE_SALES_STAKEHOLDER}
CALENDAR_SOURCE = "Company.default_holiday_list"
CANONICAL_VIEW_MODE = "canonical"
SUPABASE_DAILY_VIEW = "sales_dashboard_daily_store_metrics"
SUPABASE_WEATHER_VIEW = "sales_dashboard_weather_daily_features"
SUPABASE_DISCOUNT_VIEW = "discount_investigation_store_day"
SALES_DASHBOARD_CACHE_TTL = 300
SALES_DASHBOARD_FRESHNESS_CACHE_TTL = 300
WEATHER_EFFECT_HISTORY_LOOKBACK_DAYS = 210
WEATHER_EFFECT_MIN_COMPARABLE_HISTORY_DAYS = 56
PROJECTION_MIN_CLOSED_DAYS = 28
PROJECTION_LOOKBACK_CALENDAR_DAYS = 60
RANKING_MIN_SCOPE_STORES = 5
RANKING_MIN_POS_ORIGINAL_GROSS = 20_000.0
DEFAULT_RANKING_MODE = "discount_pct"
ALLOWED_RANKING_MODES = {DEFAULT_RANKING_MODE, "discount_amt"}
RAIN_LIGHT_PEAK_MM = 2.5
RAIN_DISRUPTIVE_PEAK_MM = 7.5
RAIN_DISRUPTIVE_TOTAL_MM = 20.0
RAIN_SUSTAINED_PEAK_MM = 4.0
RAIN_SUSTAINED_TOTAL_MM = 10.0
RAIN_SUSTAINED_HOURS = 6.0
AGGREGATE_STORM_SHARE_THRESHOLD = 0.25

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
		"avg_humidity",
		"max_temperature",
		"min_temperature",
		"avg_temperature",
		"apparent_temperature_max",
		"avg_wind_speed",
		"avg_hourly_wind_speed",
		"max_wind_speed",
		"total_precipitation",
		"precipitation_hours",
		"max_hourly_precipitation",
		"weather_description",
		"weather_code",
		"is_rainy",
		"hourly_backed",
		"hourly_points",
		"temperature_anomaly_vs_28d",
		"temperature_state",
		"rain_severity",
		"wind_disruption_level",
		"storm_flag",
		"service_window_weather_summary_lunch",
		"service_window_weather_summary_dinner",
		"business_impact",
		"synced_at",
	]
)
DISCOUNT_SELECT = ",".join(
	[
		"location_id",
		"business_date",
		"store_name",
		"pos_original_gross_sales",
		"pos_total_discounts",
		"sc_recorded_discount_amount",
		"pwd_recorded_discount_amount",
	]
)


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


def _canonical_view_mode(_view_mode: str | None = None) -> str:
	return CANONICAL_VIEW_MODE


def _parse_ranking_mode(value: str | None = None) -> str:
	if not value:
		return DEFAULT_RANKING_MODE
	normalized = str(value).strip().lower()
	return normalized if normalized in ALLOWED_RANKING_MODES else DEFAULT_RANKING_MODE


def _pct(numerator: float, denominator: float) -> float | None:
	if denominator <= 0:
		return None
	return _round_half_up((numerator / denominator) * 100)


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


def _cache_available() -> bool:
	return callable(getattr(frappe, "cache", None))


def _cache_get_or_set(cache_key: str, builder, expires_in_sec: int) -> Any:
	if not _cache_available():
		return builder()
	cache = frappe.cache()
	cached = cache.get_value(cache_key)
	if cached is not None:
		return cached
	value = builder()
	cache.set_value(cache_key, value, expires_in_sec=expires_in_sec)
	return value


def _location_scope_key(location_ids: list[int]) -> str:
	return ",".join(str(location_id) for location_id in sorted(set(location_ids)))


def _sales_dashboard_cache_key(
	prefix: str,
	location_ids: list[int],
	start_day: date | None = None,
	end_day: date | None = None,
	view_mode: str | None = None,
	channel: str | None = None,
	include_comparisons: bool | None = None,
	ranking_mode: str | None = None,
) -> str:
	parts = [prefix, _location_scope_key(location_ids)]
	if start_day:
		parts.append(start_day.isoformat())
	if end_day:
		parts.append(end_day.isoformat())
	if view_mode:
		parts.append(view_mode)
	if channel:
		parts.append(channel)
	if include_comparisons is not None:
		parts.append("cmp1" if include_comparisons else "cmp0")
	if ranking_mode:
		parts.append(ranking_mode)
	return "sales_dashboard:" + ":".join(parts)


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


def _round_half_up(value: float, places: int = 2) -> float:
	quant = Decimal("1").scaleb(-places)
	return float(Decimal(str(value or 0)).quantize(quant, rounding=ROUND_HALF_UP))


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
		location_id = lookup_location_id(row.get("warehouse_name"), row.get("name"))
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
		frappe.throw("Not authenticated", _permission_error_class())

	user = user or _current_user()
	roles = _get_roles(user)
	if not roles.intersection(ALLOWED_ROLES):
		frappe.throw("You do not have access to the Sales Dashboard.", _permission_error_class())

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
			allowed_keys[normalize_store_key(key)] = store

	if requested_stores:
		selected: list[dict[str, Any]] = []
		seen: set[str] = set()
		for requested in requested_stores:
			match = allowed_keys.get(normalize_store_key(requested))
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
	_ = roles
	return [CANONICAL_VIEW_MODE]


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
	"""S176 hotfix #6: switched from legacy foodpanda_daily_item_metrics (frozen
	2026-03-15) to Mosaic pos_order_items joined with pos_orders channel=FoodPanda.
	The POS terminal processes all FoodPanda orders, so item-level quantity data
	is available from the same Mosaic sync that provides gross_sales.
	"""
	if not location_ids:
		return None
	# Use pos_orders directly since pos_order_items has no business_date column.
	# The max business_date for FoodPanda orders with items = max FoodPanda order date.
	return _get_resource_boundary_business_date(
		"pos_orders",
		order="business_date.desc",
		location_ids=location_ids,
		extra_params=[
			("channel", "eq.FoodPanda"),
			("payment_status", "eq.PAID"),
		],
	)


def _get_resource_boundary_business_date(
	resource: str,
	*,
	order: str,
	location_ids: list[int] | None = None,
	extra_params: list[tuple[str, Any]] | None = None,
) -> str | None:
	params: list[tuple[str, Any]] = [("select", "business_date")]
	if extra_params:
		params.extend(extra_params)
	if location_ids:
		params.append(("location_id", f"in.({_location_scope_key(location_ids)})"))
	params.extend([("order", order), ("limit", "1")])
	rows = _supabase_get_all(resource, params, page_size=1)
	return str(rows[0]["business_date"]) if rows else None


def _get_resource_max_business_date(
	resource: str,
	filter_key: str,
	filter_value: str,
	location_ids: list[int] | None = None,
) -> str | None:
	return _get_resource_boundary_business_date(
		resource,
		order="business_date.desc",
		location_ids=location_ids,
		extra_params=[(filter_key, filter_value)],
	)


def _get_sales_history_start_date(location_ids: list[int]) -> str | None:
	return _get_resource_boundary_business_date(
		SUPABASE_DAILY_VIEW,
		order="business_date.asc",
		location_ids=location_ids,
	)


def _get_discount_history_start_date(location_ids: list[int]) -> str | None:
	return _get_resource_boundary_business_date(
		SUPABASE_DISCOUNT_VIEW,
		order="business_date.asc",
		location_ids=location_ids,
		extra_params=[("scope", "eq.store")],
	)


def _get_discount_max_business_date(location_ids: list[int]) -> str | None:
	return _get_resource_boundary_business_date(
		SUPABASE_DISCOUNT_VIEW,
		order="business_date.desc",
		location_ids=location_ids,
		extra_params=[("scope", "eq.store")],
	)


def _get_resource_last_sync_at(
	resource: str,
	location_ids: list[int] | None = None,
	extra_params: list[tuple[str, Any]] | None = None,
) -> str | None:
	"""S176 DD-11: fetch MAX(synced_at) for a Supabase resource via PostgREST.

	Uses the existing _supabase_get_all helper. Returns ISO-8601 timestamp string
	with timezone, or None if no rows match.
	"""
	params: list[tuple[str, Any]] = [("select", "synced_at")]
	if extra_params:
		params.extend(extra_params)
	if location_ids:
		params.append(("location_id", f"in.({_location_scope_key(location_ids)})"))
	params.extend([("order", "synced_at.desc"), ("limit", "1")])
	rows = _supabase_get_all(resource, params, page_size=1)
	return str(rows[0]["synced_at"]) if rows and rows[0].get("synced_at") is not None else None


def _build_freshness(location_ids: list[int]) -> dict[str, Any]:
	# S176 DD-21: cache topic bumped from "freshness" -> "freshness_v2" to invalidate
	# all stale cache entries on deploy. Without this, new tiles render "N/A" until
	# the old TTL expires.
	cache_key = _sales_dashboard_cache_key("freshness_v2", location_ids)

	def builder() -> dict[str, Any]:
		return {
			"pos_max_business_date": _get_resource_max_business_date(
				"pos_orders",
				"payment_status",
				"eq.PAID",
				location_ids=location_ids,
			),
			"web_max_business_date": _get_resource_max_business_date(
				"web_orders",
				"order_status_raw",
				"eq.Completed",
				location_ids=location_ids,
			),
			# S176 DD-10: FoodPanda freshness now reads from Mosaic-derived pos_orders
			# channel (single source of truth since S165). The legacy foodpanda_orders
			# Google Sheet ingest was halted 2026-03-31.
			"foodpanda_max_business_date": _get_resource_boundary_business_date(
				"pos_orders",
				order="business_date.desc",
				location_ids=location_ids,
				extra_params=[
					("channel", "eq.FoodPanda"),
					("payment_status", "eq.PAID"),
				],
			),
			# S176 DD-10 / DD-20: legacy Google-Sheet ingest preserved for audit /
			# diagnostic use. Frozen at 2026-03-31. Do NOT surface in primary UI.
			"foodpanda_legacy_sheet_max_business_date": _get_resource_max_business_date(
				"foodpanda_orders",
				"order_status",
				"ilike.delivered",
				location_ids=location_ids,
			),
			# S176 DD-11: GrabFood freshness via Mosaic pos_orders channel tag.
			"grabfood_max_business_date": _get_resource_boundary_business_date(
				"pos_orders",
				order="business_date.desc",
				location_ids=location_ids,
				extra_params=[
					("channel", "eq.GrabFood"),
					("payment_status", "eq.PAID"),
				],
			),
			"foodpanda_cups_max_business_date": _get_foodpanda_cups_max_business_date(location_ids),
			"weather_max_business_date": _get_weather_max_business_date(location_ids),
			"discount_max_business_date": _get_discount_max_business_date(location_ids),
			"sales_history_start_date": _get_sales_history_start_date(location_ids),
			"discount_history_start_date": _get_discount_history_start_date(location_ids),
			# S176 DD-11 / DD-12: Mosaic sync timestamps (ISO-8601 w/ tz) for the
			# "Last synced HH:MM PHT" subtitle rendering on the frontend.
			"mosaic_last_sync_at": _get_resource_last_sync_at(
				"pos_orders",
				location_ids=location_ids,
			),
			"foodpanda_last_sync_at": _get_resource_last_sync_at(
				"pos_orders",
				location_ids=location_ids,
				extra_params=[("channel", "eq.FoodPanda")],
			),
			"grabfood_last_sync_at": _get_resource_last_sync_at(
				"pos_orders",
				location_ids=location_ids,
				extra_params=[("channel", "eq.GrabFood")],
			),
		}

	return _cache_get_or_set(cache_key, builder, SALES_DASHBOARD_FRESHNESS_CACHE_TTL)


def _get_grabfood_channel_totals(
	start_day: date,
	end_day: date,
	location_ids: list[int],
) -> dict[str, Any]:
	"""S176 DD-14 Option A: Python-side aggregation for GrabFood totals.

	The materialized view daily_store_metrics has no grabfood_* columns, so we
	fall back to a direct PostgREST query against pos_orders filtered by
	channel='GrabFood'. Sums are computed client-side in Python.

	Returns keys: grabfood_sales, grabfood_sales_without_vat, grabfood_orders,
	grabfood_avg_ticket. All zeros on empty result set.
	"""
	if not location_ids:
		return {
			"grabfood_sales": 0.0,
			"grabfood_sales_without_vat": 0.0,
			"grabfood_orders": 0,
			"grabfood_avg_ticket": 0.0,
		}
	# S176 hotfix 2026-04-09: pos_orders does NOT have a net_sales_without_vat column
	# (that lives only in the daily_store_metrics materialized view). Derive it as
	# net_sales - vat_amount using columns that actually exist on pos_orders.
	params: list[tuple[str, Any]] = [
		("select", "gross_sales,net_sales,vat_amount"),
		("channel", "eq.GrabFood"),
		("payment_status", "eq.PAID"),
		("business_date", f"gte.{start_day.isoformat()}"),
		("business_date", f"lte.{end_day.isoformat()}"),
		("location_id", f"in.({_location_scope_key(location_ids)})"),
	]
	rows = _supabase_get_all("pos_orders", params, page_size=1000)
	gross_total = sum(_to_float(row.get("gross_sales")) for row in rows)
	net_wo_vat_total = sum(
		_to_float(row.get("net_sales")) - _to_float(row.get("vat_amount")) for row in rows
	)
	order_count = len(rows)
	avg_ticket = _round_half_up(gross_total / order_count) if order_count else 0.0
	return {
		"grabfood_sales": _round_half_up(gross_total),
		"grabfood_sales_without_vat": _round_half_up(net_wo_vat_total),
		"grabfood_orders": order_count,
		"grabfood_avg_ticket": avg_ticket,
	}


def _get_foodpanda_legacy_totals(
	start_day: date,
	end_day: date,
	location_ids: list[int],
) -> dict[str, float | int]:
	"""S176 hotfix #3: pre-cutover FoodPanda totals from legacy Google Sheet."""
	if not location_ids or start_day > end_day:
		return {"gross": 0.0, "net_wo_vat": 0.0, "orders": 0}
	params: list[tuple[str, Any]] = [
		("select", "subtotal,tax_charge"),
		("order_status", "ilike.delivered"),
		("business_date", f"gte.{start_day.isoformat()}"),
		("business_date", f"lte.{end_day.isoformat()}"),
		("location_id", f"in.({_location_scope_key(location_ids)})"),
	]
	rows = _supabase_get_all("foodpanda_orders", params, page_size=1000)
	gross = sum(_to_float(row.get("subtotal")) for row in rows)
	net_wo_vat = sum(
		_to_float(row.get("subtotal")) - _to_float(row.get("tax_charge")) for row in rows
	)
	return {"gross": gross, "net_wo_vat": net_wo_vat, "orders": len(rows)}


def _get_foodpanda_mosaic_totals(
	start_day: date,
	end_day: date,
	location_ids: list[int],
) -> dict[str, float | int]:
	"""S176 hotfix #3: post-cutover FoodPanda totals from pos_orders Mosaic channel."""
	if not location_ids or start_day > end_day:
		return {"gross": 0.0, "net_wo_vat": 0.0, "orders": 0}
	params: list[tuple[str, Any]] = [
		("select", "gross_sales,net_sales,vat_amount"),
		("channel", "eq.FoodPanda"),
		("payment_status", "eq.PAID"),
		("business_date", f"gte.{start_day.isoformat()}"),
		("business_date", f"lte.{end_day.isoformat()}"),
		("location_id", f"in.({_location_scope_key(location_ids)})"),
	]
	rows = _supabase_get_all("pos_orders", params, page_size=1000)
	gross = sum(_to_float(row.get("gross_sales")) for row in rows)
	net_wo_vat = sum(
		_to_float(row.get("net_sales")) - _to_float(row.get("vat_amount")) for row in rows
	)
	return {"gross": gross, "net_wo_vat": net_wo_vat, "orders": len(rows)}


def _get_foodpanda_channel_totals(
	start_day: date,
	end_day: date,
	location_ids: list[int],
) -> dict[str, Any]:
	"""S176 hotfix #3 2026-04-09: date-split FoodPanda aggregation.

	Pre-cutover (< _FOODPANDA_MOSAIC_START = 2026-03-27) reads legacy foodpanda_orders
	(frozen 2026-03-31). Post-cutover reads pos_orders channel=FoodPanda via Mosaic.
	Per CEO direction: prior data from sheet, current/future from Mosaic.
	"""
	if not location_ids:
		return {
			"foodpanda_sales": 0.0,
			"foodpanda_sales_without_vat": 0.0,
			"foodpanda_orders": 0,
			"foodpanda_avg_ticket": 0.0,
		}
	from datetime import timedelta
	cutover = _FOODPANDA_MOSAIC_START
	legacy_end = min(end_day, cutover - timedelta(days=1))
	mosaic_start = max(start_day, cutover)
	legacy = (
		_get_foodpanda_legacy_totals(start_day, legacy_end, location_ids)
		if start_day <= legacy_end
		else {"gross": 0.0, "net_wo_vat": 0.0, "orders": 0}
	)
	mosaic = (
		_get_foodpanda_mosaic_totals(mosaic_start, end_day, location_ids)
		if mosaic_start <= end_day
		else {"gross": 0.0, "net_wo_vat": 0.0, "orders": 0}
	)
	gross_total = legacy["gross"] + mosaic["gross"]
	net_wo_vat_total = legacy["net_wo_vat"] + mosaic["net_wo_vat"]
	order_count = legacy["orders"] + mosaic["orders"]
	avg_ticket = _round_half_up(gross_total / order_count) if order_count else 0.0
	return {
		"foodpanda_sales": _round_half_up(gross_total),
		"foodpanda_sales_without_vat": _round_half_up(net_wo_vat_total),
		"foodpanda_orders": order_count,
		"foodpanda_avg_ticket": avg_ticket,
	}


def _get_channel_cups_from_mosaic(
	start_day: date,
	end_day: date,
	location_ids: list[int],
) -> dict[str, int]:
	"""S176 hotfix #6: per-channel cups (item quantity) from Mosaic pos_order_items.

	Joins pos_order_items.order_id -> pos_orders.id to get channel, then sums
	quantity per channel. The view's pos_cups_sold already includes all channels
	(POS terminal processes everything), but we need the per-channel BREAKDOWN
	for FoodPanda and GrabFood specifically.

	Returns: {foodpanda_cups, grabfood_cups, pos_cups, total_mosaic_cups}.
	"""
	if not location_ids:
		return {"foodpanda_cups": 0, "grabfood_cups": 0, "pos_cups": 0, "total_mosaic_cups": 0}
	# PostgREST cannot do JOINs, so we first get order IDs per channel from
	# pos_orders, then sum quantities from pos_order_items.
	# For FoodPanda:
	fp_order_params: list[tuple[str, Any]] = [
		("select", "id"),
		("channel", "eq.FoodPanda"),
		("payment_status", "eq.PAID"),
		("business_date", f"gte.{start_day.isoformat()}"),
		("business_date", f"lte.{end_day.isoformat()}"),
		("location_id", f"in.({_location_scope_key(location_ids)})"),
	]
	fp_orders = _supabase_get_all("pos_orders", fp_order_params, page_size=1000)
	fp_ids = [int(r["id"]) for r in fp_orders if r.get("id")]
	# For GrabFood:
	gf_order_params: list[tuple[str, Any]] = [
		("select", "id"),
		("channel", "eq.GrabFood"),
		("payment_status", "eq.PAID"),
		("business_date", f"gte.{start_day.isoformat()}"),
		("business_date", f"lte.{end_day.isoformat()}"),
		("location_id", f"in.({_location_scope_key(location_ids)})"),
	]
	gf_orders = _supabase_get_all("pos_orders", gf_order_params, page_size=1000)
	gf_ids = [int(r["id"]) for r in gf_orders if r.get("id")]

	def _sum_cups_for_order_ids(order_ids: list[int]) -> int:
		if not order_ids:
			return 0
		total = 0
		for chunk in [order_ids[i:i+500] for i in range(0, len(order_ids), 500)]:
			id_list = ",".join(str(oid) for oid in chunk)
			params: list[tuple[str, Any]] = [
				("select", "quantity"),
				("order_id", f"in.({id_list})"),
			]
			rows = _supabase_get_all("pos_order_items", params, page_size=1000)
			total += sum(int(r.get("quantity") or 0) for r in rows)
		return total

	fp_cups = _sum_cups_for_order_ids(fp_ids)
	gf_cups = _sum_cups_for_order_ids(gf_ids)
	return {
		"foodpanda_cups": fp_cups,
		"grabfood_cups": gf_cups,
		"pos_cups": 0,  # POS cups = total - fp - gf (computed by caller if needed)
		"total_mosaic_cups": fp_cups + gf_cups,
	}


def _build_data_quality_warnings(start_day: date, end_day: date, freshness: dict[str, Any]) -> list[str]:
	warnings: list[str] = []
	foodpanda_cups_max = freshness.get("foodpanda_cups_max_business_date")
	weather_max = freshness.get("weather_max_business_date")
	effective_end_date = freshness.get("effective_end_date")
	discount_effective_end_date = freshness.get("discount_effective_end_date")
	discount_history_start_date = freshness.get("discount_history_start_date")
	sales_history_start_date = freshness.get("sales_history_start_date")

	if foodpanda_cups_max and str(foodpanda_cups_max) < end_day.isoformat():
		warnings.append(
			f"FoodPanda cups are validated only through {foodpanda_cups_max}; total cups may be understated beyond that date."
		)

	if weather_max and str(weather_max) < end_day.isoformat():
		warnings.append(
			f"Weather context is validated only through {weather_max}; later dates will not have complete weather overlays."
		)

	# S176 DD-19: regime-shift boundary warnings for Mosaic channel tagging.
	if start_day < _FOODPANDA_MOSAIC_START:
		warnings.append(
			"FoodPanda source split at 2026-03-27: earlier dates come from the legacy "
			"foodpanda_orders Google Sheet (frozen 2026-03-31), later dates come from "
			"Mosaic pos_orders. Historical totals are complete."
		)
	if start_day < _GRABFOOD_MOSAIC_START:
		warnings.append(
			"GrabFood channel tagging via Mosaic began 2026-04-01; earlier dates "
			"may under-count GrabFood orders (legacy rows tagged 'Delivery' or 'Unknown')."
		)

	if effective_end_date and str(effective_end_date) < end_day.isoformat():
		warnings.append(
			f"Dashboard analytics were clipped to {effective_end_date}, the latest closed core-sales business date for the selected scope."
		)

	if discount_effective_end_date and str(discount_effective_end_date) < str(effective_end_date or end_day.isoformat()):
		warnings.append(
			f"Projection and discount analytics were clipped to {discount_effective_end_date}, the latest aligned discount business date for the selected scope."
		)

	if discount_history_start_date and start_day.isoformat() < str(discount_history_start_date):
		warnings.append(
			f"Discount analytics start on {discount_history_start_date}; earlier dates in the selected window have partial or unavailable discount visibility."
		)

	if sales_history_start_date:
		last_year_start = start_day - timedelta(days=365)
		if last_year_start.isoformat() < str(sales_history_start_date):
			warnings.append(
				f"Same-period last year is unavailable for this window because verified sales history begins on {sales_history_start_date}."
			)

	return warnings


def _effective_end_day(requested_end_day: date, freshness: dict[str, Any]) -> date:
	core_sales_dates = [
		date.fromisoformat(value)
		for value in (
			freshness.get("pos_max_business_date"),
			freshness.get("web_max_business_date"),
		)
		if value
	]
	if not core_sales_dates:
		return requested_end_day
	return min(requested_end_day, min(core_sales_dates))


def _effective_discount_end_day(sales_effective_end_day: date, freshness: dict[str, Any]) -> date:
	discount_max_business_date = freshness.get("discount_max_business_date")
	if not discount_max_business_date:
		return sales_effective_end_day
	return min(sales_effective_end_day, date.fromisoformat(str(discount_max_business_date)))


def _build_access_context(scope: dict[str, Any]) -> dict[str, Any]:
	location_ids = [store["location_id"] for store in scope["stores"]]
	weather_max = _get_weather_max_business_date(location_ids)
	return {
		"role": scope["role"],
		"allowed_stores": scope["stores"],
		"default_store_ids": [store["warehouse"] for store in scope["stores"]],
		"allowed_view_modes": _allowed_view_modes(set(scope["roles"])),
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
	cache_key = _sales_dashboard_cache_key("daily_rows", location_ids, start_day=start_day, end_day=end_day)

	def builder() -> list[dict[str, Any]]:
		location_filter = _location_scope_key(location_ids)
		return _supabase_get_all(
			SUPABASE_DAILY_VIEW,
			[
				("select", DAILY_METRIC_SELECT),
				("business_date", f"gte.{start_day.isoformat()}"),
				("business_date", f"lte.{end_day.isoformat()}"),
				("location_id", f"in.({location_filter})"),
				("order", "business_date.asc,store_name.asc"),
			],
		)

	return _cache_get_or_set(cache_key, builder, SALES_DASHBOARD_CACHE_TTL)


def _query_weather_rows(start_day: date, end_day: date, location_ids: list[int]) -> list[dict[str, Any]]:
	if not location_ids:
		return []
	cache_key = _sales_dashboard_cache_key("weather_rows", location_ids, start_day=start_day, end_day=end_day)

	def builder() -> list[dict[str, Any]]:
		location_filter = _location_scope_key(location_ids)
		return _supabase_get_all(
			SUPABASE_WEATHER_VIEW,
			[
				("select", WEATHER_SELECT),
				("business_date", f"gte.{start_day.isoformat()}"),
				("business_date", f"lte.{end_day.isoformat()}"),
				("location_id", f"in.({location_filter})"),
				("order", "business_date.asc"),
			],
		)

	return _cache_get_or_set(cache_key, builder, SALES_DASHBOARD_CACHE_TTL)


def _query_discount_rows(start_day: date, end_day: date, location_ids: list[int]) -> list[dict[str, Any]]:
	if not location_ids or end_day < start_day:
		return []
	cache_key = _sales_dashboard_cache_key(
		"discount_rows",
		location_ids,
		start_day=start_day,
		end_day=end_day,
	)

	def builder() -> list[dict[str, Any]]:
		location_filter = _location_scope_key(location_ids)
		return _supabase_get_all(
			SUPABASE_DISCOUNT_VIEW,
			[
				("select", DISCOUNT_SELECT),
				("scope", "eq.store"),
				("business_date", f"gte.{start_day.isoformat()}"),
				("business_date", f"lte.{end_day.isoformat()}"),
				("location_id", f"in.({location_filter})"),
				("order", "business_date.asc,store_name.asc"),
			],
		)

	return _cache_get_or_set(cache_key, builder, SALES_DASHBOARD_CACHE_TTL)


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
		"pickup_sales_without_vat": 0.0,
		"delivery_sales_without_vat": 0.0,
		# S176 DD-14: GrabFood defaults - populated by _get_grabfood_channel_totals()
		# after _aggregate_sales() returns (GrabFood is not in daily_store_metrics view).
		"grabfood_sales": 0.0,
		"grabfood_sales_without_vat": 0.0,
		"grabfood_orders": 0,
		"grabfood_avg_ticket": 0.0,
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
		totals["pickup_sales_without_vat"] += _to_float(row.get("pos_net_sales_without_vat"))
		totals["delivery_sales_without_vat"] += (
			_to_float(row.get("website_non_cod_net_sales_without_vat"))
			+ _to_float(row.get("web_cod_net_sales_without_vat"))
			+ _to_float(row.get("foodpanda_vat_deducted_sales"))
		)

	transactions = totals["transactions"]
	cups = totals["cups_sold"]
	totals["average_daily_sales"] = (
		_round_half_up(totals["net_sales_without_vat"] / day_count) if day_count else 0.0
	)
	totals["average_guest_check"] = (
		_round_half_up(totals["net_sales_without_vat"] / transactions) if transactions else 0.0
	)
	totals["cups_per_transaction"] = _round_half_up(cups / transactions) if transactions else 0.0
	totals["day_count"] = day_count

	for key, value in list(totals.items()):
		if isinstance(value, float):
			totals[key] = _round_half_up(value)
	return totals


def _aggregate_sales_by_business_date(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	by_day: dict[str, float] = {}
	for row in rows:
		day_key = str(row.get("business_date"))
		by_day[day_key] = by_day.get(day_key, 0.0) + _to_float(row.get("total_net_sales_without_vat"))
	return [
		{
			"business_date": business_date,
			"net_sales_without_vat": _round_half_up(net_sales_without_vat),
		}
		for business_date, net_sales_without_vat in sorted(by_day.items())
	]


def _build_projection(
	selected_location_ids: list[int],
	start_day: date,
	projection_effective_end_day: date,
	current_window_rows: list[dict[str, Any]],
) -> dict[str, Any]:
	if not selected_location_ids:
		return {
			"available": False,
			"reason": "No stores selected.",
			"closed_days_considered": 0,
			"minimum_closed_days_required": PROJECTION_MIN_CLOSED_DAYS,
		}
	if projection_effective_end_day < start_day:
		return {
			"available": False,
			"reason": "No closed business days matched the selected window.",
			"closed_days_considered": 0,
			"minimum_closed_days_required": PROJECTION_MIN_CLOSED_DAYS,
		}

	lookback_start_day = projection_effective_end_day - timedelta(days=PROJECTION_LOOKBACK_CALENDAR_DAYS)
	projection_rows = _query_daily_rows(lookback_start_day, projection_effective_end_day, selected_location_ids)
	daily_projection_rows = _aggregate_sales_by_business_date(projection_rows)
	eligible_rows = daily_projection_rows[-PROJECTION_MIN_CLOSED_DAYS:]
	closed_days_considered = len(eligible_rows)

	if closed_days_considered < PROJECTION_MIN_CLOSED_DAYS:
		return {
			"available": False,
			"reason": "Projection requires 28 closed business days.",
			"closed_days_considered": closed_days_considered,
			"minimum_closed_days_required": PROJECTION_MIN_CLOSED_DAYS,
		}

	weighted_total = 0.0
	weight_sum = 0
	for index, row in enumerate(eligible_rows, start=1):
		weighted_total += index * _to_float(row.get("net_sales_without_vat"))
		weight_sum += index

	projected_daily_pace = _round_half_up(weighted_total / weight_sum) if weight_sum else 0.0
	projected_7_day = _round_half_up(projected_daily_pace * 7)
	current_window_summary = _aggregate_sales(current_window_rows)
	current_window_average = _to_float(current_window_summary.get("average_daily_sales"))
	delta_vs_window_average = _round_half_up(projected_daily_pace - current_window_average)
	delta_vs_window_average_pct = (
		_round_half_up((delta_vs_window_average / current_window_average) * 100)
		if current_window_average
		else None
	)

	projected_month_close = None
	month_start = projection_effective_end_day.replace(day=1)
	if start_day == month_start:
		total_days_in_month = monthrange(projection_effective_end_day.year, projection_effective_end_day.month)[1]
		remaining_days = max(total_days_in_month - projection_effective_end_day.day, 0)
		projected_month_close = _round_half_up(
			_to_float(current_window_summary.get("net_sales_without_vat")) + (projected_daily_pace * remaining_days)
		)

	return {
		"available": True,
		"reason": None,
		"closed_days_considered": closed_days_considered,
		"minimum_closed_days_required": PROJECTION_MIN_CLOSED_DAYS,
		"window_start_date": eligible_rows[0]["business_date"],
		"window_end_date": eligible_rows[-1]["business_date"],
		"projected_daily_pace_net_sales_without_vat": projected_daily_pace,
		"projected_7_day_net_sales_without_vat": projected_7_day,
		"projected_month_close_net_sales_without_vat": projected_month_close,
		"delta_vs_selected_window_average_daily_sales": delta_vs_window_average,
		"delta_vs_selected_window_average_daily_sales_pct": delta_vs_window_average_pct,
	}


def _aggregate_discount_metrics(
	discount_rows: list[dict[str, Any]],
	selected_location_ids: list[int],
	start_day: date,
	discount_effective_end_day: date,
	freshness: dict[str, Any],
) -> dict[str, Any]:
	denominator = 0.0
	total_discount_amount = 0.0
	sc_discount_amount = 0.0
	pwd_discount_amount = 0.0

	for row in discount_rows:
		denominator += _to_float(row.get("pos_original_gross_sales"))
		total_discount_amount += _to_float(row.get("pos_total_discounts"))
		sc_discount_amount += _to_float(row.get("sc_recorded_discount_amount"))
		pwd_discount_amount += _to_float(row.get("pwd_recorded_discount_amount"))

	covered_store_count = len(
		{
			_to_int(row.get("location_id"))
			for row in discount_rows
			if str(row.get("business_date")) == discount_effective_end_day.isoformat()
		}
	)
	selected_store_count = len(selected_location_ids)
	coverage_pct = _round_half_up((covered_store_count / selected_store_count) * 100) if selected_store_count else 0.0
	discount_history_start_date = freshness.get("discount_history_start_date")

	return {
		"available": bool(discount_rows),
		"partial_history": bool(
			discount_history_start_date and start_day.isoformat() < str(discount_history_start_date)
		),
		"denominator_policy": "POS original gross sales",
		"recording_policy": "Recorded discount only; excludes VAT relief and effective statutory benefit.",
		"pos_original_gross_sales": _round_half_up(denominator),
		"discount_amount": _round_half_up(total_discount_amount),
		"discount_percentage": _pct(total_discount_amount, denominator),
		"sc_discount_amount": _round_half_up(sc_discount_amount),
		"sc_discount_percentage": _pct(sc_discount_amount, denominator),
		"pwd_discount_amount": _round_half_up(pwd_discount_amount),
		"pwd_discount_percentage": _pct(pwd_discount_amount, denominator),
		"discount_effective_end_date": discount_effective_end_day.isoformat(),
		"discount_scope_coverage_pct": coverage_pct,
		"covered_store_count": covered_store_count,
		"selected_store_count": selected_store_count,
	}


def _build_discount_rankings(
	scope: dict[str, Any],
	discount_rows: list[dict[str, Any]],
	ranking_mode: str,
) -> dict[str, Any]:
	selected_stores = scope["selected_stores"]
	selected_store_count = len(selected_stores)
	if selected_store_count < RANKING_MIN_SCOPE_STORES:
		return {
			"ranking_state": {
				"visible": False,
				"reason": f"Select at least {RANKING_MIN_SCOPE_STORES} stores to compare discount burden.",
				"ranking_mode": ranking_mode,
				"selected_store_count": selected_store_count,
				"minimum_store_count": RANKING_MIN_SCOPE_STORES,
				"minimum_pos_original_gross": RANKING_MIN_POS_ORIGINAL_GROSS,
			},
			"discount_rankings": [],
		}

	store_lookup = {store["location_id"]: store for store in selected_stores}
	by_location: dict[int, dict[str, Any]] = {}
	for row in discount_rows:
		location_id = _to_int(row.get("location_id"))
		entry = by_location.setdefault(
			location_id,
			{
				"location_id": location_id,
				"warehouse": store_lookup.get(location_id, {}).get("warehouse"),
				"warehouse_name": store_lookup.get(location_id, {}).get("warehouse_name") or row.get("store_name"),
				"pos_original_gross_sales": 0.0,
				"discount_amount": 0.0,
				"sc_discount_amount": 0.0,
				"pwd_discount_amount": 0.0,
				"fact_days": 0,
			},
		)
		entry["pos_original_gross_sales"] += _to_float(row.get("pos_original_gross_sales"))
		entry["discount_amount"] += _to_float(row.get("pos_total_discounts"))
		entry["sc_discount_amount"] += _to_float(row.get("sc_recorded_discount_amount"))
		entry["pwd_discount_amount"] += _to_float(row.get("pwd_recorded_discount_amount"))
		entry["fact_days"] += 1

	eligible_rows: list[dict[str, Any]] = []
	for row in by_location.values():
		row["pos_original_gross_sales"] = _round_half_up(row["pos_original_gross_sales"])
		row["discount_amount"] = _round_half_up(row["discount_amount"])
		row["sc_discount_amount"] = _round_half_up(row["sc_discount_amount"])
		row["pwd_discount_amount"] = _round_half_up(row["pwd_discount_amount"])
		row["discount_percentage"] = _pct(row["discount_amount"], row["pos_original_gross_sales"])
		row["sc_discount_percentage"] = _pct(row["sc_discount_amount"], row["pos_original_gross_sales"])
		row["pwd_discount_percentage"] = _pct(row["pwd_discount_amount"], row["pos_original_gross_sales"])
		if row["pos_original_gross_sales"] >= RANKING_MIN_POS_ORIGINAL_GROSS and row["discount_percentage"] is not None:
			eligible_rows.append(row)

	if ranking_mode == "discount_amt":
		eligible_rows.sort(
			key=lambda row: (
				-row["discount_amount"],
				-(row["discount_percentage"] or 0.0),
				-row["pos_original_gross_sales"],
				str(row.get("warehouse_name") or ""),
			)
		)
	else:
		eligible_rows.sort(
			key=lambda row: (
				-(row["discount_percentage"] or 0.0),
				-row["discount_amount"],
				-row["pos_original_gross_sales"],
				str(row.get("warehouse_name") or ""),
			)
		)

	return {
		"ranking_state": {
			"visible": True,
			"reason": (
				None
				if eligible_rows
				else f"No store met the PHP {RANKING_MIN_POS_ORIGINAL_GROSS:,.0f} POS original gross floor in the selected window."
			),
			"ranking_mode": ranking_mode,
			"selected_store_count": selected_store_count,
			"eligible_store_count": len(eligible_rows),
			"minimum_store_count": RANKING_MIN_SCOPE_STORES,
			"minimum_pos_original_gross": RANKING_MIN_POS_ORIGINAL_GROSS,
		},
		"discount_rankings": eligible_rows,
	}


def _shift_range(start_day: date, end_day: date, delta_days: int) -> tuple[date, date]:
	return start_day - timedelta(days=delta_days), end_day - timedelta(days=delta_days)


def _build_comparisons(
	start_day: date,
	end_day: date,
	location_ids: list[int],
	current: dict[str, Any],
	sales_history_start_date: str | None = None,
) -> dict[str, Any]:
	span_days = (end_day - start_day).days + 1
	prev_start, prev_end = _shift_range(start_day, end_day, span_days)
	prev_rows = _query_daily_rows(prev_start, prev_end, location_ids)
	prev = _aggregate_sales(prev_rows) if prev_rows else {}
	last_year_start = start_day - timedelta(days=365)
	last_year_end = end_day - timedelta(days=365)
	last_year_history_floor = (
		date.fromisoformat(str(sales_history_start_date)) if sales_history_start_date else None
	)
	last_year_rows: list[dict[str, Any]] = []
	if not last_year_history_floor or last_year_start >= last_year_history_floor:
		last_year_rows = _query_daily_rows(last_year_start, last_year_end, location_ids)
	last_year = _aggregate_sales(last_year_rows) if last_year_rows else {}

	def delta_payload(baseline: dict[str, Any], reason: str | None = None) -> dict[str, Any]:
		if not baseline:
			return {"available": False, "reason": reason}
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
		"same_period_last_year": delta_payload(
			last_year,
			reason="insufficient_history"
			if last_year_history_floor and last_year_start < last_year_history_floor
			else None,
		),
	}


def _empty_comparisons() -> dict[str, Any]:
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
			"holiday_name": ", ".join(sorted(set(filter(None, holiday_names)))) or None,
			"holiday_list_used": ", ".join(sorted(set(holiday_lists))) or None,
		}
	return calendar


def _weather_by_store_day(rows: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
	result: dict[tuple[int, str], dict[str, Any]] = {}
	for row in rows:
		key = (_to_int(row.get("location_id")), str(row.get("business_date")))
		result[key] = row
	return result


RAIN_SEVERITY_ORDER = {
	"dry": 0,
	"passing_showers": 1,
	"wet": 2,
	"disruptive_rain": 3,
}

WIND_DISRUPTION_ORDER = {
	"low": 0,
	"moderate": 1,
	"high": 2,
}


def _pick_mode(values: list[str | None]) -> str | None:
	filtered = [str(value).strip() for value in values if str(value or "").strip()]
	if not filtered:
		return None
	return Counter(filtered).most_common(1)[0][0]


def _pick_highest(values: list[str | None], ordering: dict[str, int]) -> str | None:
	best: str | None = None
	best_score = -1
	for value in values:
		score = ordering.get(str(value or "").strip(), -1)
		if score > best_score:
			best = str(value).strip()
			best_score = score
	return best


def _temperature_state_from_anomaly(value: float | None) -> str | None:
	if value is None:
		return None
	if value <= -1.5:
		return "cooler_than_normal"
	if value >= 1.5:
		return "hotter_than_normal"
	return "normal"


def _classify_rain_severity(
	total_precipitation: float | None,
	precipitation_hours: float | None,
	max_hourly_precipitation: float | None,
	storm_flag: bool,
) -> str:
	total = _to_float(total_precipitation)
	hours = _to_float(precipitation_hours)
	peak = _to_float(max_hourly_precipitation)
	sustained_disruption = (peak >= RAIN_SUSTAINED_PEAK_MM and hours >= 4) or (
		hours >= RAIN_SUSTAINED_HOURS and total >= RAIN_SUSTAINED_TOTAL_MM
	)
	if total <= 0 and hours <= 0 and peak <= 0 and not storm_flag:
		return "dry"
	if (
		storm_flag
		or peak >= RAIN_DISRUPTIVE_PEAK_MM
		or total >= RAIN_DISRUPTIVE_TOTAL_MM
		or sustained_disruption
	):
		return "disruptive_rain"
	if total > 0 and peak < RAIN_LIGHT_PEAK_MM and hours <= 2:
		return "passing_showers"
	return "wet"


def _classify_business_impact(
	apparent_temperature_max: float | None,
	total_precipitation: float | None,
	precipitation_hours: float | None,
	max_hourly_precipitation: float | None,
	storm_flag: bool,
) -> str:
	apparent = _to_float(apparent_temperature_max)
	rain_severity = _classify_rain_severity(
		total_precipitation=total_precipitation,
		precipitation_hours=precipitation_hours,
		max_hourly_precipitation=max_hourly_precipitation,
		storm_flag=storm_flag,
	)
	if apparent >= 33 and _to_float(total_precipitation) == 0 and not storm_flag:
		return "peak"
	if rain_severity == "disruptive_rain":
		return "disruptive_rain"
	if rain_severity == "passing_showers":
		return "passing_showers"
	if rain_severity == "wet":
		return "wet"
	if apparent <= 27:
		return "cool"
	return "normal"


def _share_pct(count: int, total: int) -> float:
	return round((count / total) * 100, 2) if total else 0.0


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
				"pickup_sales_without_vat": 0.0,
				"delivery_sales_without_vat": 0.0,
				"cups_sold": 0,
				"transactions": 0,
				"weather_rows": [],
			},
		)
		bucket["gross_sales"] += _to_float(row.get("total_gross_sales"))
		bucket["net_sales_with_vat"] += _to_float(row.get("total_gross_sales"))
		bucket["net_sales_without_vat"] += _to_float(row.get("total_net_sales_without_vat"))
		bucket["pickup_sales_without_vat"] += _to_float(row.get("pos_net_sales_without_vat"))
		bucket["delivery_sales_without_vat"] += (
			_to_float(row.get("website_non_cod_net_sales_without_vat"))
			+ _to_float(row.get("web_cod_net_sales_without_vat"))
			+ _to_float(row.get("foodpanda_vat_deducted_sales"))
		)
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
			coverage_count = len(weather_group)
			average_temp = round(
				sum(_to_float(item.get("avg_temperature")) for item in weather_group) / coverage_count,
				2,
			)
			average_apparent_temperature_max = round(
				sum(_to_float(item.get("apparent_temperature_max")) for item in weather_group)
				/ coverage_count,
				2,
			)
			average_precipitation = round(
				sum(_to_float(item.get("total_precipitation")) for item in weather_group) / coverage_count,
				2,
			)
			average_precipitation_hours = round(
				sum(_to_float(item.get("precipitation_hours")) for item in weather_group) / coverage_count,
				2,
			)
			average_max_hourly_precipitation = round(
				sum(_to_float(item.get("max_hourly_precipitation")) for item in weather_group)
				/ coverage_count,
				2,
			)
			temperature_anomaly = round(
				sum(_to_float(item.get("temperature_anomaly_vs_28d")) for item in weather_group)
				/ coverage_count,
				2,
			)
			severity_counts = Counter(
				str(item.get("rain_severity") or "").strip()
				for item in weather_group
				if str(item.get("rain_severity") or "").strip()
			)
			disruptive_rain_store_count = severity_counts.get("disruptive_rain", 0)
			storm_share = sum(1 for item in weather_group if bool(item.get("storm_flag"))) / coverage_count
			rain_severity = _classify_rain_severity(
				total_precipitation=average_precipitation,
				precipitation_hours=average_precipitation_hours,
				max_hourly_precipitation=average_max_hourly_precipitation,
				storm_flag=storm_share >= AGGREGATE_STORM_SHARE_THRESHOLD,
			)
			wind_disruption = _pick_highest(
				[item.get("wind_disruption_level") for item in weather_group],
				WIND_DISRUPTION_ORDER,
			)
			bucket.update(
				{
					"avg_temperature": average_temp,
					"max_temperature": round(
						max(_to_float(item.get("max_temperature")) for item in weather_group), 2
					),
					"min_temperature": round(
						min(_to_float(item.get("min_temperature")) for item in weather_group), 2
					),
					"apparent_temperature_max": average_apparent_temperature_max,
					"avg_wind_speed": round(
						sum(_to_float(item.get("avg_wind_speed")) for item in weather_group) / coverage_count,
						2,
					),
					"max_wind_speed": round(
						max(_to_float(item.get("max_wind_speed")) for item in weather_group), 2
					),
					"total_precipitation": average_precipitation,
					"precipitation_hours": average_precipitation_hours,
					"average_max_hourly_precipitation": average_max_hourly_precipitation,
					"max_hourly_precipitation": round(
						max(_to_float(item.get("max_hourly_precipitation")) for item in weather_group),
						2,
					),
					"weather_description": _pick_mode(
						[item.get("weather_description") for item in weather_group]
					),
					"business_impact": _classify_business_impact(
						apparent_temperature_max=average_apparent_temperature_max,
						total_precipitation=average_precipitation,
						precipitation_hours=average_precipitation_hours,
						max_hourly_precipitation=average_max_hourly_precipitation,
						storm_flag=storm_share >= AGGREGATE_STORM_SHARE_THRESHOLD,
					),
					"temperature_anomaly_vs_28d": temperature_anomaly,
					"temperature_state": _temperature_state_from_anomaly(temperature_anomaly),
					"rain_severity": rain_severity,
					"wind_disruption_level": wind_disruption,
					"storm_flag": storm_share >= AGGREGATE_STORM_SHARE_THRESHOLD,
					"service_window_weather_summary_lunch": _pick_mode(
						[item.get("service_window_weather_summary_lunch") for item in weather_group]
					),
					"service_window_weather_summary_dinner": _pick_mode(
						[item.get("service_window_weather_summary_dinner") for item in weather_group]
					),
					"is_rainy": rain_severity in {"wet", "disruptive_rain"},
					"hourly_backed": any(bool(item.get("hourly_backed")) for item in weather_group),
					"hourly_points": sum(_to_int(item.get("hourly_points")) for item in weather_group),
					"weather_coverage_count": coverage_count,
					"dry_store_count": severity_counts.get("dry", 0),
					"passing_showers_store_count": severity_counts.get("passing_showers", 0),
					"wet_store_count": severity_counts.get("wet", 0),
					"disruptive_rain_store_count": disruptive_rain_store_count,
					"disruptive_rain_store_share_pct": _share_pct(
						disruptive_rain_store_count, coverage_count
					),
				}
			)
		else:
			bucket.update(
				{
					"avg_temperature": None,
					"max_temperature": None,
					"min_temperature": None,
					"apparent_temperature_max": None,
					"avg_wind_speed": None,
					"max_wind_speed": None,
					"total_precipitation": None,
					"precipitation_hours": None,
					"average_max_hourly_precipitation": None,
					"max_hourly_precipitation": None,
					"weather_description": None,
					"business_impact": None,
					"temperature_anomaly_vs_28d": None,
					"temperature_state": None,
					"rain_severity": None,
					"wind_disruption_level": None,
					"storm_flag": False,
					"service_window_weather_summary_lunch": None,
					"service_window_weather_summary_dinner": None,
					"is_rainy": False,
					"hourly_backed": False,
					"hourly_points": 0,
					"weather_coverage_count": 0,
					"dry_store_count": 0,
					"passing_showers_store_count": 0,
					"wet_store_count": 0,
					"disruptive_rain_store_count": 0,
					"disruptive_rain_store_share_pct": 0.0,
				}
			)
		bucket["average_guest_check"] = (
			round(bucket["net_sales_without_vat"] / bucket["transactions"], 2)
			if bucket["transactions"]
			else 0.0
		)
		bucket["cups_per_transaction"] = (
			round(bucket["cups_sold"] / bucket["transactions"], 2) if bucket["transactions"] else 0.0
		)
		bucket.update(calendar)
		for key in (
			"gross_sales",
			"net_sales_with_vat",
			"net_sales_without_vat",
			"pickup_sales_without_vat",
			"delivery_sales_without_vat",
		):
			bucket[key] = round(bucket[key], 2)
		series.append(bucket)
	return series


def _build_group_stat(rows: list[dict[str, Any]]) -> dict[str, Any]:
	if not rows:
		return {"sample_size": 0}
	return {
		"sample_size": len(rows),
		"average_net_sales_without_vat": round(
			sum(_to_float(row.get("net_sales_without_vat")) for row in rows) / len(rows),
			2,
		),
		"average_gross_sales": round(sum(_to_float(row.get("gross_sales")) for row in rows) / len(rows), 2),
		"average_cups_sold": round(sum(_to_int(row.get("cups_sold")) for row in rows) / len(rows), 2),
		"average_transactions": round(sum(_to_int(row.get("transactions")) for row in rows) / len(rows), 2),
		"average_pickup_sales_without_vat": round(
			sum(_to_float(row.get("pickup_sales_without_vat")) for row in rows) / len(rows),
			2,
		),
		"average_delivery_sales_without_vat": round(
			sum(_to_float(row.get("delivery_sales_without_vat")) for row in rows) / len(rows),
			2,
		),
		"average_temperature_anomaly_vs_28d": round(
			sum(_to_float(row.get("temperature_anomaly_vs_28d")) for row in rows) / len(rows),
			2,
		),
	}


def _build_weather_context(series: list[dict[str, Any]]) -> dict[str, Any]:
	return {
		"not_enough_history": len(series) < 7,
		"groups": {
			"disruptive_rain": _build_group_stat(
				[row for row in series if row.get("rain_severity") == "disruptive_rain"]
			),
			"non_disruptive_weather": _build_group_stat(
				[row for row in series if row.get("rain_severity") != "disruptive_rain"]
			),
			"passing_showers": _build_group_stat(
				[row for row in series if row.get("rain_severity") == "passing_showers"]
			),
			"weekend": _build_group_stat([row for row in series if row.get("is_weekend")]),
			"weekday": _build_group_stat([row for row in series if not row.get("is_weekend")]),
			"holiday": _build_group_stat([row for row in series if row.get("is_holiday")]),
			"non_holiday": _build_group_stat([row for row in series if not row.get("is_holiday")]),
			"cooler_than_normal": _build_group_stat(
				[row for row in series if row.get("temperature_state") == "cooler_than_normal"]
			),
			"hotter_than_normal": _build_group_stat(
				[row for row in series if row.get("temperature_state") == "hotter_than_normal"]
			),
		},
	}


def _build_channel_mix(summary: dict[str, Any]) -> list[dict[str, Any]]:
	return [
		{
			"key": "pickup",
			"label": "Pickup Sales",
			"sales_with_vat": summary["pickup_sales"],
			"sales_without_vat": summary["pickup_sales_without_vat"],
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
			# S176 DD-14 Option A: GrabFood surfaced via pos_orders direct query.
			"key": "grabfood",
			"label": "GrabFood",
			"orders": summary.get("grabfood_orders", 0),
			"sales_with_vat": summary.get("grabfood_sales", 0.0),
			"sales_without_vat": summary.get("grabfood_sales_without_vat", 0.0),
		},
		{
			"key": "foodpanda",
			"label": "FoodPanda",
			"sales_with_vat": summary["foodpanda_sales"],
			"sales_without_vat": summary["foodpanda_sales_without_vat"],
		},
	]


def _is_ops_scope_calibrated(
	view_mode: str,
	start_day: date,
	end_day: date,
	selected_location_ids: list[int],
	allowed_store_count: int,
) -> bool:
	_ = (view_mode, start_day, end_day, selected_location_ids, allowed_store_count)
	return False


def _build_mode_state(
	view_mode: str, start_day: date, end_day: date, scope: dict[str, Any]
) -> dict[str, Any]:
	_ = (view_mode, start_day, end_day, scope)
	return {
		"view_mode": CANONICAL_VIEW_MODE,
		"supported": True,
		"label": "Sales dashboard canonical",
		"weather_analytics_mode": "canonical",
	}


def _to_bool_flag(value: Any, default: bool = False) -> bool:
	if value is None:
		return default
	if isinstance(value, bool):
		return value
	text = str(value).strip().lower()
	if text in {"1", "true", "yes", "y", "on"}:
		return True
	if text in {"0", "false", "no", "n", "off", ""}:
		return False
	return default


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
				"disruptive_rain_days": 0,
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
			if bool(weather_row.get("is_rainy")):
				store_row["rainy_days"] += 1
			if str(weather_row.get("rain_severity") or "").strip() == "disruptive_rain":
				store_row["disruptive_rain_days"] += 1
	for row in by_location.values():
		row["gross_sales"] = round(row["gross_sales"], 2)
		row["net_sales_without_vat"] = round(row["net_sales_without_vat"], 2)
		row["average_guest_check"] = (
			round(row["net_sales_without_vat"] / row["transactions"], 2) if row["transactions"] else 0.0
		)
		row["cups_per_transaction"] = (
			round(row["cups_sold"] / row["transactions"], 2) if row["transactions"] else 0.0
		)
	return sorted(by_location.values(), key=lambda row: row["gross_sales"], reverse=True)


def _sales_row_metrics(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"location_id": _to_int(row.get("location_id")),
		"business_date": str(row.get("business_date")),
		"net_sales_without_vat": _to_float(row.get("total_net_sales_without_vat")),
		"transactions": _to_int(row.get("transactions")),
		"cups_sold": _to_int(row.get("cups_sold")),
		"pickup_sales_without_vat": _to_float(row.get("pos_net_sales_without_vat")),
		"delivery_sales_without_vat": (
			_to_float(row.get("website_non_cod_net_sales_without_vat"))
			+ _to_float(row.get("web_cod_net_sales_without_vat"))
			+ _to_float(row.get("foodpanda_vat_deducted_sales"))
		),
	}


def _build_weather_effects(
	scope: dict[str, Any],
	start_day: date,
	end_day: date,
	current_rows: list[dict[str, Any]],
	summary: dict[str, Any],
) -> dict[str, Any]:
	selected_location_ids = [store["location_id"] for store in scope["selected_stores"]]
	if not selected_location_ids or not current_rows:
		return {"available": False}

	baseline_start = start_day - timedelta(days=WEATHER_EFFECT_HISTORY_LOOKBACK_DAYS)
	baseline_end = start_day - timedelta(days=1)
	if baseline_end < baseline_start:
		return {"available": False}

	history_rows = _query_daily_rows(baseline_start, baseline_end, selected_location_ids)
	if not history_rows:
		return {"available": False}
	history_day_count = len({str(row.get("business_date")) for row in history_rows})
	if history_day_count < WEATHER_EFFECT_MIN_COMPARABLE_HISTORY_DAYS:
		return {
			"available": False,
			"history_days_considered": history_day_count,
			"minimum_history_days_required": WEATHER_EFFECT_MIN_COMPARABLE_HISTORY_DAYS,
		}

	all_dates = {str(row.get("business_date")) for row in current_rows}
	all_dates.update(str(row.get("business_date")) for row in history_rows)
	calendar_map = _calendar_map_for_scope(scope["selected_stores"], all_dates)

	by_context: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
	for row in history_rows:
		metrics = _sales_row_metrics(row)
		calendar = calendar_map.get(metrics["business_date"], {})
		day_of_week = calendar.get("day_of_week")
		is_weekend = bool(calendar.get("is_weekend"))
		is_holiday = bool(calendar.get("is_holiday"))
		context_keys = [
			(metrics["location_id"], day_of_week, is_holiday, is_weekend),
			(metrics["location_id"], day_of_week, is_weekend),
			(metrics["location_id"], day_of_week),
		]
		for context_key in context_keys:
			by_context.setdefault(context_key, []).append(metrics)

	for values in by_context.values():
		values.sort(key=lambda item: item["business_date"], reverse=True)

	expected_net = 0.0
	expected_transactions = 0.0
	expected_cups = 0.0
	expected_pickup = 0.0
	expected_delivery = 0.0
	matched_days = 0

	for row in current_rows:
		metrics = _sales_row_metrics(row)
		calendar = calendar_map.get(metrics["business_date"], {})
		context_candidates = [
			(
				metrics["location_id"],
				calendar.get("day_of_week"),
				bool(calendar.get("is_holiday")),
				bool(calendar.get("is_weekend")),
			),
			(metrics["location_id"], calendar.get("day_of_week"), bool(calendar.get("is_weekend"))),
			(metrics["location_id"], calendar.get("day_of_week")),
		]
		candidates: list[dict[str, Any]] = []
		for context_key in context_candidates:
			candidates = by_context.get(context_key, [])
			if candidates:
				break
		if not candidates:
			continue

		recent_candidates = candidates[:8]
		expected_net += sum(item["net_sales_without_vat"] for item in recent_candidates) / len(
			recent_candidates
		)
		expected_transactions += sum(item["transactions"] for item in recent_candidates) / len(
			recent_candidates
		)
		expected_cups += sum(item["cups_sold"] for item in recent_candidates) / len(recent_candidates)
		expected_pickup += sum(item["pickup_sales_without_vat"] for item in recent_candidates) / len(
			recent_candidates
		)
		expected_delivery += sum(item["delivery_sales_without_vat"] for item in recent_candidates) / len(
			recent_candidates
		)
		matched_days += 1

	if matched_days == 0:
		return {
			"available": False,
			"history_days_considered": history_day_count,
			"minimum_history_days_required": WEATHER_EFFECT_MIN_COMPARABLE_HISTORY_DAYS,
		}

	actual_net = _to_float(summary.get("net_sales_without_vat"))
	actual_transactions = _to_float(summary.get("transactions"))
	actual_cups = _to_float(summary.get("cups_sold"))
	actual_pickup = _to_float(summary.get("pickup_sales_without_vat"))
	actual_delivery = _to_float(summary.get("delivery_sales_without_vat"))
	expected_total = expected_pickup + expected_delivery
	actual_total = actual_pickup + actual_delivery

	def share(value: float, total: float) -> float:
		return round((value / total) * 100, 2) if total else 0.0

	net_delta = round(actual_net - expected_net, 2)
	return {
		"available": True,
		"expected_net_sales_without_vat": round(expected_net, 2),
		"actual_vs_expected_net_sales_delta": net_delta,
		"actual_vs_expected_net_sales_delta_pct": round((net_delta / expected_net) * 100, 2)
		if expected_net
		else None,
		"actual_vs_expected_transactions_delta": round(actual_transactions - expected_transactions, 2),
		"actual_vs_expected_cups_delta": round(actual_cups - expected_cups, 2),
		"channel_mix_shift_vs_baseline": {
			"pickup_share_delta_pct_points": round(
				share(actual_pickup, actual_total) - share(expected_pickup, expected_total),
				2,
			),
			"delivery_share_delta_pct_points": round(
				share(actual_delivery, actual_total) - share(expected_delivery, expected_total),
				2,
			),
		},
		"history_days_considered": history_day_count,
		"matched_days": matched_days,
		"matched_store_days": matched_days,
	}


def _build_dashboard_summary_payload(
	scope: dict[str, Any],
	start_day: date,
	end_day: date,
	view_mode: str,
	channel: str,
	include_comparisons: bool,
) -> dict[str, Any]:
	view_mode = _canonical_view_mode(view_mode)
	selected_location_ids = [store["location_id"] for store in scope["selected_stores"]]
	cache_key = _sales_dashboard_cache_key(
		"summary",
		selected_location_ids,
		start_day=start_day,
		end_day=end_day,
		view_mode=view_mode,
		channel=channel,
		include_comparisons=include_comparisons,
	)

	def builder() -> dict[str, Any]:
		freshness = _build_freshness(selected_location_ids)
		effective_end = _effective_end_day(end_day, freshness)
		discount_effective_end = _effective_discount_end_day(effective_end, freshness)
		freshness["effective_end_date"] = effective_end.isoformat()
		freshness["sales_effective_end_date"] = effective_end.isoformat()
		freshness["discount_effective_end_date"] = discount_effective_end.isoformat()
		freshness["requested_end_date"] = end_day.isoformat()
		freshness["data_quality_warnings"] = _build_data_quality_warnings(start_day, end_day, freshness)
		sales_rows = (
			_query_daily_rows(start_day, effective_end, selected_location_ids)
			if selected_location_ids and effective_end >= start_day
			else []
		)
		discount_rows = (
			_query_discount_rows(start_day, discount_effective_end, selected_location_ids)
			if selected_location_ids and discount_effective_end >= start_day
			else []
		)
		summary = _aggregate_sales(sales_rows)
		# S176 DD-14 Option A: inject real GrabFood totals from pos_orders direct query.
		summary.update(_get_grabfood_channel_totals(start_day, effective_end, selected_location_ids))
		# S176 hotfix 2026-04-09: override FoodPanda totals (view is stale post-2026-03-31).
		summary.update(_get_foodpanda_channel_totals(start_day, effective_end, selected_location_ids))
		# S176 hotfix #6: per-channel cups from Mosaic pos_order_items.
		summary.update(_get_channel_cups_from_mosaic(start_day, effective_end, selected_location_ids))
		projection_window_rows = [
			row for row in sales_rows if str(row.get("business_date")) <= discount_effective_end.isoformat()
		]
		summary["projection"] = _build_projection(
			selected_location_ids,
			start_day,
			discount_effective_end,
			projection_window_rows,
		)
		summary["discount_metrics"] = _aggregate_discount_metrics(
			discount_rows,
			selected_location_ids,
			start_day,
			discount_effective_end,
			freshness,
		)
		freshness["discount_scope_coverage_pct"] = summary["discount_metrics"]["discount_scope_coverage_pct"]
		mode_state = _build_mode_state(view_mode, start_day, effective_end, scope)
		response: dict[str, Any] = {
			"scope": {
				"selected_stores": scope["selected_stores"],
				"selected_location_ids": selected_location_ids,
				"channel": channel,
			},
			"date_window": {
				"start_date": start_day.isoformat(),
				"end_date": effective_end.isoformat(),
				"requested_end_date": end_day.isoformat(),
			},
			"mode_state": mode_state,
			"summary": summary,
			"freshness": freshness,
			"comparisons": _build_comparisons(
				start_day,
				effective_end,
				selected_location_ids,
				summary,
				sales_history_start_date=freshness.get("sales_history_start_date"),
			)
			if include_comparisons
			else _empty_comparisons(),
		}
		return response

	return _cache_get_or_set(cache_key, builder, SALES_DASHBOARD_CACHE_TTL)


def _build_dashboard_overview_payload(
	scope: dict[str, Any],
	start_day: date,
	end_day: date,
	view_mode: str,
	channel: str,
	include_comparisons: bool,
	ranking_mode: str,
) -> dict[str, Any]:
	view_mode = _canonical_view_mode(view_mode)
	ranking_mode = _parse_ranking_mode(ranking_mode)
	selected_location_ids = [store["location_id"] for store in scope["selected_stores"]]
	freshness = _build_freshness(selected_location_ids)
	effective_end = _effective_end_day(end_day, freshness)
	discount_effective_end = _effective_discount_end_day(effective_end, freshness)
	freshness["effective_end_date"] = effective_end.isoformat()
	freshness["sales_effective_end_date"] = effective_end.isoformat()
	freshness["discount_effective_end_date"] = discount_effective_end.isoformat()
	freshness["requested_end_date"] = end_day.isoformat()
	cache_key = _sales_dashboard_cache_key(
		"overview",
		selected_location_ids,
		start_day=start_day,
		end_day=effective_end,
		view_mode=view_mode,
		channel=channel,
		include_comparisons=include_comparisons,
		ranking_mode=ranking_mode,
	)

	def builder() -> dict[str, Any]:
		if effective_end < start_day:
			sales_rows: list[dict[str, Any]] = []
			weather_rows: list[dict[str, Any]] = []
		else:
			sales_rows = _query_daily_rows(start_day, effective_end, selected_location_ids)
			weather_rows = _query_weather_rows(start_day, effective_end, selected_location_ids)
		discount_rows = (
			_query_discount_rows(start_day, discount_effective_end, selected_location_ids)
			if selected_location_ids and discount_effective_end >= start_day
			else []
		)
		summary = _aggregate_sales(sales_rows)
		# S176 DD-14 Option A: inject real GrabFood totals from pos_orders direct query.
		summary.update(_get_grabfood_channel_totals(start_day, effective_end, selected_location_ids))
		# S176 hotfix 2026-04-09: override FoodPanda totals (view is stale post-2026-03-31).
		summary.update(_get_foodpanda_channel_totals(start_day, effective_end, selected_location_ids))
		# S176 hotfix #6: per-channel cups from Mosaic pos_order_items.
		summary.update(_get_channel_cups_from_mosaic(start_day, effective_end, selected_location_ids))
		mode_state = _build_mode_state(view_mode, start_day, effective_end, scope)
		projection_window_rows = [
			row for row in sales_rows if str(row.get("business_date")) <= discount_effective_end.isoformat()
		]
		summary["projection"] = _build_projection(
			selected_location_ids,
			start_day,
			discount_effective_end,
			projection_window_rows,
		)
		summary["discount_metrics"] = _aggregate_discount_metrics(
			discount_rows,
			selected_location_ids,
			start_day,
			discount_effective_end,
			freshness,
		)
		freshness["discount_scope_coverage_pct"] = summary["discount_metrics"]["discount_scope_coverage_pct"]
		freshness["data_quality_warnings"] = _build_data_quality_warnings(start_day, end_day, freshness)
		series = _aggregate_daily_series(scope["selected_stores"], sales_rows, weather_rows)
		analysis = _build_weather_context(series)
		analysis["effects"] = _build_weather_effects(scope, start_day, effective_end, sales_rows, summary)
		discount_ranking_payload = _build_discount_rankings(scope, discount_rows, ranking_mode)
		response: dict[str, Any] = {
			"scope": {
				"selected_stores": scope["selected_stores"],
				"selected_location_ids": selected_location_ids,
				"channel": channel,
			},
			"date_window": {
				"start_date": start_day.isoformat(),
				"end_date": effective_end.isoformat(),
				"requested_end_date": end_day.isoformat(),
			},
			"mode_state": mode_state,
			"summary": summary,
			"freshness": freshness,
			"comparisons": _build_comparisons(
				start_day,
				effective_end,
				selected_location_ids,
				summary,
				sales_history_start_date=freshness.get("sales_history_start_date"),
			)
			if include_comparisons
			else _empty_comparisons(),
			"daily": series,
			"analysis": analysis,
			"stores": _build_store_rankings(scope, sales_rows, weather_rows),
			"ranking_state": discount_ranking_payload["ranking_state"],
			"discount_rankings": discount_ranking_payload["discount_rankings"],
			"channels": _build_channel_mix(summary),
		}
		return response

	return _cache_get_or_set(cache_key, builder, SALES_DASHBOARD_CACHE_TTL)


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
				"apparent_temperature_max": day_meta.get("apparent_temperature_max"),
				"temperature_anomaly_vs_28d": day_meta.get("temperature_anomaly_vs_28d"),
				"temperature_state": day_meta.get("temperature_state"),
				"total_precipitation": day_meta.get("total_precipitation"),
				"precipitation_hours": day_meta.get("precipitation_hours"),
				"rain_severity": day_meta.get("rain_severity"),
				"wind_disruption_level": day_meta.get("wind_disruption_level"),
				"storm_flag": day_meta.get("storm_flag"),
				"weather_description": day_meta.get("weather_description"),
				"is_rainy": day_meta.get("is_rainy"),
				"hourly_backed": day_meta.get("hourly_backed"),
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
def get_sales_dashboard_overview(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
	ranking_mode: str = DEFAULT_RANKING_MODE,
	include_comparisons: bool | str | int | None = None,
) -> dict[str, Any]:
	set_backend_observability_context(
		module="sales",
		action="get_sales_dashboard_overview",
		mutation_type="read",
	)
	scope = _selected_scope(_parse_stores_param(stores))
	start_day, end_day = _resolve_date_range(start_date, end_date)
	return _build_dashboard_overview_payload(
		scope,
		start_day,
		end_day,
		view_mode,
		channel,
		include_comparisons=_to_bool_flag(include_comparisons, default=False),
		ranking_mode=ranking_mode,
	)


@frappe.whitelist()
def get_sales_dashboard_summary(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
	ranking_mode: str = DEFAULT_RANKING_MODE,
	include_comparisons: bool | str | int | None = None,
) -> dict[str, Any]:
	set_backend_observability_context(
		module="sales",
		action="get_sales_dashboard_summary",
		mutation_type="read",
	)
	_ = ranking_mode
	scope = _selected_scope(_parse_stores_param(stores))
	start_day, end_day = _resolve_date_range(start_date, end_date)
	return _build_dashboard_summary_payload(
		scope,
		start_day,
		end_day,
		view_mode,
		channel,
		include_comparisons=_to_bool_flag(include_comparisons, default=False),
	)


@frappe.whitelist()
def get_sales_dashboard_daily_series(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
	ranking_mode: str = DEFAULT_RANKING_MODE,
) -> dict[str, Any]:
	overview = get_sales_dashboard_overview(
		start_date=start_date,
		end_date=end_date,
		stores=stores,
		view_mode=view_mode,
		channel=channel,
		ranking_mode=ranking_mode,
	)
	return {
		"scope": {"selected_stores": overview["scope"]["selected_stores"], "channel": channel},
		"date_window": overview["date_window"],
		"mode_state": overview["mode_state"],
		"series": overview["daily"],
	}


@frappe.whitelist()
def get_sales_dashboard_channel_mix(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
	ranking_mode: str = DEFAULT_RANKING_MODE,
) -> dict[str, Any]:
	overview = get_sales_dashboard_overview(
		start_date=start_date,
		end_date=end_date,
		stores=stores,
		view_mode=view_mode,
		channel=channel,
		ranking_mode=ranking_mode,
	)
	return {
		"scope": {"selected_stores": overview["scope"]["selected_stores"], "channel": channel},
		"date_window": overview["date_window"],
		"mode_state": overview["mode_state"],
		"channels": overview["channels"],
	}


@frappe.whitelist()
def get_sales_dashboard_store_rankings(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
	ranking_mode: str = DEFAULT_RANKING_MODE,
) -> dict[str, Any]:
	overview = get_sales_dashboard_overview(
		start_date=start_date,
		end_date=end_date,
		stores=stores,
		view_mode=view_mode,
		channel=channel,
		ranking_mode=ranking_mode,
	)
	return {
		"scope": {"selected_stores": overview["scope"]["selected_stores"], "channel": channel},
		"date_window": overview["date_window"],
		"mode_state": overview["mode_state"],
		"stores": overview["stores"],
		"ranking_state": overview["ranking_state"],
		"discount_rankings": overview["discount_rankings"],
	}


@frappe.whitelist()
def get_sales_dashboard_weather_context(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
	ranking_mode: str = DEFAULT_RANKING_MODE,
) -> dict[str, Any]:
	overview = get_sales_dashboard_overview(
		start_date=start_date,
		end_date=end_date,
		stores=stores,
		view_mode=view_mode,
		channel=channel,
		ranking_mode=ranking_mode,
	)
	return {
		"scope": {"selected_stores": overview["scope"]["selected_stores"], "channel": channel},
		"date_window": overview["date_window"],
		"mode_state": overview["mode_state"],
		"daily": overview["daily"],
		"analysis": overview["analysis"],
	}


@frappe.whitelist()
def export_sales_dashboard_detail(
	start_date: str | None = None,
	end_date: str | None = None,
	stores: list[str] | str | None = None,
	view_mode: str = "canonical",
	channel: str = "all",
	ranking_mode: str = DEFAULT_RANKING_MODE,
) -> dict[str, Any]:
	_ = ranking_mode
	scope = _selected_scope(_parse_stores_param(stores))
	start_day, end_day = _resolve_date_range(start_date, end_date)
	selected_location_ids = [store["location_id"] for store in scope["selected_stores"]]
	freshness = _build_freshness(selected_location_ids)
	effective_end = _effective_end_day(end_day, freshness)
	sales_rows = _query_daily_rows(start_day, effective_end, selected_location_ids)
	weather_rows = _query_weather_rows(start_day, effective_end, selected_location_ids)
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
		"apparent_temperature_max",
		"temperature_anomaly_vs_28d",
		"temperature_state",
		"total_precipitation",
		"precipitation_hours",
		"rain_severity",
		"wind_disruption_level",
		"storm_flag",
		"weather_description",
		"is_rainy",
		"hourly_backed",
		"is_weekend",
		"is_holiday",
		"holiday_name",
	]
	writer = csv.DictWriter(buffer, fieldnames=fieldnames)
	writer.writeheader()
	writer.writerows(export_rows)
	filename = f"sales_dashboard_detail_{start_day.isoformat()}_{effective_end.isoformat()}.csv"

	return {
		"filename": filename,
		"content_type": "text/csv",
		"content": buffer.getvalue(),
		"row_count": len(export_rows),
		"view_mode": CANONICAL_VIEW_MODE,
		"channel": channel,
	}
