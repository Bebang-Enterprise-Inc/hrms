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
	frappe.ValidationError = getattr(frappe, "ValidationError", type("ValidationError", (Exception,), {}))
	frappe.__dict__.setdefault("local", types.SimpleNamespace())
	if not getattr(frappe.local, "db", None):
		frappe.local.db = types.SimpleNamespace(
			get_value=lambda *args, **kwargs: None,
			exists=lambda *args, **kwargs: False,
		)
	if not getattr(frappe.local, "session", None):
		frappe.local.session = types.SimpleNamespace(user="test.supervisor@bebang.ph")
	frappe.__dict__.setdefault("db", frappe.local.db)
	frappe.get_doc = getattr(frappe, "get_doc", lambda *args, **kwargs: None)
	frappe.delete_doc = getattr(frappe, "delete_doc", lambda *args, **kwargs: None)
	frappe.get_all = getattr(frappe, "get_all", lambda *args, **kwargs: [])
	frappe.__dict__.setdefault("session", frappe.local.session)

	utils.add_days = getattr(utils, "add_days", lambda value, days: value)
	utils.cint = getattr(utils, "cint", lambda value: int(float(value or 0)))
	utils.flt = getattr(utils, "flt", lambda value: float(value or 0))
	utils.getdate = getattr(utils, "getdate", lambda value=None: value)
	utils.get_time = getattr(utils, "get_time", lambda value: value)
	utils.now_datetime = getattr(utils, "now_datetime", lambda: "2026-03-11 18:50:00")
	utils.nowdate = getattr(utils, "nowdate", lambda: "2026-03-11")

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.api" not in sys.modules:
		hrms_api_pkg = types.ModuleType("hrms.api")
		hrms_api_pkg.__path__ = [str(ROOT / "hrms" / "api")]
		sys.modules["hrms.api"] = hrms_api_pkg

	if "hrms.utils" not in sys.modules:
		hrms_utils_pkg = types.ModuleType("hrms.utils")
		hrms_utils_pkg.__path__ = [str(ROOT / "hrms" / "utils")]
		sys.modules["hrms.utils"] = hrms_utils_pkg

	if "hrms.api.store" not in sys.modules:
		store_mod = types.ModuleType("hrms.api.store")
		store_mod.resolve_employee_store_context = lambda *args, **kwargs: {}
		store_mod.resolve_warehouse = lambda *args, **kwargs: {}
		sys.modules["hrms.api.store"] = store_mod

	if "hrms.utils.store_shift_config" not in sys.modules:
		config_mod = types.ModuleType("hrms.utils.store_shift_config")
		config_mod.get_shift_options_for_store = lambda *args, **kwargs: []
		sys.modules["hrms.utils.store_shift_config"] = config_mod

	if "hrms.utils.supply_chain_contracts" not in sys.modules:
		contracts_mod = types.ModuleType("hrms.utils.supply_chain_contracts")
		contracts_mod.get_preferred_commissary_warehouses = lambda *args, **kwargs: []
		sys.modules["hrms.utils.supply_chain_contracts"] = contracts_mod


_install_fake_dependencies()
spec = importlib.util.spec_from_file_location(
	"supervisor_under_test_permissions",
	ROOT / "hrms" / "api" / "supervisor.py",
)
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)


class _FakeShiftAssignment:
	def __init__(self, docstatus=0):
		self.docstatus = docstatus
		self.flags = types.SimpleNamespace(ignore_permissions=False, ignore_user_permissions=False)
		self.insert_kwargs = None
		self.cancel_called = False
		self.submit_called = False

	def insert(self, **kwargs):
		self.insert_kwargs = kwargs

	def cancel(self):
		self.cancel_called = True

	def submit(self):
		self.submit_called = True


class _AttrDict(dict):
	__getattr__ = dict.get


