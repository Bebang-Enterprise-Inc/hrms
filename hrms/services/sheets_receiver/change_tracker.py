"""
Row-level change tracking for Sheets Receiver.

Detects and logs:
- New rows added
- Existing rows modified (with before/after values)
- Rows deleted
- Suspicious patterns (e.g., many rows modified at once)

Designed to catch when team members edit existing records instead of creating new ones.
"""

import json
import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNCHANGED = "unchanged"


@dataclass
class RowChange:
    """Represents a change to a single row."""
    change_type: ChangeType
    row_key: str  # Unique identifier for the row
    row_number: int  # Excel row number (for reference)
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    changed_fields: Optional[List[str]] = None  # Which columns changed

    def to_dict(self) -> Dict:
        return {
            'change_type': self.change_type.value,
            'row_key': self.row_key,
            'row_number': self.row_number,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'changed_fields': self.changed_fields
        }


@dataclass
class ChangeReport:
    """Summary of all changes in a sync."""
    spreadsheet_id: str
    spreadsheet_name: str
    sheet_name: str
    timestamp: datetime
    total_rows_before: int
    total_rows_after: int
    rows_added: int
    rows_modified: int
    rows_deleted: int
    rows_unchanged: int
    changes: List[RowChange]
    alerts: List[str]  # Suspicious patterns detected

    def to_dict(self) -> Dict:
        return {
            'spreadsheet_id': self.spreadsheet_id,
            'spreadsheet_name': self.spreadsheet_name,
            'sheet_name': self.sheet_name,
            'timestamp': self.timestamp.isoformat(),
            'total_rows_before': self.total_rows_before,
            'total_rows_after': self.total_rows_after,
            'rows_added': self.rows_added,
            'rows_modified': self.rows_modified,
            'rows_deleted': self.rows_deleted,
            'rows_unchanged': self.rows_unchanged,
            'changes': [c.to_dict() for c in self.changes],
            'alerts': self.alerts
        }


