from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_module(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _install_fake_frappe(allow_access: bool = True):
    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")

    class ValidationError(Exception):
        pass

    class PermissionError(Exception):
        pass

    tracker = {"roles": []}

    def whitelist(*args, **kwargs):
        def decorator(fn):
            return fn

        return decorator

    def only_for(roles):
        tracker["roles"].append(list(roles))
        if not allow_access:
            raise PermissionError("not allowed")

    def throw(message, exc=None):
        err_cls = exc if isinstance(exc, type) else Exception
        raise err_cls(message)

    def sql(query, values=None, as_dict=False):
        compact = " ".join(str(query).split())
        if "COUNT(name) FROM `tabEmployee Separation`" in compact:
            return [(3,)]
        if "COUNT(name) FROM `tabBEI DOLE Compliance Checklist`" in compact:
            return [(9,)]
        if "FROM `tabSalary Slip`" in compact:
            rows = [
                {"employee": "EMP-001", "employee_name": "Ada", "total_basic": 120000},
                {"employee": "EMP-002", "employee_name": "Grace", "total_basic": 96000},
            ]
            return rows if as_dict else []
        if "FROM `tabLeave Allocation`" in compact:
            return [{"allocated": 5}] if as_dict else []
        if "FROM `tabLeave Application`" in compact:
            return [{"consumed": 2}] if as_dict else []
        return [] if as_dict else [(0,)]

    def get_all(doctype, filters=None, fields=None, order_by=None, limit=None):
        if doctype == "Exit Interview":
            return [
                {
                    "name": "EXIT-0001",
                    "employee": "EMP-001",
                    "employee_name": "Ada",
                    "status": "Submitted",
                    "creation": "2026-03-01",
                    "modified": "2026-03-01",
                }
            ]
        if doctype == "Employee Separation":
            return [
                {
                    "name": "SEP-0001",
                    "employee": "EMP-001",
                    "employee_name": "Ada",
                    "department": "HR",
                    "designation": "Supervisor",
                    "custom_separation_type": "Resignation",
                    "boarding_status": "In Process",
                    "boarding_begins_on": "2026-03-01",
                    "modified": "2026-03-01",
                }
            ]
        return []

    frappe.whitelist = whitelist
    frappe.only_for = only_for
    frappe.throw = throw
    frappe.ValidationError = ValidationError
    frappe.PermissionError = PermissionError
    frappe.db = types.SimpleNamespace(sql=sql)
    frappe.get_all = get_all
    frappe._ = lambda value: value

    utils.today = lambda: "2026-03-01"
    utils.add_days = lambda value, days: "2026-03-08"

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils
    return tracker


def test_s17_backend_contract_methods_exist():
    _install_fake_frappe()
    compliance = _load_module(ROOT / "hrms" / "api" / "compliance.py", "s17_compliance_under_test")
    clearance = _load_module(
        ROOT / "hrms" / "api" / "employee_clearance.py",
        "s17_employee_clearance_under_test",
    )

    assert hasattr(compliance, "get_compliance_dashboard")
    assert hasattr(compliance, "calculate_13th_month_pay")
    assert hasattr(compliance, "calculate_sil_balance")
    assert hasattr(compliance, "get_holiday_pay_compliance")
    assert hasattr(compliance, "generate_13th_month_report")

    assert hasattr(clearance, "get_exit_interview_analytics")
    assert hasattr(clearance, "get_team_separations")
    assert hasattr(clearance, "create_exit_interview")


def test_s17_backend_payload_shapes():
    tracker = _install_fake_frappe()
    compliance = _load_module(ROOT / "hrms" / "api" / "compliance.py", "s17_compliance_payload_test")
    clearance = _load_module(
        ROOT / "hrms" / "api" / "employee_clearance.py",
        "s17_employee_clearance_payload_test",
    )

    dashboard = compliance.get_compliance_dashboard()
    assert dashboard["success"] is True
    assert "data" in dashboard
    assert dashboard["data"]["open_separations"] == 3

    thirteenth = compliance.calculate_13th_month_pay(2026)
    assert thirteenth["success"] is True
    assert thirteenth["data"]["employee_count"] == 2

    sil = compliance.calculate_sil_balance("EMP-001")
    assert sil["success"] is True
    assert sil["data"]["remaining"] == 3

    analytics = clearance.get_exit_interview_analytics()
    assert analytics["summary"]["total"] == 1
    assert isinstance(analytics["rows"], list)

    team = clearance.get_team_separations()
    assert isinstance(team, list)
    assert team[0]["name"] == "SEP-0001"

    # Access control was applied by compliance + analytics/team methods.
    assert tracker["roles"]
