import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hrms" / "utils" / "chat_space_lockdown.py"

spec = importlib.util.spec_from_file_location("chat_space_lockdown_under_test", MODULE_PATH)
chat_space_lockdown = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat_space_lockdown)


class TestChatSpaceLockdown(unittest.TestCase):
	def test_routes_any_non_blip_space_to_blip_by_default(self):
		with patch.dict(os.environ, {}, clear=False):
			self.assertEqual(
				chat_space_lockdown.route_outbound_chat_space("spaces/AAAAvDZdY-o"),
				chat_space_lockdown.DEFAULT_BLIP_NOTIFICATIONS_SPACE,
			)

	def test_keeps_blip_space_as_is(self):
		with patch.dict(os.environ, {}, clear=False):
			self.assertEqual(
				chat_space_lockdown.route_outbound_chat_space(
					chat_space_lockdown.DEFAULT_BLIP_NOTIFICATIONS_SPACE
				),
				chat_space_lockdown.DEFAULT_BLIP_NOTIFICATIONS_SPACE,
			)

	def test_allows_explicit_override_when_enabled_and_allowlisted(self):
		with patch.dict(
			os.environ,
			{
				"BEI_ALLOW_NON_BLIP_CHAT_DESTINATIONS": "true",
				"BEI_ALLOWED_CHAT_SPACES": "spaces/AAAAvDZdY-o",
			},
			clear=False,
		):
			self.assertEqual(
				chat_space_lockdown.route_outbound_chat_space("spaces/AAAAvDZdY-o"),
				"spaces/AAAAvDZdY-o",
			)


if __name__ == "__main__":
	unittest.main()
