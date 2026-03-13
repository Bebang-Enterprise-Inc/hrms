import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_google_modules():
	if "google" not in sys.modules:
		sys.modules["google"] = types.ModuleType("google")

	if "google.oauth2" not in sys.modules:
		sys.modules["google.oauth2"] = types.ModuleType("google.oauth2")

	service_account_mod = types.ModuleType("google.oauth2.service_account")

	class _Credentials:
		@staticmethod
		def from_service_account_file(_path, scopes=None):
			return types.SimpleNamespace(scopes=scopes or [])

	service_account_mod.Credentials = _Credentials
	sys.modules["google.oauth2.service_account"] = service_account_mod

	discovery_mod = types.ModuleType("googleapiclient.discovery")
	discovery_mod.build = lambda *_args, **_kwargs: types.SimpleNamespace()
	sys.modules["googleapiclient.discovery"] = discovery_mod


def _install_fake_package_path_without_utils():
	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = [str(ROOT / "hrms")]
	sys.modules["hrms"] = hrms_pkg

	services_pkg = types.ModuleType("hrms.services")
	services_pkg.__path__ = [str(ROOT / "hrms" / "services")]
	sys.modules["hrms.services"] = services_pkg

	sheets_pkg = types.ModuleType("hrms.services.sheets_receiver")
	sheets_pkg.__path__ = [str(ROOT / "hrms" / "services" / "sheets_receiver")]
	sys.modules["hrms.services.sheets_receiver"] = sheets_pkg

	models_mod = types.ModuleType("hrms.services.sheets_receiver.models")
	models_mod.get_db = lambda: types.SimpleNamespace(log_notification=lambda **_kwargs: None)
	sys.modules["hrms.services.sheets_receiver.models"] = models_mod

	sys.modules.pop("hrms.utils", None)
	sys.modules.pop("hrms.utils.chat_space_lockdown", None)


class TestSheetsReceiverNotificationsStandalone(unittest.TestCase):
	def test_notifications_module_imports_without_hrms_utils(self):
		_install_fake_google_modules()
		_install_fake_package_path_without_utils()

		spec = importlib.util.spec_from_file_location(
			"hrms.services.sheets_receiver.notifications_standalone_under_test",
			ROOT / "hrms" / "services" / "sheets_receiver" / "notifications.py",
		)
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)

		self.assertEqual(module._get_target_space(), "spaces/AAQABiNmpBg")

	def test_standalone_fallback_honors_strict_blip_only_default(self):
		_install_fake_google_modules()
		_install_fake_package_path_without_utils()

		spec = importlib.util.spec_from_file_location(
			"hrms.services.sheets_receiver.notifications_standalone_under_test_strict",
			ROOT / "hrms" / "services" / "sheets_receiver" / "notifications.py",
		)
		module = importlib.util.module_from_spec(spec)

		original_env = dict(os.environ)
		try:
			os.environ.pop("BEI_CHAT_STRICT_BLIP_ONLY", None)
			os.environ["BEI_ALLOW_NON_BLIP_CHAT_DESTINATIONS"] = "true"
			os.environ["BEI_ALLOWED_CHAT_SPACES"] = "spaces/AAQA3NVVR6c"
			spec.loader.exec_module(module)
			self.assertEqual(
				module.route_outbound_chat_space("spaces/AAQA3NVVR6c"),
				"spaces/AAQABiNmpBg",
			)
		finally:
			os.environ.clear()
			os.environ.update(original_env)

	def test_standalone_fallback_can_disable_strict_mode_explicitly(self):
		_install_fake_google_modules()
		_install_fake_package_path_without_utils()

		spec = importlib.util.spec_from_file_location(
			"hrms.services.sheets_receiver.notifications_standalone_under_test_unlocked",
			ROOT / "hrms" / "services" / "sheets_receiver" / "notifications.py",
		)
		module = importlib.util.module_from_spec(spec)

		original_env = dict(os.environ)
		try:
			os.environ["BEI_CHAT_STRICT_BLIP_ONLY"] = "false"
			os.environ["BEI_ALLOW_NON_BLIP_CHAT_DESTINATIONS"] = "true"
			os.environ["BEI_ALLOWED_CHAT_SPACES"] = "spaces/AAQA3NVVR6c"
			spec.loader.exec_module(module)
			self.assertEqual(
				module.route_outbound_chat_space("spaces/AAQA3NVVR6c"),
				"spaces/AAQA3NVVR6c",
			)
		finally:
			os.environ.clear()
			os.environ.update(original_env)


if __name__ == "__main__":
	unittest.main()
