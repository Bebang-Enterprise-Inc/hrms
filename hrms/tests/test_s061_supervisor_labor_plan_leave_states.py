import importlib.util
import sys
import types
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

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
	frappe.PermissionError = getattr(frappe, "PermissionError", type("PermissionError", (Exception,), {}))
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
	frappe.__dict__.setdefault("session", frappe.local.session)
	frappe.get_doc = getattr(frappe, "get_doc", lambda *args, **kwargs: None)
	frappe.get_all = getattr(frappe, "get_all", lambda *args, **kwargs: [])
	frappe.get_roles = getattr(frappe, "get_roles", lambda *args, **kwargs: [])

	utils.add_days = getattr(utils, "add_days", lambda value, days: value)
	utils.cint = getattr(utils, "cint", lambda value: int(float(value or 0)))
	utils.flt = getattr(utils, "flt", lambda value: float(value or 0))
	utils.get_time = getattr(utils, "get_time", lambda value: value)
	utils.getdate = getattr(utils, "getdate", lambda value: value)
	utils.now_datetime = getattr(utils, "now_datetime", lambda: "2026-03-18 14:15:00")
	utils.nowdate = getattr(utils, "nowdate", lambda: "2026-03-18")

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.api" not in sys.modules:
		hrms_api_pkg = types.ModuleType("hrms.api")
		hrms_api_pkg.__path__ = []
		sys.modules["hrms.api"] = hrms_api_pkg

	if "hrms.utils" not in sys.modules:
		hrms_utils_pkg = types.ModuleType("hrms.utils")
		hrms_utils_pkg.__path__ = []
		sys.modules["hrms.utils"] = hrms_utils_pkg

	if "hrms.api.store" not in sys.modules:
		store_mod = types.ModuleType("hrms.api.store")
		store_mod.resolve_employee_store_context = lambda *args, **kwargs: {}
		store_mod.resolve_warehouse = lambda value: value
		sys.modules["hrms.api.store"] = store_mod

	if "hrms.utils.labor_plan_templates" not in sys.modules:
		template_mod = types.ModuleType("hrms.utils.labor_plan_templates")
		template_mod.apply_template_to_employees = lambda *args, **kwargs: {
			"template": {},
			"shifts": [],
			"warnings": [],
		}
		template_mod.get_template_metadata = lambda *args, **kwargs: []
		sys.modules["hrms.utils.labor_plan_templates"] = template_mod

	if "hrms.utils.supply_chain_contracts" not in sys.modules:
		supply_chain_mod = types.ModuleType("hrms.utils.supply_chain_contracts")
		supply_chain_mod.get_preferred_commissary_warehouses = lambda *args, **kwargs: []
		sys.modules["hrms.utils.supply_chain_contracts"] = supply_chain_mod


_install_fake_dependencies()
store_shift_config_spec = importlib.util.spec_from_file_location(
	"store_shift_config_under_test_s061",
	ROOT / "hrms" / "utils" / "store_shift_config.py",
)
store_shift_config = importlib.util.module_from_spec(store_shift_config_spec)
store_shift_config_spec.loader.exec_module(store_shift_config)
sys.modules["hrms.utils.store_shift_config"] = store_shift_config
spec = importlib.util.spec_from_file_location(
	"supervisor_under_test_s061",
	ROOT / "hrms" / "api" / "supervisor.py",
)
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)


class TestS061ShiftCatalog(unittest.TestCase):
	def test_default_shift_options_include_day_off_and_leave_states(self):
		labels = {
			option["label"] for option in store_shift_config.get_shift_options_for_store("Gateway Cubao")
		}
		self.assertTrue({"Opening", "Mid", "Closing", "Day Off", "VL", "SL"}.issubset(labels))


