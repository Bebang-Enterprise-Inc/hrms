"""
Change processor for Sheets Receiver.

Handles:
- Processing incoming webhook notifications
- Change detection via checksums
- Row-level change tracking (before/after values)
- Syncing changed data to Frappe
- Logging all operations
"""

import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

from .config import get_config, get_sheet_by_spreadsheet_id, get_watched_sheets, SheetConfig
from .models import SyncLog, get_db
from .sheets_client import get_sheets_client
from .frappe_client import get_frappe_client, SyncResult
from .change_tracker import ChangeTracker, ChangeReport, ChangeType

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

    def process_webhook(
        self,
        spreadsheet_id: str,
        resource_state: str,
        channel_id: str = None
    ) -> Optional[SyncLog]:
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
        if resource_state == 'sync':
            logger.debug(f"Received sync notification for {spreadsheet_id}")
            return None

        # File deleted - not relevant for us
        if resource_state in ('remove', 'trash'):
            logger.warning(f"File {spreadsheet_id} was removed/trashed")
            return None

        # Change notification - process it
        if resource_state == 'change':
            sheet_config = get_sheet_by_spreadsheet_id(spreadsheet_id)

            if not sheet_config:
                logger.warning(f"Received change for unknown sheet: {spreadsheet_id}")
                return None

            logger.info(f"Processing change for {sheet_config.name}")
            return self.sync_sheet(sheet_config, trigger='webhook')

        logger.debug(f"Ignoring resource_state: {resource_state}")
        return None

    def sync_sheet(
        self,
        sheet_config: SheetConfig,
        trigger: str = 'manual',
        force: bool = False
    ) -> SyncLog:
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
            trigger=trigger
        )

        change_report = None

        try:
            # Fetch data from Google Sheets
            range_name = f"{sheet_config.sheet_name}!{sheet_config.range}"
            data, checksum = self.sheets.fetch_sheet_data(
                sheet_config.spreadsheet_id,
                range_name
            )

            log.rows_processed = len(data)
            log.data_checksum = checksum

            # Check if data has changed
            if not force and not self.db.has_changed(
                sheet_config.spreadsheet_id,
                sheet_config.sheet_name,
                checksum
            ):
                log.status = 'skipped'
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
                key_column=sheet_config.key_column
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
                # TODO: Send to Google Chat if critical

            # Sync to Frappe
            result = self.frappe.sync_sheet_data(sheet_config, data, checksum)

            log.status = 'success' if result.success else 'failed'
            log.rows_created = result.rows_created
            log.rows_updated = result.rows_updated
            log.rows_failed = result.rows_failed
            if result.errors:
                log.error_message = '; '.join(result.errors[:5])  # First 5 errors

            # Update checksum on success
            if result.success:
                self.db.save_checksum(
                    sheet_config.spreadsheet_id,
                    sheet_config.sheet_name,
                    checksum,
                    len(data)
                )

            logger.info(
                f"Synced {sheet_config.name}: "
                f"{log.rows_created} created, {log.rows_updated} updated, "
                f"{log.rows_failed} failed"
            )

        except Exception as e:
            log.status = 'failed'
            log.error_message = str(e)
            logger.error(f"Failed to sync {sheet_config.name}: {e}")

        finally:
            log.duration_seconds = time.time() - start_time
            self.db.log_sync(log)

        return log

    def sync_all_sheets(self, trigger: str = 'scheduled', force: bool = False):
        """
        Sync all configured sheets.

        Args:
            trigger: What triggered the sync
            force: If True, sync even if no changes
        """
        sheets = get_watched_sheets()
        results = []

        for key, sheet_config in sheets.items():
            try:
                log = self.sync_sheet(sheet_config, trigger=trigger, force=force)
                results.append(log)
            except Exception as e:
                logger.error(f"Error syncing {sheet_config.name}: {e}")

        # Log summary
        success = sum(1 for r in results if r.status == 'success')
        skipped = sum(1 for r in results if r.status == 'skipped')
        failed = sum(1 for r in results if r.status == 'failed')

        logger.info(f"Sync complete: {success} success, {skipped} skipped, {failed} failed")

        return results

    def check_and_sync_changed(self):
        """
        Check all sheets for changes and sync if needed.

        This is an alternative to webhooks - poll for changes.
        """
        sheets = get_watched_sheets()

        for key, sheet_config in sheets.items():
            try:
                # Check if file was modified since last sync
                last_sync = self.db.get_checksum(
                    sheet_config.spreadsheet_id,
                    sheet_config.sheet_name
                )

                modified_time = self.sheets.get_file_modified_time(
                    sheet_config.spreadsheet_id
                )

                # If we have no record or file was modified, sync
                if last_sync is None:
                    logger.info(f"No sync record for {sheet_config.name}, syncing...")
                    self.sync_sheet(sheet_config, trigger='scheduled')

            except Exception as e:
                logger.error(f"Error checking {sheet_config.name}: {e}")

    # ========================================
    # CHANGE TRACKING API METHODS
    # ========================================

    def get_recent_changes(
        self,
        spreadsheet_id: str = None,
        limit: int = 100,
        change_type: str = None
    ) -> List[Dict]:
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
            spreadsheet_id=spreadsheet_id,
            limit=limit,
            change_type=change_type
        )

    def get_unacknowledged_alerts(self) -> List[Dict]:
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

    def get_change_summary(self, spreadsheet_id: str = None, days: int = 7) -> Dict:
        """
        Get summary of changes over time.

        Args:
            spreadsheet_id: Filter by spreadsheet (optional)
            days: How many days to look back

        Returns:
            Summary with counts by type
        """
        from datetime import datetime, timedelta

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

            summary = {
                'added': 0,
                'modified': 0,
                'deleted': 0,
                'period_days': days
            }

            for row in rows:
                if row['change_type'] in summary:
                    summary[row['change_type']] = row['count']

            summary['total'] = summary['added'] + summary['modified'] + summary['deleted']

            return summary


# Singleton instance
_processor: Optional[ChangeProcessor] = None


def get_processor() -> ChangeProcessor:
    """Get processor instance."""
    global _processor
    if _processor is None:
        _processor = ChangeProcessor()
    return _processor
