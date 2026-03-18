import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


class _FakeFrappe(types.ModuleType):
	def __getattr__(self, name):
		if name == "db":
			return self.local.db
		if name == "session":
			return self.local.session
		raise AttributeError(name)


class _FakeQualityInspection:
	def __init__(self):
		self.doctype = "Quality Inspection"
		self.name = "QI-TEST-0001"
		self.inspection_type = None
		self.reference_type = None
		self.reference_name = None
		self.item_code = None
		self.sample_size = None
		self.inspected_by = None
		self.status = None
		self.manual_inspection = 0
		self.batch_no = None
		self.remarks = None
		self.readings = []
		self.insert_called = False
		self.submit_called = False

	def append(self, table, row):
		self.readings.append(types.SimpleNamespace(**row))

	def insert(self, ignore_permissions=False):
		self.insert_called = ignore_permissions
		return self

	def submit(self):
		self.submit_called = True
		return self


class _FakeStockEntry:
	def __init__(self):
		self.doctype = "Stock Entry"
		self.name = "MAT-STE-WASTE-0001"
		self.company = None
		self.stock_entry_type = None
		self.purpose = None
		self.remarks = None
		self.flags = None
		self.items = []
		self.insert_called = False
		self.submit_called = False

	def append(self, table, row):
		self.items.append(types.SimpleNamespace(**row))
		return self.items[-1]

	def insert(self, ignore_permissions=False):
		self.insert_called = ignore_permissions
		return self

	def submit(self):
		self.submit_called = True
		return self


_DOCS_CREATED: list[_FakeQualityInspection] = []


def _install_fake_modules():
	if "frappe" not in sys.modules:
		frappe = _FakeFrappe("frappe")
		utils = types.ModuleType("frappe.utils")

		def whitelist(*args, **kwargs):
			def decorator(fn):
				return fn

			return decorator

		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.local = types.SimpleNamespace(
			session=types.SimpleNamespace(user="test.commissary@bebang.ph"),
			db=types.SimpleNamespace(
				get_value=lambda doctype, filters, fieldname=None, as_dict=False: (
					types.SimpleNamespace(qty=12, batch_no="BATCH-001")
					if doctype == "Stock Entry Detail"
					else None
				),
				savepoint=lambda name: None,
				release_savepoint=lambda name: None,
				rollback=lambda save_point=None: None,
			),
		)

		def _new_doc(doctype):
			doc = _FakeQualityInspection() if doctype == "Quality Inspection" else _FakeStockEntry()
			_DOCS_CREATED.append(doc)
			return doc

		frappe.new_doc = _new_doc
		frappe.get_doc = lambda doctype, name=None: None
		frappe.utils = utils

		utils.today = lambda: "2026-03-12"
		utils.add_days = lambda value, days: "2026-03-05"
		utils.flt = lambda value, precision=None: float(value or 0)

		sys.modules["frappe"] = frappe
		sys.modules["frappe.utils"] = utils

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.api" not in sys.modules:
		hrms_api_pkg = types.ModuleType("hrms.api")
		hrms_api_pkg.__path__ = []
		sys.modules["hrms.api"] = hrms_api_pkg

	if "hrms.utils" not in sys.modules:
		hrms_utils_pkg = types.ModuleType("hrms.utils")
		hrms_utils_pkg.__path__ = []
		sys.modules["hrms.utils"] = hrms_utils_pkg

	commissary_mod = types.ModuleType("hrms.api.commissary")
	commissary_mod.get_commissary_warehouse = lambda: "Shaw BLVD - BKI"
	commissary_mod.get_commissary_company = lambda: "Bebang Kitchen Inc."
	sys.modules["hrms.api.commissary"] = commissary_mod

	scm_roles_mod = types.ModuleType("hrms.utils.scm_roles")
	scm_roles_mod.SCM_COMMISSARY_ROLES = {"Commissary Supervisor", "Warehouse User"}
	scm_roles_mod.check_scm_permission = lambda roles, action="": None
	sys.modules["hrms.utils.scm_roles"] = scm_roles_mod


_install_fake_modules()

module_spec = importlib.util.spec_from_file_location(
	"commissary_quality_under_test",
	ROOT / "hrms" / "api" / "commissary_quality.py",
)
commissary_quality = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(commissary_quality)


