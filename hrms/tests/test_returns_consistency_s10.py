import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


class _FakeStockEntry:
	def __init__(self):
		self.name = "STE-RET-0001"
		self.items = []
		self.stock_entry_type = None
		self.company = None
		self.custom_return_request = None
		self.custom_return_from_store = None
		self.custom_return_photo = None
		self.set_posting_time = None
		self.posting_date = None
		self.posting_time = None
		self.remarks = None
		self.from_warehouse = None
		self.to_warehouse = None

	def append(self, table, row):
		self.items.append(types.SimpleNamespace(**row))

	def insert(self, **kwargs):
		return self

	def submit(self):
		return self


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
		frappe.PermissionError = type("PermissionError", (Exception,), {})
		frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
		frappe.log_error = lambda *args, **kwargs: None
		frappe.get_traceback = lambda: "traceback"
		frappe.parse_json = json.loads
		frappe.session = types.SimpleNamespace(user="test.supervisor@bebang.ph")
		frappe.get_roles = lambda user=None: ["Store Supervisor"]

		frappe.db = types.SimpleNamespace(
			exists=lambda doctype, value: bool(value),
			get_value=lambda doctype, filters, fieldname=None, order_by=None: None,
			sql=lambda *args, **kwargs: [],
			get_all=lambda *args, **kwargs: [],
			set_value=lambda *args, **kwargs: None,
		)
		frappe.new_doc = lambda doctype: _FakeStockEntry()
		frappe.get_doc = lambda doctype, name=None: None
		frappe.get_all = lambda *args, **kwargs: []
		frappe.utils = utils

		utils.today = lambda: "2026-02-28"
		utils.nowtime = lambda: "10:00:00"
		utils.nowdate = lambda: "2026-02-28"
		utils.now_datetime = lambda: "2026-02-28 10:00:00"
		utils.flt = lambda value, precision=None: float(value or 0)
		utils.add_days = lambda date, days: date

		sys.modules["frappe"] = frappe
		sys.modules["frappe.utils"] = utils

	frappe = sys.modules["frappe"]
	utils = sys.modules.get("frappe.utils")
	if utils is None:
		utils = types.ModuleType("frappe.utils")
		sys.modules["frappe.utils"] = utils
	frappe.utils = utils

	if not hasattr(frappe, "whitelist"):
		def whitelist(*args, **kwargs):
			def decorator(fn):
				return fn
			return decorator
		frappe.whitelist = whitelist
	if not hasattr(frappe, "_"):
		frappe._ = lambda text: text
	if not hasattr(frappe, "throw"):
		def _throw(message, exc=None, title=None):
			if isinstance(exc, type) and issubclass(exc, Exception):
				raise exc(message)
			raise Exception(message)
		frappe.throw = _throw
	if not hasattr(frappe, "PermissionError"):
		frappe.PermissionError = type("PermissionError", (Exception,), {})
	if not hasattr(frappe, "DoesNotExistError"):
		frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
	if not hasattr(frappe, "parse_json"):
		frappe.parse_json = json.loads
	if not hasattr(frappe, "session"):
		frappe.session = types.SimpleNamespace(user="test.supervisor@bebang.ph")
	if not hasattr(frappe, "get_roles"):
		frappe.get_roles = lambda user=None: ["Store Supervisor"]
	if not hasattr(frappe, "db"):
		frappe.db = types.SimpleNamespace(
			exists=lambda doctype, value: bool(value),
			get_value=lambda doctype, filters, fieldname=None, order_by=None: None,
			sql=lambda *args, **kwargs: [],
			get_all=lambda *args, **kwargs: [],
			set_value=lambda *args, **kwargs: None,
		)
	if not hasattr(frappe, "new_doc"):
		frappe.new_doc = lambda doctype: _FakeStockEntry()
	if not hasattr(frappe, "get_doc"):
		frappe.get_doc = lambda doctype, name=None: None
	if not hasattr(frappe, "get_all"):
		frappe.get_all = lambda *args, **kwargs: []
	if not hasattr(frappe, "log_error"):
		frappe.log_error = lambda *args, **kwargs: None
	if not hasattr(frappe, "get_traceback"):
		frappe.get_traceback = lambda: "traceback"

	if not hasattr(utils, "today"):
		utils.today = lambda: "2026-02-28"
	if not hasattr(utils, "nowtime"):
		utils.nowtime = lambda: "10:00:00"
	if not hasattr(utils, "nowdate"):
		utils.nowdate = lambda: "2026-02-28"
	if not hasattr(utils, "now_datetime"):
		utils.now_datetime = lambda: "2026-02-28 10:00:00"
	if not hasattr(utils, "flt"):
		utils.flt = lambda value, precision=None: float(value or 0)
	if not hasattr(utils, "add_days"):
		utils.add_days = lambda date, days: date

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.utils" not in sys.modules:
		hrms_utils_pkg = types.ModuleType("hrms.utils")
		hrms_utils_pkg.__path__ = []
		sys.modules["hrms.utils"] = hrms_utils_pkg

	if "hrms.api" not in sys.modules:
		hrms_api_pkg = types.ModuleType("hrms.api")
		hrms_api_pkg.__path__ = []
		sys.modules["hrms.api"] = hrms_api_pkg

	if "hrms.utils.bei_config" not in sys.modules:
		bei_config_mod = types.ModuleType("hrms.utils.bei_config")
		bei_config_mod.get_company = lambda: "Bebang Enterprise Inc."
		sys.modules["hrms.utils.bei_config"] = bei_config_mod

	if "hrms.utils.scm_roles" not in sys.modules:
		scm_roles_mod = types.ModuleType("hrms.utils.scm_roles")
		sys.modules["hrms.utils.scm_roles"] = scm_roles_mod

	scm_roles_mod = sys.modules["hrms.utils.scm_roles"]
	scm_roles_mod.SCM_APPROVAL_ROLES = getattr(scm_roles_mod, "SCM_APPROVAL_ROLES", ["System Manager"])
	scm_roles_mod.SCM_INVENTORY_ROLES = getattr(scm_roles_mod, "SCM_INVENTORY_ROLES", ["System Manager"])
	scm_roles_mod.SCM_COMPLIANCE_ROLES = getattr(scm_roles_mod, "SCM_COMPLIANCE_ROLES", ["System Manager"])
	scm_roles_mod.SCM_STOCK_UPDATE_ROLES = getattr(scm_roles_mod, "SCM_STOCK_UPDATE_ROLES", ["System Manager"])
	scm_roles_mod.SCM_STORE_ROLES = getattr(scm_roles_mod, "SCM_STORE_ROLES", ["Store Supervisor"])
	scm_roles_mod.SCM_DISPATCH_ROLES = getattr(scm_roles_mod, "SCM_DISPATCH_ROLES", ["System Manager"])
	scm_roles_mod.check_scm_permission = getattr(
		scm_roles_mod,
		"check_scm_permission",
		lambda roles, action: None,
	)


