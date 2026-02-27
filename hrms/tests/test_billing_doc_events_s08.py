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
    frappe.format_value = lambda value, _type=None: f"{float(value):.2f}"
    frappe.log_error = lambda *args, **kwargs: None
    frappe.new_doc = MagicMock()
    frappe.db = types.SimpleNamespace(
        sql=lambda *args, **kwargs: [],
        get_value=lambda *args, **kwargs: None,
        set_value=lambda *args, **kwargs: None,
        savepoint=lambda *args, **kwargs: None,
        release_savepoint=lambda *args, **kwargs: None,
        rollback=lambda *args, **kwargs: None,
    )

    utils.flt = lambda value, precision=None: round(float(value or 0), int(precision)) if precision is not None else float(value or 0)
    utils.now_datetime = lambda: datetime.datetime(2026, 2, 27, 10, 0, 0)
    utils.nowdate = lambda: "2026-02-27"
    utils.get_first_day = lambda value: datetime.date.fromisoformat(str(value)[:10]).replace(day=1)
    utils.get_last_day = lambda value: datetime.date.fromisoformat(str(value)[:10]).replace(day=28)
    utils.getdate = _getdate

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils


def _install_stub_dependencies():
    bei_config = types.ModuleType("hrms.utils.bei_config")
    bei_config.get_company = lambda: "Bebang Enterprises Inc."

    scm_roles = types.ModuleType("hrms.utils.scm_roles")
    scm_roles.RATE_MANAGEMENT_ROLES = ["Accounts Manager", "Supply Chain Manager"]
    scm_roles.SCM_BILLING_ROLES = ["Accounts Manager", "Supply Chain Manager"]
    scm_roles.check_scm_permission = lambda roles, action=None: True

    sys.modules["hrms.utils.bei_config"] = bei_config
    sys.modules["hrms.utils.scm_roles"] = scm_roles


_install_fake_frappe()
_install_stub_dependencies()

billing_spec = importlib.util.spec_from_file_location(
    "billing_under_test",
    ROOT / "hrms" / "api" / "billing.py",
)
billing = importlib.util.module_from_spec(billing_spec)
assert billing_spec and billing_spec.loader
billing_spec.loader.exec_module(billing)


class _BillingDoc:
    def __init__(self, name="BILL-0001", billing_type="Monthly Fees", billing_period=None, generated_on=None, status="Draft", sent_on=None):
        self.name = name
        self.billing_type = billing_type
        self.billing_period = billing_period
        self.generated_on = generated_on
        self.status = status
        self.sent_on = sent_on


class TestBillingDocEventsSprint08(unittest.TestCase):
    def setUp(self):
        billing.frappe.db.get_value = MagicMock(return_value=None)
        billing.frappe.db.sql = MagicMock(return_value=[{"ewt_atc": "WC110", "ewt_rate": 1.0}])
        billing.frappe.new_doc = MagicMock()

    def test_hooks_map_contains_billing_doc_events(self):
        hooks_path = ROOT / "hrms" / "hooks.py"
        text = hooks_path.read_text(encoding="utf-8")
        self.assertIn('"BEI Billing Schedule"', text)
        self.assertIn("hrms.api.billing.on_billing_schedule_validate", text)
        self.assertIn("hrms.api.billing.on_billing_schedule_update", text)

    def test_on_billing_schedule_validate_backfills_period(self):
        doc = _BillingDoc(generated_on="2026-02-15")
        billing.on_billing_schedule_validate(doc, "validate")
        self.assertEqual(doc.billing_period, "2026-02")

    def test_create_3pl_payment_request_is_idempotent_for_existing_cheque_no(self):
        billing.frappe.db.get_value = MagicMock(
            return_value={"name": "ACC-JV-0001", "total_debit": 1000.0, "docstatus": 1}
        )

        result = billing.create_3pl_payment_request(2, 2026, "RCS", 1000.0)

        self.assertTrue(result["success"])
        self.assertTrue(result["idempotent"])
        self.assertEqual(result["journal_entry"], "ACC-JV-0001")
        billing.frappe.new_doc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
