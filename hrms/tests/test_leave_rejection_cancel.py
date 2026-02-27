import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
    if "frappe" in sys.modules:
        return

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
    frappe.only_for = lambda *args, **kwargs: None
    frappe.get_doc = lambda *args, **kwargs: None
    frappe.db = types.SimpleNamespace(sql=lambda *args, **kwargs: [], count=lambda *args, **kwargs: 0)

    utils.getdate = lambda value=None: datetime.date.today()
    utils.date_diff = lambda to_date, from_date: 0
    utils.flt = lambda value, precision=None: float(value or 0)
    utils.today = lambda: "2026-02-27"
    utils.add_days = lambda date_obj, days: date_obj

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils


def _install_stub_dependencies():
    api_helpers = types.ModuleType("hrms.utils.api_helpers")
    api_helpers._check_hr_permission = lambda *args, **kwargs: None
    api_helpers._validate_date_range = lambda *args, **kwargs: None
    api_helpers._paginate = lambda results, page=1, page_size=50: {
        "data": results,
        "page": page,
        "page_size": page_size,
        "total": len(results),
    }
    sys.modules["hrms.utils.api_helpers"] = api_helpers


_install_fake_frappe()
_install_stub_dependencies()

hr_reports_spec = importlib.util.spec_from_file_location(
    "hr_reports_under_test",
    ROOT / "hrms" / "api" / "hr_reports.py",
)
hr_reports = importlib.util.module_from_spec(hr_reports_spec)
assert hr_reports_spec and hr_reports_spec.loader
hr_reports_spec.loader.exec_module(hr_reports)


class FakeLeaveDoc:
    def __init__(self, name, status="Open", docstatus=1):
        self.name = name
        self.status = status
        self.docstatus = docstatus
        self.cancel_called = False
        self.save_called = False
        self.db_set_calls = []

    def cancel(self):
        self.cancel_called = True
        self.docstatus = 2
        self.status = "Cancelled"

    def save(self, **kwargs):
        self.save_called = True

    def db_set(self, field, value):
        self.db_set_calls.append((field, value))
        setattr(self, field, value)


class LeaveRejectionCancelTests(unittest.TestCase):
    def test_submitted_rejection_uses_cancel_not_raw_db_set(self):
        doc = FakeLeaveDoc(name="LEAVE-0001", status="Open", docstatus=1)
        with patch.object(hr_reports.frappe, "get_doc", return_value=doc):
            result = hr_reports.bulk_update_leave_status(["LEAVE-0001"], "Rejected")

        self.assertEqual(result["success"], ["LEAVE-0001"])
        self.assertTrue(doc.cancel_called)
        self.assertNotIn(("status", "Rejected"), doc.db_set_calls)

    def test_draft_rejection_marks_rejected_and_saves(self):
        doc = FakeLeaveDoc(name="LEAVE-0002", status="Open", docstatus=0)
        with patch.object(hr_reports.frappe, "get_doc", return_value=doc):
            result = hr_reports.bulk_update_leave_status(["LEAVE-0002"], "Rejected")

        self.assertEqual(result["success"], ["LEAVE-0002"])
        self.assertEqual(doc.status, "Rejected")
        self.assertTrue(doc.save_called)
        self.assertNotIn(("status", "Rejected"), doc.db_set_calls)

    def test_invalid_status_raises(self):
        with self.assertRaises(Exception):
            hr_reports.bulk_update_leave_status(["LEAVE-0003"], "Cancelled")


if __name__ == "__main__":
    unittest.main()
