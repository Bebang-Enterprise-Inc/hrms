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
	class _FrappeModule(types.ModuleType):
		def __getattr__(self, name):
			if name == "defaults":
				return self.local.defaults
			if name == "session":
				return self.local.session
			raise AttributeError(name)

	frappe = _FrappeModule("frappe")

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

	class _Defaults:
		def __init__(self):
			self.value = None

		def get_user_default(self, key):
			return self.value

		def set_user_default(self, key, value):
			self.value = value

	frappe.whitelist = whitelist
	frappe.throw = throw
	frappe._ = lambda text: text
	frappe.PermissionError = type("PermissionError", (Exception,), {})
	frappe.get_roles = lambda *args, **kwargs: ["HR Manager"]
	frappe.local = types.SimpleNamespace(
		defaults=_Defaults(),
		session=types.SimpleNamespace(user="test.hr@bebang.ph"),
	)

	sys.modules["frappe"] = frappe


def _load_module(name: str, relative_path: str):
	spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


_install_fake_runtime()
workspace_views = _load_module("workspace_views_under_test", "hrms/api/workspace_views.py")


class TestWorkspaceViews(unittest.TestCase):
	def test_save_and_get_workspace_views(self):
		result = workspace_views.save_workspace_view(
			scope="attendance-review",
			name="Pending Today",
			filters={"status": "pending", "date_from": "2026-03-17"},
		)

		self.assertTrue(result["success"])
		views = workspace_views.get_workspace_views("attendance-review")["views"]
		self.assertEqual(len(views), 1)
		self.assertEqual(views[0]["name"], "Pending Today")
		self.assertEqual(views[0]["filters"]["status"], "pending")

	def test_delete_workspace_view(self):
		workspace_views.save_workspace_view(
			scope="coverage-review",
			name="Open Today",
			filters=json.dumps({"status": "open"}),
		)

		result = workspace_views.delete_workspace_view("coverage-review", "Open Today")

		self.assertTrue(result["success"])
		self.assertEqual(result["views"], [])

	def test_rejects_unauthorized_access(self):
		with patch.object(workspace_views.frappe, "get_roles", return_value=["Employee"]):
			with self.assertRaises(workspace_views.frappe.PermissionError):
				workspace_views.get_workspace_views("attendance-review")


if __name__ == "__main__":
	unittest.main()
