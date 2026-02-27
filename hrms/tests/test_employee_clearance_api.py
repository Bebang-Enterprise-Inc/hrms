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
	frappe.local = types.SimpleNamespace()

	def _module_getattr(name):
		if name in {"db", "session"} and hasattr(frappe.local, name):
			return getattr(frappe.local, name)
		raise AttributeError(name)

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	def make_row(data):
		row = types.SimpleNamespace(**data)
		row.get = lambda key, default=None: getattr(row, key, default)
		return row

	def fake_get_all(doctype, filters=None, fields=None, order_by=None, limit=None):
		filters = filters or {}
		if doctype == "Employee Separation":
			return [
				make_row(
					{
						"name": "SEP-0001",
						"employee": "EMP-0001",
						"employee_name": "Test Employee",
						"boarding_begins_on": "2026-02-20",
						"boarding_status": "In Process",
						"custom_exit_interview_completed": 0,
						"department": "Operations",
						"custom_separation_type": "Resignation",
					}
				)
			]
		if doctype == "Exit Interview":
			if filters.get("employee") == "EMP-0001":
				return [make_row({"name": "EXIT-0001", "status": "Draft"})]
			return []
		if doctype == "BEI DOLE Compliance Checklist":
			return [make_row({"status": "Completed"}), make_row({"status": "Pending"})]
		return []

	class FakeInterviewDoc:
		def __init__(self):
			self.name = "EXIT-NEW-0001"
			self.status = "Draft"

		def insert(self, ignore_permissions=False):
			return self

		def add_comment(self, *args, **kwargs):
			return None

	frappe.whitelist = whitelist
	frappe._ = lambda text: text
	frappe.get_all = fake_get_all
	frappe.get_doc = lambda payload, name=None: FakeInterviewDoc()
	frappe.local.db = types.SimpleNamespace(
		get_value=lambda doctype, name, field=None: "Test Employee"
		if field == "employee_name"
		else "ARANETA",
		sql=lambda *args, **kwargs: [{"month": "2026-02", "count": 1}],
	)
	frappe.utils = types.SimpleNamespace(
		today=lambda: "2026-02-27",
		add_days=lambda date, days: "2025-11-29",
	)
	frappe.local.session = types.SimpleNamespace(user="test.hr@bebang.ph")
	frappe.__getattr__ = _module_getattr

	sys.modules["frappe"] = frappe


_install_fake_frappe()

employee_clearance_spec = importlib.util.spec_from_file_location(
	"employee_clearance_under_test",
	ROOT / "hrms" / "api" / "employee_clearance.py",
)
employee_clearance = importlib.util.module_from_spec(employee_clearance_spec)
assert employee_clearance_spec and employee_clearance_spec.loader
employee_clearance_spec.loader.exec_module(employee_clearance)


class EmployeeClearanceApiTests(unittest.TestCase):
	def test_create_exit_interview_contract(self):
		with patch.object(employee_clearance.frappe, "get_all", return_value=[]):
			result = employee_clearance.create_exit_interview("EMP-0001")

		self.assertEqual(result["employee"], "EMP-0001")
		self.assertIn("name", result)
		self.assertIn("status", result)

	def test_get_team_separations_contract(self):
		result = employee_clearance.get_team_separations()
		self.assertEqual(len(result), 1)
		row = result[0]
		self.assertEqual(row["employee"], "EMP-0001")
		self.assertIn("status", row)
		self.assertIn("exit_interview_status", row)
		self.assertIn("clearance_progress", row)

	def test_get_exit_interview_analytics_contract(self):
		result = employee_clearance.get_exit_interview_analytics("2026-01-01", "2026-02-27")
		self.assertIn("total_separations", result)
		self.assertIn("total_interviews", result)
		self.assertIn("response_rate", result)
		self.assertIn("reasons_for_leaving", result)
		self.assertIn("attrition_trend", result)


if __name__ == "__main__":
	unittest.main()