class ChangeTracker:
    """
    Tracks row-level changes between sync operations.

    Stores previous data snapshots and computes diffs.
    """

    def __init__(self, db):
        self.db = db
        self._init_tables()

    def _init_tables(self):
        """Create change tracking tables."""
        with self.db._connection() as conn:
            conn.executescript("""
                -- Store previous data snapshots
                CREATE TABLE IF NOT EXISTS data_snapshots (
                    spreadsheet_id TEXT NOT NULL,
                    sheet_name TEXT NOT NULL,
                    row_key TEXT NOT NULL,
                    row_number INTEGER,
                    row_data TEXT NOT NULL,  -- JSON
                    row_hash TEXT NOT NULL,
                    snapshot_time TEXT NOT NULL,
                    PRIMARY KEY (spreadsheet_id, sheet_name, row_key)
                );

                -- Log all changes
                CREATE TABLE IF NOT EXISTS change_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spreadsheet_id TEXT NOT NULL,
                    spreadsheet_name TEXT,
                    sheet_name TEXT,
                    change_type TEXT NOT NULL,  -- added, modified, deleted
                    row_key TEXT NOT NULL,
                    row_number INTEGER,
                    old_values TEXT,  -- JSON
                    new_values TEXT,  -- JSON
                    changed_fields TEXT,  -- JSON array
                    created_at TEXT NOT NULL
                );

                -- Alerts for suspicious activity
                CREATE TABLE IF NOT EXISTS change_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spreadsheet_id TEXT NOT NULL,
                    spreadsheet_name TEXT,
                    sheet_name TEXT,
                    alert_type TEXT NOT NULL,
                    alert_message TEXT NOT NULL,
                    details TEXT,  -- JSON
                    acknowledged INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_change_logs_time
                ON change_logs(spreadsheet_id, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_change_alerts_unack
                ON change_alerts(acknowledged, created_at DESC);
            """)

    def compute_changes(
        self,
        spreadsheet_id: str,
        spreadsheet_name: str,
        sheet_name: str,
        new_data: List[Dict[str, Any]],
        key_column: str
    ) -> ChangeReport:
        """
        Compare new data with stored snapshot and compute changes.

        Args:
            spreadsheet_id: Google Spreadsheet ID
            spreadsheet_name: Human-readable name
            sheet_name: Tab name
            new_data: Current data from sheet
            key_column: Column to use as unique row identifier

        Returns:
            ChangeReport with all detected changes
        """
        timestamp = datetime.utcnow()

        # Get previous snapshot
        old_data = self._get_snapshot(spreadsheet_id, sheet_name)

        # Build lookup by key
        old_by_key = {row.get(key_column): row for row in old_data if row.get(key_column)}
        new_by_key = {row.get(key_column): row for row in new_data if row.get(key_column)}

        changes = []
        alerts = []

        # Find added and modified rows
        for row_num, row in enumerate(new_data, start=2):  # Start at 2 (row 1 is header)
            key = row.get(key_column)
            if not key:
                continue

            if key not in old_by_key:
                # New row
                changes.append(RowChange(
                    change_type=ChangeType.ADDED,
                    row_key=str(key),
                    row_number=row_num,
                    new_values=row
                ))
            else:
                # Check if modified
                old_row = old_by_key[key]
                changed_fields = self._get_changed_fields(old_row, row)

                if changed_fields:
                    changes.append(RowChange(
                        change_type=ChangeType.MODIFIED,
                        row_key=str(key),
                        row_number=row_num,
                        old_values=old_row,
                        new_values=row,
                        changed_fields=changed_fields
                    ))

        # Find deleted rows
        for key, old_row in old_by_key.items():
            if key not in new_by_key:
                changes.append(RowChange(
                    change_type=ChangeType.DELETED,
                    row_key=str(key),
                    row_number=0,  # Unknown
                    old_values=old_row
                ))

        # Count by type
        added = sum(1 for c in changes if c.change_type == ChangeType.ADDED)
        modified = sum(1 for c in changes if c.change_type == ChangeType.MODIFIED)
        deleted = sum(1 for c in changes if c.change_type == ChangeType.DELETED)
        unchanged = len(new_data) - added - modified

        # Detect suspicious patterns
        alerts = self._detect_suspicious_patterns(
            spreadsheet_name, sheet_name,
            added, modified, deleted,
            len(old_data), len(new_data),
            changes
        )

        report = ChangeReport(
            spreadsheet_id=spreadsheet_id,
            spreadsheet_name=spreadsheet_name,
            sheet_name=sheet_name,
            timestamp=timestamp,
            total_rows_before=len(old_data),
            total_rows_after=len(new_data),
            rows_added=added,
            rows_modified=modified,
            rows_deleted=deleted,
            rows_unchanged=unchanged,
            changes=changes,
            alerts=alerts
        )

        # Log changes to database
        self._log_changes(report)

        # Save new snapshot
        self._save_snapshot(spreadsheet_id, sheet_name, new_data, key_column)

        return report

    def _get_changed_fields(
        self,
        old_row: Dict[str, Any],
        new_row: Dict[str, Any]
    ) -> List[str]:
        """Find which fields changed between old and new row."""
        changed = []
        all_keys = set(old_row.keys()) | set(new_row.keys())

        for key in all_keys:
            old_val = old_row.get(key)
            new_val = new_row.get(key)

            # Normalize for comparison
            if self._normalize_value(old_val) != self._normalize_value(new_val):
                changed.append(key)

        return changed

    def _normalize_value(self, val: Any) -> str:
        """Normalize value for comparison."""
        if val is None:
            return ""
        if isinstance(val, float):
            return f"{val:.2f}"
        return str(val).strip()

    def _detect_suspicious_patterns(
        self,
        spreadsheet_name: str,
        sheet_name: str,
        added: int,
        modified: int,
        deleted: int,
        old_count: int,
        new_count: int,
        changes: List[RowChange]
    ) -> List[str]:
        """
        Detect patterns that might indicate data issues.

        Returns list of alert messages.
        """
        alerts = []

        # Alert: Many rows modified at once (possible mass edit)
        if modified > 10 and old_count > 0:
            pct = (modified / old_count) * 100
            if pct > 20:
                alerts.append(
                    f"⚠️ MASS EDIT: {modified} rows ({pct:.0f}%) modified in {spreadsheet_name}/{sheet_name}. "
                    f"Expected new rows, but existing data was changed."
                )

        # Alert: Rows deleted
        if deleted > 0:
            alerts.append(
                f"🗑️ DELETION: {deleted} rows removed from {spreadsheet_name}/{sheet_name}."
            )

        # Alert: Key financial fields changed
        financial_fields = ['amount', 'balance', 'outstanding', 'total', 'net', 'gross', 'payment', 'qty', 'quantity']
        financial_changes = []
        for change in changes:
            if change.change_type == ChangeType.MODIFIED and change.changed_fields:
                for field in change.changed_fields:
                    if any(ff in field.lower() for ff in financial_fields):
                        financial_changes.append(change)
                        break

        if financial_changes:
            alerts.append(
                f"💰 FINANCIAL DATA MODIFIED: {len(financial_changes)} rows with amount/balance changes in {spreadsheet_name}/{sheet_name}."
            )

        # Alert: More modifications than additions
        if modified > added and modified > 5:
            alerts.append(
                f"⚠️ UNUSUAL PATTERN: More modifications ({modified}) than additions ({added}) in {spreadsheet_name}/{sheet_name}. "
                f"Team may be editing existing records instead of adding new ones."
            )

        return alerts

    def _get_snapshot(self, spreadsheet_id: str, sheet_name: str) -> List[Dict]:
        """Get previous data snapshot."""
        with self.db._connection() as conn:
            rows = conn.execute("""
                SELECT row_data FROM data_snapshots
                WHERE spreadsheet_id = ? AND sheet_name = ?
            """, (spreadsheet_id, sheet_name)).fetchall()

            return [json.loads(row['row_data']) for row in rows]

    def _save_snapshot(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        data: List[Dict],
        key_column: str
    ):
        """Save current data as snapshot for next comparison."""
        timestamp = datetime.utcnow().isoformat()

        with self.db._connection() as conn:
            # Clear old snapshot
            conn.execute("""
                DELETE FROM data_snapshots
                WHERE spreadsheet_id = ? AND sheet_name = ?
            """, (spreadsheet_id, sheet_name))

            # Save new snapshot
            for row_num, row in enumerate(data, start=2):
                key = row.get(key_column)
                if not key:
                    continue

                row_json = json.dumps(row, default=str)
                row_hash = hashlib.md5(row_json.encode()).hexdigest()

                conn.execute("""
                    INSERT INTO data_snapshots
                    (spreadsheet_id, sheet_name, row_key, row_number, row_data, row_hash, snapshot_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (spreadsheet_id, sheet_name, str(key), row_num, row_json, row_hash, timestamp))

    def _log_changes(self, report: ChangeReport):
        """Log all changes to database."""
        timestamp = report.timestamp.isoformat()

        with self.db._connection() as conn:
            for change in report.changes:
                conn.execute("""
                    INSERT INTO change_logs
                    (spreadsheet_id, spreadsheet_name, sheet_name, change_type,
                     row_key, row_number, old_values, new_values, changed_fields, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report.spreadsheet_id,
                    report.spreadsheet_name,
                    report.sheet_name,
                    change.change_type.value,
                    change.row_key,
                    change.row_number,
                    json.dumps(change.old_values, default=str) if change.old_values else None,
                    json.dumps(change.new_values, default=str) if change.new_values else None,
                    json.dumps(change.changed_fields) if change.changed_fields else None,
                    timestamp
                ))

            # Log alerts
            for alert in report.alerts:
                conn.execute("""
                    INSERT INTO change_alerts
                    (spreadsheet_id, spreadsheet_name, sheet_name, alert_type,
                     alert_message, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    report.spreadsheet_id,
                    report.spreadsheet_name,
                    report.sheet_name,
                    'suspicious_pattern',
                    alert,
                    timestamp
                ))

    def get_recent_changes(
        self,
        spreadsheet_id: str = None,
        limit: int = 100,
        change_type: str = None
    ) -> List[Dict]:
        """Get recent change logs."""
        with self.db._connection() as conn:
            query = "SELECT * FROM change_logs WHERE 1=1"
            params = []

            if spreadsheet_id:
                query += " AND spreadsheet_id = ?"
                params.append(spreadsheet_id)

            if change_type:
                query += " AND change_type = ?"
                params.append(change_type)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()

            return [
                {
                    'id': row['id'],
                    'spreadsheet_name': row['spreadsheet_name'],
                    'sheet_name': row['sheet_name'],
                    'change_type': row['change_type'],
                    'row_key': row['row_key'],
                    'row_number': row['row_number'],
                    'old_values': json.loads(row['old_values']) if row['old_values'] else None,
                    'new_values': json.loads(row['new_values']) if row['new_values'] else None,
                    'changed_fields': json.loads(row['changed_fields']) if row['changed_fields'] else None,
                    'created_at': row['created_at']
                }
                for row in rows
            ]

    def get_unacknowledged_alerts(self) -> List[Dict]:
        """Get alerts that haven't been acknowledged."""
        with self.db._connection() as conn:
            rows = conn.execute("""
                SELECT * FROM change_alerts
                WHERE acknowledged = 0
                ORDER BY created_at DESC
            """).fetchall()

            return [
                {
                    'id': row['id'],
                    'spreadsheet_name': row['spreadsheet_name'],
                    'sheet_name': row['sheet_name'],
                    'alert_type': row['alert_type'],
                    'alert_message': row['alert_message'],
                    'created_at': row['created_at']
                }
                for row in rows
            ]

    def acknowledge_alert(self, alert_id: int):
        """Mark an alert as acknowledged."""
        with self.db._connection() as conn:
            conn.execute(
                "UPDATE change_alerts SET acknowledged = 1 WHERE id = ?",
                (alert_id,)
            )
