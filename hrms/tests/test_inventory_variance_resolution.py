# Copyright (c) 2026, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

"""Regression coverage for inventory variance resolution."""

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_runtime():
	if "frappe" not in sys.modules:
		frappe = types.ModuleType("frappe")
		utils = types.ModuleType("frappe.utils")

		class PermissionError(Exception):
			pass

		class ValidationError(Exception):
			pass

		def whitelist(*args, **kwargs):
			if args and callable(args[0]) and len(args) == 1 and not kwargs:
				return args[0]

			def decorator(fn):
				return fn

			return decorator

		frappe.PermissionError = PermissionError
		frappe.ValidationError = ValidationError
		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.throw = lambda message, exc=None: (_ for _ in ()).throw((exc or Exception)(message))
		frappe.log_error = lambda *args, **kwargs: None
		frappe.get_traceback = lambda: "traceback"
		frappe.get_roles = lambda *_args, **_kwargs: ["Store Supervisor"]
		frappe.session = types.SimpleNamespace(user="test.supervisor@bebang.ph")
		frappe.set_user = lambda user: setattr(frappe.session, "user", user)
		frappe.db = types.SimpleNamespace(
			savepoint=lambda *_args, **_kwargs: None,
			rollback=lambda *_args, **_kwargs: None,
			get_value=lambda doctype, name, field: "Nos",
		)
		frappe.parse_json = json.loads
		frappe.logger = lambda *args, **kwargs: types.SimpleNamespace(
			info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None
		)

		utils.flt = lambda value, precision=None: float(value or 0)
		utils.cint = lambda value: int(float(value or 0))
		utils.now_datetime = lambda: "2026-03-10 00:00:00"
		utils.nowdate = lambda: "2026-03-10"
		utils.add_days = lambda value, days: value
		utils.today = lambda: "2026-03-10"

		sys.modules["frappe"] = frappe
		sys.modules["frappe.utils"] = utils

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

	if "hrms.utils.scm_roles" not in sys.modules:
		scm_roles = types.ModuleType("hrms.utils.scm_roles")
		scm_roles.SCM_INVENTORY_ROLES = ["Warehouse User", "System Manager"]
		scm_roles.SCM_STOCK_UPDATE_ROLES = ["Warehouse User", "System Manager"]
		scm_roles.check_scm_permission = lambda *_args, **_kwargs: None
		sys.modules["hrms.utils.scm_roles"] = scm_roles

	if "hrms.utils.bei_config" not in sys.modules:
		bei_config = types.ModuleType("hrms.utils.bei_config")
		bei_config.get_company = lambda: "Bebang Enterprise Inc."
		sys.modules["hrms.utils.bei_config"] = bei_config


def _load_module(module_name: str, relative_path: str):
	spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
	module = importlib.util.module_from_spec(spec)
	sys.modules[module_name] = module
	spec.loader.exec_module(module)
	return module


_install_fake_runtime()
inventory = _load_module("hrms.api.inventory", "hrms/api/inventory.py")


class _FakeVarianceDoc:
	def __init__(self):
		self.status = "Investigating"
		self.item_code = "FG020"
		self.store = "TEST-COMMISSARY - BEI"
		self.actual_qty = 5
		self.system_qty = 3
		self.variance_qty = 2
		self.resolution = None
		self.saved_ignore_permissions = False

	def save(self, ignore_permissions=False):
		self.saved_ignore_permissions = bool(ignore_permissions)


class _FakeStockReconciliation:
	def __init__(self, frappe_module):
		self._frappe = frappe_module
		self.company = None
		self.posting_date = None
		self.purpose = None
		self.remarks = None
		self.items = []
		self.flags = types.SimpleNamespace(ignore_permissions=False)
		self.name = "MAT-RECO-UNIT-0001"
		self.insert_user = None
		self.submit_user = None

	def append(self, fieldname, payload):
		if fieldname == "items":
			self.items.append(payload)

	def insert(self, ignore_permissions=False):
		if self._frappe.session.user != "Administrator":
			raise self._frappe.PermissionError("expected elevated insert user")
		self.insert_user = self._frappe.session.user
		self.flags.ignore_permissions = bool(ignore_permissions)

	def submit(self):
		if self._frappe.session.user != "Administrator":
			raise self._frappe.PermissionError("expected elevated submit user")
		self.submit_user = self._frappe.session.user


class TestInventoryVarianceResolution(unittest.TestCase):
	def test_recount_corrected_elevates_stock_reconciliation_and_restores_user(self):
		variance_doc = _FakeVarianceDoc()
		stock_reconciliation = _FakeStockReconciliation(inventory.frappe)

		inventory.frappe.get_roles = lambda *_args, **_kwargs: ["Store Supervisor"]
		inventory.frappe.set_user = lambda user: setattr(inventory.frappe.session, "user", user)
		inventory.frappe.get_traceback = lambda: "traceback"
		inventory.frappe.session.user = "test.supervisor@bebang.ph"
		inventory.frappe.get_doc = lambda doctype, name: variance_doc
		inventory.frappe.new_doc = lambda doctype: stock_reconciliation

		result = inventory.resolve_variance(
			"BEI-VAR-UNIT-0001",
			"Recount Corrected",
			"Supervisor recount corrected stock to physical count",
			adjustment_qty=2,
		)

		self.assertTrue(result["success"])
		self.assertEqual(result["status"], "Resolved")
		self.assertEqual(result["stock_entry"], "MAT-RECO-UNIT-0001")
		self.assertEqual(stock_reconciliation.insert_user, "Administrator")
		self.assertEqual(stock_reconciliation.submit_user, "Administrator")
		self.assertEqual(inventory.frappe.session.user, "test.supervisor@bebang.ph")
		self.assertTrue(variance_doc.saved_ignore_permissions)
		self.assertEqual(
			variance_doc.resolution,
			"[Recount Corrected] Supervisor recount corrected stock to physical count",
		)


if __name__ == "__main__":
	unittest.main()
