"""Biometric Monitoring Alerts - Google Chat Integration"""

import frappe
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from datetime import datetime
import csv
import io


BIOMETRIC_ALERT_SPACE = "spaces/AAAAjVg-2Kc"  # Admin/IT space


def _send_chat_alert(message):
	"""Send alert to Google Chat space using service account (bot identity)."""
	try:
		creds = service_account.Credentials.from_service_account_file(
			"credentials/task-manager-service.json",
			scopes=["https://www.googleapis.com/auth/chat.bot"],
		)
		chat = build("chat", "v1", credentials=creds)
		chat.spaces().messages().create(
			parent=BIOMETRIC_ALERT_SPACE,
			body={"text": message},
		).execute()
	except Exception as e:
		frappe.log_error(
			title="Biometric Chat Alert Failed",
			message=f"Error: {str(e)}\nMessage: {message[:500]}"
		)
		# Fallback: log to Error Log for manual review (no silent failure)


def send_daily_digest():
	"""Scheduled: 7 AM PHT daily digest to Google Chat.

	Design rules:
	- Numbers only in chat message (no employee names)
	- Generate CSV with full details, upload to Google Drive
	- Include Drive link in chat message for drill-down
	"""
	cache = frappe.cache()
	summary = cache.get_value("biometric:v1:summary")

	if not summary:
		_send_chat_alert("⚠️ Biometric Daily Digest: No cached data. Check scheduler.")
		return

	# Get detailed data for CSV
	not_punching_data = cache.get_value("biometric:v1:not_punching") or {}
	wrong_device_data = cache.get_value("biometric:v1:wrong_device") or {}
	not_enrolled_data = cache.get_value("biometric:v1:not_enrolled") or {}
	ghost_data = cache.get_value("biometric:v1:ghost_punchers") or {}

	not_punching = not_punching_data.get("employees", [])
	wrong_device = wrong_device_data.get("employees", [])
	not_enrolled = not_enrolled_data.get("employees", [])
	ghost_punchers = ghost_data.get("punchers", [])

	# Generate detail CSV
	csv_rows = _build_detail_csv(not_punching, wrong_device, not_enrolled, ghost_punchers)

	# Upload CSV to Google Drive
	today = datetime.now().strftime("%Y-%m-%d")
	drive_link = _upload_to_drive(csv_rows, f"Biometric_Report_{today}.csv")

	# Send brief summary + Drive link to chat
	msg = _format_brief_digest(summary, drive_link, len(not_punching), len(wrong_device), len(not_enrolled), len(ghost_punchers))
	_send_chat_alert(msg)


def _build_detail_csv(not_punching, wrong_device, not_enrolled, ghost_punchers):
	"""Build CSV rows with all employee-level details."""
	rows = []

	# Not punching >48h
	for emp in not_punching:
		rows.append({
			"Issue Type": "Not Punching >48h",
			"Employee ID": emp.get("employee_id", ""),
			"Employee Name": emp.get("employee_name", ""),
			"Bio ID": emp.get("bio_id", ""),
			"Store": emp.get("store", ""),
			"Last Punch": emp.get("last_punch", "Never"),
			"Hours Since Punch": emp.get("hours_since_punch", "N/A"),
			"Supervisor": emp.get("supervisor", ""),
			"Details": "",
		})

	# Wrong device
	for emp in wrong_device:
		rows.append({
			"Issue Type": "Wrong Device",
			"Employee ID": emp.get("employee_id", ""),
			"Employee Name": emp.get("employee_name", ""),
			"Bio ID": emp.get("bio_id", ""),
			"Store": emp.get("assigned_store", ""),
			"Last Punch": "",
			"Hours Since Punch": "",
			"Supervisor": emp.get("supervisor", ""),
			"Details": f"Punching at {emp.get('punching_store')} (assigned to {emp.get('assigned_store')})",
		})

	# Not enrolled
	for emp in not_enrolled:
		rows.append({
			"Issue Type": "Not Enrolled",
			"Employee ID": emp.get("employee_id", ""),
			"Employee Name": emp.get("employee_name", ""),
			"Bio ID": emp.get("bio_id", ""),
			"Store": emp.get("store", ""),
			"Last Punch": "Never",
			"Hours Since Punch": "N/A",
			"Supervisor": emp.get("supervisor", ""),
			"Details": "No registry entry, no punches",
		})

	# Ghost punchers
	for ghost in ghost_punchers:
		stores_str = ", ".join(ghost.get("stores", []))
		rows.append({
			"Issue Type": "Ghost Puncher",
			"Employee ID": "Unknown",
			"Employee Name": "Unknown",
			"Bio ID": ghost.get("bio_id", ""),
			"Store": stores_str,
			"Last Punch": "",
			"Hours Since Punch": "",
			"Supervisor": "",
			"Details": f"Total punches: {ghost.get('total_punches', 0)}",
		})

	return rows


def _upload_to_drive(csv_rows, filename):
	"""Upload CSV to Google Drive using service account delegation."""
	try:
		creds = service_account.Credentials.from_service_account_file(
			"credentials/task-manager-service.json",
			scopes=["https://www.googleapis.com/auth/drive.file"],
		).with_subject("sam@bebang.ph")  # Domain-wide delegation

		drive = build("drive", "v3", credentials=creds)

		# Write CSV to memory
		buf = io.StringIO()
		if csv_rows:
			fieldnames = csv_rows[0].keys()
			writer = csv.DictWriter(buf, fieldnames=fieldnames)
			writer.writeheader()
			writer.writerows(csv_rows)
		else:
			# Empty CSV
			buf.write("No issues found\n")

		media = MediaInMemoryUpload(buf.getvalue().encode(), mimetype="text/csv")
		file = drive.files().create(
			body={"name": filename, "mimeType": "text/csv"},
			media_body=media,
			fields="id,webViewLink",
		).execute()

		# Make viewable by anyone in org
		drive.permissions().create(
			fileId=file["id"],
			body={"type": "domain", "domain": "bebang.ph", "role": "reader"},
		).execute()

		return file["webViewLink"]

	except Exception as e:
		frappe.log_error(
			title="Biometric CSV Upload Failed",
			message=f"Error: {str(e)}\nFilename: {filename}"
		)
		return None


def _format_brief_digest(summary, drive_link, not_punching_count, wrong_device_count, not_enrolled_count, ghost_count):
	"""Format brief chat message with KPI summary and Drive link."""
	today = datetime.now().strftime("%b %d, %Y")

	total_emp = summary.get("total_employees", 0)
	punching = summary.get("punching_employees", 0)
	enrollment_pct = summary.get("enrollment_pct", 0)
	devices_online = summary.get("devices_online", 0)
	devices_total = summary.get("devices_total", 0)
	days_left = summary.get("days_to_deadline", 0)

	message = f"""📊 BIOMETRIC REPORT — {today}

Enrollment: {punching}/{total_emp} ({enrollment_pct}%)
Devices: {devices_online}/{devices_total} online
Target: 100% by Feb 26 ({days_left} days left)

Issues:
- {not_punching_count} not punching >48h
- {not_enrolled_count} not enrolled
- {wrong_device_count} wrong device
- {ghost_count} ghost Bio IDs

"""

	if drive_link:
		message += f"Details: {drive_link}\n"

	message += "Dashboard: https://my.bebang.ph/dashboard/biometric"

	return message
