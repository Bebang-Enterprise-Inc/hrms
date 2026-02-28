import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _install_frappe_stubs():
	if "frappe" in sys.modules:
		return

	fake_frappe = types.ModuleType("frappe")
	sys.modules["frappe"] = fake_frappe

	fake_utils = types.ModuleType("frappe.utils")
	fake_utils.flt = float
	sys.modules["frappe.utils"] = fake_utils

	sys.modules.setdefault("frappe.model", types.ModuleType("frappe.model"))
	fake_document = types.ModuleType("frappe.model.document")

	class _Document:
		pass

	fake_document.Document = _Document
	sys.modules["frappe.model.document"] = fake_document


def _load_production_module():
	_install_frappe_stubs()

	sys.modules.setdefault("hrms", types.ModuleType("hrms"))
	sys.modules.setdefault("hrms.api", types.ModuleType("hrms.api"))
	sys.modules.setdefault("hrms.hr", types.ModuleType("hrms.hr"))
	sys.modules.setdefault("hrms.hr.doctype", types.ModuleType("hrms.hr.doctype"))
	sys.modules.setdefault(
		"hrms.hr.doctype.bei_production", types.ModuleType("hrms.hr.doctype.bei_production")
	)

	fake_commissary = types.ModuleType("hrms.api.commissary")
	fake_commissary.resolve_outsourced_item_flag = lambda item_code=None, item_name=None, item_meta=None: {
		"is_outsourced_item": bool((item_code or "").upper().startswith("OUT-")),
		"reason": "prefix:OUT" if bool((item_code or "").upper().startswith("OUT-")) else "none",
	}
	sys.modules["hrms.api.commissary"] = fake_commissary

	module_path = (
		Path(__file__).resolve().parents[1] / "hr" / "doctype" / "bei_production" / "bei_production.py"
	)
	spec = importlib.util.spec_from_file_location("bei_production_under_test", module_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


bei_production = _load_production_module()


class TestCommissaryOutsourcedItemFlag(unittest.TestCase):
	def test_before_save_flags_outsourced_item_and_adds_audit_marker(self):
		doc = bei_production.BEIProduction()
		doc.item_code = "OUT-BP-SAUCE"
		doc.item_name = "Outsourced BP Sauce"
		doc.qty_planned = 100
		doc.qty_produced = 95
		doc.remarks = "Initial run"

		doc.before_save()

		self.assertEqual(round(doc.yield_pct, 2), 95.0)
		self.assertEqual(doc.is_outsourced_item, 1)
		self.assertEqual(doc.outsourced_flag_reason, "prefix:OUT")
		self.assertIn("[OUTSOURCED:prefix:OUT]", doc.remarks)

	def test_before_save_marks_non_outsourced_item_cleanly(self):
		doc = bei_production.BEIProduction()
		doc.item_code = "FG-BP-SAUCE"
		doc.item_name = "BP Sauce"
		doc.qty_planned = 100
		doc.qty_produced = 100
		doc.remarks = "In-house"

		doc.before_save()

		self.assertEqual(doc.is_outsourced_item, 0)
		self.assertEqual(doc.outsourced_flag_reason, "none")
		self.assertNotIn("OUTSOURCED", doc.remarks)
