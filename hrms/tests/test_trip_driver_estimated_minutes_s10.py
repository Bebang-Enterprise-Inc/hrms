import datetime
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_frappe_and_dependencies():
	if "frappe" not in sys.modules:
		frappe = types.ModuleType("frappe")
		utils = types.ModuleType("frappe.utils")

		def whitelist(*args, **kwargs):
			def decorator(fn):
				return fn

			return decorator

		def _throw(message, exc=None):
			if isinstance(exc, type) and issubclass(exc, Exception):
				raise exc(message)
			raise Exception(message)

		def _to_dt(value):
			if isinstance(value, datetime.datetime):
				return value
			return datetime.datetime.fromisoformat(str(value).replace(" ", "T"))

		def add_to_date(value, minutes=0):
			return _to_dt(value) + datetime.timedelta(minutes=minutes)

		def format_time(value):
			return _to_dt(value).strftime("%H:%M")

		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.throw = _throw
		frappe.PermissionError = type("PermissionError", (Exception,), {})
		frappe.log_error = lambda *args, **kwargs: None
		frappe.enqueue = lambda *args, **kwargs: None
		frappe.parse_json = json.loads
		frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
		frappe.__dict__["db"] = types.SimpleNamespace(
			get_value=lambda *args, **kwargs: None,
			get_all=lambda *args, **kwargs: [],
			sql=lambda *args, **kwargs: [],
		)
		frappe.get_doc = lambda *args, **kwargs: None
		frappe.get_all = lambda *args, **kwargs: []
		frappe.new_doc = lambda *args, **kwargs: None

		utils.nowdate = lambda: "2026-02-28"
		utils.now_datetime = lambda: datetime.datetime(2026, 2, 28, 10, 0, 0)
		utils.flt = lambda value, precision=None: float(value or 0)
		utils.cint = lambda value: int(float(value or 0))
		utils.add_to_date = add_to_date
		utils.format_time = format_time
		utils.get_datetime = _to_dt

		sys.modules["frappe"] = frappe
		sys.modules["frappe.utils"] = utils

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.utils" not in sys.modules:
		hrms_utils_pkg = types.ModuleType("hrms.utils")
		hrms_utils_pkg.__path__ = []
		sys.modules["hrms.utils"] = hrms_utils_pkg

	if "hrms.api" not in sys.modules:
		hrms_api_pkg = types.ModuleType("hrms.api")
		hrms_api_pkg.__path__ = []
		sys.modules["hrms.api"] = hrms_api_pkg

	if "hrms.utils.delivery_billing_policy" not in sys.modules:
		policy_mod = types.ModuleType("hrms.utils.delivery_billing_policy")
		policy_mod.DeliveryBillingPolicyError = type("DeliveryBillingPolicyError", (Exception,), {})
		policy_mod.should_auto_create_billing_on_delivery = lambda setting: True
		policy_mod.get_pre_delivery_exception_trace = lambda *args, **kwargs: {}
		sys.modules["hrms.utils.delivery_billing_policy"] = policy_mod

	if "hrms.utils.scm_roles" not in sys.modules:
		scm_roles_mod = types.ModuleType("hrms.utils.scm_roles")
		scm_roles_mod.SCM_ADMIN_ROLES = ["System Manager"]
		scm_roles_mod.SCM_DISPATCH_ROLES = ["System Manager"]
		scm_roles_mod.SCM_STORE_ROLES = ["Store User"]
		scm_roles_mod.check_scm_permission = lambda roles, action: None
		sys.modules["hrms.utils.scm_roles"] = scm_roles_mod


_install_fake_frappe_and_dependencies()
dispatch_spec = importlib.util.spec_from_file_location(
	"dispatch_under_test",
	ROOT / "hrms" / "api" / "dispatch.py",
)
dispatch = importlib.util.module_from_spec(dispatch_spec)
dispatch_spec.loader.exec_module(dispatch)


class _Stop:
	def __init__(self, stop_order, estimated_minutes, status="Pending"):
		self.stop_order = stop_order
		self.estimated_minutes = estimated_minutes
		self.status = status


