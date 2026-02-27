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
    frappe.session = types.SimpleNamespace(user="Administrator")
    frappe.log_error = lambda *args, **kwargs: None
    frappe.get_traceback = lambda: "traceback"
    frappe.db = types.SimpleNamespace(set_value=lambda *args, **kwargs: None)

    utils.today = lambda: "2026-02-27"
    utils.now_datetime = lambda: datetime.datetime(2026, 2, 27, 10, 0, 0)
    utils.flt = lambda value, precision=None: round(float(value or 0), int(precision)) if precision is not None else float(value or 0)
    utils.nowdate = lambda: "2026-02-27"
    utils.getdate = _getdate

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils


def _install_stub_dependencies():
    bei_config = types.ModuleType("hrms.utils.bei_config")
    bei_config.get_company = lambda: "Bebang Enterprises Inc."

    store_api = types.ModuleType("hrms.api.store")
    store_api.save_base64_image = lambda *args, **kwargs: "/files/receipt.jpg"

    petty_cash = types.ModuleType("hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund")
    petty_cash.update_pcf_totals = MagicMock()

    sys.modules["hrms.utils.bei_config"] = bei_config
    sys.modules["hrms.api.store"] = store_api
    sys.modules["hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund"] = petty_cash


_install_fake_frappe()
_install_stub_dependencies()

pcf_spec = importlib.util.spec_from_file_location(
    "pcf_under_test",
    ROOT / "hrms" / "api" / "pcf.py",
)
pcf = importlib.util.module_from_spec(pcf_spec)
assert pcf_spec and pcf_spec.loader
pcf_spec.loader.exec_module(pcf)


class _Item:
    def __init__(self, expense_request=None, amount=0, expense_date=None):
        self.expense_request = expense_request
        self.amount = amount
        self.expense_date = expense_date


class _BatchDoc:
    def __init__(self, status="Submitted", store="AYALA EVO", items=None):
        self.status = status
        self.store = store
        self.items = items or []
        self.expense_count = 0
        self.total_amount = 0
        self.period_start = None
        self.period_end = None


class TestPCFHooksSprint08(unittest.TestCase):
    def setUp(self):
        pcf.frappe.db.set_value = MagicMock()

    def test_validate_pcf_batch_requires_items(self):
        doc = _BatchDoc(items=[])
        with self.assertRaises(pcf.frappe.ValidationError):
            pcf.validate_pcf_batch(doc, "validate")

    def test_validate_pcf_batch_computes_totals_and_period(self):
        doc = _BatchDoc(
            items=[
                _Item("EXP-001", 120.5, "2026-02-01"),
                _Item("EXP-002", 79.5, "2026-02-05"),
            ]
        )

        pcf.validate_pcf_batch(doc, "validate")

        self.assertEqual(doc.expense_count, 2)
        self.assertEqual(doc.total_amount, 200.0)
        self.assertEqual(str(doc.period_start), "2026-02-01")
        self.assertEqual(str(doc.period_end), "2026-02-05")

    def test_on_batch_update_syncs_expense_status(self):
        doc = _BatchDoc(
            status="Approved",
            store="AYALA EVO",
            items=[_Item("EXP-001", 100, "2026-02-10"), _Item("EXP-002", 50, "2026-02-11")],
        )

        pcf.on_batch_update(doc, "on_update")

        self.assertEqual(pcf.frappe.db.set_value.call_count, 2)
        pcf.frappe.db.set_value.assert_any_call("BEI Expense Request", "EXP-001", "status", "Approved")
        pcf.frappe.db.set_value.assert_any_call("BEI Expense Request", "EXP-002", "status", "Approved")


if __name__ == "__main__":
    unittest.main()
