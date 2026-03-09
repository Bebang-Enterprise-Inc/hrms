import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_base_frappe():
	if "frappe" not in sys.modules:
		frappe = types.ModuleType("frappe")
		sys.modules["frappe"] = frappe
	else:
		frappe = sys.modules["frappe"]

	if "frappe.utils" not in sys.modules:
		utils = types.ModuleType("frappe.utils")
		sys.modules["frappe.utils"] = utils
	else:
		utils = sys.modules["frappe.utils"]

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	frappe.whitelist = whitelist
	frappe._ = lambda text: text
	frappe.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(Exception(message))
	frappe.log_error = lambda *args, **kwargs: None
	frappe.PermissionError = type("PermissionError", (Exception,), {})
	frappe.ValidationError = type("ValidationError", (Exception,), {})
	frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
	frappe.local = types.SimpleNamespace(
		session=types.SimpleNamespace(user="tester@bebang.ph"),
		db=types.SimpleNamespace(
			has_column=lambda *args, **kwargs: False,
			get_value=lambda *args, **kwargs: None,
			sql=lambda *args, **kwargs: [],
		),
	)
	frappe.__getattr__ = lambda name: getattr(frappe.local, name)
	frappe.get_all = lambda *args, **kwargs: []
	frappe.get_roles = lambda user=None: ["System Manager"]
	frappe.get_doc = lambda *args, **kwargs: None
	frappe.get_meta = lambda *args, **kwargs: types.SimpleNamespace(has_field=lambda field: False)
	frappe.logger = lambda: types.SimpleNamespace(warning=lambda *args, **kwargs: None)

	utils.cint = lambda value, *args, **kwargs: int(value or 0)
	utils.flt = lambda value, *args, **kwargs: float(value or 0)
	utils.nowdate = lambda: "2026-03-09"
	utils.now_datetime = lambda: "2026-03-09 10:00:00"
	utils.getdate = lambda value: value
	utils.get_datetime = lambda value=None: value
	utils.add_days = lambda value, days: value
	utils.get_first_day = lambda value: value
	utils.get_last_day = lambda value: value

	frappe.utils = utils
	return frappe, utils


def _ensure_module(name: str, **attrs):
	module = sys.modules.get(name)
	if module is None:
		module = types.ModuleType(name)
		sys.modules[name] = module
	for key, value in attrs.items():
		setattr(module, key, value)
	return module


def _install_billing_deps():
	_install_base_frappe()
	_ensure_module("hrms")
	_ensure_module("hrms.api")
	_ensure_module("hrms.utils")
	_ensure_module("hrms.hr")
	_ensure_module("hrms.hr.doctype")
	_ensure_module("hrms.hr.doctype.bei_store_type")
	_ensure_module(
		"hrms.hr.doctype.bei_store_type.bei_store_type",
		resolve_store_type=lambda store_type=None, store_type_category=None: (
			store_type or store_type_category
		),
	)
	_ensure_module("hrms.utils.bei_config", get_company=lambda: "Bebang Enterprise Inc.")
	_ensure_module(
		"hrms.utils.scm_roles",
		RATE_MANAGEMENT_ROLES=["System Manager"],
		SCM_BILLING_ROLES=["System Manager"],
		check_scm_permission=lambda roles, action: None,
	)


def _install_dispatch_deps():
	_install_base_frappe()
	_ensure_module("hrms")
	_ensure_module("hrms.api")
	_ensure_module("hrms.utils")
	_ensure_module(
		"hrms.utils.delivery_billing_policy",
		DeliveryBillingPolicyError=type("DeliveryBillingPolicyError", (Exception,), {}),
		get_pre_delivery_exception_trace=lambda *args, **kwargs: {},
		should_auto_create_billing_on_delivery=lambda *args, **kwargs: False,
	)
	_ensure_module(
		"hrms.utils.scm_roles",
		SCM_ADMIN_ROLES=["System Manager"],
		SCM_DISPATCH_ROLES=["System Manager"],
		SCM_STORE_ROLES=["Store OIC"],
		check_scm_permission=lambda roles, action: None,
	)


def _install_store_deps():
	_install_base_frappe()
	_ensure_module("hrms")
	_ensure_module("hrms.api")
	_ensure_module("hrms.utils")
	_ensure_module("hrms.utils.bei_config", get_company=lambda: "Bebang Enterprise Inc.")
	_ensure_module(
		"hrms.utils.scm_roles",
		SCM_APPROVAL_ROLES=["System Manager"],
		check_scm_permission=lambda roles, action: None,
	)


def _load_module(module_name: str, relative_path: str):
	spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class TestL1BlockerContractsS27(unittest.TestCase):
	def test_billing_partner_field_falls_back_to_vehicle_partner(self):
		_install_billing_deps()
		billing = _load_module("billing_s27_under_test", "hrms/api/billing.py")

		billing.frappe.db.has_column = lambda doctype, fieldname: False
		self.assertEqual(billing._trip_partner_field_sql(), "veh.threepl_partner")
		self.assertIn("tabBEI Vehicle", billing._trip_vehicle_join_sql())

		billing.frappe.db.has_column = lambda doctype, fieldname: fieldname == "vehicle_owner"
		self.assertEqual(billing._trip_partner_field_sql(), "dt.vehicle_owner")
		self.assertEqual(billing._trip_vehicle_join_sql(), "")

	def test_dispatch_maps_cell_number_back_to_cell_phone(self):
		_install_dispatch_deps()
		dispatch = _load_module("dispatch_s27_under_test", "hrms/api/dispatch.py")

		dispatch.frappe.db.has_column = lambda doctype, fieldname: fieldname == "cell_number"

		def fake_get_all(doctype, filters=None, fields=None, order_by=None):
			if doctype == "Employee":
				return [
					types.SimpleNamespace(
						name="EMP-001",
						employee_name="Driver One",
						designation="Driver",
						status="Active",
						cell_number="09170000001",
					)
				]
			if doctype == "BEI Distribution Trip":
				return []
			return []

		dispatch.frappe.get_all = fake_get_all

		result = dispatch.get_available_drivers(date="2026-03-09")
		self.assertEqual(result["summary"]["total"], 1)
		self.assertEqual(result["drivers"][0]["cell_phone"], "09170000001")
		self.assertEqual(result["drivers"][0]["status"], "Available")

	def test_store_closing_status_skips_missing_optional_columns(self):
		_install_store_deps()
		store = _load_module("store_s27_under_test", "hrms/api/store.py")

		requested_fields = {}

		def fake_has_column(doctype, fieldname):
			return fieldname in {"cashier_signoff", "production_signoff"}

		def fake_get_value(doctype, filters, fields, as_dict=False):
			requested_fields["fields"] = list(fields)
			return {
				"name": "BEI-CLOSE-0001",
				"stage_completed": "checklist",
				"status": "Submitted",
				"pos_down": 0,
				"cash_variance": 25,
				"cashier_signoff": 1,
				"production_signoff": 0,
			}

		store.frappe.db.has_column = fake_has_column
		store.frappe.db.get_value = fake_get_value

		result = store.get_closing_report_status(store="TEST-STORE-BGC - BEI", date="2026-03-09")

		self.assertNotIn("inventory_variance_total", requested_fields["fields"])
		self.assertEqual(result["inventory_variance_total"], 0)
		self.assertEqual(result["cashier_signoff"], 1)
		self.assertEqual(result["production_signoff"], 0)


if __name__ == "__main__":
	unittest.main()
