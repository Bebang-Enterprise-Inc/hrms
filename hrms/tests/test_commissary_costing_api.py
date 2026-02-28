import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

try:
	import frappe
except ModuleNotFoundError:
	import sys
	import types
	from datetime import datetime, timedelta

	def _whitelist(fn=None, *args, **kwargs):
		if fn is None:
			return lambda real_fn: real_fn
		return fn

	fake_frappe = types.ModuleType("frappe")
	fake_frappe._dict = lambda data: types.SimpleNamespace(**data)
	fake_frappe.db = types.SimpleNamespace(sql=lambda *a, **k: [], count=lambda *a, **k: 0)
	fake_frappe.get_all = lambda *a, **k: []
	fake_frappe.whitelist = _whitelist
	fake_frappe.throw = lambda msg: (_ for _ in ()).throw(Exception(msg))
	fake_frappe._ = lambda msg: msg
	sys.modules["frappe"] = fake_frappe

	fake_utils = types.ModuleType("frappe.utils")
	fake_utils.flt = float
	fake_utils.today = lambda: datetime.utcnow().strftime("%Y-%m-%d")
	fake_utils.add_days = lambda d, n: (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=n)).strftime(
		"%Y-%m-%d"
	)
	sys.modules["frappe.utils"] = fake_utils

	import frappe


def _load_module(module_name, rel_path):
	import sys
	import types

	sys.modules.setdefault("hrms", types.ModuleType("hrms"))
	sys.modules.setdefault("hrms.api", types.ModuleType("hrms.api"))
	sys.modules.setdefault("hrms.utils", types.ModuleType("hrms.utils"))

	fake_commissary = types.ModuleType("hrms.api.commissary")
	fake_commissary.get_commissary_warehouse = lambda: "Commissary - BEI"
	sys.modules["hrms.api.commissary"] = fake_commissary

	fake_bei_config = types.ModuleType("hrms.utils.bei_config")
	fake_bei_config.get_company = lambda: "Bebang Enterprise Inc."
	sys.modules["hrms.utils.bei_config"] = fake_bei_config

	module_path = Path(__file__).resolve().parents[1] / rel_path
	spec = importlib.util.spec_from_file_location(module_name, module_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


commissary_dashboard = _load_module(
	"commissary_dashboard_under_test", Path("api") / "commissary_dashboard.py"
)


class TestCommissaryCostingAPI(unittest.TestCase):
	def test_production_cost_per_batch_aggregates_total_cost(self):
		rows = [
			{
				"batch_id": "STE-0001",
				"posting_date": "2026-02-28",
				"item_code": "FG001",
				"item_name": "Halo Halo Base",
				"material_cost": 1250.5,
				"labor_cost": 0,
				"overhead_cost": 0,
			},
			{
				"batch_id": "STE-0002",
				"posting_date": "2026-02-28",
				"item_code": "FG002",
				"item_name": "Sago Mix",
				"material_cost": 500,
				"labor_cost": 0,
				"overhead_cost": 0,
			},
		]

		with patch.object(commissary_dashboard.frappe.db, "sql", return_value=rows):
			result = commissary_dashboard.get_production_cost_per_batch(limit=10)

		self.assertTrue(result["success"])
		self.assertEqual(len(result["data"]), 2)
		self.assertEqual(result["data"][0]["total_cost"], 1250.5)
		self.assertEqual(result["data"][1]["total_cost"], 500.0)
		self.assertEqual(result["summary"]["batches"], 2)
		self.assertEqual(result["summary"]["total_cost"], 1750.5)

	def test_production_cost_per_batch_applies_item_filter(self):
		with patch.object(commissary_dashboard.frappe.db, "sql", return_value=[]) as sql_mock:
			commissary_dashboard.get_production_cost_per_batch(limit=5, item_code="FG001")

		call_args, call_kwargs = sql_mock.call_args
		self.assertEqual(call_kwargs["as_dict"], True)
		self.assertEqual(call_args[1], ("FG001", 5))
