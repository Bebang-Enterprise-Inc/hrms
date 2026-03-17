# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Biometric Monitoring API
Provides dashboard and monitoring endpoints for ADMS biometric system
"""

from datetime import datetime, timedelta
from typing import Any

import frappe
from frappe import _

BIOMETRIC_ROLES = {"HR Manager", "HR User", "IT User", "System Manager", "Administrator"}
BIOMETRIC_ADMIN_ROLES = {"System Manager", "Administrator"}
CONTRACT_REVISION = "s059-biometric-v1"
ISSUE_CACHE_SPECS = [
	("not_punching", "biometric:v1:not_punching", "employees"),
	("wrong_device", "biometric:v1:wrong_device", "employees"),
	("not_enrolled", "biometric:v1:not_enrolled", "employees"),
	("registry_mismatch", "biometric:v1:registry_mismatch", "employees"),
	("ghost", "biometric:v1:ghost_punchers", "punchers"),
]


def _check_biometric_access():
	"""Check user has HR/System Manager role. Called at start of every endpoint."""
	user_roles = set(frappe.get_roles(frappe.session.user))
	if not user_roles & BIOMETRIC_ROLES:
		frappe.throw(_("You do not have access to biometric monitoring"), frappe.PermissionError)


def _check_biometric_admin():
	"""Check user has System Manager/Administrator role. For refresh/invalidate only."""
	user_roles = set(frappe.get_roles(frappe.session.user))
	if not user_roles & BIOMETRIC_ADMIN_ROLES:
		frappe.throw(_("Only administrators can refresh biometric cache"), frappe.PermissionError)


def _is_stale(data: dict[str, Any] | None) -> bool:
	"""Check if cached data is older than 6 hours."""
	if not data or "last_refreshed" not in data:
		return True
	refreshed = datetime.fromisoformat(data["last_refreshed"])
	return (datetime.now() - refreshed) > timedelta(hours=6)


def _empty_response(list_key: str | None = None) -> dict[str, Any]:
	"""Return a normalized stale payload when cache is empty."""
	payload: dict[str, Any] = {
		"ok": True,
		"stale": True,
		"contract_revision": CONTRACT_REVISION,
		"message": "No cached data. Trigger a refresh.",
	}
	if list_key:
		payload[list_key] = []
	return payload


def _with_cache_metadata(data: dict[str, Any] | None, list_key: str | None = None) -> dict[str, Any]:
	"""Normalize cached payloads so frontend state can distinguish stale from clean-empty."""
	if not data:
		return _empty_response(list_key)

	payload = dict(data)
	payload["ok"] = True
	payload["stale"] = _is_stale(data)
	payload["contract_revision"] = payload.get("contract_revision", CONTRACT_REVISION)
	if payload["stale"]:
		payload["message"] = payload.get("message") or "Biometric cache is stale. Trigger a refresh."
	elif "message" not in payload:
		payload["message"] = None

	if list_key:
		payload.setdefault(list_key, [])

	return payload


def _matches_not_punching_threshold(employee: dict[str, Any], hours: int) -> bool:
	"""Guard against null cache values and keep never-punched rows in the result set."""
	value = employee.get("hours_since_punch")
	if value is None:
		return True
	try:
		return float(value) >= hours
	except (TypeError, ValueError):
		return True


@frappe.whitelist()
def get_dashboard_summary():
	"""Get dashboard KPIs: enrollment %, devices online, issues count."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:summary")
	return _with_cache_metadata(data)


