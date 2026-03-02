import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_runtime():
	class _FrappeModule(types.ModuleType):
		def __getattr__(self, name):
			if name == "db":
				return self.local.db
			if name == "session":
				return self.local.session
			raise AttributeError(name)

	frappe = _FrappeModule("frappe")
	frappe_utils = types.ModuleType("frappe.utils")

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

	frappe.whitelist = whitelist
	frappe.throw = throw
	frappe._ = lambda text: text
	frappe.PermissionError = type("PermissionError", (Exception,), {})
	frappe.log_error = lambda *args, **kwargs: None
	frappe.get_traceback = lambda: "traceback"
	frappe.enqueue = lambda *args, **kwargs: None
	frappe.get_roles = lambda *args, **kwargs: ["HR User", "System Manager"]
	frappe.parse_json = lambda value: __import__("json").loads(value)
	frappe.local = types.SimpleNamespace(
		session=types.SimpleNamespace(user="test.supervisor@bebang.ph"),
		db=types.SimpleNamespace(
			get_value=lambda *args, **kwargs: None,
			exists=lambda *args, **kwargs: None,
			count=lambda *args, **kwargs: 0,
			sql=lambda *args, **kwargs: [],
			set_value=lambda *args, **kwargs: None,
		),
	)
	frappe.get_all = lambda *args, **kwargs: []

	frappe_utils.today = lambda: "2026-02-28"
	frappe_utils.nowdate = lambda: "2026-02-28"
	frappe_utils.now = lambda: "2026-02-28 10:00:00"
	frappe_utils.now_datetime = lambda: datetime.datetime(2026, 2, 28, 10, 0, 0)
	frappe_utils.get_datetime = lambda value=None: datetime.datetime(2026, 2, 28, 10, 0, 0)
	frappe_utils.getdate = lambda value=None: value or "2026-02-28"
	frappe_utils.add_days = lambda date_value, days: date_value
	frappe_utils.flt = lambda value, precision=None: float(value or 0)
	frappe_utils.cint = lambda value: int(float(value or 0))

	frappe.utils = frappe_utils
	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = frappe_utils

	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = []
	sys.modules["hrms"] = hrms_pkg

	hrms_api_pkg = types.ModuleType("hrms.api")
	hrms_api_pkg.__path__ = []
	sys.modules["hrms.api"] = hrms_api_pkg

	hrms_utils_pkg = types.ModuleType("hrms.utils")
	hrms_utils_pkg.__path__ = []
	sys.modules["hrms.utils"] = hrms_utils_pkg

	bei_config_mod = types.ModuleType("hrms.utils.bei_config")
	bei_config_mod.get_company = lambda: "BEI"
	sys.modules["hrms.utils.bei_config"] = bei_config_mod

	scm_roles_mod = types.ModuleType("hrms.utils.scm_roles")
	scm_roles_mod.check_scm_permission = lambda *args, **kwargs: None
	scm_roles_mod.SCM_APPROVAL_ROLES = ["Area Supervisor", "System Manager"]
	sys.modules["hrms.utils.scm_roles"] = scm_roles_mod


def _load_module(name: str, relative_path: str):
	spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class _FakeOrderDoc:
	def __init__(self, name="SO-0001"):
		self.name = name
		self.items = []
		self.status = "Draft"

	def append(self, table, row):
		if table == "items":
			self.items.append(row)

	def insert(self, **kwargs):
		return self


_install_fake_runtime()
enrichment = _load_module("enrichment_under_test", "hrms/api/enrichment.py")
sys.modules["hrms.api.enrichment"] = enrichment
tasks = _load_module("tasks_under_test", "hrms/tasks.py")
store = _load_module("store_under_test", "hrms/api/store.py")


class TestEnrichmentReminderQueueFallbackS09(unittest.TestCase):
	def test_queue_enrichment_reminders_falls_back_to_sync_when_enqueue_fails(self):
		with (
			patch.object(enrichment.frappe, "enqueue", side_effect=RuntimeError("queue down")),
			patch.object(
				enrichment,
				"send_enrichment_reminders",
				return_value={"status": "success", "sent_count": 3, "failed_count": 0},
			),
		):
			result = enrichment.queue_enrichment_reminders(method="email")

		self.assertEqual(result["mode"], "sync_fallback")
		self.assertEqual(result["status"], "queued_fallback")
		self.assertEqual(result["sent_count"], 3)

	def test_tasks_wrapper_runs_enrichment_queue(self):
		with patch(
			"hrms.api.enrichment.queue_enrichment_reminders",
			return_value={"status": "queued", "mode": "async"},
		):
			result = tasks.run_enrichment_reminder_queue()
		self.assertEqual(result["status"], "queued")

	def test_submit_order_requires_valid_area_supervisor_mapping_for_edited_lines(self):
		store.frappe.local.session = types.SimpleNamespace(user="test.supervisor@bebang.ph")
		store.frappe.new_doc = (
			lambda doctype: _FakeOrderDoc() if doctype == "BEI Store Order" else _FakeOrderDoc("APQ-0001")
		)

		with (
			patch.object(store, "_validate_order_cutoff", return_value=None),
			patch.object(store, "resolve_warehouse", return_value="AYALA EVO - BEI"),
			patch.object(store, "_notify_store_ops", return_value=None),
			patch.object(store, "_get_area_supervisor_for_store", return_value=None),
			patch.object(store.frappe.db, "exists", return_value=None),
		):
			with self.assertRaises(Exception) as ctx:
				store.submit_order(
					store="AYALA EVO",
					items=[{"item_code": "ITM-001", "qty_requested": 2}],
					cargo_category="DRY",
				)

		self.assertIn("requires Area Supervisor approval", str(ctx.exception))


if __name__ == "__main__":
	unittest.main()
