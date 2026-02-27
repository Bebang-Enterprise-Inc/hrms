import datetime
import importlib.util
import sys
import types
import unittest

from pathlib import Path


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

    def fake_sql(query, params=None, as_dict=False):
        query = str(query)
        if "FROM `tabEmployee`" in query and "GROUP BY branch" in query:
            return [
                {"store": "ARANETA", "store_name": "ARANETA", "total_employees": 10},
                {"store": "MKT", "store_name": "MKT", "total_employees": 8},
            ]
        if "FROM `tabSalary Slip`" in query:
            return [
                {
                    "employee": "EMP-0001",
                    "employee_name": "Test Employee",
                    "months_worked": 12,
                    "basic_total": 120000.0,
                }
            ]
        if "FROM `tabLeave Allocation`" in query:
            return [(5.0,)]
        if "FROM `tabLeave Ledger Entry`" in query:
            return [(1.0,)]
        if "FROM `tabEmployee Separation`" in query:
            return [{"month": "2026-02", "count": 2}]
        return [] if as_dict else [(0,)]

    frappe.whitelist = whitelist
    frappe._ = lambda text: text
    frappe.db = types.SimpleNamespace(
        sql=fake_sql,
        get_value=lambda doctype, name, field=None: "Test Employee",
    )
    frappe.utils = types.SimpleNamespace(today=lambda: "2026-02-27")

    utils.nowdate = lambda: "2026-02-27"

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils


_install_fake_frappe()

compliance_spec = importlib.util.spec_from_file_location(
    "compliance_under_test",
    ROOT / "hrms" / "api" / "compliance.py",
)
compliance = importlib.util.module_from_spec(compliance_spec)
assert compliance_spec and compliance_spec.loader
compliance_spec.loader.exec_module(compliance)


class ComplianceApiTests(unittest.TestCase):
    def test_dashboard_contract(self):
        result = compliance.get_compliance_dashboard()
        self.assertIn("overall_score", result)
        self.assertIn("stores", result)
        self.assertIn("year", result)
        self.assertTrue(isinstance(result["stores"], list))

    def test_13th_month_contract(self):
        result = compliance.calculate_13th_month_pay(2026)
        self.assertEqual(result["year"], 2026)
        self.assertIn("employees", result)
        self.assertIn("total_amount", result)
        self.assertEqual(result["employees"][0]["thirteenth_month_amount"], 10000.0)

    def test_sil_balance_contract(self):
        result = compliance.calculate_sil_balance("EMP-0001")
        self.assertEqual(result["employee"], "EMP-0001")
        self.assertEqual(result["balance_days"], 4.0)
        self.assertIn("monetizable_days", result)

    def test_holiday_pay_contract(self):
        result = compliance.get_holiday_pay_compliance(2, 2026)
        self.assertEqual(result["month"], 2)
        self.assertEqual(result["year"], 2026)
        self.assertIn("entries", result)

    def test_export_contract(self):
        result = compliance.generate_13th_month_report(2026)
        self.assertIn("filename", result)
        self.assertIn("data", result)


if __name__ == "__main__":
    unittest.main()