_install_fake_modules()

inventory_spec = importlib.util.spec_from_file_location(
	"inventory_under_test",
	ROOT / "hrms" / "api" / "inventory.py",
)
inventory = importlib.util.module_from_spec(inventory_spec)
inventory_spec.loader.exec_module(inventory)

warehouse_spec = importlib.util.spec_from_file_location(
	"warehouse_under_test",
	ROOT / "hrms" / "api" / "warehouse.py",
)
warehouse = importlib.util.module_from_spec(warehouse_spec)
warehouse_spec.loader.exec_module(warehouse)


class _FakeMR:
	def __init__(self):
		self.status = "Ordered"
		self.items = [
			types.SimpleNamespace(item_code="ITM-001", name="MRI-001"),
			types.SimpleNamespace(item_code="ITM-002", name="MRI-002"),
		]


class _FakeItem:
	def __init__(self, item_code):
		self.name = item_code
		self.item_name = f"Item {item_code}"
		self.description = f"Desc {item_code}"
		self.stock_uom = "Nos"
		self.has_batch_no = False


class TestReturnsConsistencyS10(unittest.TestCase):
	def setUp(self):
		self.docs_created = []

		def _new_doc(doctype):
			doc = _FakeStockEntry()
			doc.name = "STE-0001"
			self.docs_created.append(doc)
			return doc

		inventory.frappe.new_doc = _new_doc
		warehouse.frappe.new_doc = _new_doc

	def test_submit_return_request_includes_consistent_transfer_contract_data(self):
		inventory.frappe.db.exists = lambda doctype, value: bool(value)
		inventory.frappe.db.get_value = (
			lambda doctype, filters, fieldname=None, order_by=None: f"Item {filters}" if doctype == "Item" else None
		)

		result = inventory.submit_return_request(
			store="STORE-A",
			items=[
				{"item_code": "ITM-001", "quantity": 2, "reason": "expired"},
				{"item_code": "ITM-002", "qty": 3, "reason": "damaged"},
			],
			photo=None,
		)

		self.assertTrue(result["success"])
		self.assertEqual(result["name"], "STE-0001")
		self.assertEqual(result["data"]["name"], "STE-0001")
		self.assertEqual(result["data"]["items_count"], 2)
		self.assertEqual(result["data"]["total_qty"], 5.0)
		self.assertEqual(result["data"]["movement_type"], "Material Issue")
		self.assertEqual(result["data"]["source_warehouse"], "STORE-A")

	def test_create_stock_transfer_accepts_quantity_alias_and_returns_consistent_data(self):
		warehouse.frappe.db.exists = lambda doctype, value: True
		warehouse.frappe.db.get_value = lambda doctype, filters, fieldname=None, order_by=None: None

		def _get_doc(doctype, name=None):
			if doctype == "Material Request":
				return _FakeMR()
			if doctype == "Item":
				return _FakeItem(name)
			return None

		warehouse.frappe.get_doc = _get_doc

		result = warehouse.create_stock_transfer(
			source_warehouse="COM - BEI",
			target_warehouse="STORE-A - BEI",
			items=[
				{"item_code": "ITM-001", "quantity": 4},
				{"item_code": "ITM-002", "qty": 1},
			],
			mr_name="MR-0001",
			remarks="S10 contract test",
		)

		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["name"], "STE-0001")
		self.assertEqual(result["data"]["items_count"], 2)
		self.assertEqual(result["data"]["total_qty"], 5.0)
		self.assertEqual(result["data"]["movement_type"], "Material Transfer")
		self.assertEqual(result["data"]["source_warehouse"], "COM - BEI")
		self.assertEqual(result["data"]["target_warehouse"], "STORE-A - BEI")


if __name__ == "__main__":
	unittest.main()
