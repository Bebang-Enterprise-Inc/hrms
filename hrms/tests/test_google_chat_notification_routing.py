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


class _FakeCache:
    def __init__(self):
        self.values = {}

    def get_value(self, key):
        return self.values.get(key)

    def set_value(self, key, value, expires_in_sec=None):
        self.values[key] = value


class _FakeMessagesAPI:
    def __init__(self):
        self.last_parent = None
        self.last_body = None
        self.call_count = 0

    def create(self, parent, body):
        self.last_parent = parent
        self.last_body = body
        self.call_count += 1
        return types.SimpleNamespace(execute=lambda: {"name": f"{parent}/messages/{self.call_count}"})


class _FakeChatAPI:
    def __init__(self):
        self.messages_api = _FakeMessagesAPI()

    def spaces(self):
        return types.SimpleNamespace(messages=lambda: self.messages_api)


def _install_fake_frappe():
    frappe_mod = types.ModuleType("frappe")
    cache = _FakeCache()

    def whitelist(*args, **kwargs):
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        def decorator(fn):
            return fn

        return decorator

    frappe_mod.logger = lambda _name=None: types.SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    frappe_mod.log_error = lambda *args, **kwargs: None
    frappe_mod.whitelist = whitelist
    frappe_mod.session = types.SimpleNamespace(user="sam@bebang.ph")
    frappe_mod.conf = {}
    frappe_mod.cache = lambda: cache
    frappe_mod.AuthenticationError = RuntimeError
    frappe_mod.get_site_path = lambda *parts: str(ROOT.joinpath(*parts))
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


class TestGoogleChatNotificationRouting(unittest.TestCase):
    def _load_module(self):
        module_name = "hrms.api.google_chat_routing_under_test"
        for key in [module_name, "hrms.utils.notification_intelligence", "hrms.utils.chat_space_lockdown"]:
            if key in sys.modules:
                del sys.modules[key]
        spec = importlib.util.spec_from_file_location(
            module_name,
            ROOT / "hrms" / "api" / "google_chat.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def setUp(self):
        fake_chat = _FakeChatAPI()
        _install_fake_frappe()
        _install_fake_hrms_package()
        _install_fake_google_oauth()
        _install_fake_bei_config()
        _install_fake_google_modules(fake_chat)
        self.fake_chat = fake_chat
        self.module = self._load_module()

    def test_send_message_to_space_reroutes_to_blip_notifications_by_default(self):
        with patch.object(self.module.os.path, "exists", return_value=True), patch.dict(os.environ, {}, clear=False):
            self.assertTrue(self.module.send_message_to_space("spaces/AAAAvDZdY-o", "hello"))

        self.assertEqual(self.fake_chat.messages_api.last_parent, "spaces/AAQABiNmpBg")
        self.assertEqual(self.fake_chat.messages_api.last_body, {"text": "hello"})

    def test_send_message_to_space_allows_explicit_override(self):
        with patch.object(self.module.os.path, "exists", return_value=True), patch.dict(
            os.environ,
            {
                "BEI_ALLOW_NON_BLIP_CHAT_DESTINATIONS": "true",
                "BEI_ALLOWED_CHAT_SPACES": "spaces/AAAAvDZdY-o",
            },
            clear=False,
        ):
            self.assertTrue(self.module.send_message_to_space("spaces/AAAAvDZdY-o", "hello"))

        self.assertEqual(self.fake_chat.messages_api.last_parent, "spaces/AAAAvDZdY-o")

    def test_ingest_notification_event_dry_run_renders_contract_sections(self):
        result = self.module.ingest_notification_event(
            event={
                "family": "approval_queue_new",
                "source_system": "frappe",
                "source_ref": "APQ-0001",
                "severity": "high",
                "owner": "Assigned Approver",
                "facts": {
                    "queue_name": "APQ-0001",
                    "reference_doctype": "BEI Store Order",
                    "reference_name": "BEI-ORD-0001",
                    "store": "Ayala Evo",
                },
            },
            dry_run=True,
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["sent"])
        self.assertIn("*Summary*", result["rendered_text"])
        self.assertIn("*Recommended fix*", result["rendered_text"])

    def test_send_notification_event_respects_family_allowed_space(self):
        event = {
            "family": "maintenance_status_update",
            "source_system": "frappe",
            "source_ref": "MR-0001",
            "severity": "medium",
            "owner": "Projects Team / Store Manager",
            "requested_space": "spaces/AAAAvDZdY-o",
            "facts": {
                "request_name": "MR-0001",
                "status": "Completed",
                "store": "Ayala Evo",
                "event_kind": "status_change",
            },
        }

        with patch.object(self.module.os.path, "exists", return_value=True), patch.dict(os.environ, {}, clear=False):
            result = self.module.ingest_notification_event(event=event)

        self.assertTrue(result["success"])
        self.assertTrue(result["sent"])
        self.assertEqual(self.fake_chat.messages_api.last_parent, "spaces/AAAAvDZdY-o")
        self.assertIn("maintenance status update", self.fake_chat.messages_api.last_body["text"].lower())

    def test_ingest_notification_event_dedups_within_policy_window(self):
        event = {
            "family": "maintenance_sla_backlog",
            "source_system": "frappe",
            "source_ref": "maintenance_sla:2026-03-13",
            "severity": "critical",
            "owner": "Projects Manager",
            "facts": {
                "report_date": "2026-03-13",
                "counts_by_priority": {"Urgent": 1, "High": 0, "Normal": 0},
                "breaches": [{"name": "MR-1", "store": "AFT", "priority": "Urgent", "age_hours": 6}],
            },
        }

        with patch.object(self.module.os.path, "exists", return_value=True), patch.dict(os.environ, {}, clear=False):
            first = self.module.ingest_notification_event(event=event)
            second = self.module.ingest_notification_event(event=event)

        self.assertTrue(first["sent"])
        self.assertTrue(second["success"])
        self.assertTrue(second["skipped"])
        self.assertEqual(self.fake_chat.messages_api.call_count, 1)


if __name__ == "__main__":
    unittest.main()