class _TripEta:
	def __init__(self):
		self.departure_time = "2026-02-28 08:00:00"
		self.stops = [
			_Stop(stop_order=1, estimated_minutes=15, status="Delivered"),
			_Stop(stop_order=2, estimated_minutes=35, status="Pending"),
			_Stop(stop_order=3, estimated_minutes=20, status="Pending"),
		]


class _TripDoc:
	def __init__(self, stops):
		self.name = "TRIP-S10-0001"
		self.driver = None
		self.vehicle = None
		self.vehicle_plate = None
		self.cargo_type = None
		self.flags = None
		self.insert_kwargs = None
		self.stops = [types.SimpleNamespace(store_order="", idx=i + 1) for i, _ in enumerate(stops)]

	def insert(self, **kwargs):
		self.insert_kwargs = kwargs
		return None


class _TripMutationDoc:
	def __init__(self, status="Preparing"):
		self.name = "TRIP-MUTATION-0001"
		self.status = status
		self.driver = None
		self.vehicle = None
		self.vehicle_plate = None
		self.departure_temp = None
		self.seal_number = None
		self.departure_time = None
		self.flags = None
		self.save_kwargs = None
		self.stops = [
			types.SimpleNamespace(
				idx=1,
				stop_order=1,
				store="STORE-A - BEI",
				status="Pending",
				arrival_time=None,
				signature=None,
				signed_by=None,
				store_order="",
				exception_reason=None,
				exception_photo=None,
			)
		]

	def save(self, **kwargs):
		self.save_kwargs = kwargs
		return None


class _Route:
	def __init__(self):
		self.route_name = "S10 Route"
		self.default_vehicle = "TRK-001"
		self.default_driver = "EMP-DRIVER-DEFAULT"
		self.cargo_type = "Mixed"
		self.active = 1
		self.stops = [
			types.SimpleNamespace(store="STORE-A - BEI", stop_order=1, estimated_minutes=11),
			types.SimpleNamespace(store="STORE-B - BEI", stop_order=2, estimated_minutes=29),
		]


