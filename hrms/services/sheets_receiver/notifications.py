"""
POS File Failure Notifications via Google Chat (Blip Bot)

Sends real-time alerts to the BEI notification space when:
- Store uploads XLS file (wrong format - should be XLSX)
- Any file fails to process

Also sends daily summary report.

All notifications are tracked in the database for audit trail.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

try:
	from hrms.utils.chat_space_lockdown import route_outbound_chat_space
except ModuleNotFoundError:
	_TRUE_VALUES = {"1", "true", "yes", "on"}

	def route_outbound_chat_space(
		requested_space: str | None,
		*,
		logger=None,
		context: str | None = None,
	) -> str:
		requested = (requested_space or "").strip()
		blip_space = (
			(os.environ.get("BEI_BLIP_NOTIFICATIONS_SPACE") or "").strip() or "spaces/AAQABiNmpBg"
		)
		lockdown_enabled = (os.environ.get("BEI_CHAT_LOCKDOWN_ENABLED") or "true").strip().lower() in _TRUE_VALUES
		allow_non_blip = (
			(os.environ.get("BEI_ALLOW_NON_BLIP_CHAT_DESTINATIONS") or "false").strip().lower()
			in _TRUE_VALUES
		)
		allowed_spaces = {
			space.strip()
			for space in (os.environ.get("BEI_ALLOWED_CHAT_SPACES") or "").split(",")
			if space.strip()
		}

		if not requested:
			return blip_space
		if not lockdown_enabled:
			return requested
		if requested == blip_space:
			return requested
		if allow_non_blip and requested in allowed_spaces:
			return requested
		if logger is not None:
			logger.warning(
				"Outbound Google Chat destination rerouted to ! Blip Notifications; requested=%s effective=%s context=%s",
				requested,
				blip_space,
				context or "unspecified",
			)
		return blip_space

logger = logging.getLogger(__name__)

# Import database for notification tracking
try:
	from .models import get_db
except ImportError:
	# Fallback for when module is run directly
	from models import get_db

# Google Chat Configuration
CREDS_FILE = "/app/credentials/task-manager-service.json"
OPS_SPACE = "spaces/AAAAvDZdY-o"  # Legacy requested space; outbound lockdown reroutes by default.

# User IDs for mentions
DAVE_USER_ID = "115256205642350673118"  # dave@bebang.ph
EDLICE_USER_ID = "104403881698162312500"  # edlice@bebang.ph


def get_chat_service():
	"""Get Google Chat service with bot credentials."""
	creds = service_account.Credentials.from_service_account_file(
		CREDS_FILE, scopes=["https://www.googleapis.com/auth/chat.bot"]
	)
	return build("chat", "v1", credentials=creds)


def _get_target_space() -> str:
	return route_outbound_chat_space(
		OPS_SPACE,
		logger=logger,
		context="hrms.services.sheets_receiver.notifications",
	)


def format_store_name(store_code: str) -> str:
	"""Convert store_code to readable name."""
	return store_code.replace("_", " ").title()


def send_wrong_format_alert(store_code: str, file_name: str, detected_at: str) -> str | None:
	"""
	Send alert when store uploads XLS file (wrong format).

	Args:
	    store_code: Store identifier
	    file_name: Name of the uploaded file
	    detected_at: ISO timestamp when file was detected

	Returns:
	    Message ID if sent successfully, None otherwise
	"""
	try:
		chat = get_chat_service()

		# Parse date
		try:
			dt = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
			date_str = dt.strftime("%Y-%m-%d %H:%M")
		except Exception:
			date_str = detected_at[:16] if detected_at else "Unknown"

		store_name = format_store_name(store_code)

		message = (
			f"*POS File Format Error*\n\n"
			f"*Store:* {store_name}\n"
			f"*File:* `{file_name}`\n"
			f"*Date:* {date_str}\n\n"
			f"Store uploaded XLS format. Please re-export as *XLSX*.\n\n"
			f"<users/{DAVE_USER_ID}> <users/{EDLICE_USER_ID}>"
		)

		result = chat.spaces().messages().create(parent=_get_target_space(), body={"text": message}).execute()

		logger.info(f"Sent wrong format alert for {store_name}: {file_name}")
		return result.get("name")

	except Exception as e:
		logger.error(f"Failed to send wrong format alert: {e}")
		return None


def send_processing_failure_alert(
	store_code: str, file_name: str, error_message: str, detected_at: str
) -> str | None:
	"""
	Send alert when file fails to process (any format).

	Args:
	    store_code: Store identifier
	    file_name: Name of the file
	    error_message: Error that occurred
	    detected_at: ISO timestamp when file was detected

	Returns:
	    Message ID if sent successfully, None otherwise
	"""
	try:
		chat = get_chat_service()

		# Parse date
		try:
			dt = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
			date_str = dt.strftime("%Y-%m-%d %H:%M")
		except Exception:
			date_str = detected_at[:16] if detected_at else "Unknown"

		store_name = format_store_name(store_code)

		# Determine error type
		if "Expected BOF" in error_message or "<div" in error_message:
			error_type = "Wrong Format (XLS exports HTML)"
			action = "Re-export as XLSX format"
		elif "not a zip file" in error_message:
			error_type = "Corrupt File"
			action = "Re-export from POS"
		elif "Cannot detect report type" in error_message:
			error_type = "Unknown Report Type"
			action = "Check filename matches expected pattern"
		else:
			error_type = "Processing Error"
			action = "Investigate file"

		message = (
			f"*POS File Processing Failed*\n\n"
			f"*Store:* {store_name}\n"
			f"*File:* `{file_name}`\n"
			f"*Date:* {date_str}\n"
			f"*Error:* {error_type}\n"
			f"*Action:* {action}\n\n"
			f"<users/{DAVE_USER_ID}> <users/{EDLICE_USER_ID}>"
		)

		result = chat.spaces().messages().create(parent=_get_target_space(), body={"text": message}).execute()

		logger.info(f"Sent processing failure alert for {store_name}: {file_name}")
		return result.get("name")

	except Exception as e:
		logger.error(f"Failed to send processing failure alert: {e}")
		return None


def send_daily_summary(db, report_date: datetime | None = None) -> str | None:
	"""
	Send daily summary report of all failures.

	Args:
	    db: Database connection
	    report_date: Date to report on (defaults to yesterday)

	Returns:
	    Message ID if sent successfully, None otherwise
	"""
	try:
		if report_date is None:
			report_date = datetime.utcnow() - timedelta(days=1)

		date_str = report_date.strftime("%Y-%m-%d")

		# Get failure stats from database
		with db._connection() as conn:
			# Total files by status for the date
			cursor = conn.execute(
				"""
                SELECT status, COUNT(*) as count
                FROM file_queue
                WHERE DATE(detected_at) = ?
                GROUP BY status
            """,
				(date_str,),
			)

			stats = {row["status"]: row["count"] for row in cursor}

			# Failures by store
			cursor = conn.execute(
				"""
                SELECT store_code, COUNT(*) as count
                FROM file_queue
                WHERE DATE(detected_at) = ? AND status = 'failed'
                GROUP BY store_code
                ORDER BY count DESC
                LIMIT 10
            """,
				(date_str,),
			)

			failures_by_store = list(cursor)

			# XLS vs XLSX breakdown
			cursor = conn.execute(
				"""
                SELECT
                    CASE
                        WHEN LOWER(file_name) LIKE '%.xlsx' THEN 'XLSX'
                        WHEN LOWER(file_name) LIKE '%.xls' THEN 'XLS'
                        ELSE 'OTHER'
                    END as format,
                    status,
                    COUNT(*) as count
                FROM file_queue
                WHERE DATE(detected_at) = ?
                GROUP BY format, status
            """,
				(date_str,),
			)

			format_stats = {}
			for row in cursor:
				fmt = row[0]
				if fmt not in format_stats:
					format_stats[fmt] = {"completed": 0, "failed": 0, "pending": 0}
				format_stats[fmt][row[1]] = row[2]

		# Build message
		total = sum(stats.values())
		completed = stats.get("completed", 0)
		failed = stats.get("failed", 0)

		if total == 0:
			message = (
				f"*POS Daily Report - {date_str}*\n\n"
				f"No files processed on this date.\n\n"
				f"<users/{DAVE_USER_ID}> <users/{EDLICE_USER_ID}>"
			)
		else:
			success_rate = (completed / total * 100) if total > 0 else 0

			# Format breakdown
			format_lines = []
			for fmt in ["XLSX", "XLS", "OTHER"]:
				if fmt in format_stats:
					s = format_stats[fmt]
					total_fmt = s["completed"] + s["failed"] + s["pending"]
					rate = (s["completed"] / total_fmt * 100) if total_fmt > 0 else 0
					format_lines.append(f"  {fmt}: {total_fmt} files ({rate:.0f}% success)")

			# Store failures
			store_lines = []
			for row in failures_by_store[:5]:
				store_name = format_store_name(row["store_code"])
				store_lines.append(f"  - {store_name}: {row['count']} failures")

			status_emoji = "" if failed == 0 else ""

			message = (
				f"*POS Daily Report - {date_str}* {status_emoji}\n\n"
				f"*Summary:*\n"
				f"  Total: {total} files\n"
				f"  Completed: {completed}\n"
				f"  Failed: {failed}\n"
				f"  Success Rate: {success_rate:.1f}%\n\n"
				f"*By Format:*\n"
				f"{chr(10).join(format_lines)}\n\n"
			)

			if failed > 0 and store_lines:
				message += f"*Top Failing Stores:*\n" f"{chr(10).join(store_lines)}\n\n"

			if failed > 0:
				message += (
					f"*Action Required:* {failed} files need attention.\n"
					f"Report: https://docs.google.com/spreadsheets/d/1odzIdRNdgNvvXM5FL0TpMif3Cm2kIK5qFgVRQu5bIEc\n\n"
				)

			message += f"<users/{DAVE_USER_ID}> <users/{EDLICE_USER_ID}>"

		chat = get_chat_service()
		result = chat.spaces().messages().create(parent=_get_target_space(), body={"text": message}).execute()

		message_id = result.get("name")
		logger.info(f"Sent daily summary for {date_str}: {message_id}")

		# Log to database for audit trail
		try:
			db.log_notification(
				message_id=message_id, message_type="daily_summary", message_preview=message[:100]
			)
		except Exception as log_error:
			logger.warning(f"Failed to log notification to database: {log_error}")

		return message_id

	except Exception as e:
		logger.error(f"Failed to send daily summary: {e}")
		return None


def send_batch_failure_alert(failures: list[dict[str, Any]]) -> str | None:
	"""
	Send batched alert for multiple failures (to avoid spam).

	Args:
	    failures: List of failure dicts with store_code, file_name, error_message, detected_at

	Returns:
	    Message ID if sent successfully, None otherwise
	"""
	if not failures:
		return None

	try:
		chat = get_chat_service()

		# Group by store
		by_store = {}
		for f in failures:
			store = f["store_code"]
			if store not in by_store:
				by_store[store] = []
			by_store[store].append(f)

		# Count XLS vs other errors
		xls_count = sum(1 for f in failures if f["file_name"].lower().endswith(".xls"))
		other_count = len(failures) - xls_count

		# Build message
		store_lines = []
		for store, files in sorted(by_store.items(), key=lambda x: -len(x[1]))[:5]:
			store_name = format_store_name(store)
			store_lines.append(f"  - {store_name}: {len(files)} files")

		message = f"*POS File Alert - {len(failures)} New Failures*\n\n"

		if xls_count > 0:
			message += f"*Wrong Format (XLS):* {xls_count} files\n"
		if other_count > 0:
			message += f"*Other Errors:* {other_count} files\n"

		message += (
			f"\n*Stores Affected:*\n"
			f"{chr(10).join(store_lines)}\n\n"
			f"<users/{DAVE_USER_ID}> <users/{EDLICE_USER_ID}>"
		)

		result = chat.spaces().messages().create(parent=_get_target_space(), body={"text": message}).execute()

		logger.info(f"Sent batch failure alert for {len(failures)} files")
		return result.get("name")

	except Exception as e:
		logger.error(f"Failed to send batch failure alert: {e}")
		return None


def send_sheets_sync_critical_alert(
	spreadsheet_name: str,
	sheet_name: str,
	trigger: str,
	reasons: list[str],
	rows_processed: int,
	rows_failed: int,
	errors: list[str] | None = None,
	alerts: list[str] | None = None,
) -> str | None:
	"""
	Send critical alert for Sheets sync failures and suspicious change patterns.

	This path is used by the sheet sync pipeline to escalate operational issues
	that can impact finance/store reporting.
	"""
	errors = errors or []
	alerts = alerts or []

	if not (reasons or rows_failed or errors or alerts):
		return None

	reason_map = {
		"sync_exception": "Sync process exception",
		"sync_result_failed": "Frappe sync returned failed status",
		"rows_failed": "One or more rows failed during sync",
		"sync_errors_reported": "Sync result returned error details",
		"suspicious_change_alert": "Suspicious data-change pattern detected",
	}

	try:
		chat = get_chat_service()
		reason_lines = [f"  - {reason_map.get(reason, reason)}" for reason in sorted(set(reasons))]
		error_lines = [f"  - {err}" for err in errors[:3]]
		alert_lines = [f"  - {msg}" for msg in alerts[:3]]

		message_parts = [
			"*SHEETS SYNC CRITICAL ALERT*",
			"",
			f"*Sheet:* {spreadsheet_name} / {sheet_name}",
			f"*Trigger:* {trigger}",
			f"*Rows:* processed={rows_processed}, failed={rows_failed}",
		]

		if reason_lines:
			message_parts.extend(["", "*Reasons:*", *reason_lines])
		if error_lines:
			message_parts.extend(["", "*Top Errors:*", *error_lines])
		if alert_lines:
			message_parts.extend(["", "*Change Alerts:*", *alert_lines])

		message_parts.extend(["", f"<users/{DAVE_USER_ID}> <users/{EDLICE_USER_ID}>"])
		message = "\n".join(message_parts)

		result = (
			chat.spaces()
			.messages()
			.create(
				parent=_get_target_space(),
				body={"text": message},
			)
			.execute()
		)
		message_id = result.get("name")

		# Best-effort audit trail; never block sync path.
		try:
			db = get_db()
			db.log_notification(
				message_id=message_id,
				message_type="sheets_sync_critical",
				message_preview=message[:100],
			)
		except Exception as log_error:
			logger.warning(f"Failed to log critical sync alert to database: {log_error}")

		logger.info(f"Sent sheets sync critical alert for {spreadsheet_name}/{sheet_name}")
		return message_id
	except Exception as e:
		logger.error(f"Failed to send sheets sync critical alert: {e}")
		return None


def delete_notification(message_id: str) -> bool:
	"""
	Delete a notification message from Google Chat.

	Args:
	    message_id: Google Chat message ID (e.g., "spaces/XXX/messages/YYY")

	Returns:
	    True if deletion succeeded
	"""
	try:
		# Get bot credentials with delete permission
		creds = service_account.Credentials.from_service_account_file(
			CREDS_FILE,
			scopes=[
				"https://www.googleapis.com/auth/chat.bot",
				"https://www.googleapis.com/auth/chat.app.delete",
			],
		)
		chat = build("chat", "v1", credentials=creds)

		# Delete the message
		chat.spaces().messages().delete(name=message_id).execute()

		logger.info(f"Deleted notification: {message_id}")

		# Mark as deleted in database
		try:
			db = get_db()
			db.mark_notification_deleted(message_id)
		except Exception as db_error:
			logger.warning(f"Failed to mark notification as deleted in DB: {db_error}")

		return True

	except Exception as e:
		logger.error(f"Failed to delete notification {message_id}: {e}")
		return False


def search_notifications_by_content(
	store_name: str | None = None, file_name: str | None = None, date_str: str | None = None
) -> list[dict[str, Any]]:
	"""
	Search for notifications by content (for screenshot-based identification).

	Args:
	    store_name: Store name from screenshot (e.g., "BF Homes")
	    file_name: File name from screenshot
	    date_str: Date from screenshot (e.g., "2026-02-02")

	Returns:
	    List of matching notification records with message_id for deletion
	"""
	try:
		db = get_db()
		results = db.find_notification_by_content(
			store_name=store_name, file_name=file_name, date_str=date_str
		)

		logger.info(f"Found {len(results)} notifications matching criteria")
		return results

	except Exception as e:
		logger.error(f"Failed to search notifications: {e}")
		return []


def get_notification_history(
	store_code: str | None = None, message_type: str | None = None, days: int = 7
) -> list[dict[str, Any]]:
	"""
	Get notification history.

	Args:
	    store_code: Filter by store code
	    message_type: Filter by type (daily_summary, wrong_format, etc.)
	    days: Number of days to look back

	Returns:
	    List of notification records
	"""
	try:
		db = get_db()
		since = datetime.utcnow() - timedelta(days=days)
		results = db.search_notifications(store_code=store_code, message_type=message_type, since=since)

		return results

	except Exception as e:
		logger.error(f"Failed to get notification history: {e}")
		return []
