import importlib.util
import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
    frappe = types.ModuleType("frappe")

    class PermissionError(Exception):
        pass

    class AuthenticationError(Exception):
        pass

    def whitelist(*args, **kwargs):
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        def decorator(fn):
            return fn

        return decorator

    def _throw(message, exc=None):
        if isinstance(exc, type) and issubclass(exc, Exception):
            raise exc(message)
        raise Exception(message)

    frappe.PermissionError = PermissionError
    frappe.AuthenticationError = AuthenticationError
    frappe.whitelist = whitelist
    frappe.throw = _throw
    frappe._ = lambda text: text
    frappe.log_error = lambda *args, **kwargs: None
    frappe.logger = lambda *args, **kwargs: types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    frappe.session = types.SimpleNamespace(user="test.user@bebang.ph")
    frappe.db = types.SimpleNamespace(
        exists=lambda *args, **kwargs: None,
        get_value=lambda *args, **kwargs: None,
        count=lambda *args, **kwargs: 0,
    )
    frappe.get_roles = lambda *args, **kwargs: []
    frappe.get_doc = lambda *args, **kwargs: None
    frappe.get_all = lambda *args, **kwargs: []
    sys.modules["frappe"] = frappe

    utils_mod = types.ModuleType("frappe.utils")
    utils_mod.now_datetime = lambda: datetime(2026, 3, 13, 10, 0, 0)
    utils_mod.today = lambda: "2026-03-13"
    utils_mod.nowdate = lambda: "2026-03-13"
    utils_mod.getdate = lambda value=None: value
    utils_mod.date_diff = lambda end, start: 0
    utils_mod.flt = lambda value: float(value or 0)
    utils_mod.sbool = lambda value: str(value).strip().lower() in {"1", "true", "yes", "on"}
    sys.modules["frappe.utils"] = utils_mod

    model_mod = types.ModuleType("frappe.model")
    sys.modules["frappe.model"] = model_mod
    document_mod = types.ModuleType("frappe.model.document")
    document_mod.Document = object
    sys.modules["frappe.model.document"] = document_mod


def _install_fake_hrms_package():
    hrms_pkg = types.ModuleType("hrms")
    hrms_pkg.__path__ = [str(ROOT / "hrms")]
    sys.modules["hrms"] = hrms_pkg

    api_pkg = types.ModuleType("hrms.api")
    api_pkg.__path__ = [str(ROOT / "hrms" / "api")]
    sys.modules["hrms.api"] = api_pkg

    hr_pkg = types.ModuleType("hrms.hr")
    hr_pkg.__path__ = [str(ROOT / "hrms" / "hr")]
    sys.modules["hrms.hr"] = hr_pkg

    doctype_pkg = types.ModuleType("hrms.hr.doctype")
    doctype_pkg.__path__ = [str(ROOT / "hrms" / "hr" / "doctype")]
    sys.modules["hrms.hr.doctype"] = doctype_pkg

    mr_pkg = types.ModuleType("hrms.hr.doctype.bei_maintenance_request")
    mr_pkg.__path__ = [str(ROOT / "hrms" / "hr" / "doctype" / "bei_maintenance_request")]
    sys.modules["hrms.hr.doctype.bei_maintenance_request"] = mr_pkg


def _load_module(module_name: str, relative_path: str):
    if module_name in sys.modules:
        del sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_install_fake_frappe()
_install_fake_hrms_package()
maintenance_module = _load_module(
    "hrms.hr.doctype.bei_maintenance_request.bei_maintenance_request",
    "hrms/hr/doctype/bei_maintenance_request/bei_maintenance_request.py",
)
projects = _load_module("hrms.api.projects", "hrms/api/projects.py")
BEIMaintenanceRequest = maintenance_module.BEIMaintenanceRequest


class _DummyMaintenanceDoc:
    def __init__(self):
        self.name = "MR-S06-0001"
        self.store = "AYALA EVO - BEI"
        self.priority = "High"
        self.issue_category = "Electrical"
        self.impact_on_operations = "Limited Operations"
        self.description = "Main outlet sparking near prep area"
        self.assigned_to = "projects.staff@bebang.ph"
        self.vendor = ""
        self.scheduled_date = "2026-02-27"
        self.status = "Assigned"


class _ChargeDoc:
    def __init__(self):
        self.name = "MR-S06-0002"
        self.store = "AYALA EVO - BEI"
        self.charge_amount = 0
        self.charging_reason = ""
        self.charge_to_store = 0
        self.status = "Open"
        self.flags = types.SimpleNamespace(ignore_permissions=False)
        self.saved = False

    def save(self):
        self.saved = True

    def as_dict(self):
        return {
            "name": self.name,
            "store": self.store,
            "charge_amount": self.charge_amount,
            "charging_reason": self.charging_reason,
            "status": self.status,
        }


class _AttrDict(dict):
    __getattr__ = dict.get


class _AckDoc:
    def __init__(self):
        self.name = "MR-S06-ACK-0001"
        self.charge_to_store = 1
        self.store = "AYALA EVO - BEI"
        self.store_code = "AYALA EVO"
        self.store_acknowledged = 0
        self.acknowledged_by = None
        self.acknowledgement_date = None
        self.status = "Pending Acknowledgement"
        self.flags = types.SimpleNamespace(ignore_permissions=False)
        self.saved = False

    def save(self):
        self.saved = True