class TestS033LaborPlanShiftAssignmentPermissions(unittest.TestCase):
	def test_copy_weekly_plan_from_previous_week_returns_marker_when_no_prior_published_plan(self):
		with (
			patch.object(
				supervisor,
				"_resolve_labor_plan_store",
				return_value={"warehouse": "Shaw BLVD - BKI", "warehouse_name": "Shaw BLVD"},
			),
			patch.object(supervisor, "_assert_schedule_access"),
			patch.object(supervisor.frappe, "get_all", return_value=[]),
		):
			result = supervisor.copy_weekly_plan_from_previous_week(
				store="Shaw BLVD - BKI",
				target_week_start="2026-03-23",
				surface="commissary_schedule",
			)

		self.assertFalse(result["success"])
		self.assertEqual(result["error"], "no_previous_week")

	def test_copy_weekly_plan_from_previous_week_returns_shift_payload(self):
		source_plan = types.SimpleNamespace(
			name="BEI-WLP-2026-00011",
			shifts=[
				types.SimpleNamespace(
					employee="EMP-001",
					employee_name="Jane Doe",
					day_of_week="Monday",
					shift_type_name="Commissary AM",
					shift_type=None,
					shift_start="06:00:00",
					shift_end="14:00:00",
					is_off=0,
					ends_next_day=0,
					hours=8,
					notes="Prep",
				)
			],
		)

		with (
			patch.object(
				supervisor,
				"_resolve_labor_plan_store",
				return_value={"warehouse": "Shaw BLVD - BKI", "warehouse_name": "Shaw BLVD"},
			),
			patch.object(supervisor, "_assert_schedule_access"),
			patch.object(
				supervisor.frappe,
				"get_all",
				return_value=[{"name": "BEI-WLP-2026-00011", "week_start_date": "2026-03-16"}],
			),
			patch.object(
				supervisor,
				"_get_labor_plan_employees",
				return_value=[
					{
						"name": "EMP-001",
						"employee_name": "Jane Doe",
						"designation": "Commissary Staff",
						"branch": "Shaw BLVD - BKI",
						"company": "BEI",
					}
				],
			),
			patch.object(supervisor.frappe, "get_doc", return_value=source_plan),
		):
			result = supervisor.copy_weekly_plan_from_previous_week(
				store="Shaw BLVD - BKI",
				target_week_start="2026-03-23",
				surface="commissary_schedule",
			)

		self.assertTrue(result["success"])
		self.assertEqual(result["source_plan"], "BEI-WLP-2026-00011")
		self.assertEqual(result["source_week"], "2026-03-16")
		self.assertEqual(result["shift_count"], 1)
		self.assertEqual(result["shifts"][0]["employee"], "EMP-001")
		self.assertEqual(result["shifts"][0]["shift_type_name"], "Commissary AM")
		self.assertEqual(result["shifts"][0]["hours"], 8)
		self.assertEqual(result["warnings"], [])

	def test_copy_weekly_plan_from_previous_week_filters_transferred_rows_and_flags_new_hires(self):
		source_plan = types.SimpleNamespace(
			name="BEI-WLP-2026-00012",
			shifts=[
				types.SimpleNamespace(
					employee="EMP-OLD",
					employee_name="Transferred Out",
					day_of_week="Monday",
					shift_type_name="Opening",
					shift_type=None,
					shift_start="09:30:00",
					shift_end="18:30:00",
					is_off=0,
					ends_next_day=0,
					hours=8,
					notes=None,
				)
			],
		)

		with (
			patch.object(
				supervisor,
				"_resolve_labor_plan_store",
				return_value={"warehouse": "AYALA", "warehouse_name": "Ayala"},
			),
			patch.object(supervisor, "_assert_schedule_access"),
			patch.object(
				supervisor.frappe,
				"get_all",
				return_value=[{"name": "BEI-WLP-2026-00012", "week_start_date": "2026-03-16"}],
			),
			patch.object(
				supervisor,
				"_get_labor_plan_employees",
				return_value=[
					{
						"name": "EMP-NEW",
						"employee_name": "New Hire",
						"designation": "Cashier",
						"branch": "AYALA",
						"company": "BEI",
					}
				],
			),
			patch.object(supervisor.frappe, "get_doc", return_value=source_plan),
		):
			result = supervisor.copy_weekly_plan_from_previous_week(
				store="AYALA",
				target_week_start="2026-03-23",
				surface="store_schedule",
			)

		self.assertTrue(result["success"])
		self.assertEqual(result["shift_count"], 0)
		self.assertEqual({warning["code"] for warning in result["warnings"]}, {"transferred_out", "new_hire"})

	def test_apply_weekly_template_returns_role_mapped_rows(self):
		with (
			patch.object(
				supervisor,
				"_resolve_labor_plan_store",
				return_value={"warehouse": "AYALA", "warehouse_name": "Ayala"},
			),
			patch.object(supervisor, "_assert_schedule_access"),
			patch.object(
				supervisor,
				"_get_labor_plan_employees",
				return_value=[
					{
						"name": "EMP-LEAD",
						"employee_name": "Lead",
						"designation": "Store Supervisor",
						"branch": "AYALA",
						"company": "BEI",
					},
					{
						"name": "EMP-CASH",
						"employee_name": "Cashier",
						"designation": "Cashier",
						"branch": "AYALA",
						"company": "BEI",
					},
				],
			),
			patch.object(
				supervisor,
				"get_shift_options_for_store",
				return_value=[
					{
						"shift_type_name": "Opening",
						"label": "Opening",
						"shift_start": "09:30",
						"shift_end": "18:30",
						"hours": 8,
						"is_off": 0,
						"ends_next_day": 0,
					},
					{
						"shift_type_name": "Mid",
						"label": "Mid",
						"shift_start": "12:00",
						"shift_end": "20:00",
						"hours": 8,
						"is_off": 0,
						"ends_next_day": 0,
					},
					{
						"shift_type_name": "Closing",
						"label": "Closing",
						"shift_start": "14:00",
						"shift_end": "22:30",
						"hours": 8,
						"is_off": 0,
						"ends_next_day": 0,
					},
					{
						"shift_type_name": "Off",
						"label": "Off",
						"shift_start": "",
						"shift_end": "",
						"hours": 0,
						"is_off": 1,
						"ends_next_day": 0,
					},
				],
			),
		):
			result = supervisor.apply_weekly_template(
				store="AYALA",
				template_key="retail_balanced",
				week_start="2026-03-23",
				surface="store_schedule",
			)

		self.assertEqual(result["template"]["template_key"], "retail_balanced")
		self.assertGreater(result["shift_count"], 0)
		self.assertTrue(any(shift["employee"] == "EMP-LEAD" for shift in result["shifts"]))
		self.assertEqual(result["warnings"], [])

	def test_get_labor_plan_employees_accepts_commissary_branch_aliases(self):
		employee_filters = {}

		def fake_get_all(doctype, **kwargs):
			if doctype == "Employee":
				employee_filters.update(kwargs.get("filters") or {})
				return [
					{
						"name": "EMP-COMM-001",
						"employee_name": "Commissary Crew",
						"designation": "Commissary Crew",
						"branch": "COMMISSARY SHAW",
						"company": "BKI",
					}
				]
			return []

		with (
			patch.object(supervisor.frappe, "get_all", side_effect=fake_get_all),
			patch.object(
				supervisor,
				"_get_labor_plan_hour_rate",
				return_value={"hour_rate": 88.5, "source": "salary_structure", "base_salary": 18408},
			),
		):
			employees = supervisor._get_labor_plan_employees(
				{"warehouse": "Shaw BLVD - BKI", "warehouse_name": "Shaw BLVD"}
			)

		self.assertIn("COMMISSARY SHAW", employee_filters["branch"][1])
		self.assertEqual(len(employees), 1)
		self.assertEqual(employees[0]["branch"], "COMMISSARY SHAW")
		self.assertEqual(employees[0]["hour_rate"], 88.5)

	def test_get_area_schedule_overview_uses_schedule_scope_for_area_personas_with_hr_roles(self):
		store_mod = sys.modules["hrms.api.store"]
		store_mod.get_user_store = lambda surface=None: {
			"stores": [{"name": "TEST-STORE-BGC - BEI", "warehouse_name": "TEST-STORE-BGC"}]
		}
		store_mod._get_store_schedule_locations = lambda: []

		with (
			patch.object(
				supervisor.frappe, "get_roles", return_value=["Area Supervisor", "HR User"], create=True
			),
			patch.object(
				supervisor.frappe.db,
				"get_value",
				return_value=_AttrDict(designation="Area Supervisor"),
			),
			patch.object(
				supervisor,
				"_resolve_labor_plan_store",
				return_value={"warehouse": "TEST-STORE-BGC - BEI", "warehouse_name": "TEST-STORE-BGC"},
			),
			patch.object(supervisor, "_get_labor_plan_employees", return_value=[]),
			patch.object(supervisor.frappe, "get_all", return_value=[]),
		):
			result = supervisor.get_area_schedule_overview("2026-03-16")

		self.assertEqual(result["summary"]["locations"], 1)
		self.assertEqual(result["summary"]["missing_locations"], 1)
		self.assertEqual(result["items"][0]["store"], "TEST-STORE-BGC - BEI")

	def test_cancel_and_delete_shift_assignment_uses_system_permission_flags(self):
		doc = _FakeShiftAssignment(docstatus=1)
		delete_doc = MagicMock()

		with (
			patch.object(supervisor.frappe, "get_doc", return_value=doc),
			patch.object(supervisor.frappe, "delete_doc", delete_doc),
		):
			supervisor._cancel_and_delete_shift_assignment("SHIFT-0001")

		self.assertTrue(doc.flags.ignore_permissions)
		self.assertTrue(doc.flags.ignore_user_permissions)
		self.assertTrue(doc.cancel_called)
		delete_doc.assert_called_once_with("Shift Assignment", "SHIFT-0001", ignore_permissions=True)

	def test_create_shift_assignment_from_plan_uses_system_permission_flags_before_submit(self):
		doc = _FakeShiftAssignment(docstatus=0)
		row = types.SimpleNamespace(employee="TEST-CREW-001", shift_type_name="Opening")
		plan = types.SimpleNamespace(name="BEI-WLP-2026-00007")

		with (
			patch.object(
				supervisor.frappe.db,
				"get_value",
				return_value=_AttrDict(company="Bebang Enterprise Inc.", branch="Araneta Gateway"),
			),
			patch.object(supervisor, "_ensure_shift_type_for_plan_row", return_value="Opening"),
			patch.object(supervisor.frappe, "get_doc", return_value=doc),
		):
			result = supervisor._create_shift_assignment_from_plan(
				plan=plan,
				row=row,
				work_date="2026-05-04",
				publish_run_id="2026-03-11 18:50:00",
			)

		self.assertIs(result, doc)
		self.assertTrue(doc.flags.ignore_permissions)
		self.assertTrue(doc.flags.ignore_user_permissions)
		self.assertEqual(doc.insert_kwargs, {"ignore_permissions": True})
		self.assertTrue(doc.submit_called)

	def test_approve_shift_swap_request_elevates_assignment_mutation_permissions(self):
		doc = types.SimpleNamespace(
			status="Pending Approval",
			store="TEST-STORE-BGC - BEI",
			requester_shift_assignment="HR-SHA-1",
			target_shift_assignment="HR-SHA-2",
			target_employee="TEST-STAFF-001",
			swap_date="2026-03-17",
			save=MagicMock(),
		)
		swap_shift = MagicMock()
		roster_mod = types.ModuleType("hrms.api.roster")
		roster_mod.swap_shift = swap_shift
		assignment_doc = types.SimpleNamespace(
			custom_bei_weekly_labor_plan="BEI-WLP-1",
			docstatus=1,
			status="Active",
		)

		with (
			patch.dict(sys.modules, {"hrms.api.roster": roster_mod}),
			patch.object(
				supervisor.frappe,
				"get_doc",
				side_effect=lambda doctype, name: doc if doctype == "BEI Shift Swap Request" else assignment_doc,
			),
			patch.object(supervisor, "_is_commissary_schedule_store", return_value=False),
			patch.object(supervisor, "_assert_schedule_access"),
			patch.object(supervisor, "_sync_shift_swap_plan_rows"),
			patch.object(supervisor, "_notify_shift_swap_decision"),
			patch.object(supervisor, "_serialize_shift_swap_request", return_value={"name": "BEI-SSR-1"}),
			patch.object(supervisor, "now_datetime", return_value="2026-03-17 20:10:00"),
		):
			result = supervisor.approve_shift_swap_request("BEI-SSR-1", "approved")

		swap_shift.assert_called_once_with(
			"HR-SHA-1",
			"2026-03-17",
			"TEST-STAFF-001",
			"2026-03-17",
			"HR-SHA-2",
			ignore_permissions=True,
		)
		self.assertEqual(doc.save.call_count, 2)
		doc.save.assert_any_call(ignore_permissions=True)
		self.assertIsNone(doc.requester_shift_assignment)
		self.assertIsNone(doc.target_shift_assignment)
		self.assertTrue(result["success"])


if __name__ == "__main__":
	unittest.main()
