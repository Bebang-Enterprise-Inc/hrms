"""Shared ADMS configuration helper.

Extracted from hrms/api/transfer_requests.py in S164 Phase 0 to eliminate
cross-module import of a private helper (audit NG5).
"""

from __future__ import annotations

import os
from typing import Any

import frappe
from frappe.utils import cint


def get_adms_config() -> dict[str, Any]:
	"""Return ADMS receiver config (base_url, token, timeouts).

	Reads from site_config (frappe.conf) first, falling back to environment
	variables. Public helper — use this from any module that needs to talk
	to the ADMS receiver.
	"""
	base_url = (
		(frappe.conf.get("adms_base_url") if getattr(frappe, "conf", None) else None)
		or os.environ.get("ADMS_BASE_URL")
		or "http://localhost:8080"
	)
	token = (
		frappe.conf.get("adms_admin_token") if getattr(frappe, "conf", None) else None
	) or os.environ.get("ADMS_ADMIN_TOKEN")
	timeout_seconds = cint(
		(frappe.conf.get("adms_request_timeout_seconds") if getattr(frappe, "conf", None) else None)
		or os.environ.get("ADMS_REQUEST_TIMEOUT_SECONDS")
		or 15
	)
	stale_timeout_minutes = cint(
		(frappe.conf.get("adms_sync_stale_timeout_minutes") if getattr(frappe, "conf", None) else None)
		or os.environ.get("ADMS_SYNC_STALE_TIMEOUT_MINUTES")
		or 30
	)

	return {
		"base_url": (base_url or "").rstrip("/"),
		"token": token,
		"timeout_seconds": max(5, timeout_seconds),
		"stale_timeout_minutes": max(5, stale_timeout_minutes),
	}