@frappe.whitelist()
def get_device_status():
	"""Get all 46 devices with connectivity status."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:devices")
	return _with_cache_metadata(data, "devices")


@frappe.whitelist()
def get_not_punching(hours: int | str = 48):
	"""Get employees not punching for X hours."""
	_check_biometric_access()
	cache = frappe.cache()
	hours = int(hours)

	# Cache key is based on the hours parameter
	cache_key = f"biometric:v1:not_punching_{hours}h"
	data = cache.get_value(cache_key)

	# Fallback to 48h cache if specific hours not found
	if not data:
		data = cache.get_value("biometric:v1:not_punching")

	payload = _with_cache_metadata(data, "employees")

	# Filter by hours if we have timestamp data
	employees = payload.get("employees", [])
	if hours != 48 and employees:
		employees = [e for e in employees if _matches_not_punching_threshold(e, hours)]

	payload["employees"] = employees
	return payload


@frappe.whitelist()
def get_wrong_device():
	"""Get employees punching at wrong store device."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:wrong_device")
	return _with_cache_metadata(data, "employees")


@frappe.whitelist()
def get_not_enrolled():
	"""Get employees who never punched since Feb 3."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:not_enrolled")
	return _with_cache_metadata(data, "employees")


@frappe.whitelist()
def get_registry_mismatch():
	"""Get active punchers with raw ADMS punches but no registry-backed enrollment."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:registry_mismatch")
	return _with_cache_metadata(data, "employees")


@frappe.whitelist()
def get_ghost_punchers():
	"""Get Bio IDs punching but not in Employee Master."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:ghost_punchers")
	return _with_cache_metadata(data, "punchers")


@frappe.whitelist()
def get_store_leaderboard():
	"""Get store ranking by compliance %."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:leaderboard")
	return _with_cache_metadata(data, "stores")


@frappe.whitelist()
def get_all_issues():
	"""Get all issues combined with freshness metadata preserved."""
	_check_biometric_access()
	cache = frappe.cache()

	all_employees = []
	missing_sources = []
	last_refreshed_values = []
	stale = False
	contract_revision = CONTRACT_REVISION

	for issue_type, cache_key, list_key in ISSUE_CACHE_SPECS:
		data = cache.get_value(cache_key)
		if not data:
			stale = True
			missing_sources.append(issue_type)
			continue

		stale = stale or _is_stale(data)
		contract_revision = data.get("contract_revision", contract_revision)
		if data.get("last_refreshed"):
			last_refreshed_values.append(data["last_refreshed"])

		for entry in data.get(list_key, []):
			row = dict(entry)
			row["issue_type"] = issue_type
			all_employees.append(row)

	return {
		"ok": True,
		"stale": stale or bool(missing_sources),
		"contract_revision": contract_revision,
		"last_refreshed": max(last_refreshed_values) if last_refreshed_values else None,
		"employees": all_employees,
		"missing_sources": missing_sources,
		"message": (
			"Biometric cache is stale or incomplete. Trigger a refresh." if stale or missing_sources else None
		),
	}


@frappe.whitelist()
def refresh_biometric_cache():
	"""Manual trigger to refresh cached data (admin-only)."""
	_check_biometric_admin()

	# Import here to avoid circular dependency
	from hrms.utils.adms_monitor import refresh_biometric_status

	try:
		start_time = datetime.now()
		refresh_biometric_status()
		duration = (datetime.now() - start_time).total_seconds()
		return {
			"ok": True,
			"refreshed": True,
			"duration_seconds": duration,
			"message": f"Cache refreshed successfully in {duration:.1f}s",
		}
	except Exception as e:
		frappe.log_error(title="Manual Biometric Refresh Failed", message=f"Error: {e!s}")
		return {"ok": False, "refreshed": False, "message": f"Refresh failed: {e!s}"}


@frappe.whitelist()
def invalidate_biometric_cache():
	"""Force-clear all cached data (admin-only)."""
	_check_biometric_admin()
	cache = frappe.cache()

	cache_keys = [
		"biometric:v1:summary",
		"biometric:v1:devices",
		"biometric:v1:not_punching",
		"biometric:v1:wrong_device",
		"biometric:v1:not_enrolled",
		"biometric:v1:registry_mismatch",
		"biometric:v1:ghost_punchers",
		"biometric:v1:leaderboard",
		"biometric:v1:refresh_lock",
		"biometric:v1:failure_count",
	]

	for key in cache_keys:
		cache.delete_value(key)

	return {"ok": True, "message": "All biometric cache cleared."}
