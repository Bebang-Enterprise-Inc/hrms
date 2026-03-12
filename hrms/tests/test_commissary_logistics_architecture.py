import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _install_frappe_stubs():
	if "frappe" in sys.modules:
		return

	def _whitelist(fn=None, *args, **kwargs):
		if fn is None:
			return lambda real_fn: real_fn
		return fn

	fake_frappe = types.ModuleType("frappe")
	fake_frappe.whitelist = _whitelist
	fake_frappe._ = lambda msg: msg
	fake_frappe.throw = lambda msg: (_ for _ in ()).throw(ValueError(msg))
	fake_frappe.db = types.SimpleNamespace(
		exists=lambda *a, **k: False, count=lambda *a, **k: 0, sql=lambda *a, **k: []
	)
	fake_frappe.get_doc = lambda *a, **k: None
	sys.modules["frappe"] = fake_frappe

	fake_utils = types.ModuleType("frappe.utils")
	fake_utils.today = lambda: "2026-02-28"
	fake_utils.add_days = lambda d, n: d
	fake_utils.flt = float
	sys.modules["frappe.utils"] = fake_utils

	sys.modules.setdefault("frappe.model", types.ModuleType("frappe.model"))
	fake_document = types.ModuleType("frappe.model.document")

	class _Document:
		pass

	fake_document.Document = _Document
	sys.modules["frappe.model.document"] = fake_document


def _load_module(module_name, rel_path):
	_install_frappe_stubs()
	module_path = Path(__file__).resolve().parents[1] / rel_path
	spec = importlib.util.spec_from_file_location(module_name, module_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def _load_dashboard_module():
	_install_frappe_stubs()
	sys.modules.setdefault("hrms", types.ModuleType("hrms"))
	sys.modules.setdefault("hrms.api", types.ModuleType("hrms.api"))
	sys.modules.setdefault("hrms.utils", types.ModuleType("hrms.utils"))

	fake_commissary = types.ModuleType("hrms.api.commissary")
	fake_commissary.get_commissary_warehouse = lambda: "Shaw BLVD - BKI"
	sys.modules["hrms.api.commissary"] = fake_commissary

	fake_bei_config = types.ModuleType("hrms.utils.bei_config")
	fake_bei_config.get_company = lambda: "Bebang Enterprise Inc."
	sys.modules["hrms.utils.bei_config"] = fake_bei_config

	return _load_module("commissary_dashboard_under_test", Path("api") / "commissary_dashboard.py")


bei_route = _load_module("bei_route_under_test", Path("hr") / "doctype" / "bei_route" / "bei_route.py")
commissary_dashboard = _load_dashboard_module()


class TestCommissaryLogisticsArchitecture(unittest.TestCase):
	def test_route_resolves_direct_mode_from_notes(self):
		route = bei_route.BEIRoute()
		route.notes = "dispatch plan mode:direct for sprint c"
		mode = route.resolve_architecture_mode()
		self.assertEqual(mode, "direct")
		self.assertIn("Direct", route.architecture_hint())

	def test_route_rejects_invalid_architecture_mode(self):
		route = bei_route.BEIRoute()
		route.architecture_mode = "hybrid"
		with self.assertRaises(ValueError):
			route.resolve_architecture_mode()

	def test_dashboard_reports_route_architecture_mode(self):
		class _RouteDoc:
			def resolve_architecture_mode(self):
				return "direct"

			def architecture_hint(self):
				return "Direct store dispatch mode: transfers bypass external hubs."

		commissary_dashboard.frappe.db.exists = (
			lambda doctype, name: doctype == "BEI Route" and name == "ROUTE-001"
		)
		commissary_dashboard.frappe.get_doc = lambda doctype, name: _RouteDoc()

		result = commissary_dashboard.get_logistics_architecture_mode("ROUTE-001")
		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["architecture_mode"], "direct")
		self.assertIn("bypass external hubs", result["data"]["hint"])
