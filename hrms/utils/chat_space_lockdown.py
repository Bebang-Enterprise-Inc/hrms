"""Pure-Python outbound Google Chat routing guard.

This module is intentionally Frappe-free so it can be reused by standalone
services, scripts, and CI jobs that still need the BEI notification policy.
"""

from __future__ import annotations

import os

from hrms.utils.notification_intelligence import (
	SPACE_NOTIFICATIONS as DEFAULT_BLIP_NOTIFICATIONS_SPACE,
)
from hrms.utils.notification_intelligence import (
	family_allows_requested_space,
	get_family_allowed_spaces,
)

_TRUE_VALUES = {"1", "true", "yes", "on"}
_LOCKDOWN_ENV = "BEI_CHAT_LOCKDOWN_ENABLED"
_ALLOW_NON_BLIP_ENV = "BEI_ALLOW_NON_BLIP_CHAT_DESTINATIONS"
_EXTRA_ALLOWED_SPACES_ENV = "BEI_ALLOWED_CHAT_SPACES"
_BLIP_SPACE_ENV = "BEI_BLIP_NOTIFICATIONS_SPACE"


def _env_flag(name: str, default: bool) -> bool:
	value = os.environ.get(name)
	if value is None:
		return default
	return value.strip().lower() in _TRUE_VALUES


def get_blip_notifications_space() -> str:
	configured = (os.environ.get(_BLIP_SPACE_ENV) or "").strip()
	return configured or DEFAULT_BLIP_NOTIFICATIONS_SPACE


def is_chat_lockdown_enabled() -> bool:
	return _env_flag(_LOCKDOWN_ENV, default=True)


def allow_non_blip_chat_destinations() -> bool:
	return _env_flag(_ALLOW_NON_BLIP_ENV, default=False)


def get_explicitly_allowed_chat_spaces() -> set[str]:
	raw = os.environ.get(_EXTRA_ALLOWED_SPACES_ENV, "")
	return {space.strip() for space in raw.split(",") if space.strip()}


def route_outbound_chat_space(
	requested_space: str | None,
	*,
	logger=None,
	context: str | None = None,
	family: str | None = None,
) -> str:
	"""Return the only permitted outbound chat space for the current policy."""
	requested = (requested_space or "").strip()
	blip_space = get_blip_notifications_space()

	if not requested:
		return blip_space

	if not is_chat_lockdown_enabled():
		return requested

	if requested == blip_space:
		return requested

	if family:
		family_allowed_spaces = get_family_allowed_spaces(family)
		if requested in family_allowed_spaces:
			return requested
		if family_allows_requested_space(family):
			return requested

	if allow_non_blip_chat_destinations() and requested in get_explicitly_allowed_chat_spaces():
		return requested

	if logger is not None:
		logger.warning(
			"Outbound Google Chat destination rerouted to ! Blip Notifications; requested=%s effective=%s family=%s context=%s",
			requested,
			blip_space,
			family or "legacy",
			context or "unspecified",
		)

	return blip_space
