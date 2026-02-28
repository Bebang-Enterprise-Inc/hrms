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


def _install_fake_frappe(sql_responses):
    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")

    def whitelist(*args, **kwargs):
        def decorator(fn):
            return fn

        return decorator

    queue = list(sql_responses)

    def sql(*args, **kwargs):
        if not queue:
            return []
        return queue.pop(0)

    frappe.whitelist = whitelist
    frappe.only_for = lambda roles: None
    frappe.throw = lambda message: (_ for _ in ()).throw(Exception(message))
    frappe.db = types.SimpleNamespace(sql=sql, get_value=lambda *a, **k: {})
    frappe.get_doc = lambda *args, **kwargs: None
    frappe._ = lambda value: value

    utils.today = lambda: "2026-02-28"
    utils.add_days = lambda value, days: "2026-03-06"
    utils.nowdate = lambda: "2026-02-28"
    utils.getdate = lambda value=None: value or "2026-02-28"
    utils.add_to_date = lambda *a, **k: "2026-02-28"

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils


def test_get_dashboard_data_returns_expected_shape():
    pending = [
        {
            "name": "LV-OPEN-001",
            "employee": "EMP-001",
            "employee_name": "Jane Doe",
            "leave_type": "Vacation Leave",
            "from_date": "2026-03-01",
            "to_date": "2026-03-03",
            "status": "Open",
            "branch": "Market Market",
        }
    ]
    history = [
        {
            "name": "LV-APP-001",
            "employee": "EMP-002",
            "employee_name": "John Smith",
            "leave_type": "Sick Leave",
            "from_date": "2026-02-10",
            "to_date": "2026-02-11",
            "status": "Approved",
            "branch": "Market Market",
        }
    ]

    _install_fake_frappe(
        sql_responses=[
            [(42,)],  # total employees
            [(3,)],  # on leave today
            [(6,)],  # pending count
            [(5,)],  # upcoming count
            pending,
            history,
        ]
    )
    leave_dashboard = _load_leave_dashboard_module()

    result = leave_dashboard.get_dashboard_data(branch="Market Market")

    assert set(result.keys()) == {"kpis", "pending_requests", "historical_requests", "calendar_events"}
    assert result["kpis"]["total_employees"] == 42
    assert len(result["pending_requests"]) == 1
    assert len(result["historical_requests"]) == 1
    assert len(result["calendar_events"]) == 1
    assert result["calendar_events"][0]["id"] == "LV-APP-001"


def test_hr_reports_contains_leave_dashboard_wrappers():
    source = (ROOT / "hrms" / "api" / "hr_reports.py").read_text(encoding="utf-8")

    assert "from hrms.api import leave_dashboard as leave_dashboard_api" in source
    assert "def get_dashboard_data(" in source
    assert "return leave_dashboard_api.get_dashboard_data(" in source
    assert "def get_leave_overview(" in source
    assert "return leave_dashboard_api.get_leave_overview(" in source
