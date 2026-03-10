import importlib.util
import pathlib
import sys
import types
from datetime import date, datetime


class _AttrDict(dict):
	"""Frappe-style row object with both dict and attribute access."""

	__getattr__ = dict.get


def _install_common_stubs():
	frappe = types.ModuleType("frappe")

	class _DB:
		@staticmethod
		def exists(*args, **kwargs):
			return False

		@staticmethod
		def get_value(*args, **kwargs):
			return None

		@staticmethod
		def sql(*args, **kwargs):
			return []

		@staticmethod
		def get_single_value(*args, **kwargs):
			return None

	def _flt(value, precision=None):
		num = float(value or 0)
		return round(num, precision) if precision is not None else num

	def _cint(value):
		return int(value or 0)

	def _getdate(value=None):
		if value is None or value == "":
			return date(2026, 3, 2)
		if isinstance(value, date):
			return value
		return datetime.strptime(str(value), "%Y-%m-%d").date()

	frappe.db = _DB()
	frappe.session = types.SimpleNamespace(user="test.user@bebang.ph")
	frappe.PermissionError = RuntimeError
	frappe.log_error = lambda *args, **kwargs: None
	frappe.get_roles = lambda *args, **kwargs: []
	frappe.get_all = lambda *args, **kwargs: []
	frappe.parse_json = lambda payload: payload

	def _whitelist(fn=None, **kwargs):
		if fn is None:
			return lambda inner: inner
		return fn

	frappe.whitelist = _whitelist

	def _throw(msg, *args, **kwargs):
		raise RuntimeError(msg)

	frappe.throw = _throw
	frappe._ = lambda msg: msg

	utils = types.ModuleType("frappe.utils")
	utils.nowdate = lambda: "2026-03-02"
	utils.add_days = lambda _d, _n: "2026-03-03"
	utils.now_datetime = lambda: datetime(2026, 3, 2, 9, 0, 0)
	utils.flt = _flt
	utils.cint = _cint
	utils.getdate = _getdate
	utils.get_datetime = lambda value=None: datetime(2026, 3, 2, 9, 0, 0)
	utils.today = lambda: "2026-03-02"
	utils.now = lambda: "2026-03-02 09:00:00"
	utils.get_time = lambda _v=None: None

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = []
	utils_pkg = types.ModuleType("hrms.utils")
	utils_pkg.__path__ = []
	bei_config = types.ModuleType("hrms.utils.bei_config")
	bei_config.get_company = lambda: "Bebang Enterprise Inc."

	scm_roles = types.ModuleType("hrms.utils.scm_roles")
	scm_roles.SCM_APPROVAL_ROLES = []
	scm_roles.check_scm_permission = lambda *args, **kwargs: None

	sys.modules["hrms"] = hrms_pkg
	sys.modules["hrms.utils"] = utils_pkg
	sys.modules["hrms.utils.bei_config"] = bei_config
	sys.modules["hrms.utils.scm_roles"] = scm_roles