class TestS37CommissaryQualityContract(unittest.TestCase):
	def test_get_pending_inspections_accepts_no_bom_production_receipts(self):
		captured: dict[str, object] = {}

		def fake_sql(query, params=None, as_dict=False):
			captured["query"] = query
			captured["params"] = params
			captured["as_dict"] = as_dict
			return [
				{
					"name": "STE-ROW-0001",
					"reference_name": "MAT-STE-0001",
					"posting_date": "2026-03-12",
					"item_code": "FG002-A",
					"item_name": "BANANA CINNAMON",
					"qty": 5,
					"uom": "KG",
					"quality_inspection_template": "Commissary FG QC",
				}
			]

		commissary_quality.frappe.db.sql = fake_sql

		result = commissary_quality.get_pending_inspections()

		self.assertTrue(result["success"])
		self.assertEqual(result["total"], 1)
		self.assertEqual(result["data"][0]["name"], "STE-ROW-0001")
		self.assertEqual(result["data"][0]["reference_name"], "MAT-STE-0001")
		self.assertIn("Material Receipt", str(captured.get("query", "")))
		self.assertIn("Production output", str(captured.get("query", "")))
		self.assertEqual(captured.get("params"), "Shaw BLVD - BKI")
		self.assertTrue(captured.get("as_dict"))

	def test_create_quality_inspection_accepts_portal_readings_array_and_notes(self):
		_DOCS_CREATED.clear()
		result = commissary_quality.create_quality_inspection(
			stock_entry_name="STE-0001",
			item_code="FG004",
			readings=json.dumps(
				[
					{"specification": "Visual Appearance", "status": "Accepted"},
					{
						"specification": "Texture/Consistency",
						"status": "Rejected",
						"reading_value": "Too soft",
					},
				]
			),
			status="Rejected",
			remarks="Texture check failed during QA",
		)

		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["name"], "QI-TEST-0001")
		self.assertEqual(result["data"]["status"], "Rejected")
		self.assertEqual(len(_DOCS_CREATED), 1)

		created = _DOCS_CREATED[0]
		self.assertEqual(created.reference_name, "STE-0001")
		self.assertEqual(created.item_code, "FG004")
		self.assertEqual(created.remarks, "Texture check failed during QA")
		self.assertTrue(created.insert_called)
		self.assertTrue(created.submit_called)
		self.assertEqual(len(created.readings), 2)
		self.assertEqual(created.readings[0].specification, "Visual Appearance")
		self.assertEqual(created.readings[0].status, "Accepted")
		self.assertEqual(created.readings[1].specification, "Texture/Consistency")
		self.assertEqual(created.readings[1].status, "Rejected")
		self.assertEqual(created.readings[1].reading_1, "Too soft")

	def test_create_quality_inspection_marks_template_rows_manual_and_prefills_readings(self):
		_DOCS_CREATED.clear()
		original_get_value = commissary_quality.frappe.db.get_value
		original_get_doc = commissary_quality.frappe.get_doc

		def fake_get_value(doctype, filters, fieldname=None, as_dict=False):
			if doctype == "Stock Entry Detail":
				return types.SimpleNamespace(qty=4, batch_no="BATCH-TEMPLATE")
			if doctype == "Item" and fieldname == "quality_inspection_template":
				return "Commissary FG QC"
			return original_get_value(doctype, filters, fieldname, as_dict)

		def fake_get_doc(doctype, name=None):
			if doctype == "Quality Inspection Template" and name == "Commissary FG QC":
				return types.SimpleNamespace(
					item_quality_inspection_parameter=[
						types.SimpleNamespace(specification="Visual Appearance", value="No defects, correct color"),
						types.SimpleNamespace(specification="Temperature", value="-18°C to 4°C range"),
					]
				)
			return original_get_doc(doctype, name)

		commissary_quality.frappe.db.get_value = fake_get_value
		commissary_quality.frappe.get_doc = fake_get_doc
		try:
			result = commissary_quality.create_quality_inspection(
				stock_entry_name="STE-TEMPLATE-0001",
				item_code="FG002-A",
				readings=json.dumps([{"specification": "Temperature", "status": "Accepted"}]),
				status="Accepted",
				remarks="Template-backed QA",
			)
		finally:
			commissary_quality.frappe.db.get_value = original_get_value
			commissary_quality.frappe.get_doc = original_get_doc

		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["status"], "Accepted")
		self.assertEqual(len(_DOCS_CREATED), 1)

		created = _DOCS_CREATED[0]
		self.assertEqual(created.manual_inspection, 1)
		self.assertEqual(len(created.readings), 2)
		self.assertEqual(created.readings[0].specification, "Visual Appearance")
		self.assertEqual(created.readings[0].manual_inspection, 1)
		self.assertEqual(created.readings[0].reading_1, "No defects, correct color")
		self.assertEqual(created.readings[0].status, "Accepted")
		self.assertEqual(created.readings[1].specification, "Temperature")
		self.assertEqual(created.readings[1].manual_inspection, 1)
		self.assertEqual(created.readings[1].reading_1, "-18°C to 4°C range")
		self.assertEqual(created.readings[1].status, "Accepted")

	def test_log_wastage_uses_commissary_company_and_role_gated_submit(self):
		_DOCS_CREATED.clear()
		original_get_value = commissary_quality.frappe.db.get_value
		original_get_doc = commissary_quality.frappe.get_doc

		def fake_get_value(doctype, filters, fieldname=None, as_dict=False):
			if doctype == "Item":
				return types.SimpleNamespace(item_name="TAPIOCA", stock_uom="KG", valuation_rate=0)
			return original_get_value(doctype, filters, fieldname, as_dict)

		def fake_get_doc(doctype, name=None):
			if doctype == "Stock Entry":
				return _DOCS_CREATED[-1]
			return original_get_doc(doctype, name)

		commissary_quality.frappe.db.get_value = fake_get_value
		commissary_quality.frappe.get_doc = fake_get_doc
		try:
			result = commissary_quality.log_wastage(
				item_code="FG009",
				qty=2,
				reason_code="expired",
				remarks="S078 wastage hardening",
			)
		finally:
			commissary_quality.frappe.db.get_value = original_get_value
			commissary_quality.frappe.get_doc = original_get_doc

		self.assertTrue(result["success"])
		created = _DOCS_CREATED[-1]
		self.assertEqual(created.company, "Bebang Kitchen Inc.")
		self.assertEqual(created.stock_entry_type, "Material Issue")
		self.assertTrue(created.insert_called)
		self.assertTrue(created.submit_called)
		self.assertTrue(created.flags.ignore_permissions)
		self.assertTrue(created.flags.ignore_user_permissions)
		self.assertEqual(created.items[0].allow_zero_valuation_rate, 1)
		self.assertEqual(created.items[0].valuation_rate, 0)


if __name__ == "__main__":
	unittest.main()
