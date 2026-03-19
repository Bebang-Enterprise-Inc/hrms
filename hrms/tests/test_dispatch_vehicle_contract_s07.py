# Copyright (c) 2026, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

"""Sprint 07 contract checks for warehouse vehicle + variance APIs."""

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_runtime():
	if "frappe" not in sys.modules:
		frappe = types.ModuleType("frappe")
		utils = types.ModuleType("frappe.utils")

		def whitelist(*args, **kwargs):
			if args and callable(args[0]) and len(args) == 1 and not kwargs:
				return args[0]

			def decorator(fn):
				return fn

			return decorator

		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.throw = lambda message, exc=None: (_ for _ in ()).throw(Exception(message))
		frappe.log_error = lambda *args, **kwargs: None
		frappe.get_roles = lambda *_args, **_kwargs: ["Warehouse User", "System Manager"]
		frappe.session = types.SimpleNamespace(user="test.warehouse@bebang.ph")
		fake_db = types.SimpleNamespace(
			has_column=lambda *args, **kwargs: True,
			get_single_value=lambda *args, **kwargs: None,
			get_value=lambda *args, **kwargs: None,
			exists=lambda *args, **kwargs: None,
			sql=lambda *args, **kwargs: [],
			count=lambda *args, **kwargs: 0,
		)
		frappe.local = types.SimpleNamespace(db=fake_db)
		frappe.__getattr__ = (
			lambda name, _frappe=frappe: getattr(_frappe.local, name)
			if name == "db"
			else (_ for _ in ()).throw(AttributeError(name))
		)
		frappe.get_all = lambda *args, **kwargs: []
		frappe.get_doc = lambda *args, **kwargs: types.SimpleNamespace(
			name="DOC-0001", doctype="DocType", save=lambda **kw: None, insert=lambda **kw: None
		)
		frappe.new_doc = lambda *args, **kwargs: types.SimpleNamespace(
			name="DOC-NEW",
			doctype="DocType",
			append=lambda *a, **k: None,
			save=lambda **kw: None,
			insert=lambda **kw: None,
		)
		frappe.parse_json = json.loads
		frappe.logger = lambda *args, **kwargs: types.SimpleNamespace(
			info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None
		)

		utils.flt = lambda value, precision=None: float(value or 0)
		utils.cint = lambda value: int(float(value or 0))
		utils.now_datetime = lambda: "2026-02-27 00:00:00"
		utils.nowdate = lambda: "2026-02-27"
		utils.add_days = lambda value, days: value
		utils.today = lambda: "2026-02-27"

		sys.modules["frappe"] = frappe
		sys.modules["frappe.utils"] = utils

	frappe_exceptions = types.ModuleType("frappe.exceptions")
	frappe_exceptions.TimestampMismatchError = type("TimestampMismatchError", (Exception,), {})
	sys.modules["frappe.exceptions"] = frappe_exceptions

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.utils" not in sys.modules:
		utils_pkg = types.ModuleType("hrms.utils")
		utils_pkg.__path__ = []
		sys.modules["hrms.utils"] = utils_pkg

	if "hrms.api" not in sys.modules:
		api_pkg = types.ModuleType("hrms.api")
		api_pkg.__path__ = []
		sys.modules["hrms.api"] = api_pkg

	if "hrms.utils.delivery_billing_policy" not in sys.modules:
		policy = types.ModuleType("hrms.utils.delivery_billing_policy")

		class DeliveryBillingPolicyError(Exception):
			pass

		policy.DeliveryBillingPolicyError = DeliveryBillingPolicyError
		policy.get_pre_delivery_exception_trace = lambda *_args, **_kwargs: {}
		policy.should_auto_create_billing_on_delivery = lambda *_args, **_kwargs: True
		sys.modules["hrms.utils.delivery_billing_policy"] = policy

	if "hrms.utils.scm_roles" not in sys.modules:
		scm_roles = types.ModuleType("hrms.utils.scm_roles")
		scm_roles.SCM_ADMIN_ROLES = ["System Manager"]
		scm_roles.SCM_DISPATCH_ROLES = ["Warehouse User", "System Manager"]
		scm_roles.SCM_INVENTORY_ROLES = ["Warehouse User", "System Manager"]
		scm_roles.SCM_ROUTE_MANAGEMENT_ROLES = ["Warehouse User", "System Manager"]
		scm_roles.SCM_STOCK_UPDATE_ROLES = ["Warehouse User", "System Manager"]
		scm_roles.SCM_STORE_ROLES = ["Store User", "Warehouse User"]
		scm_roles.check_scm_permission = lambda *_args, **_kwargs: None
		sys.modules["hrms.utils.scm_roles"] = scm_roles

	if "hrms.utils.bei_config" not in sys.modules:
		bei_config = types.ModuleType("hrms.utils.bei_config")
		bei_config.get_company = lambda: "BEI"
		sys.modules["hrms.utils.bei_config"] = bei_config

	if "hrms.utils.inventory_visibility" not in sys.modules:
		inventory_visibility = types.ModuleType("hrms.utils.inventory_visibility")
		inventory_visibility.FACILITY_MODE_ALL = "all"
		inventory_visibility.FACILITY_MODE_STORES = "stores"
		inventory_visibility.FACILITY_MODE_WAREHOUSES = "warehouses"
		inventory_visibility.get_inventory_facility_catalog = lambda *args, **kwargs: []
		inventory_visibility.get_inventory_scope_context = lambda *args, **kwargs: {}
		inventory_visibility.resolve_inventory_requested_facilities = lambda *args, **kwargs: []
		inventory_visibility.resolve_inventory_requested_warehouses = lambda *args, **kwargs: []
		sys.modules["hrms.utils.inventory_visibility"] = inventory_visibility

	if "hrms.utils.sentry" not in sys.modules:
		sentry_mod = types.ModuleType("hrms.utils.sentry")
		sentry_mod.set_backend_observability_context = lambda *args, **kwargs: None
		sys.modules["hrms.utils.sentry"] = sentry_mod

	if "hrms.utils.supply_chain_contracts" not in sys.modules:
		contracts_spec = importlib.util.spec_from_file_location(
			"hrms.utils.supply_chain_contracts",
			ROOT / "hrms" / "utils" / "supply_chain_contracts.py",
		)
		contracts_mod = importlib.util.module_from_spec(contracts_spec)
		contracts_spec.loader.exec_module(contracts_mod)
		sys.modules["hrms.utils.supply_chain_contracts"] = contracts_mod


