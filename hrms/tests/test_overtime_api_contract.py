import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


class AttrDict(dict):
	def __getattr__(self, name):
		try:
			return self[name]
		except KeyError as exc:
			raise AttributeError(name) from exc


def _install_fake_frappe():
	sys.modules.pop("frappe", None)
	sys.modules.pop("frappe.utils", None)

	frappe = types.ModuleType("frappe")
	utils = types.ModuleType("frappe.utils")
	frappe.local = types.SimpleNamespace()

	def _module_getattr(name):
		if name in {"db", "session"} and hasattr(frappe.local, name):
			return getattr(frappe.local, name)
		raise AttributeError(name)

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	def _throw(message, exc=None):
		if isinstance(exc, type) and issubclass(exc, Exception):
			raise exc(message)
		raise Exception(message)

	def _sql(query, params=None, as_dict=False):
		query = str(query)
		if "GROUP BY COALESCE(emp.department" in query:
			return [
				AttrDict(
					{
					"department": "Operations",
					"store": "ARANETA",
					"total_requests": 3,
					"total_hours": 8.0,
					"approved_hours": 5.0,
					"pending_hours": 2.0,
					"rejected_hours": 1.0,
					"approved_count": 2,
					"pending_count": 1,
					"rejected_count": 0,
					}
				)
			]

		return [
			AttrDict(
				{
				"name": "OT-0001",
				"employee": "EMP-0001",
				"employee_name": "Test Employee",
				"branch": "ARANETA",
				"attendance_date": "2026-02-27",
				"shift": "Morning",
				"regular_hours": 8.0,
				"overtime_hours": 1.5,
				"total_hours": 9.5,
				"overtime_status": "Pending Approval",
				"supervisor": "EMP-MGR-001",
				"reviewed_by": None,
				"reviewed_at": None,
				"approval_notes": None,
				"rejection_reason": None,
				}
			)
		]

	frappe.whitelist = whitelist
	frappe.throw = _throw
	frappe._ = lambda text: text
	frappe.PermissionError = Exception
	frappe.get_roles = lambda user=None: ["HR Manager"]
	frappe.local.session = types.SimpleNamespace(user="test.hr@bebang.ph")
	frappe.get_doc = lambda *args, **kwargs: None
	frappe.local.db = types.SimpleNamespace(
		sql=_sql,
		exists=lambda *args, **kwargs: False,
		get_value=lambda *args, **kwargs: None,
	)
	frappe.__getattr__ = _module_getattr
	frappe._dict = lambda value=None: AttrDict(value or {})
	frappe.logger = lambda *args, **kwargs: types.SimpleNamespace(info=lambda *a, **k: None)

	utils.cint = lambda value=0: int(value or 0)
	utils.flt = lambda value, precision=None: float(value or 0)
	utils.nowdate = lambda: "2026-02-27"
	utils.now_datetime = lambda: datetime(2026, 2, 27, 8, 0, 0)
	utils.getdate = lambda value=None: value
	utils.get_datetime = lambda value=None: value if isinstance(value, datetime) else datetime(2026, 2, 27, 8, 0, 0)
	utils.get_time = lambda value=None: value if isinstance(value, time) else time(8, 0, 0)
	utils.add_days = lambda date_obj, days: date_obj

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils


def _install_stub_dependencies():
	api_helpers = types.ModuleType("hrms.utils.api_helpers")
	api_helpers._paginate = lambda rows, page=1, page_size=20: {
		"data": rows,
		"total": len(rows),
		"page": page,
		"page_size": page_size,
	}
	sys.modules["hrms.utils.api_helpers"] = api_helpers

	store = types.ModuleType("hrms.api.store")
	store.resolve_employee_store_context = lambda *args, **kwargs: {}
	sys.modules["hrms.api.store"] = store


class FakeOTDoc:
	def __init__(self, name):
		self.name = name
		self.overtime_status = "Pending Approval"
		self.overtime_hours = 1.5
		self.employee = "EMP-0001"
		self.assigned_approver = "test.supervisor@bebang.ph"
		self.fallback_approver = "test.staff@bebang.ph"
		self.escalation_approver = "test.area@bebang.ph"
		self.approval_notes = None
		self.rejection_reason = None
		self.reviewed_by = None
		self.reviewed_at = None
		self.candidate_overtime_type = "Regular Day Overtime"
		self.approved_overtime_type = None
		self.review_note = None
		self.override_note = None
		self.payroll_bridge_status = None

	def save(self, **kwargs):
		return self


_install_fake_frappe()
_install_stub_dependencies()

overtime_spec = importlib.util.spec_from_file_location(
	"overtime_under_test",
	ROOT / "hrms" / "api" / "overtime.py",
)
overtime = importlib.util.module_from_spec(overtime_spec)
assert overtime_spec and overtime_spec.loader
overtime_spec.loader.exec_module(overtime)


class OvertimeApiContractTests(unittest.TestCase):
	def test_get_overtime_requests_contract(self):
		result = overtime.get_overtime_requests(
			status="Pending Approval",
			page=1,
			page_size=20,
		)
		self.assertIn("data", result)
		self.assertIn("total", result)
		self.assertEqual(result["page"], 1)
		self.assertEqual(result["page_size"], 20)
		self.assertEqual(result["data"][0]["name"], "OT-0001")

	def test_get_overtime_summary_contract(self):
		result = overtime.get_overtime_summary()
		self.assertIn("summary", result)
		self.assertIn("totals", result)
		self.assertEqual(result["summary"][0]["store"], "ARANETA")
		self.assertEqual(result["totals"]["total_requests"], 3)

	def test_approve_accepts_portal_payload_keys(self):
		doc = FakeOTDoc("OT-0001")
		with patch.object(overtime.frappe, "get_doc", return_value=doc):
			result = overtime.approve_overtime(name="OT-0001", approval_notes="approved")

		self.assertEqual(result["status"], "Approved")
		self.assertEqual(doc.approval_notes, "approved")

	def test_reject_accepts_portal_payload_keys(self):
		doc = FakeOTDoc("OT-0002")
		with patch.object(overtime.frappe, "get_doc", return_value=doc):
			result = overtime.reject_overtime(name="OT-0002", rejection_reason="invalid")

		self.assertEqual(result["status"], "Rejected")
		self.assertEqual(doc.rejection_reason, "invalid")

	def test_escalate_prefers_escalation_approver_over_fallback(self):
		doc = FakeOTDoc("OT-0003")
		with (
			patch.object(overtime.frappe, "get_doc", return_value=doc),
			patch.object(overtime, "_assert_review_access", return_value=False),
		):
			result = overtime.escalate_overtime(name="OT-0003", notes="Escalating to area supervisor")

		self.assertEqual(result["status"], overtime.OT_ESCALATED)
		self.assertEqual(result["assigned_approver"], "test.area@bebang.ph")
		self.assertEqual(doc.assigned_approver, "test.area@bebang.ph")
		self.assertEqual(doc.review_note, "Escalating to area supervisor")


if __name__ == "__main__":
	unittest.main()
