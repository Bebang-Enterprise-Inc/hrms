import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_runtime():
	frappe = types.ModuleType("frappe")
	frappe_utils = types.ModuleType("frappe.utils")
	frappe_rate_limiter = types.ModuleType("frappe.rate_limiter")
	frappe_query_builder = types.ModuleType("frappe.query_builder")

	def whitelist(*args, **kwargs):
		if args and callable(args[0]) and len(args) == 1 and not kwargs:
			return args[0]

		def decorator(fn):
			return fn

		return decorator

	def throw(message, exc=None, **kwargs):
		if isinstance(exc, type) and issubclass(exc, Exception):
			raise exc(message)
		raise Exception(message)

	def rate_limit(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	frappe.whitelist = whitelist
	frappe.throw = throw
	frappe._ = lambda text: text
	frappe.PermissionError = type("PermissionError", (Exception,), {})
	frappe.ValidationError = type("ValidationError", (Exception,), {})
	frappe.log_error = lambda *args, **kwargs: None
	frappe.get_traceback = lambda: "traceback"
	frappe.get_roles = lambda *args, **kwargs: ["System Manager"]
	frappe.get_doc = lambda *args, **kwargs: None
	frappe.new_doc = lambda *args, **kwargs: None
	frappe.db = types.SimpleNamespace(
		get_value=lambda *args, **kwargs: None,
		exists=lambda *args, **kwargs: None,
		sql=lambda *args, **kwargs: [],
	)
	frappe.session = types.SimpleNamespace(user="test.staff@bebang.ph")

	frappe_utils.now_datetime = lambda: datetime.datetime(2026, 2, 28, 9, 0, 0)
	frappe_utils.nowdate = lambda: "2026-02-28"
	frappe_utils.flt = lambda value, precision=None: float(value or 0)
	frappe_utils.cint = lambda value: int(float(value or 0))

	frappe_rate_limiter.rate_limit = rate_limit
	frappe_query_builder.DocType = lambda value: value

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = frappe_utils
	sys.modules["frappe.rate_limiter"] = frappe_rate_limiter
	sys.modules["frappe.query_builder"] = frappe_query_builder

	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = []
	sys.modules["hrms"] = hrms_pkg

	hrms_utils_pkg = types.ModuleType("hrms.utils")
	hrms_utils_pkg.__path__ = []
	sys.modules["hrms.utils"] = hrms_utils_pkg

	aws_location_mod = types.ModuleType("hrms.utils.aws_location")
	aws_location_mod.AWSLocationService = object
	sys.modules["hrms.utils.aws_location"] = aws_location_mod

	geo_mod = types.ModuleType("hrms.utils.geo")
	geo_mod.calculate_haversine_distance = lambda *args, **kwargs: 0.0
	sys.modules["hrms.utils.geo"] = geo_mod


def _load_module(name: str, relative_path: str):
	spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


_install_fake_runtime()
official_business = _load_module("official_business_under_test", "hrms/api/official_business.py")
coverage = _load_module("coverage_under_test", "hrms/api/coverage.py")


class _FakeDoc:
	def __init__(self, **kwargs):
		self.__dict__.update(kwargs)
		self.saved_kwargs = None

	def save(self, **kwargs):
		self.saved_kwargs = kwargs
		return self


class TestHrSelfServiceOpenFirstS09(unittest.TestCase):
	def test_cancel_ob_marks_out_record_as_cancelled(self):
		ob_doc = _FakeDoc(employee="EMP-001", status="Out")

		with patch.object(official_business, "_get_employee_or_throw", return_value="EMP-001"), patch.object(
			official_business.frappe, "get_doc", return_value=ob_doc
		):
			result = official_business.cancel_ob("OB-0001")

		self.assertEqual(result["status"], "success")
		self.assertEqual(ob_doc.status, "Cancelled")
		self.assertEqual(ob_doc.saved_kwargs, {"ignore_permissions": True})

	def test_approve_coverage_assigns_only_pending_records(self):
		request_doc = _FakeDoc(status="Pending")
		coverage.frappe.session = types.SimpleNamespace(user="test.supervisor@bebang.ph")

		with patch.object(coverage.frappe, "get_roles", return_value=["Store Supervisor"]), patch.object(
			coverage, "resolve_employee", return_value="EMP-777"
		), patch.object(coverage.frappe, "get_doc", return_value=request_doc):
			result = coverage.approve_coverage("COV-0001", "John Doe")

		self.assertTrue(result["success"])
		self.assertEqual(result["assigned_employee"], "EMP-777")
		self.assertEqual(request_doc.status, "Assigned")
		self.assertEqual(request_doc.assigned_employee, "EMP-777")
		self.assertEqual(request_doc.assigned_by, "test.supervisor@bebang.ph")
		self.assertEqual(request_doc.saved_kwargs, {"ignore_permissions": True})

	def test_approve_coverage_rejects_non_pending_records(self):
		request_doc = _FakeDoc(status="Assigned")
		coverage.frappe.session = types.SimpleNamespace(user="test.supervisor@bebang.ph")

		with patch.object(coverage.frappe, "get_roles", return_value=["Store Supervisor"]), patch.object(
			coverage.frappe, "get_doc", return_value=request_doc
		):
			with self.assertRaises(Exception):
				coverage.approve_coverage("COV-0002", "EMP-123")


if __name__ == "__main__":
	unittest.main()
