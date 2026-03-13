import importlib.util
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


class _FakeStockEntry:
	def __init__(self):
		self.doctype = "Stock Entry"
		self.name = "MAT-STE-TEST-0001"
		self.stock_entry_type = None
		self.company = None
		self.posting_date = None
		self.posting_time = None
		self.from_warehouse = None
		self.remarks = None
		self.items = []
		self.custom_request_source = None
		self.custom_return_photo = None
		self.insert_called = False
		self.submit_called = False

	def append(self, table, row):
		self.items.append(types.SimpleNamespace(**row))

	def insert(self, ignore_permissions=True):
		self.insert_called = True

	def submit(self):
		self.submit_called = True


_DOCS_CREATED: list[_FakeStockEntry] = []


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
		frappe.throw = lambda message, exc=None, title=None: (_ for _ in ()).throw(Exception(message))
		frappe.log_error = lambda *args, **kwargs: None
		frappe.local = types.SimpleNamespace(session=types.SimpleNamespace(user="test.supervisor@bebang.ph"))
		frappe.get_roles = lambda user=None: ["Store Supervisor"]
		frappe.local.db = types.SimpleNamespace(
			exists=lambda doctype, value: False,
			get_value=lambda doctype, filters, fieldname=None, order_by=None, as_dict=False: (
				"Bebang Enterprise Inc." if doctype == "Warehouse" else None
			),
			has_column=lambda doctype, fieldname: True,
			savepoint=lambda name: None,
			release_savepoint=lambda name: None,
			rollback=lambda save_point=None: None,
		)

		def _new_doc(doctype):
			doc = _FakeStockEntry()
			_DOCS_CREATED.append(doc)
			return doc

		def _get_doc(doctype, name=None):
			if doctype == "BEI Store Receiving":
				return types.SimpleNamespace(store="TEST-STORE-BGC - BEI")
			if doctype == "Item":
				return types.SimpleNamespace(
					item_name=f"Item {name}", description=f"Item {name}", stock_uom="Nos"
				)
			return None

		frappe.new_doc = _new_doc
		frappe.get_doc = _get_doc
		frappe.get_all = lambda *args, **kwargs: []
		frappe.utils = utils

		utils.add_days = lambda date, days: "2026-03-13"
		utils.cint = lambda value: int(value or 0)
		utils.flt = lambda value, precision=None: float(value or 0)
		utils.get_datetime = lambda value=None: value
		utils.getdate = lambda value=None: value
		utils.now_datetime = lambda: "2026-03-12 09:00:00"
		utils.nowdate = lambda: "2026-03-12"
		utils.today = lambda: "2026-03-12"

		sys.modules["frappe"] = frappe
		sys.modules["frappe.utils"] = utils

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.utils" not in sys.modules:
		hrms_utils_pkg = types.ModuleType("hrms.utils")
		hrms_utils_pkg.__path__ = []
		sys.modules["hrms.utils"] = hrms_utils_pkg

	if "hrms.utils.bei_config" not in sys.modules:
		bei_config_mod = types.ModuleType("hrms.utils.bei_config")
		bei_config_mod.get_company = lambda: "Bebang Enterprise Inc."
		sys.modules["hrms.utils.bei_config"] = bei_config_mod

	if "hrms.utils.scm_roles" not in sys.modules:
		scm_roles_mod = types.ModuleType("hrms.utils.scm_roles")
		scm_roles_mod.SCM_APPROVAL_ROLES = ["Warehouse User"]
		scm_roles_mod.check_scm_permission = lambda roles, action: None
		sys.modules["hrms.utils.scm_roles"] = scm_roles_mod

	if "hrms.utils.supply_chain_contracts" not in sys.modules:
		contracts_spec = importlib.util.spec_from_file_location(
			"hrms.utils.supply_chain_contracts",
			ROOT / "hrms" / "utils" / "supply_chain_contracts.py",
		)
		contracts_mod = importlib.util.module_from_spec(contracts_spec)
		contracts_spec.loader.exec_module(contracts_mod)
		sys.modules["hrms.utils.supply_chain_contracts"] = contracts_mod


_install_fake_modules()

store_spec = importlib.util.spec_from_file_location(
	"store_under_test",
	ROOT / "hrms" / "api" / "store.py",
)
store = importlib.util.module_from_spec(store_spec)
store_spec.loader.exec_module(store)


class TestS37StoreDisposalContract(unittest.TestCase):
	def test_create_store_disposal_creates_material_issue_with_disposal_contract(self):
		_DOCS_CREATED.clear()
		original_stamp = store.stamp_stock_entry_contract
		original_save_image = store.save_base64_image
		stamp_calls = []
		try:
			store.stamp_stock_entry_contract = lambda doc, **kwargs: stamp_calls.append(kwargs)
			store.save_base64_image = (
				lambda photo, doctype, docname=None, fieldname="photo": "/files/disposal-proof.jpg"
			)

			result = store.create_store_disposal(
				receiving="BEI-RCV-TEST-0001",
				items=[{"item_code": "FG-001", "qty": 2, "reason": "damaged"}],
				reason="damaged",
				photo="data:image/png;base64,ZmFrZQ==",
			)
		finally:
			store.stamp_stock_entry_contract = original_stamp
			store.save_base64_image = original_save_image

		self.assertTrue(result["success"])
		self.assertEqual(result["stock_entry"], "MAT-STE-TEST-0001")
		self.assertEqual(len(_DOCS_CREATED), 1)

		created = _DOCS_CREATED[0]
		self.assertEqual(created.stock_entry_type, "Material Issue")
		self.assertEqual(created.company, "Bebang Enterprise Inc.")
		self.assertEqual(created.from_warehouse, "TEST-STORE-BGC - BEI")
		self.assertIn("Store Disposal from TEST-STORE-BGC - BEI", created.remarks)
		self.assertTrue(created.insert_called)
		self.assertTrue(created.submit_called)
		self.assertEqual(created.custom_return_photo, "/files/disposal-proof.jpg")
		self.assertEqual(created.items[0].item_code, "FG-001")
		self.assertEqual(created.items[0].qty, 2)
		self.assertEqual(stamp_calls[0]["request_source"], "store_disposal")


if __name__ == "__main__":
	unittest.main()
