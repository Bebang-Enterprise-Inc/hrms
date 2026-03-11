import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_dependencies():
	frappe = sys.modules.get("frappe") or types.ModuleType("frappe")
	utils = sys.modules.get("frappe.utils") or types.ModuleType("frappe.utils")

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	frappe.whitelist = getattr(frappe, "whitelist", whitelist)
	frappe._ = getattr(frappe, "_", lambda text: text)
	frappe.throw = getattr(
		frappe, "throw", lambda message, exc=None: (_ for _ in ()).throw(Exception(message))
	)
	frappe.ValidationError = getattr(frappe, "ValidationError", type("ValidationError", (Exception,), {}))
	frappe.__dict__.setdefault("local", types.SimpleNamespace())
	if not getattr(frappe.local, "db", None):
		frappe.local.db = types.SimpleNamespace(
			get_value=lambda *args, **kwargs: None,
			exists=lambda *args, **kwargs: False,
		)
	if not getattr(frappe.local, "session", None):
		frappe.local.session = types.SimpleNamespace(user="test.supervisor@bebang.ph")
	frappe.__dict__.setdefault("db", frappe.local.db)
	frappe.get_doc = getattr(frappe, "get_doc", lambda *args, **kwargs: None)
	frappe.delete_doc = getattr(frappe, "delete_doc", lambda *args, **kwargs: None)
	frappe.get_all = getattr(frappe, "get_all", lambda *args, **kwargs: [])
	frappe.__dict__.setdefault("session", frappe.local.session)

	utils.add_days = getattr(utils, "add_days", lambda value, days: value)
	utils.cint = getattr(utils, "cint", lambda value: int(float(value or 0)))
	utils.get_time = getattr(utils, "get_time", lambda value: value)
	utils.now_datetime = getattr(utils, "now_datetime", lambda: "2026-03-11 18:50:00")
	utils.nowdate = getattr(utils, "nowdate", lambda: "2026-03-11")

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

	if "hrms.api.store" not in sys.modules:
		store_mod = types.ModuleType("hrms.api.store")
		store_mod.resolve_employee_store_context = lambda *args, **kwargs: {}
		store_mod.resolve_warehouse = lambda *args, **kwargs: {}
		sys.modules["hrms.api.store"] = store_mod

	if "hrms.utils.store_shift_config" not in sys.modules:
		config_mod = types.ModuleType("hrms.utils.store_shift_config")
		config_mod.get_shift_options_for_store = lambda *args, **kwargs: []
		sys.modules["hrms.utils.store_shift_config"] = config_mod


_install_fake_dependencies()
spec = importlib.util.spec_from_file_location(
	"supervisor_under_test_permissions",
	ROOT / "hrms" / "api" / "supervisor.py",
)
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)


class _FakeShiftAssignment:
	def __init__(self, docstatus=0):
		self.docstatus = docstatus
		self.flags = types.SimpleNamespace(ignore_permissions=False, ignore_user_permissions=False)
		self.insert_kwargs = None
		self.cancel_called = False
		self.submit_called = False

	def insert(self, **kwargs):
		self.insert_kwargs = kwargs

	def cancel(self):
		self.cancel_called = True

	def submit(self):
		self.submit_called = True


class _AttrDict(dict):
	__getattr__ = dict.get


class TestS033LaborPlanShiftAssignmentPermissions(unittest.TestCase):
	def test_cancel_and_delete_shift_assignment_uses_system_permission_flags(self):
		doc = _FakeShiftAssignment(docstatus=1)
		delete_doc = MagicMock()

		with (
			patch.object(supervisor.frappe, "get_doc", return_value=doc),
			patch.object(supervisor.frappe, "delete_doc", delete_doc),
		):
			supervisor._cancel_and_delete_shift_assignment("SHIFT-0001")

		self.assertTrue(doc.flags.ignore_permissions)
		self.assertTrue(doc.flags.ignore_user_permissions)
		self.assertTrue(doc.cancel_called)
		delete_doc.assert_called_once_with("Shift Assignment", "SHIFT-0001", ignore_permissions=True)

	def test_create_shift_assignment_from_plan_uses_system_permission_flags_before_submit(self):
		doc = _FakeShiftAssignment(docstatus=0)
		row = types.SimpleNamespace(employee="TEST-CREW-001", shift_type_name="Opening")
		plan = types.SimpleNamespace(name="BEI-WLP-2026-00007")

		with (
			patch.object(
				supervisor.frappe.db,
				"get_value",
				return_value=_AttrDict(company="Bebang Enterprise Inc.", branch="Araneta Gateway"),
			),
			patch.object(supervisor, "_ensure_shift_type_for_plan_row", return_value="Opening"),
			patch.object(supervisor.frappe, "get_doc", return_value=doc),
		):
			result = supervisor._create_shift_assignment_from_plan(
				plan=plan,
				row=row,
				work_date="2026-05-04",
				publish_run_id="2026-03-11 18:50:00",
			)

		self.assertIs(result, doc)
		self.assertTrue(doc.flags.ignore_permissions)
		self.assertTrue(doc.flags.ignore_user_permissions)
		self.assertEqual(doc.insert_kwargs, {"ignore_permissions": True})
		self.assertTrue(doc.submit_called)


if __name__ == "__main__":
	unittest.main()
