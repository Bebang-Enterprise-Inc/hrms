import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


class _LocalProxy:
	def __init__(self, getter):
		object.__setattr__(self, "_getter", getter)

	def __getattr__(self, name):
		return getattr(object.__getattribute__(self, "_getter")(), name)

	def __setattr__(self, name, value):
		setattr(object.__getattribute__(self, "_getter")(), name, value)


def _install_fake_modules():
	if "frappe" not in sys.modules:
		frappe = types.ModuleType("frappe")
		sys.modules["frappe"] = frappe
	else:
		frappe = sys.modules["frappe"]

	if "frappe.utils" not in sys.modules:
		utils = types.ModuleType("frappe.utils")
		sys.modules["frappe.utils"] = utils
	else:
		utils = sys.modules["frappe.utils"]

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	def _throw(message, exc=None):
		if isinstance(exc, type) and issubclass(exc, Exception):
			raise exc(message)
		raise Exception(message)

	if not hasattr(frappe, "ValidationError"):
		frappe.ValidationError = type("ValidationError", (Exception,), {})
	if not hasattr(frappe, "PermissionError"):
		frappe.PermissionError = type("PermissionError", (Exception,), {})
	if not hasattr(frappe, "DoesNotExistError"):
		frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})

	frappe.whitelist = whitelist
	frappe._ = lambda text: text
	frappe.throw = _throw
	frappe.local = types.SimpleNamespace()
	frappe.local.session = types.SimpleNamespace(user="approver@bebang.ph")
	frappe.get_roles = lambda user=None: ["System Manager"]
	frappe.log_error = lambda *args, **kwargs: None
	frappe.has_permission = lambda *args, **kwargs: True
	frappe.format_value = lambda value, _type=None: f"{float(value):.2f}"
	frappe.local.db = types.SimpleNamespace(
		sql=lambda *args, **kwargs: [],
		get_value=lambda *args, **kwargs: None,
		set_value=lambda *args, **kwargs: None,
		savepoint=lambda *args, **kwargs: None,
		release_savepoint=lambda *args, **kwargs: None,
		rollback=lambda *args, **kwargs: None,
	)
	frappe.__dict__["session"] = _LocalProxy(lambda: frappe.local.session)
	frappe.__dict__["db"] = _LocalProxy(lambda: frappe.local.db)

	utils.flt = lambda value, precision=None: float(value or 0)
	utils.now_datetime = lambda: datetime.datetime(2026, 3, 10, 10, 0, 0)
	utils.nowdate = lambda: "2026-03-10"
	utils.get_first_day = lambda value: value
	utils.get_last_day = lambda value: value
	utils.getdate = lambda value=None: datetime.date.fromisoformat(str(value or "2026-03-10")[:10])
	frappe.utils = utils

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.utils" not in sys.modules:
		hrms_utils_pkg = types.ModuleType("hrms.utils")
		hrms_utils_pkg.__path__ = []
		sys.modules["hrms.utils"] = hrms_utils_pkg

	bei_config = types.ModuleType("hrms.utils.bei_config")
	bei_config.get_company = lambda: "Bebang Enterprise Inc."
	sys.modules["hrms.utils.bei_config"] = bei_config

	store_type_mod = types.ModuleType("hrms.hr.doctype.bei_store_type.bei_store_type")
	store_type_mod.resolve_store_type = (
		lambda store_type=None, store_type_category=None: store_type or store_type_category
	)
	sys.modules["hrms.hr.doctype.bei_store_type.bei_store_type"] = store_type_mod

	scm_roles = types.ModuleType("hrms.utils.scm_roles")
	scm_roles.RATE_MANAGEMENT_ROLES = [
		"Accounts Manager",
		"Supply Chain Manager",
		"Warehouse User",
		"System Manager",
	]
	scm_roles.SCM_BILLING_ROLES = [
		"Accounts Manager",
		"Supply Chain Manager",
		"Warehouse User",
		"System Manager",
	]
	scm_roles.check_scm_permission = lambda roles, action=None: None
	sys.modules["hrms.utils.scm_roles"] = scm_roles


_install_fake_modules()

billing_spec = importlib.util.spec_from_file_location(
	"billing_under_test",
	ROOT / "hrms" / "api" / "billing.py",
)
billing = importlib.util.module_from_spec(billing_spec)
assert billing_spec and billing_spec.loader
billing_spec.loader.exec_module(billing)


class _RateDoc:
	def __init__(
		self,
		*,
		name="RATE-0001",
		store="TEST-STORE-BGC - BEI",
		cargo_type="Dry Goods",
		status="Pending Review",
		set_by="creator@bebang.ph",
		set_by_role="Finance",
	):
		self.name = name
		self.store = store
		self.cargo_type = cargo_type
		self.status = status
		self.set_by = set_by
		self.set_by_role = set_by_role
		self.reviewed_by = None
		self.reviewed_by_role = None
		self.reviewed_at = None
		self.save = MagicMock()


class TestBillingRateApprovalGuardS027(unittest.TestCase):
	def setUp(self):
		self.rate = _RateDoc()
		billing.frappe.local.session.user = "approver@bebang.ph"
		billing.frappe.get_doc = MagicMock(return_value=self.rate)
		billing.frappe.get_all = MagicMock(return_value=[types.SimpleNamespace(name="RATE-OLD-001")])
		billing.frappe.local.db.set_value = MagicMock()
		billing.frappe.get_roles = MagicMock(return_value=["Supply Chain Manager"])

	def test_self_approval_is_blocked(self):
		self.rate.set_by = "approver@bebang.ph"

		with self.assertRaisesRegex(Exception, "Cannot approve your own rate"):
			billing.approve_rate(self.rate.name)

		billing.frappe.db.set_value.assert_not_called()
		self.rate.save.assert_not_called()

	def test_same_department_approval_is_blocked(self):
		billing.frappe.get_roles = MagicMock(return_value=["Accounts Manager"])
		self.rate.set_by = "finance.creator@bebang.ph"
		self.rate.set_by_role = "Finance"

		with self.assertRaisesRegex(Exception, "approved by the other department"):
			billing.approve_rate(self.rate.name)

		billing.frappe.db.set_value.assert_not_called()
		self.rate.save.assert_not_called()

	def test_cross_department_approval_activates_rate_and_expires_prior_active(self):
		billing.frappe.get_roles = MagicMock(return_value=["Supply Chain Manager"])
		self.rate.set_by = "finance.creator@bebang.ph"
		self.rate.set_by_role = "Finance"

		result = billing.approve_rate(self.rate.name)

		self.assertTrue(result["success"])
		self.assertEqual(result["status"], "Active")
		self.assertEqual(self.rate.status, "Active")
		self.assertEqual(self.rate.reviewed_by, "approver@bebang.ph")
		self.assertEqual(self.rate.reviewed_by_role, "Supply Chain")
		billing.frappe.db.set_value.assert_called_once_with(
			"BEI Delivery Rate",
			"RATE-OLD-001",
			"status",
			"Expired",
		)
		self.rate.save.assert_called_once()

	def test_warehouse_user_is_treated_as_supply_chain_for_approval(self):
		billing.frappe.get_roles = MagicMock(return_value=["Warehouse User"])
		self.rate.set_by = "finance.creator@bebang.ph"
		self.rate.set_by_role = "Finance"

		result = billing.approve_rate(self.rate.name)

		self.assertTrue(result["success"])
		self.assertEqual(result["status"], "Active")
		self.assertEqual(self.rate.reviewed_by_role, "Supply Chain")


if __name__ == "__main__":
	unittest.main()
