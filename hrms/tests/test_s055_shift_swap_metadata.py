import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_dependencies():
	frappe = sys.modules.get("frappe") or types.ModuleType("frappe")
	utils = sys.modules.get("frappe.utils") or types.ModuleType("frappe.utils")

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	frappe.whitelist = getattr(frappe, "whitelist", whitelist)
	frappe._ = getattr(frappe, "_", lambda text: text)
	frappe.throw = getattr(
		frappe, "throw", lambda message, exc=None: (_ for _ in ()).throw(Exception(message))
	)
	frappe.db = getattr(
		frappe,
		"db",
		types.SimpleNamespace(
			exists=lambda *args, **kwargs: False,
			get_value=lambda *args, **kwargs: None,
			set_value=lambda *args, **kwargs: None,
		),
	)
	frappe.get_doc = getattr(frappe, "get_doc", lambda *args, **kwargs: None)
	frappe.delete_doc = getattr(frappe, "delete_doc", lambda *args, **kwargs: None)
	frappe.get_all = getattr(frappe, "get_all", lambda *args, **kwargs: [])
	frappe.defaults = getattr(
		frappe,
		"defaults",
		types.SimpleNamespace(get_user_default=lambda key: "Bebang Enterprise Inc."),
	)

	utils.add_days = getattr(utils, "add_days", lambda value, days: value)
	utils.date_diff = getattr(utils, "date_diff", lambda end, start: 0)

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	if "erpnext" not in sys.modules:
		sys.modules["erpnext"] = types.ModuleType("erpnext")
	if "erpnext.setup" not in sys.modules:
		sys.modules["erpnext.setup"] = types.ModuleType("erpnext.setup")
	if "erpnext.setup.doctype" not in sys.modules:
		sys.modules["erpnext.setup.doctype"] = types.ModuleType("erpnext.setup.doctype")
	if "erpnext.setup.doctype.employee" not in sys.modules:
		sys.modules["erpnext.setup.doctype.employee"] = types.ModuleType(
			"erpnext.setup.doctype.employee"
		)
	if "erpnext.setup.doctype.employee.employee" not in sys.modules:
		employee_mod = types.ModuleType("erpnext.setup.doctype.employee.employee")
		employee_mod.get_holiday_list_for_employee = lambda *args, **kwargs: None
		sys.modules["erpnext.setup.doctype.employee.employee"] = employee_mod

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg
	if "hrms.api" not in sys.modules:
		api_pkg = types.ModuleType("hrms.api")
		api_pkg.__path__ = [str(ROOT / "hrms" / "api")]
		sys.modules["hrms.api"] = api_pkg
	if "hrms.hr" not in sys.modules:
		hr_pkg = types.ModuleType("hrms.hr")
		hr_pkg.__path__ = [str(ROOT / "hrms" / "hr")]
		sys.modules["hrms.hr"] = hr_pkg
	if "hrms.hr.doctype" not in sys.modules:
		doctype_pkg = types.ModuleType("hrms.hr.doctype")
		doctype_pkg.__path__ = [str(ROOT / "hrms" / "hr" / "doctype")]
		sys.modules["hrms.hr.doctype"] = doctype_pkg
	if "hrms.hr.doctype.shift_assignment" not in sys.modules:
		sys.modules["hrms.hr.doctype.shift_assignment"] = types.ModuleType(
			"hrms.hr.doctype.shift_assignment"
		)
	if "hrms.hr.doctype.shift_assignment.shift_assignment" not in sys.modules:
		shift_assignment_mod = types.ModuleType("hrms.hr.doctype.shift_assignment.shift_assignment")
		shift_assignment_mod.ShiftAssignment = type("ShiftAssignment", (), {})
		sys.modules["hrms.hr.doctype.shift_assignment.shift_assignment"] = shift_assignment_mod
	if "hrms.hr.doctype.shift_assignment_tool" not in sys.modules:
		sys.modules["hrms.hr.doctype.shift_assignment_tool"] = types.ModuleType(
			"hrms.hr.doctype.shift_assignment_tool"
		)
	if "hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool" not in sys.modules:
		shift_tool_mod = types.ModuleType(
			"hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool"
		)
		shift_tool_mod.create_shift_assignment = lambda *args, **kwargs: None
		sys.modules["hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool"] = shift_tool_mod
	if "hrms.hr.doctype.shift_schedule" not in sys.modules:
		sys.modules["hrms.hr.doctype.shift_schedule"] = types.ModuleType(
			"hrms.hr.doctype.shift_schedule"
		)
	if "hrms.hr.doctype.shift_schedule.shift_schedule" not in sys.modules:
		shift_schedule_mod = types.ModuleType("hrms.hr.doctype.shift_schedule.shift_schedule")
		shift_schedule_mod.get_or_insert_shift_schedule = lambda *args, **kwargs: "SHIFT-SCHEDULE"
		sys.modules["hrms.hr.doctype.shift_schedule.shift_schedule"] = shift_schedule_mod