class TestProjectsNotificationsS06(unittest.TestCase):
    def test_new_request_notification_dispatches_event(self):
        doc = _DummyMaintenanceDoc()
        with patch.object(maintenance_module, "_notify_maintenance_event") as notify_mock:
            BEIMaintenanceRequest.send_notification(doc)

        notify_mock.assert_called_once()
        call_args = notify_mock.call_args.kwargs
        self.assertIn("New Maintenance Request", call_args["title"])
        self.assertEqual(call_args["store"], doc.store)
        self.assertEqual(call_args["event_kind"], "created")
        self.assertEqual(call_args["request_name"], doc.name)

    def test_status_notification_dispatches_event(self):
        doc = _DummyMaintenanceDoc()
        with patch.object(maintenance_module, "_notify_maintenance_event") as notify_mock:
            BEIMaintenanceRequest.send_status_notification(doc)

        notify_mock.assert_called_once()
        call_args = notify_mock.call_args.kwargs
        self.assertIn("Maintenance Status Updated", call_args["title"])
        self.assertEqual(call_args["store"], doc.store)
        self.assertEqual(call_args["event_kind"], "status_change")
        self.assertEqual(call_args["status"], doc.status)

    def test_set_maintenance_charge_triggers_pending_ack_notification(self):
        doc = _ChargeDoc()

        with patch.object(projects.frappe, "get_roles", return_value=["Projects Manager"]), patch.object(
            projects.frappe.db, "exists", return_value=True
        ), patch.object(projects.frappe, "get_doc", return_value=doc), patch.object(
            projects, "_notify_maintenance_charge_pending_ack"
        ) as notify_mock:
            result = projects.set_maintenance_charge(
                request_id=doc.name,
                charge_amount=1250,
                charging_reason="Parts replacement",
            )

        self.assertTrue(result["success"])
        self.assertTrue(doc.saved)
        self.assertEqual(doc.status, "Pending Acknowledgement")
        self.assertEqual(doc.charge_amount, 1250)
        notify_mock.assert_called_once_with(doc)

    def test_acknowledge_charge_allows_store_staff(self):
        doc = _AckDoc()

        def _db_get_value(doctype, filters_or_name=None, fieldname=None):
            if doctype == "Employee" and isinstance(filters_or_name, dict):
                return "HR-EMP-TEST-0001"
            if doctype == "Employee" and filters_or_name == "HR-EMP-TEST-0001" and fieldname == "branch":
                return "AYALA EVO - BEI"
            if doctype == "BEI Maintenance Request" and fieldname == "store":
                return "AYALA EVO - BEI"
            return None

        with patch.object(projects.frappe, "get_roles", return_value=["Store Staff"]), patch.object(
            projects.frappe.db, "exists", return_value=True
        ), patch.object(projects.frappe.db, "get_value", side_effect=_db_get_value), patch.object(
            projects.frappe, "get_doc", return_value=doc
        ):
            result = projects.acknowledge_maintenance_charge(request_id=doc.name)

        self.assertTrue(result["success"])
        self.assertTrue(doc.saved)
        self.assertEqual(doc.status, "Verified")
        self.assertEqual(doc.store_acknowledged, 1)

    def test_get_pending_charges_allows_store_staff(self):
        rows = [
            _AttrDict({
                "name": "MR-S06-ACK-0002",
                "store": "AYALA EVO - BEI",
                "store_code": "AYALA EVO",
                "request_date": "2026-02-27",
                "issue_category": "Electrical",
                "description": "Pending ack sample",
                "charge_amount": 750.0,
                "charging_reason": "Wire replacement",
                "concern_type": "Wear & Tear",
                "priority": "High",
                "status": "Pending Acknowledgement",
            })
        ]

        with patch.object(projects.frappe, "get_roles", return_value=["Store Staff"]), patch.object(
            projects.frappe.db, "count", return_value=1
        ), patch.object(projects.frappe, "get_all", return_value=rows), patch.object(
            projects.frappe.db, "get_value", return_value="Ayala Evo"
        ):
            result = projects.get_pending_charges(page=1, page_size=20)

        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["requests"]), 1)
        self.assertEqual(result["requests"][0]["name"], "MR-S06-ACK-0002")

    def test_check_sla_violations_sends_grouped_digest(self):
        now = datetime(2026, 3, 13, 10, 0, 0)

        def fake_get_all(_doctype, filters=None, fields=None):
            priority = (filters or {}).get("priority")
            if priority == "Urgent":
                return [
                    types.SimpleNamespace(
                        name="MR-SLA-URG-0001",
                        store="AYALA EVO - BEI",
                        priority="Urgent",
                        issue_category="Electrical",
                        description="Outlet sparking",
                        creation=now - timedelta(hours=6),
                    )
                ]
            if priority == "High":
                return [
                    types.SimpleNamespace(
                        name="MR-SLA-HIGH-0001",
                        store="AYALA EVO - BEI",
                        priority="High",
                        issue_category="Plumbing",
                        description="Leaking sink",
                        creation=now - timedelta(hours=30),
                    )
                ]
            return []

        google_chat_mod = types.ModuleType("hrms.api.google_chat")
        captured = {}

        def _send(event):
            captured["event"] = event
            return True

        google_chat_mod.send_notification_event = _send

        with patch.dict(sys.modules, {"hrms.api.google_chat": google_chat_mod}, clear=False), patch.object(
            projects, "now_datetime", return_value=now
        ), patch.object(projects, "nowdate", return_value="2026-03-13"), patch.object(
            projects.frappe, "get_all", side_effect=fake_get_all
        ):
            projects.check_sla_violations()

        event = captured["event"]
        self.assertEqual(event["family"], "maintenance_sla_backlog")
        self.assertEqual(event["severity"], "critical")
        self.assertEqual(event["facts"]["counts_by_priority"]["Urgent"], 1)
        self.assertEqual(len(event["facts"]["breaches"]), 2)


if __name__ == "__main__":
    unittest.main()
