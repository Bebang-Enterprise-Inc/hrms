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
	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = [str(ROOT / "hrms")]
	sys.modules["hrms"] = hrms_pkg

	utils_pkg = types.ModuleType("hrms.utils")
	utils_pkg.__path__ = [str(ROOT / "hrms" / "utils")]
	sys.modules["hrms.utils"] = utils_pkg

	services_pkg = types.ModuleType("hrms.services")
	services_pkg.__path__ = [str(ROOT / "hrms" / "services")]
	sys.modules["hrms.services"] = services_pkg

	sheets_pkg = types.ModuleType("hrms.services.sheets_receiver")
	sheets_pkg.__path__ = [str(ROOT / "hrms" / "services" / "sheets_receiver")]
	sys.modules["hrms.services.sheets_receiver"] = sheets_pkg

	frappe_client_mod = types.ModuleType("hrms.services.sheets_receiver.frappe_client")
	frappe_client_mod.get_frappe_client = lambda: types.SimpleNamespace(
		call_method=lambda *_args, **_kwargs: {}
	)
	sys.modules["hrms.services.sheets_receiver.frappe_client"] = frappe_client_mod

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
assert notif_spec.loader is not None
notif_spec.loader.exec_module(notifications)


class TestSheetsReceiverNotifications(unittest.TestCase):
	def test_send_sheets_sync_critical_alert_ingests_structured_event_and_logs(self):
		fake_client = types.SimpleNamespace(
			call_method=MagicMock(
				return_value={
					"success": True,
					"sent": True,
					"message_id": "spaces/AAA/messages/123",
					"rendered_text": "Structured alert text",
				}
			)
		)
		fake_db = types.SimpleNamespace(log_notification=MagicMock())

		with (
			patch.object(notifications, "get_frappe_client", return_value=fake_client),
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
				alerts=["MASS EDIT: 12 rows modified"],
				spreadsheet_id="sheet-123",
			)

		self.assertEqual(message_id, "spaces/AAA/messages/123")
		fake_client.call_method.assert_called_once()
		method_name = fake_client.call_method.call_args.args[0]
		payload = fake_client.call_method.call_args.kwargs["data"]["event"]
		self.assertEqual(method_name, "hrms.api.google_chat.ingest_notification_event")
		self.assertEqual(payload["family"], "sheets_sync_critical")
		self.assertEqual(payload["facts"]["spreadsheet_id"], "sheet-123")
		self.assertEqual(payload["facts"]["rows_failed"], 3)
		fake_db.log_notification.assert_called_once()

	def test_send_sheets_sync_critical_alert_skips_empty_payload(self):
		with patch.object(notifications, "get_frappe_client") as get_frappe_client:
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
		get_frappe_client.assert_not_called()

	def test_send_sheets_sync_critical_alert_handles_ingest_error(self):
		with patch.object(notifications, "get_frappe_client", side_effect=RuntimeError("frappe down")):
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

	def test_send_sheets_sync_critical_alert_dedupes_errors_alerts_and_reasons(self):
		fake_client = types.SimpleNamespace(
			call_method=MagicMock(return_value={"success": True, "sent": False})
		)

		with patch.object(notifications, "get_frappe_client", return_value=fake_client):
			notifications.send_sheets_sync_critical_alert(
				spreadsheet_name="AR Aging",
				sheet_name="AR",
				trigger="scheduled",
				reasons=["rows_failed", "rows_failed", "sync_errors_reported"],
				rows_processed=1674,
				rows_failed=1674,
				errors=[
					"Missing invoice_no in AR invoice row",
					"Missing invoice_no in AR invoice row",
					"Missing invoice_no in AR invoice row",
				],
				alerts=[
					"⚠️ MASS EDIT: 1502 rows modified",
					"⚠️ MASS EDIT: 1502 rows modified",
					"⚠️ UNUSUAL PATTERN: More modifications than additions",
				],
			)

		payload = fake_client.call_method.call_args.kwargs["data"]["event"]
		self.assertEqual(payload["facts"]["reasons"], ["rows_failed", "sync_errors_reported"])
		self.assertEqual(payload["facts"]["errors"], ["Missing invoice_no in AR invoice row"])
		self.assertEqual(
			payload["facts"]["alerts"],
			[
				"⚠️ MASS EDIT: 1502 rows modified",
				"⚠️ UNUSUAL PATTERN: More modifications than additions",
			],
		)


if __name__ == "__main__":
	unittest.main()