class TestS061LeaveAwareMerging(unittest.TestCase):
	def test_day_off_uses_off_storage_but_keeps_day_off_display(self):
		normalized = supervisor._normalize_shift_payload(
			{
				"employee": "EMP-001",
				"employee_name": "Pat",
				"day_of_week": "Monday",
				"shift_type_name": "Day Off",
				"shift_type": "Day Off",
				"is_off": 1,
			}
		)

		self.assertEqual(normalized["storage_shift_type_name"], "Off")
		self.assertEqual(normalized["display_label"], "Day Off")
		self.assertEqual(normalized["hours"], 0)

	def test_approved_leave_override_wins_over_manual_shift(self):
		manual_shift = {
			"employee": "EMP-001",
			"employee_name": "Pat",
			"day_of_week": "Monday",
			"shift_type_name": "Opening",
			"shift_type": "Opening",
			"shift_label": "Opening",
			"is_off": 0,
			"shift_start": "09:30",
			"shift_end": "18:30",
			"hours": 8,
		}
		leave_override = {
			"employee": "EMP-001",
			"employee_name": "Pat",
			"day_of_week": "Monday",
			"shift_type_name": "Off",
			"shift_type": "VL",
			"shift_label": "VL",
			"is_off": 1,
			"hours": 0,
			"shift_source": "approved_leave",
			"is_locked": 1,
		}

		with patch.object(supervisor, "_get_approved_leave_overrides", return_value=[leave_override]):
			merged = supervisor._merge_approved_leave_shifts(
				{"warehouse": "W1", "warehouse_name": "W1"},
				"2026-03-16",
				[manual_shift],
				employees=[],
			)

		self.assertEqual(len(merged), 1)
		self.assertEqual(merged[0]["shift_label"], "VL")
		self.assertEqual(merged[0]["shift_source"], "approved_leave")

	def test_manual_leave_state_requires_approved_leave(self):
		with patch.object(supervisor, "_get_approved_leave_overrides", return_value=[]):
			with self.assertRaises(Exception) as exc:
				supervisor._merge_approved_leave_shifts(
					{"warehouse": "W1", "warehouse_name": "W1"},
					"2026-03-16",
					[
						{
							"employee": "EMP-001",
							"employee_name": "Pat",
							"day_of_week": "Monday",
							"shift_type_name": "VL",
							"shift_type": "VL",
							"shift_label": "VL",
							"is_off": 1,
						}
					],
					employees=[],
				)

		self.assertIn("Approved leave is required", str(exc.exception))

	def test_approved_leave_overrides_include_status_approved_rows_even_if_not_submitted(self):
		def fake_get_all(*args, **kwargs):
			filters = kwargs.get("filters") or {}
			if filters.get("docstatus") == 1:
				return []
			return [
				{
					"name": "HR-LAP-0001",
					"employee": "EMP-001",
					"employee_name": "Pat",
					"leave_type": "Vacation Leave",
					"from_date": "2026-03-16",
					"to_date": "2026-03-16",
					"description": "Approved but still draft-docstatus contract",
				}
			]

		with (
			patch.object(supervisor, "getdate", side_effect=lambda value: date.fromisoformat(str(value))),
			patch.object(
				supervisor,
				"add_days",
				side_effect=lambda value, days: (
					date.fromisoformat(str(value)) + timedelta(days=days)
				).isoformat(),
			),
			patch.object(supervisor.frappe, "get_all", side_effect=fake_get_all),
		):
			overrides = supervisor._get_approved_leave_overrides(
				{"warehouse": "W1", "warehouse_name": "W1"},
				"2026-03-16",
				employees=[{"name": "EMP-001", "employee_name": "Pat"}],
			)

		self.assertEqual(len(overrides), 1)
		self.assertEqual(overrides[0]["shift_label"], "VL")
		self.assertEqual(overrides[0]["leave_application"], "HR-LAP-0001")
		self.assertEqual(overrides[0]["shift_source"], "approved_leave")

	def test_apply_shifts_persists_leave_metadata_on_plan_rows(self):
		class FakeRow:
			pass

		class FakeDoc:
			def __init__(self):
				self.shifts = []
				self.total_hours = 0

			def append(self, fieldname, value):
				self.asserted_fieldname = fieldname
				row = FakeRow()
				self.shifts.append(row)
				return row

		doc = FakeDoc()

		supervisor._apply_shifts(
			doc,
			[
				{
					"employee": "EMP-001",
					"employee_name": "Pat",
					"day_of_week": "Monday",
					"shift_type_name": "Off",
					"shift_type": "VL",
					"shift_label": "VL",
					"storage_shift_type_name": "Off",
					"is_off": 1,
					"shift_source": "approved_leave",
					"is_locked": 1,
					"notes": "Approved vacation leave",
				}
			],
		)

		self.assertEqual(doc.asserted_fieldname, "shifts")
		self.assertEqual(len(doc.shifts), 1)
		self.assertEqual(doc.shifts[0].shift_type, "VL")
		self.assertEqual(doc.shifts[0].shift_source, "approved_leave")
		self.assertEqual(doc.shifts[0].leave_locked, 1)
		self.assertEqual(doc.shifts[0].notes, "Approved vacation leave")

	def test_serialize_weekly_plan_exposes_is_locked_alias(self):
		class FakeRow(dict):
			pass

		class FakeDoc:
			def as_dict(self):
				return {
					"name": "BEI-WLP-TEST",
					"status": "Draft",
					"shifts": [
						FakeRow(
							employee="EMP-001",
							day_of_week="Monday",
							shift_type="VL",
							shift_source="approved_leave",
							leave_locked=1,
						)
					],
				}

		serialized = supervisor._serialize_weekly_plan(FakeDoc())
		self.assertEqual(serialized["shifts"][0]["shift_source"], "approved_leave")
		self.assertEqual(serialized["shifts"][0]["is_locked"], 1)
		self.assertNotIn("leave_locked", serialized["shifts"][0])

	def test_serialize_weekly_plan_handles_rows_with_noncallable_as_dict(self):
		row = {"employee": "EMP-001", "shift_source": None, "leave_locked": 0}
		row["as_dict"] = None

		class FakeDoc:
			def as_dict(self):
				return {"name": "BEI-WLP-TEST", "status": "Draft", "shifts": [row]}

		serialized = supervisor._serialize_weekly_plan(FakeDoc())
		self.assertEqual(serialized["shifts"][0]["shift_source"], "manual")
		self.assertEqual(serialized["shifts"][0]["is_locked"], 0)


if __name__ == "__main__":
	unittest.main()
