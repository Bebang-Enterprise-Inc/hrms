import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


class _FakeMaterialRequest:
	def __init__(self):
		self.doctype = "Material Request"
		self.name = "MAT-REQ-0001"
		self.material_request_type = None
		self.company = None
		self.transaction_date = None
		self.schedule_date = None
		self.set_warehouse = None
		self.remarks = None
		self.items = []
		self.status = "Draft"
		self.docstatus = 0

	def append(self, table, row):
		self.items.append(types.SimpleNamespace(**row))

	def insert(self, ignore_permissions=False):
		return self

	def submit(self):
		self.docstatus = 1
		self.status = "Pending"
		return self


class _FakeItem:
	def __init__(self, item_code):
		self.name = item_code
		self.item_name = f"Item {item_code}"
		self.description = f"Desc {item_code}"
		self.stock_uom = "Kg"


_DOCS_CREATED: list[_FakeMaterialRequest] = []


def _install_fake_modules():
	if "frappe" not in sys.modules:
		frappe = types.ModuleType("frappe")
		utils = types.ModuleType("frappe.utils")

		def whitelist(*args, **kwargs):
			def decorator(fn):
				return fn

			return decorator

		def _throw(message, exc=None, title=None):
			if isinstance(exc, type) and issubclass(exc, Exception):
				raise exc(message)
			raise Exception(message)

		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.throw = _throw
		frappe.ValidationError = type("ValidationError", (Exception,), {})
		frappe.session = types.SimpleNamespace(user="bryan@bebang.ph")
		frappe.db = types.SimpleNamespace(
			exists=lambda doctype, value: False,
			has_column=lambda doctype, fieldname: False,
		)

		def _new_doc(doctype):
			doc = _FakeMaterialRequest()
			_DOCS_CREATED.append(doc)
			return doc

		frappe.new_doc = _new_doc
		frappe.get_doc = lambda doctype, name=None: _FakeItem(name)
		frappe.utils = utils

		utils.today = lambda: "2026-03-12"
		utils.add_days = lambda date, days: "2026-03-15"
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
	commissary_mod.get_commissary_warehouse = lambda: "Commissary - BEI"
	sys.modules["hrms.api.commissary"] = commissary_mod

	bei_config_mod = types.ModuleType("hrms.utils.bei_config")
	bei_config_mod.get_company = lambda: "Bebang Enterprise Inc."
	sys.modules["hrms.utils.bei_config"] = bei_config_mod

	spec = importlib.util.spec_from_file_location(
		"hrms.utils.supply_chain_contracts",
		ROOT / "hrms" / "utils" / "supply_chain_contracts.py",
	)
	contracts_mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(contracts_mod)
	sys.modules["hrms.utils.supply_chain_contracts"] = contracts_mod


_install_fake_modules()

module_spec = importlib.util.spec_from_file_location(
	"commissary_requisition_under_test",
	ROOT / "hrms" / "api" / "commissary_requisition.py",
)
commissary_requisition = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(commissary_requisition)


class TestS37CommissaryRequestContract(unittest.TestCase):
	def test_create_rm_requisition_auto_submits_into_warehouse_queue(self):
		_DOCS_CREATED.clear()
		result = commissary_requisition.create_rm_requisition(
			items=json.dumps([{"item_code": "RM-001", "qty": 5}]),
			remarks=None,
			source_warehouse="SHAW BLVD - BEBANG ENTERPRISE INC.",
		)

		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["name"], "MAT-REQ-0001")
		self.assertEqual(result["data"]["request_source"], "commissary_raw_material_request")
		self.assertIn("warehouse queue", result["message"].lower())
		self.assertEqual(result["data"]["status"], "Pending")
		self.assertEqual(len(_DOCS_CREATED), 1)
		created = _DOCS_CREATED[0]
		self.assertEqual(created.material_request_type, "Material Transfer")
		self.assertEqual(created.set_warehouse, "Commissary - BEI")
		self.assertEqual(created.items[0].from_warehouse, "SHAW BLVD - BEBANG ENTERPRISE INC.")
		self.assertEqual(created.docstatus, 1)
		self.assertEqual(created.status, "Pending")


if __name__ == "__main__":
	unittest.main()
