import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _load_module(fake_app_path: str):
	frappe = types.ModuleType("frappe")
	frappe.get_app_path = lambda _app_name: fake_app_path
	frappe.defaults = types.SimpleNamespace(get_global_default=lambda _key: None)
	sys.modules["frappe"] = frappe
	sys.modules.pop("bei_config_under_test", None)
	spec = importlib.util.spec_from_file_location(
		"bei_config_under_test",
		ROOT / "hrms" / "utils" / "bei_config.py",
	)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	sys.modules["bei_config_under_test"] = module
	spec.loader.exec_module(module)
	return module


class TestBeiConfig(unittest.TestCase):
	def test_service_account_path_prefers_env_var(self):
		with tempfile.TemporaryDirectory() as tmp_dir:
			cred_path = Path(tmp_dir) / "task-manager-service.json"
			cred_path.write_text("{}", encoding="utf-8")
			module = _load_module("/home/frappe/frappe-bench/apps/hrms/hrms")
			original = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
			try:
				os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"] = str(cred_path)
				self.assertEqual(module.get_service_account_path(), str(cred_path))
			finally:
				if original is None:
					os.environ.pop("GOOGLE_SERVICE_ACCOUNT_FILE", None)
				else:
					os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"] = original

	def test_service_account_path_anchors_to_bench_root(self):
		module = _load_module("/home/frappe/frappe-bench/apps/hrms/hrms")
		resolved = module.get_service_account_path().replace("\\", "/")
		self.assertTrue(resolved.endswith("/home/frappe/frappe-bench/credentials/task-manager-service.json"))


if __name__ == "__main__":
	unittest.main()
