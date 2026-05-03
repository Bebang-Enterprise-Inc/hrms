"""Centralized BEI configuration constants.

All Google Chat Space IDs and shared config values live here.
Production code should import from this module instead of hardcoding values.
"""

import os
from pathlib import Path

import frappe

# ── Google Chat Space IDs ──────────────────────────────────────────────────
# Canonical space IDs. Use get_chat_space() to allow BEI Settings overrides.

SPACE_NOTIFICATIONS = "spaces/AAQABiNmpBg"  # Blip / general notifications
SPACE_ERP_AUTOMATION = "spaces/AAQA3NVVR6c"  # ERP Automation Committee
SPACE_ACCOUNTING = "spaces/AAAA9RN0JZQ"  # Accounting Private
SPACE_ADMIN_IT = "spaces/AAAAjVg-2Kc"  # Admin / IT
SPACE_OPS = "spaces/AAAAvDZdY-o"  # Ops

# ── BEI Settings field → space mapping ─────────────────────────────────────
_SETTINGS_FIELD_MAP = {
	SPACE_NOTIFICATIONS: "gchat_notification_space",
	SPACE_ERP_AUTOMATION: "gchat_erp_automation_space",
	SPACE_ACCOUNTING: "gchat_accounting_space",
	SPACE_ADMIN_IT: "gchat_admin_it_space",
	SPACE_OPS: "gchat_ops_space",
}


def get_chat_space(default_space: str) -> str:
	"""Return the configured space from BEI Settings, falling back to *default_space*.

	Usage::

	    from hrms.utils.bei_config import get_chat_space, SPACE_ERP_AUTOMATION

	    space = get_chat_space(SPACE_ERP_AUTOMATION)
	"""
	field = _SETTINGS_FIELD_MAP.get(default_space)
	if field:
		try:
			if not frappe.db.has_column("BEI Settings", field):
				return default_space
			configured = frappe.db.get_single_value("BEI Settings", field)
			if configured:
				return configured
		except Exception:
			pass
	return default_space


# ── Service Account Credential Path ───────────────────────────────────────


def get_service_account_path() -> str:
	"""Return the service account JSON path, preferring env var over hardcoded default."""
	env_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
	if env_path and os.path.exists(env_path):
		return env_path

	app_path = Path(frappe.get_app_path("hrms")).resolve()
	bench_root = None
	for candidate in (app_path, *app_path.parents):
		if candidate.name == "apps":
			bench_root = candidate.parent
			break
	if bench_root is None:
		bench_root = app_path.parent
	return str(bench_root / "credentials" / "task-manager-service.json")


# ── Company Name ──────────────────────────────────────────────────────────


def get_company() -> str:
	"""Return the default company name from Frappe global defaults."""
	return frappe.defaults.get_global_default("company") or "Bebang Enterprise Inc."


# ── S037 store/entity register CSV (S233 v2 A7 + v3 A16) ─────────────────
# Extracted from hrms/api/company_master.py to break the circular import
# that emerges when hrms/api/create_new_store.py needs to read it.
# v3 A16: name is STORE_ENTITY_MAPPING_RELPATH (descriptive) to avoid
# confusion with hrms/overrides/company.py::_S037_REGISTER_RELPATH which
# points to a DIFFERENT CSV (store_buyer_entity_register_2026-03-12.csv).
STORE_ENTITY_MAPPING_RELPATH = ("data_seed", "store_entity_mapping_2026-04-13.csv")
