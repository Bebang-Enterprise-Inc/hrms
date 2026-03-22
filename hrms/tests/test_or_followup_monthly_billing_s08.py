import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
    if "frappe" in sys.modules:
        return

    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")

    class ValidationError(Exception):
        pass

    class PermissionError(Exception):
        pass

    def whitelist(*args, **kwargs):
        def decorator(fn):
            return fn

        return decorator

    def _throw(message, exc=None):
        if isinstance(exc, type) and issubclass(exc, Exception):
            raise exc(message)
        raise Exception(message)

    def _getdate(value=None):
        if isinstance(value, datetime.date):
            return value
        if not value:
            return datetime.date(2026, 2, 27)
        return datetime.date.fromisoformat(str(value))

    frappe.whitelist = whitelist
    frappe._ = lambda text: text
    frappe.throw = _throw
    frappe.ValidationError = ValidationError
    frappe.PermissionError = PermissionError
    frappe.session = types.SimpleNamespace(user="Administrator")
    frappe.has_permission = lambda *args, **kwargs: True
    frappe.get_roles = lambda user=None: ["System Manager"]
    frappe.log_error = lambda *args, **kwargs: None
    frappe.get_traceback = lambda: "traceback"
    frappe.format_value = lambda value, _type=None: f"{float(value):.2f}"
    frappe.sendmail = MagicMock()
    frappe.get_all = MagicMock(return_value=[])
    frappe.get_doc = MagicMock()
    frappe.new_doc = MagicMock()
    frappe.db = types.SimpleNamespace(
        sql=lambda *args, **kwargs: [],
        exists=lambda *args, **kwargs: None,
        get_value=lambda *args, **kwargs: None,
        set_value=lambda *args, **kwargs: None,
        savepoint=lambda *args, **kwargs: None,
        release_savepoint=lambda *args, **kwargs: None,
        rollback=lambda *args, **kwargs: None,
        count=lambda *args, **kwargs: 0,
    )

    utils.flt = lambda value, precision=None: round(float(value or 0), int(precision)) if precision is not None else float(value or 0)
    utils.cint = lambda value: int(float(value or 0))
    utils.now_datetime = lambda: datetime.datetime(2026, 2, 27, 10, 0, 0)
    utils.nowdate = lambda: "2026-02-27"
    utils.today = lambda: "2026-02-27"
    utils.getdate = _getdate
    utils.get_first_day = lambda value: datetime.date.fromisoformat(str(value)[:10]).replace(day=1)
    utils.get_last_day = lambda value: datetime.date.fromisoformat(str(value)[:10]).replace(day=28)
    utils.add_days = lambda date_value, days: _getdate(date_value) + datetime.timedelta(days=int(days))
    utils.date_diff = lambda end, start: (_getdate(end) - _getdate(start)).days

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils


def _install_stub_dependencies():
    bei_config = types.ModuleType("hrms.utils.bei_config")
    bei_config.get_company = lambda: "Bebang Enterprises Inc."
    bei_config.get_chat_space = lambda _space: "spaces/AA_TEST"
    bei_config.SPACE_ERP_AUTOMATION = "SPACE_ERP_AUTOMATION"

    scm_roles = types.ModuleType("hrms.utils.scm_roles")
    scm_roles.RATE_MANAGEMENT_ROLES = ["Accounts Manager", "Supply Chain Manager"]
    scm_roles.SCM_BILLING_ROLES = ["Accounts Manager", "Supply Chain Manager"]
    scm_roles.check_scm_permission = lambda roles, action=None: True

    delivery_policy = types.ModuleType("hrms.utils.delivery_billing_policy")
    delivery_policy.CPO_APPROVER_EMAIL = "mae@bebang.ph"
    delivery_policy.CFO_APPROVER_EMAIL = "butch@bebang.ph"
    delivery_policy.append_approval_audit_log = lambda *args, **kwargs: None

    google_chat = types.ModuleType("hrms.api.google_chat")
    google_chat.send_message_to_space = lambda *args, **kwargs: True

    sys.modules["hrms.utils.bei_config"] = bei_config
    sys.modules["hrms.utils.scm_roles"] = scm_roles
    sys.modules["hrms.utils.delivery_billing_policy"] = delivery_policy
    sys.modules["hrms.api.google_chat"] = google_chat


_install_fake_frappe()
_install_stub_dependencies()