def _load_module(module_name: str, relative_path: str):
	spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
	module = importlib.util.module_from_spec(spec)
	sys.modules[module_name] = module
	spec.loader.exec_module(module)
	return module


_install_fake_runtime()
dispatch = _load_module("hrms.api.dispatch", "hrms/api/dispatch.py")
inventory = _load_module("hrms.api.inventory", "hrms/api/inventory.py")


class TestDispatchVehicleContractS07(unittest.TestCase):
	"""Lock contract shape used by trip/warehouse UI flows."""

	@patch.object(dispatch, "_check_scm_permission")
	@patch.object(dispatch.frappe, "get_all")
	def test_get_vehicles_returns_object_and_flat_contract(self, mock_get_all, _mock_perm):
		mock_get_all.return_value = [
			{"name": "VEH-001", "vehicle_plate": "ABC 123"},
			{"name": "VEH-002", "vehicle_plate": "XYZ 789"},
		]

		result = dispatch.get_vehicles()

		self.assertIn("vehicles", result)
		self.assertIn("vehicle_names", result)
		self.assertIn("data", result)
		self.assertEqual(result["vehicle_names"], ["VEH-001", "VEH-002"])
		self.assertEqual(result["data"], ["VEH-001", "VEH-002"])
		self.assertEqual(len(result["vehicles"]), 2)

	def test_inventory_variance_resolution_contract_is_explicit(self):
		result = inventory.get_variance_resolution_contract()
		self.assertTrue(result["success"])
		self.assertEqual(result["action"], "resolve_variance")
		self.assertIn("variance_name", result["required_fields"])
		self.assertIn("resolution_type", result["required_fields"])
		self.assertIn("resolution_notes", result["required_fields"])
		self.assertIn("System Error", result["resolution_types"])

	@patch.object(dispatch, "_check_scm_permission")
	@patch.object(dispatch, "_has_column", return_value=True)
	def test_create_vehicle_normalizes_portal_contract_inputs(self, _mock_has_column, _mock_perm):
		insert_calls = []
		comment_calls = []
		vehicle_doc = types.SimpleNamespace(
			name="BEI-VEH-0009",
			doctype="BEI Vehicle",
			vehicle_plate="ABC 1234",
			vehicle_type="",
			owner_type="",
			threepl_partner="",
			status="",
			notes="",
		)

		def _insert(**kwargs):
			insert_calls.append(kwargs)

		def _add_comment(_comment_type, text=None):
			comment_calls.append(text)

		vehicle_doc.insert = _insert
		vehicle_doc.add_comment = _add_comment

		def _fake_get_value(doctype, filters=None, fieldname=None, as_dict=False):
			if doctype == "BEI Vehicle":
				return None
			if doctype == "Supplier" and filters == "RCS Logistics":
				return None
			if doctype == "Supplier" and filters == {"supplier_name": "RCS Logistics"}:
				return "SUP-RCS"
			return None

		with (
			patch.object(dispatch.frappe.db, "get_value", side_effect=_fake_get_value),
			patch.object(dispatch.frappe, "new_doc", return_value=vehicle_doc),
		):
			result = dispatch.create_vehicle(
				vehicle_plate="ABC 1234",
				vehicle_type="Non-Reefer",
				owner_type="3PL",
				threepl_partner="RCS Logistics",
				notes="Portal onboarding",
			)

		self.assertTrue(result["success"])
		self.assertTrue(result["created"])
		self.assertEqual(vehicle_doc.vehicle_type, "Truck")
		self.assertEqual(vehicle_doc.threepl_partner, "SUP-RCS")
		self.assertEqual(insert_calls, [{"ignore_permissions": True}])
		self.assertTrue(any("Vehicle onboarded by" in str(text) for text in comment_calls))


if __name__ == "__main__":
	unittest.main()
