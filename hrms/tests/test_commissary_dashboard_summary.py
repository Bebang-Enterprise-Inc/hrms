import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class _FakeFrappe(types.ModuleType):
	def __getattr__(self, name):
		if name == "db":
			return self.local.db
		if name == "session":
			return self.local.session
		raise AttributeError(name)


def _install_fake_modules():
	def _whitelist(fn=None, *args, **kwargs):
		if fn is None:
			return lambda real_fn: real_fn
		return fn

	fake_frappe = _FakeFrappe("frappe")
	fake_frappe._dict = lambda data: types.SimpleNamespace(**data)
	fake_frappe.local = types.SimpleNamespace(
		session=types.SimpleNamespace(user="test.commissary@bebang.ph"),
		db=types.SimpleNamespace(
			sql=lambda *args, **kwargs: [],
			count=lambda *args, **kwargs: 0,
			savepoint=lambda *args, **kwargs: None,
			release_savepoint=lambda *args, **kwargs: None,
			rollback=lambda *args, **kwargs: None,
		),
	)
	fake_frappe.get_all = lambda *args, **kwargs: []
	fake_frappe.whitelist = _whitelist
	fake_frappe.throw = lambda msg: (_ for _ in ()).throw(Exception(msg))
	fake_frappe._ = lambda msg: msg

	fake_utils = types.ModuleType("frappe.utils")
	fake_utils.flt = float
	fake_utils.today = lambda: "2026-03-12"
	fake_utils.add_days = lambda value, days: value
	fake_utils.nowtime = lambda: "12:00:00"
	fake_frappe.utils = fake_utils
	sys.modules["frappe"] = fake_frappe
	sys.modules["frappe.utils"] = fake_utils

	sys.modules.setdefault("hrms", types.ModuleType("hrms"))
	sys.modules.setdefault("hrms.api", types.ModuleType("hrms.api"))
	sys.modules.setdefault("hrms.utils", types.ModuleType("hrms.utils"))

	fake_commissary = types.ModuleType("hrms.api.commissary")
	fake_commissary.get_commissary_warehouse = lambda: "Shaw BLVD - BKI"
	fake_commissary.get_commissary_company = lambda: "Bebang Kitchen Inc."
	fake_commissary.resolve_outsourced_item_flag = (
		lambda item_code=None, item_name=None, item_meta=None: {
			"is_outsourced_item": False,
			"reason": "unit-test-default",
		}
	)
	sys.modules["hrms.api.commissary"] = fake_commissary

	fake_scm_roles = types.ModuleType("hrms.utils.scm_roles")
	fake_scm_roles.SCM_COMMISSARY_ROLES = {"Commissary Supervisor", "Warehouse User"}
	fake_scm_roles.check_scm_permission = lambda roles, action="": None
	sys.modules["hrms.utils.scm_roles"] = fake_scm_roles

	fake_bei_config = types.ModuleType("hrms.utils.bei_config")
	fake_bei_config.get_company = lambda: "Bebang Kitchen Inc."
	fake_bei_config.SPACE_OPS = "ops"
	fake_bei_config.get_chat_space = lambda *args, **kwargs: "spaces/OPS"
	sys.modules["hrms.utils.bei_config"] = fake_bei_config

	fake_sentry = types.ModuleType("hrms.utils.sentry")
	fake_sentry.set_backend_observability_context = lambda *args, **kwargs: None
	fake_sentry.capture_backend_message = lambda *args, **kwargs: None
	sys.modules["hrms.utils.sentry"] = fake_sentry


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
	def test_get_production_items_handles_missing_item_supplier_columns(self):
		sql_calls = []

		def fake_sql(query, *args, **kwargs):
			sql_calls.append(query)
			if "FROM `tabItem` i" in query:
				return [
					{
						"item_code": "FG-OUT-001",
						"item_name": "Finished Good Outsourced",
						"description": "Outsourced finished good",
						"stock_uom": "PC",
						"standard_rate": 0,
						"item_group": "Finished Goods",
						"current_stock": 3,
						"bom_name": None,
					}
				]
			return []

		with (
			patch.object(commissary_dashboard, "get_commissary_warehouse", return_value="Shaw BLVD - BKI"),
			patch.object(commissary_dashboard.frappe.db, "sql", side_effect=fake_sql, create=True),
			patch.object(commissary_dashboard.frappe.db, "has_column", return_value=False, create=True),
			patch.object(
				commissary_dashboard,
				"resolve_outsourced_item_flag",
				return_value={"is_outsourced_item": True, "reason": "unit-test-outsourced"},
			),
		):
			result = commissary_dashboard.get_production_items()

		self.assertTrue(result["success"])
		self.assertEqual(len(result["data"]), 1)
		self.assertNotIn("default_supplier", sql_calls[0])
		self.assertTrue(result["data"][0]["is_outsourced_item"])
		self.assertEqual(result["data"][0]["outsourced_flag_reason"], "unit-test-outsourced")

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
				create=True,
			),
			patch.object(
				commissary_dashboard.frappe.db,
				"sql",
				side_effect=sql_results,
				create=True,
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

	def test_submit_production_output_uses_commissary_company_for_bki_warehouse(self):
		created = {}

		class _FakeStockEntry:
			def __init__(self):
				self.doctype = "Stock Entry"
				self.company = None
				self.stock_entry_type = None
				self.posting_date = None
				self.posting_time = None
				self.to_warehouse = None
				self.remarks = None
				self.items = []
				self.insert_called = False
				self.submit_called = False
				self.name = "MAT-STE-UNIT-0001"

			def append(self, table, row):
				defaults = {"batch_no": None, "s_warehouse": None, "t_warehouse": None}
				defaults.update(row)
				self.items.append(types.SimpleNamespace(**defaults))
				return self.items[-1]

			def insert(self, ignore_permissions=False):
				self.insert_called = ignore_permissions
				return self

			def submit(self):
				self.submit_called = True
				return self

		def fake_new_doc(doctype):
			self.assertEqual(doctype, "Stock Entry")
			doc = _FakeStockEntry()
			created["doc"] = doc
			return doc

		def fake_get_doc(doctype, name=None):
			if doctype == "Stock Entry":
				return created["doc"]
			return types.SimpleNamespace(
				item_name="BANANA CINNAMON", description="Finished good", stock_uom="KG"
			)

		with (
			patch.object(commissary_dashboard, "get_commissary_warehouse", return_value="Shaw BLVD - BKI"),
			patch.object(commissary_dashboard, "get_commissary_company", return_value="Bebang Kitchen Inc."),
			patch.object(
				commissary_dashboard,
				"resolve_outsourced_item_flag",
				return_value={"is_outsourced_item": True, "reason": "unit-test-outsourced"},
			),
			patch.object(commissary_dashboard.frappe, "new_doc", side_effect=fake_new_doc, create=True),
			patch.object(
				commissary_dashboard.frappe.db,
				"get_value",
				side_effect=[
					{
						"item_name": "BANANA CINNAMON",
						"description": "Finished good",
						"stock_uom": "KG",
						"item_group": "Finished Goods",
						"default_supplier": "Bebang Outsourced",
					},
					None,
				],
				create=True,
			),
			patch.object(
				commissary_dashboard.frappe,
				"get_doc",
				side_effect=fake_get_doc,
				create=True,
			),
		):
			result = commissary_dashboard.submit_production_output(
				items='[{"item_code":"FG002-A","qty":1,"uom":"KG"}]',
				remarks="unit-test",
			)

		doc = created["doc"]
		self.assertEqual(doc.company, "Bebang Kitchen Inc.")
		self.assertEqual(doc.to_warehouse, "Shaw BLVD - BKI")
		self.assertEqual(doc.stock_entry_type, "Material Receipt")
		self.assertTrue(doc.insert_called)
		self.assertTrue(doc.submit_called)
		self.assertTrue(doc.flags.ignore_permissions)
		self.assertTrue(doc.flags.ignore_user_permissions)
		self.assertEqual(result["data"]["name"], "MAT-STE-UNIT-0001")

	def test_submit_production_output_skips_missing_supplier_columns(self):
		requested_fields = []
		created = {}

		class _FakeStockEntry:
			def __init__(self):
				self.doctype = "Stock Entry"
				self.company = None
				self.stock_entry_type = None
				self.posting_date = None
				self.posting_time = None
				self.to_warehouse = None
				self.remarks = None
				self.items = []
				self.name = "MAT-STE-UNIT-0002"

			def append(self, table, row):
				defaults = {"batch_no": None, "s_warehouse": None, "t_warehouse": None}
				defaults.update(row)
				self.items.append(types.SimpleNamespace(**defaults))
				return self.items[-1]

			def insert(self, ignore_permissions=False):
				return self

			def submit(self):
				return self

		def fake_get_value(doctype, name_or_filters, fields=None, as_dict=False):
			if doctype == "Item":
				requested_fields.extend(fields or [])
				return {
					"item_name": "Finished Good Outsourced",
					"description": "Outsourced finished good",
					"stock_uom": "PC",
					"item_group": "Finished Goods",
				}
			if doctype == "BOM":
				return None
			return None

		def fake_new_doc(doctype):
			doc = _FakeStockEntry()
			created["doc"] = doc
			return doc

		def fake_get_doc(doctype, name=None):
			if doctype == "Stock Entry":
				return created["doc"]
			return types.SimpleNamespace(
				item_name="Finished Good Outsourced",
				description="Outsourced finished good",
				stock_uom="PC",
			)

		with (
			patch.object(commissary_dashboard, "get_commissary_warehouse", return_value="Shaw BLVD - BKI"),
			patch.object(commissary_dashboard, "get_commissary_company", return_value="Bebang Kitchen Inc."),
			patch.object(commissary_dashboard.frappe.db, "get_value", side_effect=fake_get_value, create=True),
			patch.object(commissary_dashboard.frappe.db, "has_column", return_value=False, create=True),
			patch.object(
				commissary_dashboard,
				"resolve_outsourced_item_flag",
				return_value={"is_outsourced_item": True, "reason": "unit-test-outsourced"},
			),
			patch.object(commissary_dashboard.frappe, "new_doc", side_effect=fake_new_doc, create=True),
			patch.object(commissary_dashboard.frappe, "get_doc", side_effect=fake_get_doc, create=True),
		):
			result = commissary_dashboard.submit_production_output(
				items='[{"item_code":"FG-OUT-001","qty":1,"uom":"PC"}]',
				remarks="schema-safe test",
			)

		self.assertTrue(result["success"])
		self.assertEqual(
			requested_fields,
			["item_name", "description", "stock_uom", "item_group"],
		)


if __name__ == "__main__":
	unittest.main()
