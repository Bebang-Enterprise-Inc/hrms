import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _install_fake_modules():
	def _whitelist(fn=None, *args, **kwargs):
		if fn is None:
			return lambda real_fn: real_fn
		return fn

	fake_frappe = types.ModuleType("frappe")
	fake_frappe._dict = lambda data: types.SimpleNamespace(**data)
	fake_frappe.db = types.SimpleNamespace(sql=lambda *args, **kwargs: [], count=lambda *args, **kwargs: 0)
	fake_frappe.get_all = lambda *args, **kwargs: []
	fake_frappe.whitelist = _whitelist
	fake_frappe.throw = lambda msg: (_ for _ in ()).throw(Exception(msg))
	fake_frappe._ = lambda msg: msg
	sys.modules["frappe"] = fake_frappe

	fake_utils = types.ModuleType("frappe.utils")
	fake_utils.flt = float
	fake_utils.today = lambda: "2026-03-12"
	fake_utils.add_days = lambda value, days: value
	sys.modules["frappe.utils"] = fake_utils

	sys.modules.setdefault("hrms", types.ModuleType("hrms"))
	sys.modules.setdefault("hrms.api", types.ModuleType("hrms.api"))
	sys.modules.setdefault("hrms.utils", types.ModuleType("hrms.utils"))

	fake_commissary = types.ModuleType("hrms.api.commissary")
	fake_commissary.get_commissary_warehouse = lambda: "Shaw BLVD - BKI"
	sys.modules["hrms.api.commissary"] = fake_commissary

	fake_bei_config = types.ModuleType("hrms.utils.bei_config")
	fake_bei_config.get_company = lambda: "Bebang Kitchen Inc."
	sys.modules["hrms.utils.bei_config"] = fake_bei_config


def _load_module():
	_install_fake_modules()
	module_path = ROOT / "api" / "commissary_dashboard.py"
	spec = importlib.util.spec_from_file_location("commissary_dashboard_under_test", module_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


commissary_dashboard = _load_module()


class TestCommissaryDashboardSummary(unittest.TestCase):
	def test_dashboard_includes_portal_compatibility_aliases(self):
		sql_results = [
			[(3,)],
			[
				{"item_code": "FG010", "item_name": "TAPIOCA", "qty_produced": 1.0, "uom": "KG"},
			],
			[
				{
					"total_items": 2,
					"total_qty": 6.5,
					"total_value": 900.75,
				}
			],
		]

		with (
			patch.object(commissary_dashboard, "get_commissary_warehouse", return_value="Shaw BLVD - BKI"),
			patch.object(
				commissary_dashboard.frappe.db,
				"count",
				side_effect=[4, 2, 1, 0],
			),
			patch.object(
				commissary_dashboard.frappe.db,
				"sql",
				side_effect=sql_results,
			),
			patch.object(
				commissary_dashboard.frappe,
				"get_all",
				return_value=[
					{"name": "STE-0001", "posting_date": "2026-03-12", "total_outgoing_value": 123.45}
				],
			),
		):
			result = commissary_dashboard.get_commissary_dashboard()

		self.assertTrue(result["success"])
		data = result["data"]
		self.assertEqual(data["commissary_warehouse"], "Shaw BLVD - BKI")
		self.assertEqual(data["todays_production"], 4)
		self.assertEqual(data["pending_orders"], 2)
		self.assertEqual(data["todays_dispatches"], 1)
		self.assertEqual(data["dispatches_today"], 1)
		self.assertEqual(data["low_stock_count"], 3)
		self.assertEqual(data["low_stock_items"], 3)
		self.assertEqual(data["production_summary"][0]["item_code"], "FG010")
		self.assertEqual(data["stock_summary"]["total_items"], 2)
		self.assertEqual(data["stock_summary"]["total_qty"], 6.5)
		self.assertEqual(data["stock_summary"]["total_value"], 900.75)


if __name__ == "__main__":
	unittest.main()
