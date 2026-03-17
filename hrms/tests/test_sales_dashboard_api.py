from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _ensure_package(name: str) -> types.ModuleType:
	module = sys.modules.get(name)
	if module is None:
		module = types.ModuleType(name)
		module.__path__ = []
		sys.modules[name] = module
		if "." in name:
			parent_name, child_name = name.rsplit(".", 1)
			parent = _ensure_package(parent_name)
			setattr(parent, child_name, module)
	return module


def _register_module(name: str, module: types.ModuleType) -> None:
	sys.modules[name] = module
	if "." in name:
		parent_name, child_name = name.rsplit(".", 1)
		parent = _ensure_package(parent_name)
		setattr(parent, child_name, module)


def _load_module(path: Path, alias: str):
	_prime_sales_location_mapping_module()
	spec = importlib.util.spec_from_file_location(alias, path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def _prime_sales_location_mapping_module() -> None:
	module_name = "hrms.utils.sales_location_mapping"
	if module_name in sys.modules:
		return
	_ensure_package("hrms.utils")
	spec = importlib.util.spec_from_file_location(
		module_name,
		ROOT / "hrms" / "utils" / "sales_location_mapping.py",
	)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	_register_module(module_name, module)


def _install_fake_frappe(user_roles: list[str]):
	frappe = types.ModuleType("frappe")
	frappe.local = types.SimpleNamespace(session=types.SimpleNamespace(user="stakeholder@example.com"))

	class PermissionError(Exception):
		pass

	class ValidationError(Exception):
		pass

	def whitelist(*args, **kwargs):
		if args and callable(args[0]) and len(args) == 1 and not kwargs:
			return args[0]

		def decorator(fn):
			return fn

		return decorator

	def throw(message, exc=None):
		err_cls = exc if isinstance(exc, type) else Exception
		raise err_cls(message)

	def __getattr__(name: str):
		if name == "session":
			return frappe.local.session
		raise AttributeError(name)

	frappe.whitelist = whitelist
	frappe.throw = throw
	frappe.PermissionError = PermissionError
	frappe.ValidationError = ValidationError
	frappe.get_roles = lambda user=None: list(user_roles)
	frappe.get_all = lambda *args, **kwargs: []
	frappe.get_doc = lambda *args, **kwargs: None
	frappe.db = types.SimpleNamespace(get_value=lambda *args, **kwargs: None)
	frappe.conf = {}
	frappe.__getattr__ = __getattr__

	utils = types.ModuleType("frappe.utils")
	utils.add_days = lambda value, days: value
	utils.date_diff = lambda end, start: 0
	frappe.utils = utils

	_register_module("frappe", frappe)
	_register_module("frappe.utils", utils)
	return frappe


def test_scope_resolution_prefers_sales_stakeholder_assignments():
	_install_fake_frappe(["Sales Stakeholder"])
	module = _load_module(ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_scope_test")

	module.frappe.get_all = lambda doctype, filters=None, fields=None, order_by=None: (
		[{"warehouse": "SM Megamall - Bebang Enterprise Inc."}]
		if doctype == "BEI Sales Dashboard Store Access"
		else [
			{
				"name": "SM Megamall - Bebang Enterprise Inc.",
				"warehouse_name": "SM Megamall",
				"company": "Bebang Enterprise Inc.",
				"custom_area_supervisor": None,
			}
		]
	)

	scope = module._resolve_allowed_store_scope()

	assert scope["role"] == "Sales Stakeholder"
	assert scope["stores"] == [
		{
			"warehouse": "SM Megamall - Bebang Enterprise Inc.",
			"warehouse_name": "SM Megamall",
			"company": "Bebang Enterprise Inc.",
			"location_id": 2338,
		}
	]


def test_selected_scope_rejects_store_outside_allowlist():
	_install_fake_frappe(["Sales Stakeholder"])
	module = _load_module(ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_selection_test")

	module._resolve_allowed_store_scope = lambda user=None: {
		"user": "stakeholder@example.com",
		"role": "Sales Stakeholder",
		"roles": ["Sales Stakeholder"],
		"stores": [
			{
				"warehouse": "SM Megamall - Bebang Enterprise Inc.",
				"warehouse_name": "SM Megamall",
				"company": "Bebang Enterprise Inc.",
				"location_id": 2338,
			}
		],
	}

	with pytest.raises(module._permission_error_class()):
		module._selected_scope(["SM North EDSA"])


def test_aggregate_sales_computes_dashboard_metrics():
	_install_fake_frappe(["System Manager"])
	module = _load_module(ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_aggregate_test")

	rows = [
		{
			"business_date": "2026-03-13",
			"total_gross_sales": "1000.00",
			"total_net_sales_without_vat": "892.86",
			"cups_sold": "10",
			"transactions": "5",
			"pos_gross_sales": "600.00",
			"website_non_cod_gross_sales": "150.00",
			"website_non_cod_net_sales_without_vat": "133.93",
			"web_cod_orders": "1",
			"web_cod_gross_sales": "50.00",
			"web_cod_net_sales_without_vat": "44.64",
			"foodpanda_subtotal": "200.00",
			"foodpanda_vat_deducted_sales": "178.57",
		},
		{
			"business_date": "2026-03-14",
			"total_gross_sales": "500.00",
			"total_net_sales_without_vat": "446.43",
			"cups_sold": "5",
			"transactions": "2",
			"pos_gross_sales": "300.00",
			"website_non_cod_gross_sales": "80.00",
			"website_non_cod_net_sales_without_vat": "71.43",
			"web_cod_orders": "0",
			"web_cod_gross_sales": "0.00",
			"web_cod_net_sales_without_vat": "0.00",
			"foodpanda_subtotal": "120.00",
			"foodpanda_vat_deducted_sales": "107.14",
		},
	]

	result = module._aggregate_sales(rows)

	assert result["gross_sales"] == 1500.0
	assert result["net_sales_without_vat"] == 1339.29
	assert result["cups_sold"] == 15
	assert result["transactions"] == 7
	assert result["average_daily_sales"] == 669.65
	assert result["average_guest_check"] == 191.33
	assert result["cups_per_transaction"] == 2.14
	assert result["website_cod_orders"] == 1


def test_data_quality_warning_flags_stale_foodpanda_cups():
	_install_fake_frappe(["System Manager"])
	module = _load_module(ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_quality_test")

	freshness = {
		"foodpanda_cups_max_business_date": "2026-03-08",
		"weather_max_business_date": "2026-03-14",
	}

	warnings = module._build_data_quality_warnings(
		module.date(2026, 3, 1),
		module.date(2026, 3, 14),
		freshness,
	)

	assert any("FoodPanda cups" in warning for warning in warnings)


def test_supabase_get_all_honors_requested_limit():
	_install_fake_frappe(["System Manager"])
	module = _load_module(ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_paging_test")

	calls: list[list[tuple[str, str]]] = []

	def fake_supabase_get(resource, params=None):
		assert resource == "daily_weather"
		assert params is not None
		calls.append(list(params))
		return [{"business_date": "2026-03-14"}]

	module._supabase_get = fake_supabase_get

	rows = module._supabase_get_all(
		"daily_weather",
		[
			("select", "business_date"),
			("order", "business_date.desc"),
			("limit", "1"),
		],
		page_size=1000,
	)

	assert rows == [{"business_date": "2026-03-14"}]
	assert len(calls) == 1
	assert ("limit", "1") in calls[0]
	assert ("offset", "0") in calls[0]


def test_summary_hot_path_skips_overview_only_builders():
	_install_fake_frappe(["System Manager"])
	module = _load_module(
		ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_summary_default_test"
	)

	scope = {
		"selected_stores": [
			{
				"warehouse": "SM Megamall - Bebang Enterprise Inc.",
				"warehouse_name": "SM Megamall",
				"company": "Bebang Enterprise Inc.",
				"location_id": 2338,
			}
		],
		"stores": [
			{
				"warehouse": "SM Megamall - Bebang Enterprise Inc.",
				"warehouse_name": "SM Megamall",
				"company": "Bebang Enterprise Inc.",
				"location_id": 2338,
			}
		],
	}
	module._selected_scope = lambda requested_stores, user=None: scope
	module._resolve_date_range = lambda start_date, end_date: (module.date(2026, 3, 1), module.date(2026, 3, 14))
	module._build_freshness = lambda location_ids: {
		"pos_max_business_date": "2026-03-14",
		"web_max_business_date": "2026-03-14",
		"weather_max_business_date": "2026-03-14",
		"discount_max_business_date": "2026-03-14",
		"sales_history_start_date": "2025-06-01",
		"discount_history_start_date": "2026-02-01",
	}
	module._query_daily_rows = lambda *args, **kwargs: [
		{
			"business_date": "2026-03-14",
			"total_gross_sales": "123.00",
			"total_net_sales_without_vat": "100.00",
			"cups_sold": "5",
			"transactions": "2",
			"pos_gross_sales": "70.00",
			"pos_net_sales_without_vat": "62.50",
			"website_non_cod_gross_sales": "20.00",
			"website_non_cod_net_sales_without_vat": "17.86",
			"web_cod_orders": "0",
			"web_cod_gross_sales": "0.00",
			"web_cod_net_sales_without_vat": "0.00",
			"foodpanda_subtotal": "33.00",
			"foodpanda_vat_deducted_sales": "29.46",
		}
	]
	module._query_discount_rows = lambda *args, **kwargs: [
		{
			"location_id": 2338,
			"business_date": "2026-03-14",
			"store_name": "SM Megamall",
			"pos_original_gross_sales": "70.00",
			"pos_total_discounts": "7.00",
			"sc_recorded_discount_amount": "3.00",
			"pwd_recorded_discount_amount": "2.00",
		}
	]
	module._build_mode_state = lambda *args, **kwargs: {
		"view_mode": "canonical",
		"supported": True,
		"label": "Sales dashboard canonical",
	}
	module._build_weather_effects = lambda *args, **kwargs: (_ for _ in ()).throw(
		AssertionError("summary hot path must not build weather effects")
	)
	module._query_weather_rows = lambda *args, **kwargs: (_ for _ in ()).throw(
		AssertionError("summary hot path must not query weather rows")
	)
	module._build_store_rankings = lambda *args, **kwargs: (_ for _ in ()).throw(
		AssertionError("summary hot path must not build store rankings")
	)
	module._build_channel_mix = lambda *args, **kwargs: (_ for _ in ()).throw(
		AssertionError("summary hot path must not build channel mix")
	)
	module._build_comparisons = lambda *args, **kwargs: (_ for _ in ()).throw(
		AssertionError("summary hot path must not build comparisons when omitted")
	)

	result = module.get_sales_dashboard_summary()

	assert result["summary"]["gross_sales"] == 123.0
	assert result["summary"]["projection"]["available"] is False
	assert result["summary"]["discount_metrics"]["discount_percentage"] == 10.0
	assert result["comparisons"]["previous_period"]["available"] is False
	assert result["comparisons"]["same_period_last_year"]["available"] is False


def test_effective_end_day_clips_to_closed_core_sales_date():
	_install_fake_frappe(["System Manager"])
	module = _load_module(ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_effective_end_test")

	freshness = {
		"pos_max_business_date": "2026-03-14",
		"web_max_business_date": "2026-03-13",
	}

	result = module._effective_end_day(module.date(2026, 3, 15), freshness)

	assert result == module.date(2026, 3, 13)


def test_daily_series_treats_passing_showers_as_not_operational_rain():
	_install_fake_frappe(["System Manager"])
	module = _load_module(
		ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_daily_series_weather_test"
	)

	stores = [
		{
			"warehouse": "SM Megamall - Bebang Enterprise Inc.",
			"warehouse_name": "SM Megamall",
			"company": "Bebang Enterprise Inc.",
			"location_id": 2338,
		}
	]
	sales_rows = [
		{
			"location_id": 2338,
			"business_date": "2026-03-14",
			"total_gross_sales": "1000.00",
			"total_net_sales_without_vat": "892.86",
			"pos_net_sales_without_vat": "600.00",
			"website_non_cod_net_sales_without_vat": "150.00",
			"web_cod_net_sales_without_vat": "50.00",
			"foodpanda_vat_deducted_sales": "92.86",
			"cups_sold": "10",
			"transactions": "5",
		}
	]
	weather_rows = [
		{
			"location_id": 2338,
			"business_date": "2026-03-14",
			"avg_temperature": 29.5,
			"max_temperature": 31.0,
			"min_temperature": 26.0,
			"apparent_temperature_max": 33.0,
			"avg_wind_speed": 10.0,
			"max_wind_speed": 12.0,
			"total_precipitation": 1.2,
			"precipitation_hours": 1,
			"max_hourly_precipitation": 0.8,
			"weather_description": "Slight rain showers",
			"business_impact": "passing_showers",
			"temperature_anomaly_vs_28d": -0.4,
			"rain_severity": "passing_showers",
			"wind_disruption_level": "low",
			"storm_flag": False,
			"service_window_weather_summary_lunch": "showery_lunch",
			"service_window_weather_summary_dinner": "stable_dinner",
			"is_rainy": False,
			"hourly_backed": True,
			"hourly_points": 24,
		}
	]

	module._calendar_map_for_scope = lambda *_args, **_kwargs: {
		"2026-03-14": {
			"business_date": "2026-03-14",
			"day_of_week": "Saturday",
			"is_weekend": True,
			"is_holiday": False,
			"holiday_name": None,
			"holiday_list_used": None,
		}
	}

	series = module._aggregate_daily_series(stores, sales_rows, weather_rows)

	assert len(series) == 1
	assert series[0]["is_rainy"] is False
	assert series[0]["rain_severity"] == "passing_showers"
	assert series[0]["average_guest_check"] == 178.57


def test_weather_effects_require_minimum_comparable_history():
	_install_fake_frappe(["System Manager"])
	module = _load_module(
		ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_effects_history_floor_test"
	)

	scope = {
		"selected_stores": [
			{
				"warehouse": "SM Megamall - Bebang Enterprise Inc.",
				"warehouse_name": "SM Megamall",
				"company": "Bebang Enterprise Inc.",
				"location_id": 2338,
			}
		]
	}
	current_rows = [
		{
			"location_id": 2338,
			"business_date": "2026-03-14",
			"total_net_sales_without_vat": "1000.00",
			"transactions": "5",
			"cups_sold": "10",
			"pos_net_sales_without_vat": "700.00",
			"website_non_cod_net_sales_without_vat": "200.00",
			"web_cod_net_sales_without_vat": "50.00",
			"foodpanda_vat_deducted_sales": "50.00",
		}
	]
	history_rows = [
		{
			"location_id": 2338,
			"business_date": f"2025-12-{index + 1:02d}",
			"total_net_sales_without_vat": "900.00",
			"transactions": "4",
			"cups_sold": "9",
			"pos_net_sales_without_vat": "650.00",
			"website_non_cod_net_sales_without_vat": "150.00",
			"web_cod_net_sales_without_vat": "50.00",
			"foodpanda_vat_deducted_sales": "50.00",
		}
		for index in range(10)
	]
	module._query_daily_rows = lambda *args, **kwargs: history_rows

	result = module._build_weather_effects(
		scope=scope,
		start_day=module.date(2026, 3, 1),
		end_day=module.date(2026, 3, 14),
		current_rows=current_rows,
		summary={"net_sales_without_vat": 1000.0},
	)

	assert result["available"] is False
	assert result["history_days_considered"] == 10
	assert result["minimum_history_days_required"] == 56


def test_daily_series_recomputes_scope_rain_severity_from_aggregate_metrics():
	_install_fake_frappe(["System Manager"])
	module = _load_module(
		ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_scope_weather_aggregate_test"
	)

	stores = [
		{
			"warehouse": "SM Megamall - Bebang Enterprise Inc.",
			"warehouse_name": "SM Megamall",
			"company": "Bebang Enterprise Inc.",
			"location_id": 2338,
		},
		{
			"warehouse": "SM North EDSA - Bebang Enterprise Inc.",
			"warehouse_name": "SM North EDSA",
			"company": "Bebang Enterprise Inc.",
			"location_id": 2340,
		},
		{
			"warehouse": "SM Southmall - Bebang Enterprise Inc.",
			"warehouse_name": "SM Southmall",
			"company": "Bebang Enterprise Inc.",
			"location_id": 2345,
		},
	]
	sales_rows = [
		{
			"location_id": 2338,
			"business_date": "2026-03-11",
			"total_gross_sales": "1000.00",
			"total_net_sales_without_vat": "892.86",
			"pos_net_sales_without_vat": "600.00",
			"website_non_cod_net_sales_without_vat": "150.00",
			"web_cod_net_sales_without_vat": "50.00",
			"foodpanda_vat_deducted_sales": "92.86",
			"cups_sold": "10",
			"transactions": "5",
		},
		{
			"location_id": 2340,
			"business_date": "2026-03-11",
			"total_gross_sales": "1200.00",
			"total_net_sales_without_vat": "1071.43",
			"pos_net_sales_without_vat": "700.00",
			"website_non_cod_net_sales_without_vat": "200.00",
			"web_cod_net_sales_without_vat": "60.00",
			"foodpanda_vat_deducted_sales": "111.43",
			"cups_sold": "12",
			"transactions": "6",
		},
		{
			"location_id": 2345,
			"business_date": "2026-03-11",
			"total_gross_sales": "900.00",
			"total_net_sales_without_vat": "803.57",
			"pos_net_sales_without_vat": "500.00",
			"website_non_cod_net_sales_without_vat": "140.00",
			"web_cod_net_sales_without_vat": "40.00",
			"foodpanda_vat_deducted_sales": "123.57",
			"cups_sold": "9",
			"transactions": "4",
		},
	]
	weather_rows = [
		{
			"location_id": 2338,
			"business_date": "2026-03-11",
			"avg_temperature": 28.5,
			"max_temperature": 30.0,
			"min_temperature": 26.0,
			"apparent_temperature_max": 31.0,
			"avg_wind_speed": 9.0,
			"max_wind_speed": 12.0,
			"total_precipitation": 1.4,
			"precipitation_hours": 6,
			"max_hourly_precipitation": 1.9,
			"weather_description": "Slight rain showers",
			"business_impact": "disruptive_rain",
			"temperature_anomaly_vs_28d": -0.6,
			"rain_severity": "disruptive_rain",
			"wind_disruption_level": "low",
			"storm_flag": False,
			"service_window_weather_summary_lunch": "showery_lunch",
			"service_window_weather_summary_dinner": "stable_dinner",
			"is_rainy": True,
			"hourly_backed": True,
			"hourly_points": 24,
		},
		{
			"location_id": 2340,
			"business_date": "2026-03-11",
			"avg_temperature": 27.5,
			"max_temperature": 29.0,
			"min_temperature": 25.0,
			"apparent_temperature_max": 30.0,
			"avg_wind_speed": 8.0,
			"max_wind_speed": 11.0,
			"total_precipitation": 1.2,
			"precipitation_hours": 6,
			"max_hourly_precipitation": 1.8,
			"weather_description": "Moderate drizzle",
			"business_impact": "disruptive_rain",
			"temperature_anomaly_vs_28d": -0.5,
			"rain_severity": "disruptive_rain",
			"wind_disruption_level": "low",
			"storm_flag": False,
			"service_window_weather_summary_lunch": "showery_lunch",
			"service_window_weather_summary_dinner": "stable_dinner",
			"is_rainy": True,
			"hourly_backed": True,
			"hourly_points": 24,
		},
		{
			"location_id": 2345,
			"business_date": "2026-03-11",
			"avg_temperature": 26.5,
			"max_temperature": 28.0,
			"min_temperature": 24.0,
			"apparent_temperature_max": 29.0,
			"avg_wind_speed": 8.0,
			"max_wind_speed": 10.0,
			"total_precipitation": 1.0,
			"precipitation_hours": 5,
			"max_hourly_precipitation": 1.5,
			"weather_description": "Light drizzle",
			"business_impact": "wet",
			"temperature_anomaly_vs_28d": -0.4,
			"rain_severity": "wet",
			"wind_disruption_level": "low",
			"storm_flag": False,
			"service_window_weather_summary_lunch": "showery_lunch",
			"service_window_weather_summary_dinner": "stable_dinner",
			"is_rainy": True,
			"hourly_backed": True,
			"hourly_points": 24,
		},
	]

	module._calendar_map_for_scope = lambda *_args, **_kwargs: {
		"2026-03-11": {
			"business_date": "2026-03-11",
			"day_of_week": "Wednesday",
			"is_weekend": False,
			"is_holiday": False,
			"holiday_name": None,
			"holiday_list_used": None,
		}
	}

	series = module._aggregate_daily_series(stores, sales_rows, weather_rows)

	assert len(series) == 1
	assert series[0]["rain_severity"] == "wet"
	assert series[0]["is_rainy"] is True
	assert series[0]["disruptive_rain_store_count"] == 2
	assert series[0]["disruptive_rain_store_share_pct"] == 66.67
	assert series[0]["apparent_temperature_max"] == 30.0
	assert series[0]["average_max_hourly_precipitation"] == 1.73
	assert series[0]["max_hourly_precipitation"] == 1.9


def test_weather_effects_return_matched_store_day_count():
	_install_fake_frappe(["System Manager"])
	module = _load_module(
		ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_effects_match_count_test"
	)

	scope = {
		"selected_stores": [
			{
				"warehouse": "SM Megamall - Bebang Enterprise Inc.",
				"warehouse_name": "SM Megamall",
				"company": "Bebang Enterprise Inc.",
				"location_id": 2338,
			}
		]
	}
	current_rows = [
		{
			"location_id": 2338,
			"business_date": "2026-03-14",
			"total_net_sales_without_vat": "1000.00",
			"transactions": "5",
			"cups_sold": "10",
			"pos_net_sales_without_vat": "700.00",
			"website_non_cod_net_sales_without_vat": "200.00",
			"web_cod_net_sales_without_vat": "50.00",
			"foodpanda_vat_deducted_sales": "50.00",
		}
	]
	history_rows = [
		{
			"location_id": 2338,
			"business_date": f"2026-02-{index + 1:02d}",
			"total_net_sales_without_vat": "900.00",
			"transactions": "4",
			"cups_sold": "9",
			"pos_net_sales_without_vat": "650.00",
			"website_non_cod_net_sales_without_vat": "150.00",
			"web_cod_net_sales_without_vat": "50.00",
			"foodpanda_vat_deducted_sales": "50.00",
		}
		for index in range(28)
	] + [
		{
			"location_id": 2338,
			"business_date": f"2026-01-{index + 1:02d}",
			"total_net_sales_without_vat": "950.00",
			"transactions": "5",
			"cups_sold": "10",
			"pos_net_sales_without_vat": "700.00",
			"website_non_cod_net_sales_without_vat": "150.00",
			"web_cod_net_sales_without_vat": "50.00",
			"foodpanda_vat_deducted_sales": "50.00",
		}
		for index in range(28)
	]

	module._query_daily_rows = lambda *args, **kwargs: history_rows
	module._calendar_map_for_scope = lambda *_args, **_kwargs: {
		**{
			row["business_date"]: {
				"business_date": row["business_date"],
				"day_of_week": "Friday",
				"is_weekend": False,
				"is_holiday": False,
				"holiday_name": None,
				"holiday_list_used": None,
			}
			for row in history_rows
		},
		"2026-03-14": {
			"business_date": "2026-03-14",
			"day_of_week": "Friday",
			"is_weekend": False,
			"is_holiday": False,
			"holiday_name": None,
			"holiday_list_used": None,
		},
	}

	result = module._build_weather_effects(
		scope=scope,
		start_day=module.date(2026, 3, 14),
		end_day=module.date(2026, 3, 14),
		current_rows=current_rows,
		summary={
			"net_sales_without_vat": 1000.0,
			"transactions": 5,
			"cups_sold": 10,
			"pickup_sales_without_vat": 700.0,
			"delivery_sales_without_vat": 300.0,
		},
	)

	assert result["available"] is True
	assert result["matched_days"] == 1
	assert result["matched_store_days"] == 1


def test_projection_uses_weighted_last_28_closed_days():
	_install_fake_frappe(["System Manager"])
	module = _load_module(ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_projection_test")

	projection_rows = [
		{
			"business_date": f"2026-02-{index:02d}",
			"total_net_sales_without_vat": f"{index * 100:.2f}",
		}
		for index in range(1, 29)
	]
	module._query_daily_rows = lambda *args, **kwargs: projection_rows

	result = module._build_projection(
		[2338],
		module.date(2026, 2, 1),
		module.date(2026, 2, 28),
		projection_rows[-7:],
	)

	expected_daily_pace = module._round_half_up(
		sum(index * (index * 100) for index in range(1, 29)) / sum(range(1, 29))
	)

	assert result["available"] is True
	assert result["closed_days_considered"] == 28
	assert result["projected_daily_pace_net_sales_without_vat"] == expected_daily_pace
	assert result["projected_7_day_net_sales_without_vat"] == module._round_half_up(expected_daily_pace * 7)


def test_discount_metrics_use_pos_original_gross_denominator():
	_install_fake_frappe(["System Manager"])
	module = _load_module(
		ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_discount_metrics_test"
	)

	result = module._aggregate_discount_metrics(
		[
			{
				"location_id": 2338,
				"business_date": "2026-03-14",
				"pos_original_gross_sales": "1000.00",
				"pos_total_discounts": "120.00",
				"sc_recorded_discount_amount": "40.00",
				"pwd_recorded_discount_amount": "20.00",
			}
		],
		[2338],
		module.date(2026, 3, 1),
		module.date(2026, 3, 14),
		{"discount_history_start_date": "2026-02-01"},
	)

	assert result["discount_percentage"] == 12.0
	assert result["sc_discount_percentage"] == 4.0
	assert result["pwd_discount_percentage"] == 2.0
	assert result["discount_scope_coverage_pct"] == 100.0


def test_discount_metrics_return_na_when_pos_denominator_is_zero():
	_install_fake_frappe(["System Manager"])
	module = _load_module(
		ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_discount_zero_denom_test"
	)

	result = module._aggregate_discount_metrics(
		[
			{
				"location_id": 2774,
				"business_date": "2026-03-14",
				"pos_original_gross_sales": "0.00",
				"pos_total_discounts": "0.00",
				"sc_recorded_discount_amount": "0.00",
				"pwd_recorded_discount_amount": "0.00",
			}
		],
		[2774],
		module.date(2026, 3, 1),
		module.date(2026, 3, 14),
		{"discount_history_start_date": "2026-02-01"},
	)

	assert result["discount_percentage"] is None
	assert result["sc_discount_percentage"] is None
	assert result["pwd_discount_percentage"] is None


def test_discount_rankings_hide_below_scope_minimum_and_exclude_low_floor_rows():
	_install_fake_frappe(["System Manager"])
	module = _load_module(ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_rankings_test")

	hidden = module._build_discount_rankings(
		{
			"selected_stores": [
				{
					"warehouse": "SM Megamall - Bebang Enterprise Inc.",
					"warehouse_name": "SM Megamall",
					"company": "Bebang Enterprise Inc.",
					"location_id": 2338,
				}
			]
		},
		[],
		"discount_pct",
	)
	assert hidden["ranking_state"]["visible"] is False

	scope = {
		"selected_stores": [
			{"warehouse": f"Store {index}", "warehouse_name": f"Store {index}", "location_id": index}
			for index in range(1, 6)
		]
	}
	result = module._build_discount_rankings(
		scope,
		[
			{
				"location_id": 1,
				"business_date": "2026-03-14",
				"pos_original_gross_sales": "50000.00",
				"pos_total_discounts": "5000.00",
				"sc_recorded_discount_amount": "1000.00",
				"pwd_recorded_discount_amount": "500.00",
			},
			{
				"location_id": 2,
				"business_date": "2026-03-14",
				"pos_original_gross_sales": "15000.00",
				"pos_total_discounts": "3000.00",
				"sc_recorded_discount_amount": "200.00",
				"pwd_recorded_discount_amount": "100.00",
			},
		],
		"discount_pct",
	)

	assert result["ranking_state"]["visible"] is True
	assert result["ranking_state"]["eligible_store_count"] == 1
	assert [row["location_id"] for row in result["discount_rankings"]] == [1]


def test_same_period_last_year_is_hidden_when_history_floor_not_met():
	_install_fake_frappe(["System Manager"])
	module = _load_module(
		ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_history_floor_test"
	)

	module._query_daily_rows = lambda *args, **kwargs: []

	result = module._build_comparisons(
		module.date(2026, 3, 1),
		module.date(2026, 3, 14),
		[2338],
		{"gross_sales": 1000.0},
		sales_history_start_date="2025-06-01",
	)

	assert result["same_period_last_year"]["available"] is False
	assert result["same_period_last_year"]["reason"] == "insufficient_history"


def test_view_mode_param_is_ignored_and_summary_stays_canonical():
	_install_fake_frappe(["System Manager"])
	module = _load_module(
		ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_view_mode_ignored_test"
	)

	scope = {
		"selected_stores": [
			{
				"warehouse": "SM Megamall - Bebang Enterprise Inc.",
				"warehouse_name": "SM Megamall",
				"company": "Bebang Enterprise Inc.",
				"location_id": 2338,
			}
		],
		"stores": [
			{
				"warehouse": "SM Megamall - Bebang Enterprise Inc.",
				"warehouse_name": "SM Megamall",
				"company": "Bebang Enterprise Inc.",
				"location_id": 2338,
			}
		],
	}
	module._selected_scope = lambda requested_stores, user=None: scope
	module._resolve_date_range = lambda start_date, end_date: (module.date(2026, 3, 1), module.date(2026, 3, 14))
	module._build_freshness = lambda location_ids: {
		"pos_max_business_date": "2026-03-14",
		"web_max_business_date": "2026-03-14",
		"discount_max_business_date": "2026-03-14",
		"sales_history_start_date": "2025-06-01",
		"discount_history_start_date": "2026-02-01",
	}
	module._query_daily_rows = lambda *args, **kwargs: [
		{
			"business_date": "2026-03-14",
			"total_gross_sales": "123.00",
			"total_net_sales_without_vat": "100.00",
			"cups_sold": "5",
			"transactions": "2",
			"pos_gross_sales": "70.00",
			"pos_net_sales_without_vat": "62.50",
			"website_non_cod_gross_sales": "20.00",
			"website_non_cod_net_sales_without_vat": "17.86",
			"web_cod_orders": "0",
			"web_cod_gross_sales": "0.00",
			"web_cod_net_sales_without_vat": "0.00",
			"foodpanda_subtotal": "33.00",
			"foodpanda_vat_deducted_sales": "29.46",
		}
	]
	module._query_discount_rows = lambda *args, **kwargs: []

	result = module.get_sales_dashboard_summary(view_mode="ops_matched")

	assert result["mode_state"]["view_mode"] == "canonical"
	assert result["mode_state"]["supported"] is True
	assert "ops_summary" not in result