billing_spec = importlib.util.spec_from_file_location(
    "billing_under_test",
    ROOT / "hrms" / "api" / "billing.py",
)
billing = importlib.util.module_from_spec(billing_spec)
assert billing_spec and billing_spec.loader
billing_spec.loader.exec_module(billing)

soa_spec = importlib.util.spec_from_file_location(
    "soa_under_test",
    ROOT / "hrms" / "api" / "soa.py",
)
soa = importlib.util.module_from_spec(soa_spec)
assert soa_spec and soa_spec.loader
soa_spec.loader.exec_module(soa)

proc_spec = importlib.util.spec_from_file_location(
    "procurement_under_test",
    ROOT / "hrms" / "api" / "procurement.py",
)
procurement = importlib.util.module_from_spec(proc_spec)
assert proc_spec and proc_spec.loader
proc_spec.loader.exec_module(procurement)


class _PayReqDoc:
    def __init__(self):
        self.name = "PAY-0001"
        self.status = "Paid - Awaiting OR"
        self.supplier = "SUP-001"
        self.supplier_name = "Supplier A"
        self.payment_amount = 1250
        self.or_follow_up_count = 0
        self.or_last_follow_up = None

    def save(self, ignore_permissions=False):
        return self


class _CommentDoc:
    def insert(self, ignore_permissions=False):
        return self


class TestOrFollowupMonthlyBillingSprint08(unittest.TestCase):
    def test_trigger_monthly_billing_service_returns_stable_contract(self):
        billing.generate_monthly_billing = MagicMock(
            return_value={
                "success": True,
                "billing_period": "2026-02",
                "generated": 3,
                "skipped": 1,
                "errors": [],
            }
        )

        result = billing.trigger_monthly_billing_service("2026-02")

        self.assertTrue(result["success"])
        self.assertEqual(result["service"], "monthly_billing_trigger")
        self.assertEqual(result["generated"], 3)
        self.assertEqual(result["skipped"], 1)

    def test_get_monthly_billing_service_snapshot_combines_billing_and_or_stats(self):
        soa.frappe.db.sql = MagicMock(
            side_effect=[
                [{"billing_count": 4, "total_billed": 10000, "total_outstanding": 3500}],
                [{"overdue_or_count": 2, "overdue_or_amount": 1500}],
            ]
        )

        result = soa.get_monthly_billing_service_snapshot("2026-02")

        self.assertTrue(result["success"])
        self.assertEqual(result["billing"]["billing_count"], 4)
        self.assertEqual(result["or_follow_up"]["overdue_or_count"], 2)

    def test_send_or_follow_up_returns_notification_flags(self):
        pay_req = _PayReqDoc()

        def _get_doc(*args, **kwargs):
            if args and args[0] == "BEI Payment Request":
                return pay_req
            if args and isinstance(args[0], dict):
                return _CommentDoc()
            raise AssertionError(f"Unexpected get_doc call: {args} {kwargs}")

        procurement.frappe.get_doc = MagicMock(side_effect=_get_doc)
        procurement._dispatch_or_follow_up_notification = MagicMock(
            return_value={"any_sent": True, "channels": ["google_chat"]}
        )

        result = procurement.send_or_follow_up("PAY-0001")

        self.assertTrue(result["success"])
        self.assertTrue(result["notification_sent"])
        self.assertEqual(result["notification_channels"], ["google_chat"])
        self.assertEqual(result["follow_up_count"], 1)

    def test_generate_monthly_billing_uses_named_savepoint_for_release(self):
        billing.frappe.has_permission = lambda *args, **kwargs: True
        billing.frappe.get_all = MagicMock(
            return_value=[SimpleNamespace(store="TEST STORE", store_type="Full Franchise")]
        )

        savepoint = MagicMock(return_value=None)
        release_savepoint = MagicMock()
        rollback = MagicMock()

        billing.frappe.db.savepoint = savepoint
        billing.frappe.db.release_savepoint = release_savepoint
        billing.frappe.db.rollback = rollback
        billing.frappe.db.exists = MagicMock(return_value="BILL-EXISTING")

        result = billing.generate_monthly_billing("2099-01")

        self.assertTrue(result["success"])
        self.assertEqual(result["skipped"], 1)
        savepoint.assert_called_once_with("billing_TEST_STORE")
        release_savepoint.assert_called_once_with("billing_TEST_STORE")
        rollback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
