"""
Database models for Sheets Receiver Service.

Uses SQLite for persistent storage of:
- Watch channels (for renewal management)
- Sync logs (audit trail)
- Data checksums (change detection)
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from .config import get_config


@dataclass
class WatchChannel:
    """Google Drive watch channel."""
    channel_id: str
    spreadsheet_id: str
    spreadsheet_name: str
    resource_id: str
    expiration: datetime
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expiration

    @property
    def hours_until_expiry(self) -> float:
        delta = self.expiration - datetime.utcnow()
        return delta.total_seconds() / 3600


@dataclass
class SyncLog:
    """Record of a sync operation."""
    id: int = None
    spreadsheet_id: str = None
    spreadsheet_name: str = None
    sheet_name: str = None
    trigger: str = None  # 'webhook', 'manual', 'scheduled'
    status: str = None  # 'success', 'failed', 'skipped'
    rows_processed: int = 0
    rows_created: int = 0
    rows_updated: int = 0
    rows_failed: int = 0
    error_message: str = None
    duration_seconds: float = 0
    data_checksum: str = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class DataChecksum:
    """Checksum for change detection."""
    spreadsheet_id: str
    sheet_name: str
    checksum: str
    row_count: int
    last_synced: datetime


class Database:
    """SQLite database for Sheets Receiver."""

    def __init__(self, db_path: str = None):
        config = get_config()
        self.db_path = db_path or config.db_path

        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS watch_channels (
                    channel_id TEXT PRIMARY KEY,
                    spreadsheet_id TEXT NOT NULL,
                    spreadsheet_name TEXT,
                    resource_id TEXT,
                    expiration TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sync_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spreadsheet_id TEXT NOT NULL,
                    spreadsheet_name TEXT,
                    sheet_name TEXT,
                    trigger TEXT,
                    status TEXT,
                    rows_processed INTEGER DEFAULT 0,
                    rows_created INTEGER DEFAULT 0,
                    rows_updated INTEGER DEFAULT 0,
                    rows_failed INTEGER DEFAULT 0,
                    error_message TEXT,
                    duration_seconds REAL DEFAULT 0,
                    data_checksum TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS data_checksums (
                    spreadsheet_id TEXT NOT NULL,
                    sheet_name TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    row_count INTEGER DEFAULT 0,
                    last_synced TEXT NOT NULL,
                    PRIMARY KEY (spreadsheet_id, sheet_name)
                );

                CREATE INDEX IF NOT EXISTS idx_sync_logs_spreadsheet
                ON sync_logs(spreadsheet_id, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_watch_expiration
                ON watch_channels(expiration);

                -- Folder watch tables (POS file processing)
                CREATE TABLE IF NOT EXISTS folder_watches (
                    channel_id TEXT PRIMARY KEY,
                    folder_id TEXT NOT NULL,
                    folder_name TEXT,
                    store_code TEXT,
                    resource_id TEXT,
                    expiration TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS file_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    folder_id TEXT NOT NULL,
                    store_code TEXT,
                    mime_type TEXT,
                    file_size INTEGER,
                    md5_checksum TEXT,
                    status TEXT DEFAULT 'pending',
                    detected_at TEXT NOT NULL,
                    processed_at TEXT,
                    error_message TEXT,
                    record_count INTEGER DEFAULT 0,
                    report_type TEXT
                );

                CREATE TABLE IF NOT EXISTS processed_files (
                    file_id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    folder_id TEXT NOT NULL,
                    store_code TEXT,
                    md5_checksum TEXT,
                    processed_at TEXT NOT NULL,
                    record_count INTEGER DEFAULT 0,
                    report_type TEXT,
                    extracted_data TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_folder_watch_expiration
                ON folder_watches(expiration);

                CREATE INDEX IF NOT EXISTS idx_file_queue_status
                ON file_queue(status, detected_at);

                CREATE INDEX IF NOT EXISTS idx_processed_files_store
                ON processed_files(store_code, processed_at DESC);
            """)

    @contextmanager
    def _connection(self):
        """Context manager for database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # Watch Channels
    def save_watch(self, watch: WatchChannel):
        """Save or update a watch channel."""
        with self._connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO watch_channels
                (channel_id, spreadsheet_id, spreadsheet_name, resource_id, expiration, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                watch.channel_id,
                watch.spreadsheet_id,
                watch.spreadsheet_name,
                watch.resource_id,
                watch.expiration.isoformat(),
                watch.created_at.isoformat()
            ))

    def get_watch(self, spreadsheet_id: str) -> Optional[WatchChannel]:
        """Get watch channel by spreadsheet ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM watch_channels WHERE spreadsheet_id = ?",
                (spreadsheet_id,)
            ).fetchone()

            if row:
                return WatchChannel(
                    channel_id=row['channel_id'],
                    spreadsheet_id=row['spreadsheet_id'],
                    spreadsheet_name=row['spreadsheet_name'],
                    resource_id=row['resource_id'],
                    expiration=datetime.fromisoformat(row['expiration']),
                    created_at=datetime.fromisoformat(row['created_at'])
                )
        return None

    def get_expiring_watches(self, hours: int = 2) -> List[WatchChannel]:
        """Get watches expiring within given hours."""
        cutoff = datetime.utcnow()
        with self._connection() as conn:
            rows = conn.execute("""
                SELECT * FROM watch_channels
                WHERE expiration <= datetime(?, '+' || ? || ' hours')
            """, (cutoff.isoformat(), hours)).fetchall()

            return [
                WatchChannel(
                    channel_id=row['channel_id'],
                    spreadsheet_id=row['spreadsheet_id'],
                    spreadsheet_name=row['spreadsheet_name'],
                    resource_id=row['resource_id'],
                    expiration=datetime.fromisoformat(row['expiration']),
                    created_at=datetime.fromisoformat(row['created_at'])
                )
                for row in rows
            ]

    def delete_watch(self, channel_id: str):
        """Delete a watch channel."""
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM watch_channels WHERE channel_id = ?",
                (channel_id,)
            )

    # Sync Logs
    def log_sync(self, log: SyncLog) -> int:
        """Log a sync operation. Returns log ID."""
        with self._connection() as conn:
            cursor = conn.execute("""
                INSERT INTO sync_logs
                (spreadsheet_id, spreadsheet_name, sheet_name, trigger, status,
                 rows_processed, rows_created, rows_updated, rows_failed,
                 error_message, duration_seconds, data_checksum, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log.spreadsheet_id,
                log.spreadsheet_name,
                log.sheet_name,
                log.trigger,
                log.status,
                log.rows_processed,
                log.rows_created,
                log.rows_updated,
                log.rows_failed,
                log.error_message,
                log.duration_seconds,
                log.data_checksum,
                log.created_at.isoformat()
            ))
            return cursor.lastrowid

    def get_recent_syncs(self, limit: int = 50) -> List[SyncLog]:
        """Get recent sync logs."""
        with self._connection() as conn:
            rows = conn.execute("""
                SELECT * FROM sync_logs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

            return [
                SyncLog(
                    id=row['id'],
                    spreadsheet_id=row['spreadsheet_id'],
                    spreadsheet_name=row['spreadsheet_name'],
                    sheet_name=row['sheet_name'],
                    trigger=row['trigger'],
                    status=row['status'],
                    rows_processed=row['rows_processed'],
                    rows_created=row['rows_created'],
                    rows_updated=row['rows_updated'],
                    rows_failed=row['rows_failed'],
                    error_message=row['error_message'],
                    duration_seconds=row['duration_seconds'],
                    data_checksum=row['data_checksum'],
                    created_at=datetime.fromisoformat(row['created_at'])
                )
                for row in rows
            ]

    # Checksums
    def get_checksum(self, spreadsheet_id: str, sheet_name: str) -> Optional[str]:
        """Get stored checksum for a sheet."""
        with self._connection() as conn:
            row = conn.execute("""
                SELECT checksum FROM data_checksums
                WHERE spreadsheet_id = ? AND sheet_name = ?
            """, (spreadsheet_id, sheet_name)).fetchone()

            return row['checksum'] if row else None

    def save_checksum(self, spreadsheet_id: str, sheet_name: str, checksum: str, row_count: int):
        """Save checksum after successful sync."""
        with self._connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO data_checksums
                (spreadsheet_id, sheet_name, checksum, row_count, last_synced)
                VALUES (?, ?, ?, ?, ?)
            """, (spreadsheet_id, sheet_name, checksum, row_count, datetime.utcnow().isoformat()))

    def has_changed(self, spreadsheet_id: str, sheet_name: str, new_checksum: str) -> bool:
        """Check if data has changed since last sync."""
        stored = self.get_checksum(spreadsheet_id, sheet_name)
        return stored != new_checksum

    # =========================================================================
    # Folder Watches (POS file processing)
    # =========================================================================

    def save_folder_watch(self, watch: Dict[str, Any]):
        """Save or update a folder watch channel."""
        with self._connection() as conn:
            expiration = watch['expiration']
            if isinstance(expiration, datetime):
                expiration = expiration.isoformat()

            created_at = watch.get('created_at', datetime.utcnow())
            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()

            conn.execute("""
                INSERT OR REPLACE INTO folder_watches
                (channel_id, folder_id, folder_name, store_code, resource_id, expiration, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                watch['channel_id'],
                watch['folder_id'],
                watch.get('folder_name'),
                watch.get('store_code'),
                watch.get('resource_id'),
                expiration,
                created_at
            ))

    def get_folder_watch(self, folder_id: str) -> Optional[Dict[str, Any]]:
        """Get folder watch by folder ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM folder_watches WHERE folder_id = ?",
                (folder_id,)
            ).fetchone()

            if row:
                return {
                    'channel_id': row['channel_id'],
                    'folder_id': row['folder_id'],
                    'folder_name': row['folder_name'],
                    'store_code': row['store_code'],
                    'resource_id': row['resource_id'],
                    'expiration': datetime.fromisoformat(row['expiration']),
                    'created_at': datetime.fromisoformat(row['created_at'])
                }
        return None

    def get_folder_watch_by_channel(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get folder watch by channel ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM folder_watches WHERE channel_id = ?",
                (channel_id,)
            ).fetchone()

            if row:
                return {
                    'channel_id': row['channel_id'],
                    'folder_id': row['folder_id'],
                    'folder_name': row['folder_name'],
                    'store_code': row['store_code'],
                    'resource_id': row['resource_id'],
                    'expiration': datetime.fromisoformat(row['expiration']),
                    'created_at': datetime.fromisoformat(row['created_at'])
                }
        return None

    def get_expiring_folder_watches(self, hours: int = 2) -> List[Dict[str, Any]]:
        """Get folder watches expiring within given hours."""
        cutoff = datetime.utcnow()
        with self._connection() as conn:
            rows = conn.execute("""
                SELECT * FROM folder_watches
                WHERE expiration <= datetime(?, '+' || ? || ' hours')
            """, (cutoff.isoformat(), hours)).fetchall()

            return [
                {
                    'channel_id': row['channel_id'],
                    'folder_id': row['folder_id'],
                    'folder_name': row['folder_name'],
                    'store_code': row['store_code'],
                    'resource_id': row['resource_id'],
                    'expiration': datetime.fromisoformat(row['expiration']),
                    'created_at': datetime.fromisoformat(row['created_at'])
                }
                for row in rows
            ]

    def delete_folder_watch(self, channel_id: str):
        """Delete a folder watch channel."""
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM folder_watches WHERE channel_id = ?",
                (channel_id,)
            )

    def get_all_folder_watches(self) -> List[Dict[str, Any]]:
        """Get all folder watches."""
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM folder_watches").fetchall()

            return [
                {
                    'channel_id': row['channel_id'],
                    'folder_id': row['folder_id'],
                    'folder_name': row['folder_name'],
                    'store_code': row['store_code'],
                    'resource_id': row['resource_id'],
                    'expiration': datetime.fromisoformat(row['expiration']),
                    'created_at': datetime.fromisoformat(row['created_at'])
                }
                for row in rows
            ]

    # =========================================================================
    # File Queue (POS file processing)
    # =========================================================================

    def queue_file(self, file_info: Dict[str, Any], store_code: str = None):
        """Add a file to the processing queue."""
        with self._connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO file_queue
                (file_id, file_name, folder_id, store_code, mime_type, file_size,
                 md5_checksum, status, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """, (
                file_info['id'],
                file_info['name'],
                file_info.get('parents', [''])[0] if 'parents' in file_info else file_info.get('folder_id', ''),
                store_code,
                file_info.get('mimeType'),
                file_info.get('size'),
                file_info.get('md5Checksum'),
                datetime.utcnow().isoformat()
            ))

    def get_pending_files(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get files pending processing."""
        with self._connection() as conn:
            rows = conn.execute("""
                SELECT * FROM file_queue
                WHERE status = 'pending'
                ORDER BY detected_at ASC
                LIMIT ?
            """, (limit,)).fetchall()

            return [dict(row) for row in rows]

    def update_file_status(
        self,
        file_id: str,
        status: str,
        record_count: int = 0,
        report_type: str = None,
        error: str = None
    ):
        """Update file processing status."""
        with self._connection() as conn:
            if status == 'completed':
                conn.execute("""
                    UPDATE file_queue
                    SET status = ?, processed_at = ?, record_count = ?, report_type = ?
                    WHERE file_id = ?
                """, (status, datetime.utcnow().isoformat(), record_count, report_type, file_id))
            elif status == 'failed':
                conn.execute("""
                    UPDATE file_queue
                    SET status = ?, error_message = ?
                    WHERE file_id = ?
                """, (status, error, file_id))
            else:
                conn.execute("""
                    UPDATE file_queue SET status = ? WHERE file_id = ?
                """, (status, file_id))

    def is_file_processed(self, file_id: str) -> bool:
        """Check if a file has already been processed."""
        with self._connection() as conn:
            row = conn.execute("""
                SELECT 1 FROM processed_files WHERE file_id = ?
                UNION
                SELECT 1 FROM file_queue WHERE file_id = ? AND status IN ('completed', 'processing')
            """, (file_id, file_id)).fetchone()

            return row is not None

    def mark_file_processed(
        self,
        file_id: str,
        file_name: str,
        folder_id: str,
        store_code: str,
        md5_checksum: str,
        record_count: int,
        report_type: str,
        extracted_data: Dict = None
    ):
        """Record a processed file."""
        with self._connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO processed_files
                (file_id, file_name, folder_id, store_code, md5_checksum,
                 processed_at, record_count, report_type, extracted_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_id,
                file_name,
                folder_id,
                store_code,
                md5_checksum,
                datetime.utcnow().isoformat(),
                record_count,
                report_type,
                json.dumps(extracted_data) if extracted_data else None
            ))

    def get_processed_files(
        self,
        store_code: str = None,
        since: datetime = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get list of processed files."""
        with self._connection() as conn:
            query = "SELECT * FROM processed_files WHERE 1=1"
            params = []

            if store_code:
                query += " AND store_code = ?"
                params.append(store_code)

            if since:
                query += " AND processed_at >= ?"
                params.append(since.isoformat())

            query += " ORDER BY processed_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_file_queue_summary(self) -> Dict[str, int]:
        """Get summary counts of file queue by status."""
        with self._connection() as conn:
            rows = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM file_queue
                GROUP BY status
            """).fetchall()

            return {row['status']: row['count'] for row in rows}


# Singleton instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Get database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db
