import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_leave_dashboard_module():
    module_path = ROOT / "hrms" / "api" / "leave_dashboard.py"
    spec = importlib.util.spec_from_file_location("leave_dashboard_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class _Flags:
    ignore_permissions = False


class _FakeLeaveDoc:
    def __init__(self, status="Open", docstatus=0):
        self.status = status
        self.docstatus = docstatus
        self.flags = _Flags()
        self.submit_called = False
        self.db_updates = []
        self.comments = []

    def submit(self):
        self.submit_called = True
        self.status = "Approved"
        self.docstatus = 1

    def db_set(self, fieldname, value):
        self.db_updates.append((fieldname, value))
        if fieldname == "status":
            self.status = value

    def add_comment(self, comment_type, message):
        self.comments.append((comment_type, message))


def _install_fake_frappe(docs):
    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")

    def whitelist(*args, **kwargs):
        def decorator(fn):
            return fn

        return decorator

    frappe.whitelist = whitelist
    frappe.only_for = lambda roles: None
    frappe.throw = lambda message: (_ for _ in ()).throw(Exception(message))
    frappe.db = types.SimpleNamespace(sql=lambda *a, **k: [], get_value=lambda *a, **k: {})
    frappe.get_doc = lambda doctype, name: docs[name]
    frappe._ = lambda value: value

    utils.today = lambda: "2026-02-28"
    utils.add_days = lambda value, days: "2026-03-06"

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils


def test_bulk_action_approved_persists_state_changes():
    docs = {"LV-001": _FakeLeaveDoc(status="Open", docstatus=0)}
    _install_fake_frappe(docs)
    leave_dashboard = _load_leave_dashboard_module()

    result = leave_dashboard.bulk_action(["LV-001"], "Approved", remarks="Looks good")

    assert result["success"] == ["LV-001"]
    assert result["failed"] == []
    assert docs["LV-001"].submit_called is True
    assert docs["LV-001"].status == "Approved"
    assert docs["LV-001"].docstatus == 1
    assert docs["LV-001"].comments


def test_bulk_action_rejects_non_open_leave():
    docs = {"LV-002": _FakeLeaveDoc(status="Approved", docstatus=1)}
    _install_fake_frappe(docs)
    leave_dashboard = _load_leave_dashboard_module()

    result = leave_dashboard.bulk_action(["LV-002"], "Rejected")

    assert result["success"] == []
    assert len(result["failed"]) == 1
    assert result["failed"][0]["id"] == "LV-002"
