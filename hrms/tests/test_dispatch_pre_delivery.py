import datetime
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_frappe_and_dependencies():
	if "frappe" not in sys.modules:
		frappe = types.ModuleType("frappe")
		utils = types.ModuleType("frappe.utils")

		def whitelist(*args, **kwargs):
			def decorator(fn):
				return fn

			return decorator

		def _throw(message, exc=None):
			if isinstance(exc, type) and issubclass(exc, Exception):
				raise exc(message)
			raise Exception(message)

		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.throw = _throw
		frappe.PermissionError = type("PermissionError", (Exception,), {})
		frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
		frappe.log_error = lambda *args, **kwargs: None
		frappe.logger = lambda: types.SimpleNamespace(info=lambda *args, **kwargs: None)
		frappe.get_traceback = lambda: "traceback"
		frappe.enqueue = lambda *args, **kwargs: None
		frappe.parse_json = json.loads
		frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")

		frappe.__dict__["db"] = types.SimpleNamespace(
			get_single_value=lambda *args, **kwargs: 1,
			exists=lambda *args, **kwargs: None,
			get_value=lambda *args, **kwargs: None,
			sql=lambda *args, **kwargs: [(0,)],
			savepoint=lambda name: name,
			release_savepoint=lambda name: None,
			rollback=lambda **kwargs: None,
			commit=lambda: None,
		)
		frappe.get_doc = lambda *args, **kwargs: types.SimpleNamespace(
			name="DOC-0001",
			stops=[],
			save=lambda **kw: None,
			reload=lambda: None,
		)
		frappe.get_all = lambda *args, **kwargs: []
		frappe.new_doc = lambda *args, **kwargs: types.SimpleNamespace(
			update=lambda *a, **k: None,
			insert=lambda **k: None,
			name="DOC-0001",
		)

		utils.nowdate = lambda: "2026-02-26"
		utils.now_datetime = lambda: datetime.datetime(2026, 2, 26, 10, 0, 0)
		utils.flt = lambda value, precision=None: float(value or 0)
		utils.cint = lambda value: int(float(value or 0))

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

	if "hrms.api" not in sys.modules:
		hrms_api_pkg = types.ModuleType("hrms.api")
		hrms_api_pkg.__path__ = []
		sys.modules["hrms.api"] = hrms_api_pkg

	if "hrms.utils.delivery_billing_policy" not in sys.modules:
		policy_mod = types.ModuleType("hrms.utils.delivery_billing_policy")

		class DeliveryBillingPolicyError(Exception):
			pass

		policy_mod.DeliveryBillingPolicyError = DeliveryBillingPolicyError
		policy_mod.should_auto_create_billing_on_delivery = lambda setting: True
		policy_mod.get_pre_delivery_exception_trace = lambda exception_doc, trip_reference, trip_stop_idx: {
			"exception_name": exception_doc.get("name") if isinstance(exception_doc, dict) else "EXC-0001",
			"cpo_approved_by": "mae@bebang.ph",
			"cpo_approved_at": "2026-02-26 10:00:00",
			"cfo_approved_by": "butch@bebang.ph",
			"cfo_approved_at": "2026-02-26 11:00:00",
			"approval_audit_log": "dual approval complete",
		}
		sys.modules["hrms.utils.delivery_billing_policy"] = policy_mod

	if "hrms.utils.scm_roles" not in sys.modules:
		scm_roles_mod = types.ModuleType("hrms.utils.scm_roles")
		scm_roles_mod.SCM_ADMIN_ROLES = ["System Manager"]
		scm_roles_mod.SCM_DISPATCH_ROLES = ["System Manager"]
		scm_roles_mod.SCM_STORE_ROLES = ["Store User"]
		scm_roles_mod.check_scm_permission = lambda roles, action: None
		sys.modules["hrms.utils.scm_roles"] = scm_roles_mod

	if "hrms.api.procurement" not in sys.modules:
		procurement_mod = types.ModuleType("hrms.api.procurement")
		procurement_mod.request_match_exception = lambda payload: {
			"success": True,
			"name": "BEI-EXC-0001",
			"payload": payload,
		}
		sys.modules["hrms.api.procurement"] = procurement_mod


_install_fake_frappe_and_dependencies()
dispatch_spec = importlib.util.spec_from_file_location(
	"dispatch_under_test",
	ROOT / "hrms" / "api" / "dispatch.py",
)
dispatch = importlib.util.module_from_spec(dispatch_spec)
dispatch_spec.loader.exec_module(dispatch)


class _Stop:
	def __init__(self, idx=1, status="Pending", billing_reference=None, billing_creation_status=None):
		self.idx = idx
		self.status = status
		self.billing_reference = billing_reference
		self.billing_creation_status = billing_creation_status


class _Trip:
	def __init__(self, stop):
		self.name = "TRIP-0001"
		self.stops = [stop]

	def save(self, **kwargs):
		return None


class TestDispatchPreDelivery(unittest.TestCase):
	def test_request_pre_delivery_billing_exception_requires_reason(self):
		with self.assertRaises(Exception):
			dispatch.request_pre_delivery_billing_exception("TRIP-0001", 1, "")

	def test_request_pre_delivery_billing_exception_calls_procurement_api(self):
		with patch(
			"hrms.api.procurement.request_match_exception",
			return_value={"success": True, "name": "BEI-EXC-0092"},
		) as request_match:
			result = dispatch.request_pre_delivery_billing_exception(
				trip_name="TRIP-0001",
				stop_idx=2,
				reason="Store requested advance billing before receipt",
			)

		request_match.assert_called_once()
		payload = request_match.call_args.args[0]
		self.assertEqual(payload["delivery_trip_reference"], "TRIP-0001")
		self.assertEqual(payload["delivery_stop_idx"], 2)
		self.assertEqual(result["name"], "BEI-EXC-0092")

	def test_get_pre_delivery_billing_exception_status_returns_latest(self):
		exceptions = [
			{"name": "BEI-EXC-0003", "status": "Approved", "modified": "2026-02-26 12:00:00"},
			{"name": "BEI-EXC-0002", "status": "Pending CFO", "modified": "2026-02-26 11:00:00"},
		]
		dispatch.frappe.get_all = MagicMock(return_value=exceptions)

		result = dispatch.get_pre_delivery_billing_exception_status("TRIP-0001", 3)

		self.assertEqual(result["latest"]["name"], "BEI-EXC-0003")
		self.assertEqual(len(result["exceptions"]), 2)

	def test_create_pre_delivery_billing_requires_exception_name(self):
		with self.assertRaises(Exception):
			dispatch.create_pre_delivery_billing("TRIP-0001", 1, "")

	def test_create_pre_delivery_billing_calls_internal_guarded_path(self):
		stop = _Stop(
			idx=1, status="Pending", billing_reference="BILL-0001", billing_creation_status="Success"
		)
		trip = _Trip(stop)
		dispatch.frappe.get_doc = MagicMock(return_value=trip)

		with patch.object(dispatch, "_create_delivery_billing") as create_billing:
			result = dispatch.create_pre_delivery_billing(
				trip_name="TRIP-0001",
				stop_idx=1,
				pre_delivery_exception="BEI-EXC-0003",
			)

		create_billing.assert_called_once_with(
			trip_name="TRIP-0001",
			stop_idx=1,
			pre_delivery_exception="BEI-EXC-0003",
			require_pre_delivery_exception=True,
		)
		self.assertEqual(result["billing_reference"], "BILL-0001")


if __name__ == "__main__":
	unittest.main()
