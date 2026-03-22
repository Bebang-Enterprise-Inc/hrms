"""
Change processor for Sheets Receiver.

Handles:
- Processing incoming webhook notifications
- Change detection via checksums
- Row-level change tracking (before/after values)
- Syncing changed data to Frappe
- Logging all operations
"""

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from .change_tracker import ChangeReport, ChangeTracker, ChangeType
from .config import (
	SheetConfig,
	get_all_sheet_configs,
	get_config,
	get_sheets_by_spreadsheet_id,
	get_watched_sheets,
)
from .frappe_client import SyncResult, get_frappe_client
from .models import SyncLog, get_db
from .sheets_client import get_sheets_client
from .transforms import transform_sheet_rows

logger = logging.getLogger(__name__)


class ChangeProcessor:
	"""Processes sheet changes and syncs to Frappe."""

	def __init__(self):
		self.config = get_config()
		self.db = get_db()
		self.sheets = get_sheets_client()
		self.frappe = get_frappe_client()
		self.change_tracker = ChangeTracker(self.db)

		# Thread pool for parallel processing
		self._executor = ThreadPoolExecutor(max_workers=4)

	@staticmethod
	def _is_critical_change_alert(alert: str) -> bool:
		"""Return True when a change alert should trigger immediate escalation."""
		alert_text = (alert or "").upper()
		critical_markers = (
			"MASS EDIT",
			"DELETION",
			"FINANCIAL DATA MODIFIED",
			"UNUSUAL PATTERN",
		)
		return any(marker in alert_text for marker in critical_markers)

	def _critical_alerts_suppressed_for_trigger(self, trigger: str) -> bool:
		"""Return True when the current sync trigger should not emit chat alerts."""
		suppressed = {
			str(value).strip()
			for value in getattr(self.config, "suppress_critical_alert_triggers", ())
			if str(value).strip()
		}
		return trigger in suppressed

	def _send_critical_sync_alert(
		self,
		*,
		sheet_config: SheetConfig,
		trigger: str,
		reasons: list[str],
		rows_processed: int,
		rows_failed: int,
		errors: list[str] | None = None,
		critical_alerts: list[str] | None = None,
	) -> None:
		"""Send critical sync alerts to Google Chat (non-blocking)."""
		if not (reasons or rows_failed or errors or critical_alerts):
			return
		if self._critical_alerts_suppressed_for_trigger(trigger):
			logger.info(
				"Critical sync alert suppressed for %s/%s trigger=%s",
				sheet_config.name,
				sheet_config.sheet_name,
				trigger,
			)
			return

		try:
			from .notifications import send_sheets_sync_critical_alert

			send_sheets_sync_critical_alert(
				spreadsheet_name=sheet_config.name,
				sheet_name=sheet_config.sheet_name,
				spreadsheet_id=sheet_config.spreadsheet_id,
				trigger=trigger,
				reasons=reasons,
				rows_processed=rows_processed,
				rows_failed=rows_failed,
				errors=errors or [],
				alerts=critical_alerts or [],
			)
		except Exception as e:
			logger.error(f"Failed to dispatch critical sync alert for {sheet_config.name}: {e}")

	def process_webhook(
		self, spreadsheet_id: str, resource_state: str, channel_id: str | None = None
	) -> SyncLog | None:
		"""
		Process a webhook notification from Google Drive.

		Args:
		    spreadsheet_id: The file that changed
		    resource_state: 'sync', 'change', 'remove', etc.
		    channel_id: Watch channel ID

		Returns:
		    SyncLog if sync was performed
		"""
		# Initial sync notification - just acknowledge
		if resource_state == "sync":
			logger.debug(f"Received sync notification for {spreadsheet_id}")
			return None

		# File deleted - not relevant for us
		if resource_state in ("remove", "trash"):
			logger.warning(f"File {spreadsheet_id} was removed/trashed")
			return None

		# Change notification - process it
		if resource_state == "change":
			matching_sheets = get_sheets_by_spreadsheet_id(spreadsheet_id)

			if not matching_sheets:
				logger.warning(f"Received change for unknown sheet: {spreadsheet_id}")
				return None

			last_log = None
			for _sheet_key, sheet_config in matching_sheets.items():
				logger.info(f"Processing change for {sheet_config.name}")
				last_log = self.sync_sheet(sheet_config, trigger="webhook")
			return last_log

		logger.debug(f"Ignoring resource_state: {resource_state}")
		return None

	@staticmethod
	def _build_bundle_checksum(primary_checksum: str, related_checksums: dict[str, str]) -> str:
		"""Create a stable checksum for sync payloads that include related tabs."""
		if not related_checksums:
			return primary_checksum

		payload = {
			"primary": primary_checksum,
			"related": related_checksums,
		}
		content = json.dumps(payload, sort_keys=True)
		return hashlib.md5(content.encode()).hexdigest()

	def _fetch_related_sheet_payload(
		self, sheet_config: SheetConfig
	) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
		"""Fetch related tabs for logical bundle syncs such as PR/PO/GR parent-child data."""
		related_data: dict[str, list[dict[str, Any]]] = {}
		related_checksums: dict[str, str] = {}
		if not sheet_config.related_sheet_keys:
			return related_data, related_checksums

		all_sheet_configs = get_all_sheet_configs()
		for related_key in sheet_config.related_sheet_keys:
			related_config = all_sheet_configs.get(related_key)
			if not related_config:
				raise ValueError(f"Missing related sheet config: {related_key}")

			range_name = f"{related_config.sheet_name}!{related_config.range}"
			related_rows, related_checksum = self.sheets.fetch_sheet_data(
				related_config.spreadsheet_id, range_name
			)
			related_data[related_key] = related_rows
			related_checksums[related_key] = related_checksum

		return related_data, related_checksums

	@staticmethod
	def _chunk_sheet_rows(
		sheet_config: SheetConfig, data: list[dict[str, Any]]
	) -> list[tuple[str | None, list[dict[str, Any]]]]:
		"""Split large logical sheets into stable sub-payloads when configured."""
		chunk_field = getattr(sheet_config, "sync_chunk_field", None)
		chunk_max_rows = max(0, int(getattr(sheet_config, "sync_chunk_max_rows", 0) or 0))
		if not chunk_field or not data:
			return [(None, data)]

		grouped: dict[str, list[dict[str, Any]]] = {}
		for row in data:
			group_value = str(row.get(chunk_field) or "").strip() or "__empty__"
			grouped.setdefault(group_value, []).append(row)

		chunks: list[tuple[str | None, list[dict[str, Any]]]] = []
		for group_key in sorted(grouped):
			rows = grouped[group_key]
			if chunk_max_rows > 0 and len(rows) > chunk_max_rows:
				for index in range(0, len(rows), chunk_max_rows):
					chunk_number = (index // chunk_max_rows) + 1
					chunks.append((f"{group_key}#{chunk_number}", rows[index : index + chunk_max_rows]))
			else:
				chunks.append((group_key, rows))

		return chunks

	def _sync_sheet_payload(
		self,
		sheet_config: SheetConfig,
		data: list[dict[str, Any]],
		checksum: str,
		*,
		related_data: dict[str, list[dict[str, Any]]] | None = None,
	) -> SyncResult:
		"""Sync a sheet payload, optionally chunked into smaller API calls."""
		chunk_field = getattr(sheet_config, "sync_chunk_field", None)
		chunks = self._chunk_sheet_rows(sheet_config, data)
		if len(chunks) == 1 and chunks[0][0] is None:
			return self.frappe.sync_sheet_data(
				sheet_config,
				data,
				checksum,
				related_data=related_data or None,
			)

		aggregate = SyncResult(success=True)
		for chunk_index, (chunk_key, chunk_rows) in enumerate(chunks, start=1):
			chunk_checksum = checksum
			if len(chunks) > 1:
				chunk_payload = {
					"checksum": checksum,
					"chunk_key": chunk_key,
					"chunk_index": chunk_index,
					"rows": chunk_rows,
				}
				chunk_checksum = hashlib.md5(
					json.dumps(chunk_payload, sort_keys=True, default=str).encode()
				).hexdigest()
			chunk_result = self.frappe.sync_sheet_data(
				sheet_config,
				chunk_rows,
				chunk_checksum,
				related_data=related_data or None,
			)
			aggregate.success = aggregate.success and chunk_result.success
			aggregate.rows_processed += chunk_result.rows_processed or len(chunk_rows)
			aggregate.rows_created += chunk_result.rows_created
			aggregate.rows_updated += chunk_result.rows_updated
			aggregate.rows_failed += chunk_result.rows_failed
			for error in chunk_result.errors or []:
				if chunk_field and chunk_key is not None:
					aggregate.errors.append(f"{chunk_field}={chunk_key}: {error}")
				else:
					aggregate.errors.append(error)

		return aggregate

	def sync_sheet(self, sheet_config: SheetConfig, trigger: str = "manual", force: bool = False) -> SyncLog:
		"""
		Sync a single sheet to Frappe.

		Args:
		    sheet_config: Sheet configuration
		    trigger: What triggered the sync ('webhook', 'manual', 'scheduled')
		    force: If True, sync even if no changes detected

		Returns:
		    SyncLog with results
		"""
		start_time = time.time()
		log = SyncLog(
			spreadsheet_id=sheet_config.spreadsheet_id,
			spreadsheet_name=sheet_config.name,
			sheet_name=sheet_config.sheet_name,
			trigger=trigger,
		)

		change_report = None
		critical_alerts: list[str] = []
		critical_reasons: list[str] = []

		try:
			# Fetch data from Google Sheets
			range_name = f"{sheet_config.sheet_name}!{sheet_config.range}"
			if getattr(sheet_config, "data_transformer", None):
				raw_rows, _raw_checksum = self.sheets.fetch_sheet_values(
					sheet_config.spreadsheet_id, range_name
				)
				data = transform_sheet_rows(sheet_config.data_transformer, raw_rows)
				primary_checksum = self.sheets.compute_checksum(data)
			else:
				data, primary_checksum = self.sheets.fetch_sheet_data(sheet_config.spreadsheet_id, range_name)
			related_data, related_checksums = self._fetch_related_sheet_payload(sheet_config)
			checksum = self._build_bundle_checksum(primary_checksum, related_checksums)

			log.rows_processed = len(data)
			log.data_checksum = checksum

			# Check if data has changed
			if not force and not self.db.has_changed(
				sheet_config.spreadsheet_id, sheet_config.sheet_name, checksum
			):
				log.status = "skipped"
				log.duration_seconds = time.time() - start_time
				logger.info(f"No changes detected for {sheet_config.name}, skipping sync")
				self.db.log_sync(log)
				return log

			# ========================================
			# ROW-LEVEL CHANGE TRACKING
			# Detects edits to existing rows vs new rows
			# ========================================
			change_report = self.change_tracker.compute_changes(
				spreadsheet_id=sheet_config.spreadsheet_id,
				spreadsheet_name=sheet_config.name,
				sheet_name=sheet_config.sheet_name,
				new_data=data,
				key_column=sheet_config.key_column,
			)

			# Log change summary
			logger.info(
				f"Change tracking for {sheet_config.name}: "
				f"{change_report.rows_added} added, {change_report.rows_modified} modified, "
				f"{change_report.rows_deleted} deleted, {change_report.rows_unchanged} unchanged"
			)

			# Log any alerts (suspicious patterns)
			for alert in change_report.alerts:
				logger.warning(f"ALERT: {alert}")
				if self._is_critical_change_alert(alert):
					critical_alerts.append(alert)

			# Sync to Frappe
			result = self._sync_sheet_payload(
				sheet_config,
				data,
				checksum,
				related_data=related_data or None,
			)

			log.status = "success" if result.success else "failed"
			log.rows_created = result.rows_created
			log.rows_updated = result.rows_updated
			log.rows_failed = result.rows_failed
			if result.errors:
				log.error_message = "; ".join(result.errors[:5])  # First 5 errors

			if not result.success:
				critical_reasons.append("sync_result_failed")
			if log.rows_failed > 0:
				critical_reasons.append("rows_failed")
			if result.errors:
				critical_reasons.append("sync_errors_reported")

			if critical_alerts or critical_reasons:
				self._send_critical_sync_alert(
					sheet_config=sheet_config,
					trigger=trigger,
					reasons=sorted(
						set(critical_reasons + (["suspicious_change_alert"] if critical_alerts else []))
					),
					rows_processed=log.rows_processed,
					rows_failed=log.rows_failed,
					errors=result.errors,
					critical_alerts=critical_alerts,
				)

			# Update checksum on success
			if result.success:
				self.db.save_checksum(
					sheet_config.spreadsheet_id, sheet_config.sheet_name, checksum, len(data)
				)

			logger.info(
				f"Synced {sheet_config.name}: "
				f"{log.rows_created} created, {log.rows_updated} updated, "
				f"{log.rows_failed} failed"
			)

		except Exception as e:
			log.status = "failed"
			log.error_message = str(e)
			logger.error(f"Failed to sync {sheet_config.name}: {e}")
			self._send_critical_sync_alert(
				sheet_config=sheet_config,
				trigger=trigger,
				reasons=["sync_exception"],
				rows_processed=log.rows_processed,
				rows_failed=max(log.rows_failed, 1),
				errors=[str(e)],
				critical_alerts=critical_alerts,
			)

		finally:
			log.duration_seconds = time.time() - start_time
			self.db.log_sync(log)

		return log

	def sync_all_sheets(self, trigger: str = "scheduled", force: bool = False):
		"""
		Sync all configured sheets.

		Args:
		    trigger: What triggered the sync
		    force: If True, sync even if no changes
		"""
		sheets = get_watched_sheets()
		results = []

		for _key, sheet_config in sheets.items():
			try:
				log = self.sync_sheet(sheet_config, trigger=trigger, force=force)
				results.append(log)
			except Exception as e:
				logger.error(f"Error syncing {sheet_config.name}: {e}")

		# Log summary
		success = sum(1 for r in results if r.status == "success")
		skipped = sum(1 for r in results if r.status == "skipped")
		failed = sum(1 for r in results if r.status == "failed")

		logger.info(f"Sync complete: {success} success, {skipped} skipped, {failed} failed")

		return results

	def check_and_sync_changed(self):
		"""
		Check all sheets for changes and sync if needed.

		This is an alternative to webhooks - poll for changes.
		"""
		sheets = get_watched_sheets()

		for _key, sheet_config in sheets.items():
			try:
				# Check if file was modified since last sync
				last_sync = self.db.get_checksum(sheet_config.spreadsheet_id, sheet_config.sheet_name)

				# If we have no record or file was modified, sync
				if last_sync is None:
					logger.info(f"No sync record for {sheet_config.name}, syncing...")
					self.sync_sheet(sheet_config, trigger="scheduled")

			except Exception as e:
				logger.error(f"Error checking {sheet_config.name}: {e}")

	# ========================================
	# CHANGE TRACKING API METHODS
	# ========================================

	def get_recent_changes(
		self, spreadsheet_id: str | None = None, limit: int = 100, change_type: str | None = None
	) -> list[dict]:
		"""
		Get recent row-level changes.

		Args:
		    spreadsheet_id: Filter by spreadsheet (optional)
		    limit: Max records to return
		    change_type: Filter by type (added, modified, deleted)

		Returns:
		    List of change records with before/after values
		"""
		return self.change_tracker.get_recent_changes(
			spreadsheet_id=spreadsheet_id, limit=limit, change_type=change_type
		)

	def get_unacknowledged_alerts(self) -> list[dict]:
		"""Get alerts that haven't been acknowledged."""
		return self.change_tracker.get_unacknowledged_alerts()

	def acknowledge_alert(self, alert_id: int) -> bool:
		"""
		Mark an alert as acknowledged.

		Args:
		    alert_id: The alert ID to acknowledge

		Returns:
		    True if acknowledged successfully
		"""
		try:
			self.change_tracker.acknowledge_alert(alert_id)
			return True
		except Exception as e:
			logger.error(f"Error acknowledging alert {alert_id}: {e}")
			return False

	def get_change_summary(self, spreadsheet_id: str | None = None, days: int = 7) -> dict:
		"""
		Get summary of changes over time.

		Args:
		    spreadsheet_id: Filter by spreadsheet (optional)
		    days: How many days to look back

		Returns:
		    Summary with counts by type
		"""
		from datetime import timedelta

		cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

		with self.db._connection() as conn:
			query = """
                SELECT
                    change_type,
                    COUNT(*) as count
                FROM change_logs
                WHERE created_at >= ?
            """
			params = [cutoff]

			if spreadsheet_id:
				query += " AND spreadsheet_id = ?"
				params.append(spreadsheet_id)

			query += " GROUP BY change_type"

			rows = conn.execute(query, params).fetchall()

			summary = {"added": 0, "modified": 0, "deleted": 0, "period_days": days}

			for row in rows:
				if row["change_type"] in summary:
					summary[row["change_type"]] = row["count"]

			summary["total"] = summary["added"] + summary["modified"] + summary["deleted"]

			return summary


# Singleton instance
_processor: ChangeProcessor | None = None


def get_processor() -> ChangeProcessor:
	"""Get processor instance."""
	global _processor
	if _processor is None:
		_processor = ChangeProcessor()
	return _processor
