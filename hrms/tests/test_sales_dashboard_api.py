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
	spec = importlib.util.spec_from_file_location(alias, path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def _install_fake_frappe(user_roles: list[str]):
	frappe = types.ModuleType("frappe")
	frappe.local = types.SimpleNamespace(
		session=types.SimpleNamespace(user="stakeholder@example.com"),
		db=types.SimpleNamespace(get_value=lambda *args, **kwargs: None),
		conf={},
	)

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
		if name == "db":
			return frappe.local.db
		if name == "conf":
			return frappe.local.conf
		raise AttributeError(name)

	frappe.whitelist = whitelist
	frappe.throw = throw
	frappe._ = lambda message: message
	frappe.PermissionError = PermissionError
	frappe.ValidationError = ValidationError
	frappe.get_roles = lambda user=None: list(user_roles)
	frappe.get_all = lambda *args, **kwargs: []
	frappe.get_doc = lambda *args, **kwargs: None
	frappe.__getattr__ = __getattr__

	_register_module("frappe", frappe)
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
	assert result["average_daily_sales"] == 750.0
	assert result["average_guest_check"] == 214.29
	assert result["cups_per_transaction"] == 2.14
	assert result["website_cod_orders"] == 1


def test_data_quality_warning_flags_stale_foodpanda_cups():
	_install_fake_frappe(["System Manager"])
	module = _load_module(ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_quality_test")

	freshness = {
		"foodpanda_cups_max_business_date": "2026-03-08",
		"weather_max_business_date": "2026-03-14",
	}

	warnings = module._build_data_quality_warnings(module.date(2026, 3, 14), freshness)

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
		page_size=1,
	)

	assert rows == [{"business_date": "2026-03-14"}]
	assert len(calls) == 1


def test_query_daily_rows_filters_scope_after_fetch():
	_install_fake_frappe(["System Manager"])
	module = _load_module(ROOT / "hrms" / "api" / "sales_dashboard.py", "sales_dashboard_query_rows_test")

	captured: dict[str, object] = {}

	def fake_supabase_get_all(resource, params=None, page_size=1000):
		captured["resource"] = resource
		captured["params"] = params
		captured["page_size"] = page_size
		return [
			{"location_id": 2217, "business_date": "2026-03-02", "store_name": "BF Homes"},
			{"location_id": 2557, "business_date": "2026-03-02", "store_name": "Araneta Gateway"},
		]

	module._supabase_get_all = fake_supabase_get_all

	rows = module._query_daily_rows(module.date(2026, 3, 2), module.date(2026, 3, 8), [2217])

	assert rows == [{"location_id": 2217, "business_date": "2026-03-02", "store_name": "BF Homes"}]
	assert captured["resource"] == module.SUPABASE_DAILY_VIEW
	assert ("location_id", "in.(2217)") not in captured["params"]
