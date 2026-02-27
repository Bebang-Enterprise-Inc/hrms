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


def _install_fake_frappe():
    if "frappe" in sys.modules:
        return

    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")
    rate_limiter = types.ModuleType("frappe.rate_limiter")

    def whitelist(*args, **kwargs):
        def decorator(fn):
            return fn

        return decorator

    def _throw(message, exc=None):
        if isinstance(exc, type) and issubclass(exc, Exception):
            raise exc(message)
        raise Exception(message)

    def _rate_limit(*args, **kwargs):
        def decorator(fn):
            return fn

        return decorator

    frappe.whitelist = whitelist
    frappe._ = lambda text: text
    frappe.throw = _throw
    frappe.get_doc = lambda *args, **kwargs: None
    frappe.get_all = lambda *args, **kwargs: []
    frappe.get_roles = lambda user=None: ["HR Manager"]
    frappe.session = types.SimpleNamespace(user="test.hr@bebang.ph")
    frappe.publish_realtime = MagicMock()
    frappe.db = types.SimpleNamespace(
        get_value=lambda *args, **kwargs: "STORE SUPERVISOR",
        count=lambda *args, **kwargs: 0,
        sql=lambda *args, **kwargs: [],
    )

    utils.getdate = lambda value=None: datetime.date.today()
    utils.date_diff = lambda to_date, from_date: 0
    utils.flt = lambda value, precision=None: float(value or 0)
    utils.today = lambda: "2026-02-27"
    utils.nowdate = lambda: "2026-02-27"

    rate_limiter.rate_limit = _rate_limit

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils
    sys.modules["frappe.rate_limiter"] = rate_limiter


def _install_stub_dependencies():
    bei_config = types.ModuleType("hrms.utils.bei_config")
    bei_config.get_company = lambda: "Bebang Enterprises Inc."
    sys.modules["hrms.utils.bei_config"] = bei_config

    api_helpers = types.ModuleType("hrms.utils.api_helpers")
    api_helpers._get_employee_or_throw = lambda: "EMP-0001"
    api_helpers._get_employee_details = lambda: {"employee_name": "Test HR"}
    api_helpers._check_hr_permission = lambda *args, **kwargs: None
    api_helpers._check_manager_permission = lambda *args, **kwargs: None
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

recruitment_spec = importlib.util.spec_from_file_location(
    "recruitment_under_test",
    ROOT / "hrms" / "api" / "recruitment.py",
)
recruitment = importlib.util.module_from_spec(recruitment_spec)
assert recruitment_spec and recruitment_spec.loader
recruitment_spec.loader.exec_module(recruitment)


class FakeMRF:
    def __init__(self, name="MRF-0001", status="Draft", department="Operations", designation="Store Supervisor"):
        self.name = name
        self.status = status
        self.department = department
        self.designation = designation
        self.comments = []

    def insert(self):
        return self

    def db_set(self, field, value):
        setattr(self, field, value)

    def add_comment(self, comment_type, text=None):
        self.comments.append((comment_type, text))


class RecruitmentNotificationTests(unittest.TestCase):
    def setUp(self):
        recruitment.frappe.publish_realtime.reset_mock()

    def test_create_mrf_emits_transition_notification(self):
        mrf = FakeMRF(status="Draft")
        payload = {
            "requesting_department": "Operations",
            "position_title": "Store Supervisor",
            "designation": "Store Supervisor",
            "department": "Operations",
            "reason": "Replacement",
            "preferred_start_date": "2026-03-01",
            "job_description": "Lead store operations",
            "justification": "Backfill role",
        }

        with patch.object(recruitment.frappe, "get_doc", return_value=mrf):
            result = recruitment.create_mrf(json.dumps(payload))

        self.assertEqual(result["status"], "Pending Hiring Manager")
        self.assertTrue(any("Draft" in (text or "") and "Pending Hiring Manager" in (text or "") for _, text in mrf.comments))
        recruitment.frappe.publish_realtime.assert_called_once()
        args, kwargs = recruitment.frappe.publish_realtime.call_args
        self.assertEqual(args[0], "mrf_status_transition")
        self.assertEqual(args[1]["to_status"], "Pending Hiring Manager")

    def test_approve_mrf_emits_pending_hr_manager_notification(self):
        mrf = FakeMRF(status="Pending Hiring Manager")

        with patch.object(recruitment.frappe, "get_doc", return_value=mrf):
            result = recruitment.approve_mrf("MRF-0001", "approve")

        self.assertEqual(result["status"], "Pending HR Manager")
        self.assertTrue(any("Pending Hiring Manager" in (text or "") and "Pending HR Manager" in (text or "") for _, text in mrf.comments))
        recruitment.frappe.publish_realtime.assert_called_once()
        args, kwargs = recruitment.frappe.publish_realtime.call_args
        self.assertEqual(args[0], "mrf_status_transition")
        self.assertEqual(args[1]["to_status"], "Pending HR Manager")


if __name__ == "__main__":
    unittest.main()
