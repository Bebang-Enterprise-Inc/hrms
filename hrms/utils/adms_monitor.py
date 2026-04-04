"""ADMS Biometric Monitoring - SSM Query and Cache Management"""

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta

import boto3

import frappe
from frappe import _

INSTANCE_ID = "i-026b7477d27bd46d6"
DB_CONTAINER = "62c9d67fd960_adms_receiver_adms-db_1"
REGION = "ap-southeast-1"
SSM_TIMEOUT_SECONDS = 60
SSM_POLL_INTERVAL = 2

# Cache configuration
CACHE_KEYS = {
	"summary": "biometric:v1:summary",
	"devices": "biometric:v1:devices",
	"not_punching": "biometric:v1:not_punching",
	"wrong_device": "biometric:v1:wrong_device",
	"not_enrolled": "biometric:v1:not_enrolled",
	"registry_mismatch": "biometric:v1:registry_mismatch",
	"ghost": "biometric:v1:ghost_punchers",
	"leaderboard": "biometric:v1:leaderboard",
	"refresh_lock": "biometric:v1:refresh_lock",
}
CACHE_TTL = 6 * 60 * 60  # 6 hours in seconds
CONTRACT_REVISION = "s059-biometric-v1"

# SQL Queries
SQL_PUNCH_BY_DEVICE = """
SELECT pin, sn, COUNT(*) as punch_count, MAX(event_time) as last_punch
FROM adms_attlog_raw
WHERE event_time >= NOW() - INTERVAL '10 days'
GROUP BY pin, sn
"""

SQL_DEVICE_LAST_ACTIVITY = """
SELECT sn, MAX(event_time) as last_activity, COUNT(*) as total_punches
FROM adms_attlog_raw
GROUP BY sn
"""

SQL_REGISTRY_ENTRIES = """
SELECT pin, sn
FROM adms_user_registry
WHERE pin ~ '^900'
"""

SQL_48H_ACTIVITY = """
SELECT pin, COUNT(*) as punch_count, MAX(event_time) as last_punch
FROM adms_attlog_raw
WHERE event_time >= NOW() - INTERVAL '48 hours'
GROUP BY pin
"""

SQL_PUNCH_LAST_ACTIVITY = """
SELECT pin, COUNT(*) as punch_count, MAX(event_time) as last_punch
FROM adms_attlog_raw
GROUP BY pin
"""

# Device mapping path
DEVICE_MAPPING_PATH = os.path.join(frappe.get_app_path("hrms"), "..", "data", "ADMS", "device_mapping.json")


