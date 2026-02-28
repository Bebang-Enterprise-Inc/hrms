import unittest
from unittest.mock import patch
from pathlib import Path
import importlib.util

try:
	import frappe
except ModuleNotFoundError:
	import sys
	import types

	def _whitelist(fn=None, *args, **kwargs):
		if fn is None:
			return lambda real_fn: real_fn
		return fn

	fake_frappe = types.ModuleType("frappe")
	fake_frappe._dict = lambda data: types.SimpleNamespace(**data)
	fake_frappe.db = types.SimpleNamespace(get_value=lambda *a, **k: None)
	fake_frappe.get_all = lambda *a, **k: []
	fake_frappe.whitelist = _whitelist
	fake_frappe.throw = lambda msg: (_ for _ in ()).throw(Exception(msg))
	fake_frappe._ = lambda msg: msg
	sys.modules["frappe"] = fake_frappe

	fake_utils = types.ModuleType("frappe.utils")
	fake_utils.flt = float
	sys.modules["frappe.utils"] = fake_utils

	import frappe

try:
	from hrms.api import commissary_bom
except Exception:
	import sys
	import types

	# Minimal dependency stubs so module under test can be loaded without full Frappe bench.
	sys.modules.setdefault("hrms", types.ModuleType("hrms"))
	sys.modules.setdefault("hrms.api", types.ModuleType("hrms.api"))
	sys.modules.setdefault("hrms.utils", types.ModuleType("hrms.utils"))

	fake_commissary = types.ModuleType("hrms.api.commissary")
	fake_commissary.get_commissary_warehouse = lambda: "Commissary - BEI"
	sys.modules["hrms.api.commissary"] = fake_commissary

	fake_bei_config = types.ModuleType("hrms.utils.bei_config")
	fake_bei_config.get_company = lambda: "Bebang Enterprise Inc."
	sys.modules["hrms.utils.bei_config"] = fake_bei_config

	module_path = Path(__file__).resolve().parents[1] / "api" / "commissary_bom.py"
	spec = importlib.util.spec_from_file_location("commissary_bom_under_test", module_path)
	commissary_bom = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(commissary_bom)


class TestCommissaryBOMRuntimeProof(unittest.TestCase):
	def test_runtime_deduction_proof_returns_line_level_evidence(self):
		bom = frappe._dict({"name": "BOM-FG-001", "quantity": 10})
		bom_items = [
			frappe._dict({"item_code": "RM-FLOUR", "item_name": "Flour", "qty": 2, "stock_uom": "Kg"}),
			frappe._dict({"item_code": "RM-SUGAR", "item_name": "Sugar", "qty": 1, "stock_uom": "Kg"}),
		]

		def _fake_get_value(doctype, filters, fieldname=None, as_dict=False):
			if doctype == "BOM":
				return bom
			if doctype == "Bin":
				if isinstance(filters, dict) and filters.get("item_code") == "RM-FLOUR":
					return 100
				if isinstance(filters, dict) and filters.get("item_code") == "RM-SUGAR":
					return 80
				return 0
			return None

		with patch("frappe.db.get_value", side_effect=_fake_get_value), patch(
			"frappe.get_all", return_value=bom_items
		), patch.object(commissary_bom, "get_commissary_warehouse", return_value="Commissary - BEI"):
			result = commissary_bom.get_bom_runtime_deduction_proof("FG001", 20)

		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["bom_name"], "BOM-FG-001")
		self.assertEqual(result["data"]["proof_line_count"], 2)

		flour = result["data"]["proof_lines"][0]
		sugar = result["data"]["proof_lines"][1]

		self.assertEqual(flour["item_code"], "RM-FLOUR")
		self.assertEqual(flour["qty_required"], 4.0)
		self.assertEqual(flour["qty_before"], 100.0)
		self.assertEqual(flour["qty_after"], 96.0)
		self.assertEqual(flour["delta"], -4.0)

		self.assertEqual(sugar["item_code"], "RM-SUGAR")
		self.assertEqual(sugar["qty_required"], 2.0)
		self.assertEqual(sugar["qty_before"], 80.0)
		self.assertEqual(sugar["qty_after"], 78.0)
		self.assertEqual(sugar["delta"], -2.0)

	def test_runtime_deduction_proof_rejects_non_positive_qty(self):
		result = commissary_bom.get_bom_runtime_deduction_proof("FG001", 0)
		self.assertFalse(result["success"])
		self.assertIn("produced_qty", result["error"])
