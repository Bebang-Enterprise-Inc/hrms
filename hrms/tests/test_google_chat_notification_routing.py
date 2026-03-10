import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
	frappe_mod = types.ModuleType("frappe")
	frappe_mod.logger = lambda _name=None: types.SimpleNamespace(
		info=lambda *_args, **_kwargs: None,
		warning=lambda *_args, **_kwargs: None,
		error=lambda *_args, **_kwargs: None,
	)
	frappe_mod.log_error = lambda *args, **kwargs: None
	frappe_mod.whitelist = lambda *args, **kwargs: (lambda fn: fn)
	frappe_mod.session = types.SimpleNamespace(user="sam@bebang.ph")
	sys.modules["frappe"] = frappe_mod


def _install_fake_hrms_package():
	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = [str(ROOT / "hrms")]
	sys.modules["hrms"] = hrms_pkg

	utils_pkg = types.ModuleType("hrms.utils")
	utils_pkg.__path__ = [str(ROOT / "hrms" / "utils")]
	sys.modules["hrms.utils"] = utils_pkg

	api_pkg = types.ModuleType("hrms.api")
	api_pkg.__path__ = [str(ROOT / "hrms" / "api")]
	sys.modules["hrms.api"] = api_pkg


def _install_fake_google_oauth():
	google_oauth_mod = types.ModuleType("hrms.utils.google_oauth")
	google_oauth_mod.force_refresh_access_token = lambda _user: "token"
	google_oauth_mod.get_valid_access_token = lambda _user: "token"
	google_oauth_mod.has_valid_token = lambda _user: True
	sys.modules["hrms.utils.google_oauth"] = google_oauth_mod


def _install_fake_bei_config():
	bei_config_mod = types.ModuleType("hrms.utils.bei_config")
	bei_config_mod.get_service_account_path = lambda: "credentials/task-manager-service.json"
	sys.modules["hrms.utils.bei_config"] = bei_config_mod


def _install_fake_google_modules(fake_chat):
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
	discovery_mod.build = lambda *_args, **_kwargs: fake_chat
	sys.modules["googleapiclient.discovery"] = discovery_mod


class _FakeMessagesAPI:
	def __init__(self):
		self.last_parent = None
		self.last_body = None

	def create(self, parent, body):
		self.last_parent = parent
		self.last_body = body
		return types.SimpleNamespace(execute=lambda: {"name": "spaces/AAQABiNmpBg/messages/123"})


class _FakeChatAPI:
	def __init__(self):
		self.messages_api = _FakeMessagesAPI()

	def spaces(self):
		return types.SimpleNamespace(messages=lambda: self.messages_api)


class TestGoogleChatNotificationRouting(unittest.TestCase):
	def _load_module(self):
		module_name = "hrms.api.google_chat_routing_under_test"
		if module_name in sys.modules:
			del sys.modules[module_name]
		spec = importlib.util.spec_from_file_location(
			module_name,
			ROOT / "hrms" / "api" / "google_chat.py",
		)
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
		return module

	def test_send_message_to_space_reroutes_to_blip_notifications_by_default(self):
		fake_chat = _FakeChatAPI()
		_install_fake_frappe()
		_install_fake_hrms_package()
		_install_fake_google_oauth()
		_install_fake_bei_config()
		_install_fake_google_modules(fake_chat)
		module = self._load_module()

		with patch.object(module.os.path, "exists", return_value=True), patch.dict(
			os.environ, {}, clear=False
		):
			self.assertTrue(module.send_message_to_space("spaces/AAAAvDZdY-o", "hello"))

		self.assertEqual(fake_chat.messages_api.last_parent, "spaces/AAQABiNmpBg")
		self.assertEqual(fake_chat.messages_api.last_body, {"text": "hello"})

	def test_send_message_to_space_allows_explicit_override(self):
		fake_chat = _FakeChatAPI()
		_install_fake_frappe()
		_install_fake_hrms_package()
		_install_fake_google_oauth()
		_install_fake_bei_config()
		_install_fake_google_modules(fake_chat)
		module = self._load_module()

		with patch.object(module.os.path, "exists", return_value=True), patch.dict(
			os.environ,
			{
				"BEI_ALLOW_NON_BLIP_CHAT_DESTINATIONS": "true",
				"BEI_ALLOWED_CHAT_SPACES": "spaces/AAAAvDZdY-o",
			},
			clear=False,
		):
			self.assertTrue(module.send_message_to_space("spaces/AAAAvDZdY-o", "hello"))

		self.assertEqual(fake_chat.messages_api.last_parent, "spaces/AAAAvDZdY-o")


if __name__ == "__main__":
	unittest.main()
