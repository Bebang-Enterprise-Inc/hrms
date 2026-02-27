import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_google_modules():
	if "google" not in sys.modules:
		sys.modules["google"] = types.ModuleType("google")

	if "google.oauth2" not in sys.modules:
		sys.modules["google.oauth2"] = types.ModuleType("google.oauth2")

	if "google.oauth2.service_account" not in sys.modules:
		service_account_mod = types.ModuleType("google.oauth2.service_account")

		class _Credentials:
			@staticmethod
			def from_service_account_file(_path, scopes=None):
				return types.SimpleNamespace(scopes=scopes or [])

		service_account_mod.Credentials = _Credentials
		sys.modules["google.oauth2.service_account"] = service_account_mod

	if "googleapiclient" not in sys.modules:
		sys.modules["googleapiclient"] = types.ModuleType("googleapiclient")

	if "googleapiclient.discovery" not in sys.modules:
		discovery_mod = types.ModuleType("googleapiclient.discovery")
		discovery_mod.build = lambda *_args, **_kwargs: types.SimpleNamespace()
		sys.modules["googleapiclient.discovery"] = discovery_mod


def _install_fake_package_path():
	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.services" not in sys.modules:
		services_pkg = types.ModuleType("hrms.services")
		services_pkg.__path__ = []
		sys.modules["hrms.services"] = services_pkg

	if "hrms.services.sheets_receiver" not in sys.modules:
		sheets_pkg = types.ModuleType("hrms.services.sheets_receiver")
		sheets_pkg.__path__ = []
		sys.modules["hrms.services.sheets_receiver"] = sheets_pkg

	if "hrms.services.sheets_receiver.models" not in sys.modules:
		models_mod = types.ModuleType("hrms.services.sheets_receiver.models")
		models_mod.get_db = lambda: types.SimpleNamespace(log_notification=lambda **_kwargs: None)
		sys.modules["hrms.services.sheets_receiver.models"] = models_mod


_install_fake_google_modules()
_install_fake_package_path()
notif_spec = importlib.util.spec_from_file_location(
	"hrms.services.sheets_receiver.notifications_under_test",
	ROOT / "hrms" / "services" / "sheets_receiver" / "notifications.py",
)
notifications = importlib.util.module_from_spec(notif_spec)
notif_spec.loader.exec_module(notifications)


class _FakeMessagesAPI:
	def __init__(self):
		self.last_parent = None
		self.last_body = None

	def create(self, parent, body):
		self.last_parent = parent
		self.last_body = body
		return types.SimpleNamespace(execute=lambda: {"name": "spaces/AAA/messages/123"})


class _FakeChatAPI:
	def __init__(self):
		self.messages_api = _FakeMessagesAPI()

	def spaces(self):
		return types.SimpleNamespace(messages=lambda: self.messages_api)


class TestSheetsReceiverNotifications(unittest.TestCase):
	def test_send_sheets_sync_critical_alert_sends_message_and_logs(self):
		fake_chat = _FakeChatAPI()
		fake_db = types.SimpleNamespace(log_notification=MagicMock())

		with (
			patch.object(notifications, "get_chat_service", return_value=fake_chat),
			patch.object(notifications, "get_db", return_value=fake_db),
		):
			message_id = notifications.send_sheets_sync_critical_alert(
				spreadsheet_name="AR Aging",
				sheet_name="AR",
				trigger="webhook",
				reasons=["rows_failed", "suspicious_change_alert"],
				rows_processed=120,
				rows_failed=3,
				errors=["missing supplier", "invalid amount"],
				alerts=["⚠️ MASS EDIT: 12 rows modified"],
			)

		self.assertEqual(message_id, "spaces/AAA/messages/123")
		self.assertEqual(fake_chat.messages_api.last_parent, notifications.OPS_SPACE)
		text = fake_chat.messages_api.last_body.get("text", "")
		self.assertIn("SHEETS SYNC CRITICAL ALERT", text)
		self.assertIn("AR Aging / AR", text)
		self.assertIn("processed=120, failed=3", text)
		self.assertIn("MASS EDIT", text)
		fake_db.log_notification.assert_called_once()

	def test_send_sheets_sync_critical_alert_skips_empty_payload(self):
		with patch.object(notifications, "get_chat_service") as get_chat_service:
			result = notifications.send_sheets_sync_critical_alert(
				spreadsheet_name="AR Aging",
				sheet_name="AR",
				trigger="manual",
				reasons=[],
				rows_processed=0,
				rows_failed=0,
				errors=[],
				alerts=[],
			)

		self.assertIsNone(result)
		get_chat_service.assert_not_called()

	def test_send_sheets_sync_critical_alert_handles_chat_error(self):
		with patch.object(notifications, "get_chat_service", side_effect=RuntimeError("chat down")):
			result = notifications.send_sheets_sync_critical_alert(
				spreadsheet_name="AR Aging",
				sheet_name="AR",
				trigger="scheduled",
				reasons=["sync_exception"],
				rows_processed=0,
				rows_failed=1,
				errors=["timeout"],
				alerts=[],
			)

		self.assertIsNone(result)


if __name__ == "__main__":
	unittest.main()
