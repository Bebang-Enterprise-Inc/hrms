# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Biometric Monitoring API
Provides dashboard and monitoring endpoints for ADMS biometric system
"""

import frappe
from frappe import _
from datetime import datetime, timedelta


BIOMETRIC_ROLES = {"HR Manager", "HR User", "System Manager", "Administrator"}
BIOMETRIC_ADMIN_ROLES = {"System Manager", "Administrator"}


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


def _is_stale(data):
	"""Check if cached data is older than 6 hours."""
	if not data or "last_refreshed" not in data:
		return True
	refreshed = datetime.fromisoformat(data["last_refreshed"])
	return (datetime.now() - refreshed) > timedelta(hours=6)


@frappe.whitelist()
def get_dashboard_summary():
	"""Get dashboard KPIs: enrollment %, devices online, issues count."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:summary")
	if not data:
		return {"ok": True, "stale": True, "message": "No cached data. Trigger a refresh."}
	return {"ok": True, "stale": _is_stale(data), **data}


@frappe.whitelist()
def get_device_status():
	"""Get all 46 devices with connectivity status."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:devices")
	if not data:
		return {"ok": True, "stale": True, "devices": [], "message": "No cached data. Trigger a refresh."}
	return {"ok": True, "stale": _is_stale(data), "devices": data.get("devices", [])}


@frappe.whitelist()
def get_not_punching(hours=48):
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

	if not data:
		return {"ok": True, "stale": True, "employees": [], "message": "No cached data. Trigger a refresh."}

	# Filter by hours if we have timestamp data
	employees = data.get("employees", [])
	if hours != 48 and employees:
		# Filter employees based on hours_since_punch if available
		employees = [e for e in employees if e.get("hours_since_punch", 0) >= hours]

	return {"ok": True, "stale": _is_stale(data), "employees": employees}


@frappe.whitelist()
def get_wrong_device():
	"""Get employees punching at wrong store device."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:wrong_device")
	if not data:
		return {"ok": True, "stale": True, "employees": [], "message": "No cached data. Trigger a refresh."}
	return {"ok": True, "stale": _is_stale(data), "employees": data.get("employees", [])}


@frappe.whitelist()
def get_not_enrolled():
	"""Get employees who never punched since Feb 3."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:not_enrolled")
	if not data:
		return {"ok": True, "stale": True, "employees": [], "message": "No cached data. Trigger a refresh."}
	return {"ok": True, "stale": _is_stale(data), "employees": data.get("employees", [])}


@frappe.whitelist()
def get_ghost_punchers():
	"""Get Bio IDs punching but not in Employee Master."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:ghost_punchers")
	if not data:
		return {"ok": True, "stale": True, "punchers": [], "message": "No cached data. Trigger a refresh."}
	return {"ok": True, "stale": _is_stale(data), "punchers": data.get("punchers", [])}


@frappe.whitelist()
def get_store_leaderboard():
	"""Get store ranking by compliance %."""
	_check_biometric_access()
	cache = frappe.cache()
	data = cache.get_value("biometric:v1:leaderboard")
	if not data:
		return {"ok": True, "stale": True, "stores": [], "message": "No cached data. Trigger a refresh."}
	return {"ok": True, "stale": _is_stale(data), "stores": data.get("stores", [])}


@frappe.whitelist()
def get_all_issues():
	"""Get all issues combined (not_punching + wrong_device + not_enrolled + ghost)."""
	_check_biometric_access()
	cache = frappe.cache()

	all_employees = []

	# Collect from all 4 issue caches, tagging each with issue_type
	for issue_type, cache_key, list_key in [
		("not_punching", "biometric:v1:not_punching", "employees"),
		("wrong_device", "biometric:v1:wrong_device", "employees"),
		("not_enrolled", "biometric:v1:not_enrolled", "employees"),
		("ghost", "biometric:v1:ghost_punchers", "punchers"),
	]:
		data = cache.get_value(cache_key)
		if data:
			for emp in data.get(list_key, []):
				emp["issue_type"] = issue_type
				all_employees.append(emp)

	return {"ok": True, "employees": all_employees}


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
			"message": f"Cache refreshed successfully in {duration:.1f}s"
		}
	except Exception as e:
		frappe.log_error(
			title="Manual Biometric Refresh Failed",
			message=f"Error: {str(e)}"
		)
		return {
			"ok": False,
			"refreshed": False,
			"message": f"Refresh failed: {str(e)}"
		}


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
		"biometric:v1:ghost_punchers",
		"biometric:v1:leaderboard",
		"biometric:v1:refresh_lock",
		"biometric:v1:failure_count",
	]

	for key in cache_keys:
		cache.delete_value(key)

	return {"ok": True, "message": "All biometric cache cleared."}