class TestTripDriverEstimatedMinutesS10(unittest.TestCase):
	def test_calculate_eta_uses_per_stop_estimated_minutes(self):
		trip = _TripEta()
		result = dispatch._calculate_eta(trip, my_stop_order=3)
		# Last delivered is stop 1, remaining path is stop 2 + stop 3 (35 + 20)
		self.assertEqual(result["eta_minutes"], 55)
		self.assertEqual(result["eta_window"]["min"], "08:55")
		self.assertEqual(result["eta_window"]["max"], "09:25")

	def test_create_trip_from_route_preserves_selected_stop_order_and_estimated_minutes(self):
		route = _Route()
		captured = {}

		def _get_value(doctype, filters=None, fieldname=None):
			if doctype == "BEI Distribution Trip":
				return None
			if doctype == "BEI Vehicle":
				return "ABC-1234"
			return None

		def _get_all(doctype, filters=None, fields=None):
			if doctype == "BEI Store Order":
				return [types.SimpleNamespace(name="SO-001", store="STORE-B - BEI")]
			return []

		def _sql(*args, **kwargs):
			return [types.SimpleNamespace(parent="SO-001", cnt=5)]

		def _build_trip_doc(trip_date, route_name, stops):
			captured["stops"] = stops
			captured["trip_date"] = trip_date
			captured["route_name"] = route_name
			captured["trip"] = _TripDoc(stops)
			return captured["trip"]

		dispatch.frappe.get_doc = MagicMock(return_value=route)
		dispatch.frappe.db.get_value = MagicMock(side_effect=_get_value)
		dispatch.frappe.db.get_all = MagicMock(side_effect=_get_all)
		dispatch.frappe.db.sql = MagicMock(side_effect=_sql)

		selected_stops = json.dumps(
			[
				{"store": "STORE-B - BEI", "stop_order": 1},
				{"store": "STORE-A - BEI", "stop_order": 2},
			]
		)

		with (
			patch.object(dispatch, "_build_trip_doc", side_effect=_build_trip_doc),
			patch.object(dispatch, "_set_store_orders_in_transit", return_value=None),
		):
			result = dispatch.create_trip_from_route(
				route_name="ROUTE-S10",
				trip_date="2026-02-28",
				vehicle="TRK-001",
				driver="EMP-DRIVER-001",
				selected_stops=selected_stops,
			)

		self.assertTrue(result["success"])
		self.assertEqual(captured["trip_date"], "2026-02-28")
		self.assertEqual(captured["route_name"], "S10 Route")
		self.assertEqual(captured["stops"][0]["store"], "STORE-B - BEI")
		self.assertEqual(captured["stops"][0]["stop_order"], 1)
		self.assertEqual(captured["stops"][0]["estimated_minutes"], 29)
		self.assertEqual(captured["stops"][1]["store"], "STORE-A - BEI")
		self.assertEqual(captured["stops"][1]["stop_order"], 2)
		self.assertEqual(captured["stops"][1]["estimated_minutes"], 11)
		self.assertTrue(captured["trip"].flags.ignore_permissions)
		self.assertTrue(captured["trip"].flags.ignore_user_permissions)
		self.assertEqual(captured["trip"].insert_kwargs, {"ignore_permissions": True})

	def test_enable_role_gated_write_sets_ignore_user_permissions(self):
		doc = types.SimpleNamespace(flags=None)
		dispatch._enable_role_gated_write(doc)
		self.assertTrue(doc.flags.ignore_permissions)
		self.assertTrue(doc.flags.ignore_user_permissions)

	def test_confirm_departure_uses_role_gated_save(self):
		trip = _TripMutationDoc(status="Preparing")
		dispatch.frappe.get_doc = MagicMock(return_value=trip)

		with patch.object(dispatch, "now_datetime", return_value="2026-02-28 08:00:00"):
			result = dispatch.confirm_departure(
				trip_name="TRIP-MUTATION-0001",
				driver="EMP-DRIVER-001",
				vehicle="TRK-001",
				vehicle_plate="ABC-1234",
				temperature="4.5",
				seal_number="SEAL-1",
			)

		self.assertTrue(result["success"])
		self.assertEqual(trip.status, "In Transit")
		self.assertEqual(trip.driver, "EMP-DRIVER-001")
		self.assertEqual(trip.vehicle, "TRK-001")
		self.assertEqual(trip.vehicle_plate, "ABC-1234")
		self.assertEqual(trip.departure_temp, 4.5)
		self.assertEqual(trip.seal_number, "SEAL-1")
		self.assertTrue(trip.flags.ignore_permissions)
		self.assertTrue(trip.flags.ignore_user_permissions)
		self.assertEqual(trip.save_kwargs, {"ignore_permissions": True})

	def test_confirm_delivery_uses_role_gated_save(self):
		trip = _TripMutationDoc(status="In Transit")
		dispatch.frappe.get_doc = MagicMock(return_value=trip)
		dispatch.frappe.db.get_single_value = MagicMock(return_value=0)

		with (
			patch.object(dispatch, "now_datetime", return_value="2026-02-28 09:00:00"),
			patch.object(dispatch, "_set_store_order_status", return_value=None),
		):
			result = dispatch.confirm_delivery(
				trip_name="TRIP-MUTATION-0001",
				stop_idx=1,
				signature="sig",
				signed_by="Receiver",
			)

		self.assertTrue(result["success"])
		self.assertEqual(trip.stops[0].status, "Delivered")
		self.assertTrue(trip.flags.ignore_permissions)
		self.assertTrue(trip.flags.ignore_user_permissions)
		self.assertEqual(trip.save_kwargs, {"ignore_permissions": True})

	def test_report_exception_uses_role_gated_save(self):
		trip = _TripMutationDoc(status="In Transit")
		dispatch.frappe.get_doc = MagicMock(return_value=trip)

		with patch.object(dispatch, "now_datetime", return_value="2026-02-28 09:15:00"):
			result = dispatch.report_exception(
				trip_name="TRIP-MUTATION-0001",
				stop_idx=1,
				exception_type="Store Closed",
				reason="Gate closed",
				photo="data:image/png;base64,abc",
			)

		self.assertTrue(result["success"])
		self.assertEqual(trip.stops[0].status, "Store Closed")
		self.assertEqual(trip.status, "Partial")
		self.assertTrue(trip.flags.ignore_permissions)
		self.assertTrue(trip.flags.ignore_user_permissions)
		self.assertEqual(trip.save_kwargs, {"ignore_permissions": True})


if __name__ == "__main__":
	unittest.main()