_install_fake_dependencies()
spec = importlib.util.spec_from_file_location(
	"roster_under_test_metadata",
	ROOT / "hrms" / "api" / "roster.py",
)
roster = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roster)


class TestS055ShiftSwapMetadata(unittest.TestCase):
	def test_swap_shift_preserves_weekly_plan_metadata_for_replacement_assignments(self):
		src_doc = types.SimpleNamespace(
			name="HR-SHA-SRC",
			employee="TEST-CREW-001",
			company="Bebang Enterprise Inc.",
			shift_type="Opening",
			status="Active",
			shift_location=None,
			custom_bei_schedule_source="bei_weekly_labor_plan",
			custom_bei_weekly_labor_plan="BEI-WLP-1",
			custom_bei_weekly_plan_row_key="TEST-CREW-001|2026-03-17",
			custom_bei_publish_run_id="run-1",
		)
		tgt_doc = types.SimpleNamespace(
			name="HR-SHA-TGT",
			employee="TEST-STAFF-001",
			company="Bebang Enterprise Inc.",
			shift_type="Mid",
			status="Active",
			shift_location=None,
			custom_bei_schedule_source="bei_weekly_labor_plan",
			custom_bei_weekly_labor_plan="BEI-WLP-1",
			custom_bei_weekly_plan_row_key="TEST-STAFF-001|2026-03-17",
			custom_bei_publish_run_id="run-1",
		)

		with (
			patch.object(
				roster.frappe,
				"get_doc",
				side_effect=lambda doctype, name: src_doc if name == "HR-SHA-SRC" else tgt_doc,
			),
			patch.object(roster, "break_shift") as break_shift,
			patch.object(roster, "insert_shift") as insert_shift,
		):
			roster.swap_shift(
				"HR-SHA-SRC",
				"2026-03-17",
				"TEST-STAFF-001",
				"2026-03-17",
				"HR-SHA-TGT",
				ignore_permissions=True,
			)

		break_shift.assert_any_call(tgt_doc, "2026-03-17", ignore_permissions=True)
		break_shift.assert_any_call(src_doc, "2026-03-17", ignore_permissions=True)
		insert_shift.assert_any_call(
			"TEST-STAFF-001",
			"Bebang Enterprise Inc.",
			"Opening",
			"2026-03-17",
			"2026-03-17",
			"Active",
			None,
			custom_fields={
				"custom_bei_schedule_source": "bei_weekly_labor_plan",
				"custom_bei_weekly_labor_plan": "BEI-WLP-1",
				"custom_bei_weekly_plan_row_key": "TEST-STAFF-001|2026-03-17",
				"custom_bei_publish_run_id": "run-1",
			},
			ignore_permissions=True,
		)
		insert_shift.assert_any_call(
			"TEST-CREW-001",
			"Bebang Enterprise Inc.",
			"Mid",
			"2026-03-17",
			"2026-03-17",
			"Active",
			None,
			custom_fields={
				"custom_bei_schedule_source": "bei_weekly_labor_plan",
				"custom_bei_weekly_labor_plan": "BEI-WLP-1",
				"custom_bei_weekly_plan_row_key": "TEST-CREW-001|2026-03-17",
				"custom_bei_publish_run_id": "run-1",
			},
			ignore_permissions=True,
		)

	def test_insert_shift_skips_merge_path_for_schedule_managed_rows(self):
		create_shift_assignment = MagicMock()
		exists = MagicMock(return_value=False)

		with (
			patch.object(roster, "create_shift_assignment", create_shift_assignment),
			patch.object(roster.frappe.db, "exists", exists),
		):
			roster.insert_shift(
				employee="TEST-CREW-001",
				company="Bebang Enterprise Inc.",
				shift_type="Mid",
				start_date="2026-03-17",
				end_date="2026-03-17",
				status="Active",
				shift_location=None,
				custom_fields={
					"custom_bei_schedule_source": "bei_weekly_labor_plan",
					"custom_bei_weekly_labor_plan": "BEI-WLP-1",
					"custom_bei_weekly_plan_row_key": "TEST-CREW-001|2026-03-17",
				},
				ignore_permissions=True,
			)

		create_shift_assignment.assert_called_once_with(
			"TEST-CREW-001",
			"Bebang Enterprise Inc.",
			"Mid",
			"2026-03-17",
			"2026-03-17",
			"Active",
			None,
			ignore_permissions=True,
			custom_fields={
				"custom_bei_schedule_source": "bei_weekly_labor_plan",
				"custom_bei_weekly_labor_plan": "BEI-WLP-1",
				"custom_bei_weekly_plan_row_key": "TEST-CREW-001|2026-03-17",
			},
		)
		exists.assert_not_called()


if __name__ == "__main__":
	unittest.main()