def _run_ssm_query(ssm_client, sql, description="query"):
	"""Execute SQL via SSM with timeout and error handling."""
	try:
		cmd = f"docker exec {DB_CONTAINER} psql -U adms -d adms -t -A -F'|' -c \"{sql}\""
		resp = ssm_client.send_command(
			InstanceIds=[INSTANCE_ID],
			DocumentName="AWS-RunShellScript",
			Parameters={"commands": [cmd]},
		)
		command_id = resp["Command"]["CommandId"]

		elapsed = 0
		while elapsed < SSM_TIMEOUT_SECONDS:
			time.sleep(SSM_POLL_INTERVAL)
			elapsed += SSM_POLL_INTERVAL
			try:
				result = ssm_client.get_command_invocation(CommandId=command_id, InstanceId=INSTANCE_ID)
				if result["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
					break
			except ssm_client.exceptions.InvocationDoesNotExist:
				continue

		if result["Status"] == "Success":
			return result.get("StandardOutputContent", "").strip()
		else:
			error_msg = result.get("StandardErrorContent", "")[:500]
			frappe.log_error(
				title=f"ADMS SSM Query Failed: {description}",
				message=f"Status: {result['Status']}\nError: {error_msg}\nSQL: {sql[:200]}",
			)
			return None

	except Exception as e:
		frappe.log_error(
			title=f"ADMS SSM Connection Failed: {description}", message=f"Error: {e!s}\nSQL: {sql[:200]}"
		)
		return None


def _load_all_employees():
	"""Batch-load all active employees with Bio ID + store. Called once per refresh."""
	return frappe.db.sql(
		"""
		SELECT name, employee_name, attendance_device_id, branch,
		       designation, reports_to, department
		FROM tabEmployee
		WHERE status = 'Active' AND attendance_device_id IS NOT NULL
		    AND attendance_device_id != ''
	""",
		as_dict=True,
	)


def _load_device_mapping():
	"""Load device mapping from JSON file."""
	try:
		if os.path.exists(DEVICE_MAPPING_PATH):
			# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal -- DEVICE_MAPPING_PATH is derived from frappe.get_app_path("hrms") and fixed path segments only.
			with open(DEVICE_MAPPING_PATH) as f:
				return json.load(f)
		else:
			frappe.log_error(
				title="Device Mapping Not Found", message=f"File not found: {DEVICE_MAPPING_PATH}"
			)
			return {}
	except Exception as e:
		frappe.log_error(
			title="Device Mapping Load Failed", message=f"Error: {e!s}\nPath: {DEVICE_MAPPING_PATH}"
		)
		return {}


def _parse_ssm_result(output):
	"""Parse SSM query output (pipe-delimited) into list of dicts."""
	if not output:
		return []

	rows = []
	for line in output.strip().split("\n"):
		if line.strip():
			rows.append(line.strip())
	return rows


def _cache_payload(now_iso, **data):
	"""Wrap cache data with the active contract revision."""
	return {
		"last_refreshed": now_iso,
		"contract_revision": CONTRACT_REVISION,
		**data,
	}


def _increment_failure_count(cache):
	"""Track consecutive failures. Alert after 3."""
	count = cache.get_value("biometric:v1:failure_count") or 0
	count = int(count) + 1
	cache.set_value("biometric:v1:failure_count", count)

	if count >= 3:
		from hrms.utils.biometric_alerts import _send_chat_alert

		_send_chat_alert(
			f"⚠️ ADMS queries have failed {count} consecutive times. "
			"Dashboard showing stale data. Check EC2 instance and SSM connectivity."
		)


def refresh_biometric_status():
	"""Scheduled task: refresh all biometric data from ADMS. Runs every 6 hours."""
	cache = frappe.cache()

	# Concurrency lock — prevent duplicate refreshes
	if cache.get_value(CACHE_KEYS["refresh_lock"]):
		frappe.log_error(title="Biometric Refresh Skipped", message="Another refresh is already in progress.")
		return

	cache.set_value(CACHE_KEYS["refresh_lock"], "1", expires_in_sec=300)  # 5-min lock

	try:
		ssm = boto3.client("ssm", region_name=REGION)

		# Run all core queries
		q1_result = _run_ssm_query(ssm, SQL_PUNCH_BY_DEVICE, "punch_by_device")
		q2_result = _run_ssm_query(ssm, SQL_DEVICE_LAST_ACTIVITY, "device_last_activity")
		q3_result = _run_ssm_query(ssm, SQL_REGISTRY_ENTRIES, "registry_entries")
		q4_result = _run_ssm_query(ssm, SQL_48H_ACTIVITY, "48h_activity")
		q5_result = _run_ssm_query(ssm, SQL_PUNCH_LAST_ACTIVITY, "punch_last_activity")

		# If ALL queries fail, keep stale cache and alert
		if all(r is None for r in [q1_result, q2_result, q3_result, q4_result, q5_result]):
			frappe.log_error(
				title="ADMS All Queries Failed",
				message="All ADMS SSM queries returned None. Keeping stale cache.",
			)
			_increment_failure_count(cache)
			return

		# Load employee master and device mapping
		employees = _load_all_employees()
		device_mapping = _load_device_mapping()

		# Build lookup maps
		emp_by_bioid = {e.attendance_device_id: e for e in employees}
		all_bioids = set(emp_by_bioid.keys())
		employee_count_by_store = defaultdict(int)
		for emp in employees:
			employee_count_by_store[emp.branch or "Unknown"] += 1

		# Parse query results
		punch_data = _parse_ssm_result(q1_result)
		device_activity = _parse_ssm_result(q2_result)
		registry_data = _parse_ssm_result(q3_result)
		recent_activity = _parse_ssm_result(q4_result)
		punch_last_activity = _parse_ssm_result(q5_result)

		# Process punch_by_device (pin|sn|count|last_punch) for wrong-device checks
		punch_by_emp_device = defaultdict(lambda: defaultdict(int))
		for row in punch_data:
			parts = row.split("|")
			if len(parts) >= 4:
				pin, sn, count = parts[0], parts[1], int(parts[2])
				punch_by_emp_device[pin][sn] = count

		# Process punch_last_activity (pin|count|last_punch) for truth-level punch history
		all_punchers = set()
		emp_last_punch = {}
		for row in punch_last_activity:
			parts = row.split("|")
			if len(parts) >= 3:
				pin, last_punch = parts[0], parts[2]
				all_punchers.add(pin)
				emp_last_punch[pin] = last_punch

		# Process device_last_activity (sn|last_activity|total_punches)
		device_status = {}
		for row in device_activity:
			parts = row.split("|")
			if len(parts) >= 3:
				sn, last_activity, total = parts[0], parts[1], int(parts[2])
				device_status[sn] = {
					"sn": sn,
					"last_activity": last_activity,
					"total_punches": total,
					"store": device_mapping.get(sn, {}).get("store", "Unknown"),
					"employee_count": employee_count_by_store.get(
						device_mapping.get(sn, {}).get("store", "Unknown"),
						0,
					),
					"status": _get_device_status(last_activity),
				}

		# Process registry (pin|sn)
		enrolled_bioids = set()
		for row in registry_data:
			parts = row.split("|")
			if len(parts) >= 1:
				enrolled_bioids.add(parts[0])

		# Process 48h activity (pin|count|last_punch)
		recent_punchers = set()
		for row in recent_activity:
			parts = row.split("|")
			if len(parts) >= 1:
				recent_punchers.add(parts[0])

		# Build issues lists
		not_punching = []
		wrong_device = []
		not_enrolled = []
		registry_mismatch = []
		ghost_punchers = []

		# Find employees not punching in 48h
		for bioid, emp in emp_by_bioid.items():
			if bioid not in recent_punchers:
				last_punch = emp_last_punch.get(bioid)
				hours_since = _calculate_hours_since(last_punch) if last_punch else None
				not_punching.append(
					{
						"employee_id": emp.name,
						"employee_name": emp.employee_name,
						"bio_id": bioid,
						"store": emp.branch or "Unknown",
						"last_punch": last_punch,
						"hours_since_punch": hours_since,
						"supervisor": emp.reports_to,
					}
				)

		# Find employees punching at wrong device
		for bioid, devices in punch_by_emp_device.items():
			emp = emp_by_bioid.get(bioid)
			if not emp:
				continue

			assigned_store = emp.branch
			for sn, punch_count in devices.items():
				device_store = device_mapping.get(sn, {}).get("store")
				if device_store and assigned_store and device_store != assigned_store:
					wrong_device.append(
						{
							"employee_id": emp.name,
							"employee_name": emp.employee_name,
							"bio_id": bioid,
							"assigned_store": assigned_store,
							"punching_store": device_store,
							"device_sn": sn,
							"punch_count": punch_count,
							"supervisor": emp.reports_to,
						}
					)

		# Find employees with registry mismatch or never enrolled
		for bioid, emp in emp_by_bioid.items():
			last_punch = emp_last_punch.get(bioid)
			hours_since = _calculate_hours_since(last_punch) if last_punch else None
			if bioid not in enrolled_bioids and bioid in recent_punchers:
				registry_mismatch.append(
					{
						"employee_id": emp.name,
						"employee_name": emp.employee_name,
						"bio_id": bioid,
						"store": emp.branch or "Unknown",
						"last_punch": last_punch,
						"hours_since_punch": hours_since,
						"supervisor": emp.reports_to,
					}
				)
			elif bioid not in enrolled_bioids and bioid not in all_punchers:
				not_enrolled.append(
					{
						"employee_id": emp.name,
						"employee_name": emp.employee_name,
						"bio_id": bioid,
						"store": emp.branch or "Unknown",
						"last_punch": last_punch,
						"hours_since_punch": hours_since,
						"supervisor": emp.reports_to,
					}
				)

		# Find ghost punchers (Bio IDs punching but not in Employee Master)
		punching_bioids = set(punch_by_emp_device.keys())
		ghost_ids = punching_bioids - all_bioids
		for bioid in ghost_ids:
			# Find which devices they're punching at
			devices_used = list(punch_by_emp_device[bioid].keys())
			last_punch = emp_last_punch.get(bioid)
			ghost_punchers.append(
				{
					"employee_id": None,
					"employee_name": "Unknown Bio ID",
					"bio_id": bioid,
					"store": device_mapping.get(devices_used[0], {}).get("store", "Unknown")
					if devices_used
					else "Unknown",
					"last_punch": last_punch,
					"hours_since_punch": _calculate_hours_since(last_punch) if last_punch else None,
					"supervisor": None,
					"devices": devices_used,
					"stores": [device_mapping.get(sn, {}).get("store", "Unknown") for sn in devices_used],
					"total_punches": sum(punch_by_emp_device[bioid].values()),
				}
			)

		# Build store leaderboard
		store_stats = defaultdict(lambda: {"total": 0, "punching": 0})
		for emp in employees:
			store = emp.branch or "Unknown"
			store_stats[store]["total"] += 1
			if emp.attendance_device_id in recent_punchers:
				store_stats[store]["punching"] += 1

		leaderboard = []
		for store, stats in store_stats.items():
			compliance_pct = (stats["punching"] / stats["total"] * 100) if stats["total"] > 0 else 0
			leaderboard.append(
				{
					"store_name": store,
					"total_employees": stats["total"],
					"punching_employees": stats["punching"],
					"compliance_pct": round(compliance_pct, 1),
				}
			)
		leaderboard.sort(key=lambda x: x["compliance_pct"], reverse=True)
		for i, store in enumerate(leaderboard, 1):
			store["rank"] = i

		# Build summary
		total_employees = len(employees)
		punching_employees = len(recent_punchers & all_bioids)
		registry_enrolled_employees = len(enrolled_bioids & all_bioids)
		enrollment_pct = (registry_enrolled_employees / total_employees * 100) if total_employees > 0 else 0
		punching_pct = (punching_employees / total_employees * 100) if total_employees > 0 else 0
		devices_online = sum(1 for d in device_status.values() if d["status"] == "online")
		devices_total = len(device_status)
		issues_count = (
			len(not_punching)
			+ len(wrong_device)
			+ len(not_enrolled)
			+ len(registry_mismatch)
			+ len(ghost_punchers)
		)

		now_iso = datetime.now().isoformat()

		# Store all results in cache
		summary_data = _cache_payload(
			now_iso,
			total_employees=total_employees,
			punching_employees=punching_employees,
			punching_pct=round(punching_pct, 1),
			registry_enrolled_employees=registry_enrolled_employees,
			enrollment_pct=round(enrollment_pct, 1),
			devices_online=devices_online,
			devices_total=devices_total,
			issues_count=issues_count,
			registry_mismatch_count=len(registry_mismatch),
		)

		cache.set_value(CACHE_KEYS["summary"], summary_data, expires_in_sec=CACHE_TTL)
		cache.set_value(
			CACHE_KEYS["devices"],
			_cache_payload(now_iso, devices=list(device_status.values())),
			expires_in_sec=CACHE_TTL,
		)
		cache.set_value(
			CACHE_KEYS["not_punching"],
			_cache_payload(now_iso, employees=not_punching),
			expires_in_sec=CACHE_TTL,
		)
		cache.set_value(
			CACHE_KEYS["wrong_device"],
			_cache_payload(now_iso, employees=wrong_device),
			expires_in_sec=CACHE_TTL,
		)
		cache.set_value(
			CACHE_KEYS["not_enrolled"],
			_cache_payload(now_iso, employees=not_enrolled),
			expires_in_sec=CACHE_TTL,
		)
		cache.set_value(
			CACHE_KEYS["registry_mismatch"],
			_cache_payload(now_iso, employees=registry_mismatch),
			expires_in_sec=CACHE_TTL,
		)
		cache.set_value(
			CACHE_KEYS["ghost"],
			_cache_payload(now_iso, punchers=ghost_punchers),
			expires_in_sec=CACHE_TTL,
		)
		cache.set_value(
			CACHE_KEYS["leaderboard"],
			_cache_payload(now_iso, stores=leaderboard),
			expires_in_sec=CACHE_TTL,
		)

		# Reset failure counter on success
		cache.delete_value("biometric:v1:failure_count")

	finally:
		cache.delete_value(CACHE_KEYS["refresh_lock"])


def _get_device_status(last_activity_str):
	"""Determine device status based on last activity timestamp."""
	if not last_activity_str:
		return "never_connected"

	try:
		last_activity = datetime.fromisoformat(last_activity_str.replace(" ", "T"))
		hours_since = (datetime.now() - last_activity).total_seconds() / 3600

		if hours_since < 6:
			return "online"
		elif hours_since < 24:
			return "recent"
		else:
			return "offline"
	except Exception:
		return "unknown"


def _calculate_hours_since(timestamp_str):
	"""Calculate hours since a timestamp string."""
	if not timestamp_str:
		return None

	try:
		ts = datetime.fromisoformat(timestamp_str.replace(" ", "T"))
		return round((datetime.now() - ts).total_seconds() / 3600, 1)
	except Exception:
		return None