def _load_store_module():
	_install_common_stubs()
	file_path = pathlib.Path(__file__).resolve().parents[1] / "api" / "store.py"
	spec = importlib.util.spec_from_file_location("s19_store_under_test", file_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def test_orderable_items_contract_includes_recommendation_fields():
	store_mod = _load_store_module()

	contract = store_mod._build_recommendation_contract(
		last_order_qty=12,
		available_to_promise=5,
		lane="Frozen",
		order_count=9,
		signal_multiplier=1.1,
	)

	assert "recommended_qty" in contract
	assert "suggested_qty" in contract
	assert "available_to_promise" in contract
	assert "coverage_window_days" in contract
	assert "projected_sales" in contract
	assert "bom_consumption" in contract
	assert contract["suggested_qty"] == contract["recommended_qty"]
	assert contract["lane"] in {"Frozen", "Dry", "Fresh Market"}


def test_delivery_lane_resolution_defaults_to_dry():
	store_mod = _load_store_module()

	assert store_mod._resolve_delivery_lane({"item_group": "Frozen Meat"}) == "Frozen"
	assert store_mod._resolve_delivery_lane({"item_group": "Staples"}) == "Dry"
	assert store_mod._resolve_delivery_lane({"item_name": "FROZEN ICE MILK (GRIFFITH POWDER)"}) == "Frozen"
	assert store_mod._resolve_delivery_lane({"item_name": "ALUMINUM PIZZA SPICE"}) == "Dry"
	assert store_mod._resolve_delivery_lane({"cargo_category": "FM"}) == "Fresh Market"
	assert (
		store_mod._resolve_delivery_lane({"item_name": "FROZEN ICE MILK", "cargo_category": "DRY"})
		== "Frozen"
	)
	assert (
		store_mod._resolve_delivery_lane({"item_name": "FRESH LETTUCE", "cargo_category": "DRY"})
		== "Fresh Market"
	)


def test_orderable_items_prefers_snapshot_backed_demand_over_heuristic():
	store_mod = _load_store_module()

	def _sql(query, params=None, as_dict=False):
		if "FROM `tabItem` i" in query:
			return [
				_AttrDict(
					name="RM-001",
					item_name="Frozen Milk",
					item_group="Frozen Goods",
					stock_uom="Barrel",
					image=None,
					order_count=4,
				)
			]
		if "FROM `tabBEI Store Order Item` oi" in query:
			return [_AttrDict(item_code="RM-001", qty_requested=9)]
		return []

	def _get_all(doctype, filters=None, fields=None, **kwargs):
		if doctype == "Bin":
			return [_AttrDict(item_code="RM-001", actual_qty=1)]
		if doctype == "BEI Inventory Risk Snapshot":
			return [
				_AttrDict(
					item_code="RM-001",
					warehouse="Test Store - BEI",
					snapshot_date="2026-03-02",
					avg_daily_demand=4.0,
					source_reference=(
						'{"signal_source":"sales_bom_snapshot","lookback_days":14,'
						'"projected_sales":2.5,"bom_consumption":4.0,"coverage_window_days":2}'
					),
				)
			]
		return []

	store_mod.frappe.db.sql = _sql
	store_mod.frappe.get_all = _get_all
	store_mod.resolve_warehouse = lambda store: "Test Store - BEI"
	store_mod._get_signal_flags = lambda warehouse, for_date=None: {
		"is_salary_week": False,
		"is_holiday": False,
		"is_weather_risk": False,
	}
	store_mod._get_adaptive_delta = lambda warehouse: 0.0

	result = store_mod.get_orderable_items("Test Store", "2026-03-02")
	item = result["items"][0]

	assert item["recommendation_source"] == "sales_bom_snapshot"
	assert item["avg_daily_demand"] == 4.0
	assert item["projected_sales"] == 2.5
	assert item["bom_consumption"] == 4.0
	assert item["coverage_window_days"] == 2
	assert item["forecast_demand"] == 13.0
	assert item["recommended_qty"] == 13.95


def test_orderable_items_falls_back_to_heuristic_when_snapshot_missing():
	store_mod = _load_store_module()

	def _sql(query, params=None, as_dict=False):
		if "FROM `tabItem` i" in query:
			return [
				_AttrDict(
					name="RM-001",
					item_name="Sugar Syrup",
					item_group="Dry Goods",
					stock_uom="Bottle",
					image=None,
					order_count=4,
				)
			]
		if "FROM `tabBEI Store Order Item` oi" in query:
			return [_AttrDict(item_code="RM-001", qty_requested=9)]
		return []

	def _get_all(doctype, filters=None, fields=None, **kwargs):
		if doctype == "Bin":
			return [_AttrDict(item_code="RM-001", actual_qty=1)]
		if doctype == "BEI Inventory Risk Snapshot":
			return []
		return []

	store_mod.frappe.db.sql = _sql
	store_mod.frappe.get_all = _get_all
	store_mod.resolve_warehouse = lambda store: "Test Store - BEI"
	store_mod._get_signal_flags = lambda warehouse, for_date=None: {
		"is_salary_week": False,
		"is_holiday": False,
		"is_weather_risk": False,
	}
	store_mod._get_adaptive_delta = lambda warehouse: 0.0

	result = store_mod.get_orderable_items("Test Store", "2026-03-02")
	item = result["items"][0]

	assert item["recommendation_source"] == "heuristic"
	assert item["projected_sales"] == 5.85
	assert item["bom_consumption"] == 2.25
	assert item["coverage_window_days"] == 3
