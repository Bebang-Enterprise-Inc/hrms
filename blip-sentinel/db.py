"""
Blip Sentinel v2.3 — Database Layer
SQLite schema, CRUD operations, WAL mode init, retention pruning.
"""

import functools
import json
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from typing import Optional

from config import DB_PATH, DATA_RETENTION_DAYS

log = logging.getLogger("sentinel.db")


def retry_on_locked(max_retries=3, base_delay=1.0):
    """Retry decorator for database operations that may fail with 'database is locked'."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e) and attempt < max_retries - 1:
                        wait = base_delay * (2 ** attempt)
                        log.warning("Database locked (attempt %d/%d), retrying in %.1fs: %s",
                                   attempt + 1, max_retries, wait, func.__name__)
                        import time
                        time.sleep(wait)
                    else:
                        raise
        return wrapper
    return decorator

# ── Schema ──

SCHEMA_SQL = """
-- Layer 1: Raw chat messages
CREATE TABLE IF NOT EXISTS raw_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    space_id TEXT NOT NULL,
    space_name TEXT,
    space_type TEXT,
    message_id TEXT UNIQUE NOT NULL,
    sender_id TEXT,
    sender_name TEXT,
    text TEXT,
    has_attachment BOOLEAN DEFAULT 0,
    is_image_only BOOLEAN DEFAULT 0,
    create_time TEXT NOT NULL,
    thread_id TEXT,
    mentions_sam BOOLEAN DEFAULT 0,
    collected_at TEXT NOT NULL DEFAULT (datetime('now')),
    classification TEXT,
    classification_reason TEXT,
    classified_at TEXT,
    classified_by TEXT,
    included_in_briefing TEXT,
    text_hash TEXT,
    contains_sensitive BOOLEAN DEFAULT 0,
    parent_message_id TEXT,
    parent_sender_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_unclassified
    ON raw_messages(classification) WHERE classification IS NULL;
CREATE INDEX IF NOT EXISTS idx_messages_for_briefing
    ON raw_messages(classification, included_in_briefing)
    WHERE classification IN ('URGENT', 'ACTION', 'FYI') AND included_in_briefing IS NULL;
CREATE INDEX IF NOT EXISTS idx_messages_text_hash
    ON raw_messages(text_hash) WHERE text_hash IS NOT NULL;

-- Layer 1: Raw emails
CREATE TABLE IF NOT EXISTS raw_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_id TEXT UNIQUE NOT NULL,
    from_addr TEXT,
    subject TEXT,
    date TEXT,
    snippet TEXT,
    labels TEXT,
    is_unread BOOLEAN DEFAULT 1,
    collected_at TEXT NOT NULL DEFAULT (datetime('now')),
    classification TEXT,
    classification_reason TEXT,
    classified_at TEXT,
    classified_by TEXT,
    included_in_briefing TEXT
);

-- Calendar events
CREATE TABLE IF NOT EXISTS calendar_events (
    event_id TEXT PRIMARY KEY,
    calendar_id TEXT,
    summary TEXT,
    start_time TEXT,
    end_time TEXT,
    location TEXT,
    attendees TEXT,
    meet_link TEXT,
    status TEXT,
    last_updated TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Sweep state (auto-discovery + last-checked tracking)
CREATE TABLE IF NOT EXISTS sweep_state (
    space_id TEXT PRIMARY KEY,
    space_name TEXT,
    space_type TEXT,
    last_message_time TEXT,
    last_swept_at TEXT,
    discovered_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Gmail incremental sync state
CREATE TABLE IF NOT EXISTS gmail_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    history_id TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Notifications sent via Blip
CREATE TABLE IF NOT EXISTS sent_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_type TEXT NOT NULL,
    trigger_message_id TEXT,
    trigger_source TEXT,
    blip_message_id TEXT,
    notification_preview TEXT,
    notification_hash TEXT,
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(notification_type, trigger_message_id)
);

-- Calendar reminders already sent
CREATE TABLE IF NOT EXISTS calendar_reminders (
    event_id TEXT NOT NULL,
    reminder_type TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    PRIMARY KEY (event_id, reminder_type)
);

-- Carry-forward unresolved items
CREATE TABLE IF NOT EXISTS unresolved_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    source_type TEXT,
    source_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    last_briefing TEXT
);

-- Digest state (tracks last digest timestamp)
CREATE TABLE IF NOT EXISTS digest_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_digest_at TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- User name cache (resolved from Admin Directory API)
CREATE TABLE IF NOT EXISTS user_names (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    email TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- System metrics for observability
CREATE TABLE IF NOT EXISTS system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    job_name TEXT NOT NULL,
    duration_ms INTEGER,
    messages_processed INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    api_calls_used INTEGER DEFAULT 0,
    notes TEXT
);
"""


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Initialize database with WAL mode and schema."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")  # 30s — handles concurrent cron writes
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    log.info("Database initialized at %s", db_path)
    return conn


@contextmanager
def get_db(db_path: str = DB_PATH):
    """Context manager for database connections."""
    conn = init_db(db_path)
    try:
        yield conn
    finally:
        conn.close()


# ── Sweep State ──

def get_all_monitored_spaces(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM sweep_state ORDER BY space_name").fetchall()


def upsert_space(conn: sqlite3.Connection, space_id: str, space_name: str, space_type: str):
    conn.execute(
        """INSERT INTO sweep_state (space_id, space_name, space_type)
           VALUES (?, ?, ?)
           ON CONFLICT(space_id) DO UPDATE SET space_name=excluded.space_name, space_type=excluded.space_type""",
        (space_id, space_name, space_type),
    )
    conn.commit()


def get_last_checked(conn: sqlite3.Connection, space_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT last_message_time FROM sweep_state WHERE space_id = ?", (space_id,)
    ).fetchone()
    return row["last_message_time"] if row else None


def update_last_checked(conn: sqlite3.Connection, space_id: str, timestamp: Optional[str] = None):
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE sweep_state SET last_swept_at = ?, last_message_time = ? WHERE space_id = ?",
        (datetime.now(timezone.utc).isoformat(), ts, space_id),
    )
    conn.commit()


# ── Raw Messages ──

def insert_raw_message(conn: sqlite3.Connection, **kwargs):
    # Set defaults for optional columns
    kwargs.setdefault('parent_message_id', None)
    kwargs.setdefault('parent_sender_id', None)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO raw_messages
               (space_id, space_name, space_type, message_id, sender_id, sender_name,
                text, has_attachment, is_image_only, create_time, thread_id, mentions_sam,
                parent_message_id, parent_sender_id)
               VALUES (:space_id, :space_name, :space_type, :message_id, :sender_id, :sender_name,
                       :text, :has_attachment, :is_image_only, :create_time, :thread_id, :mentions_sam,
                       :parent_message_id, :parent_sender_id)""",
            kwargs,
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Duplicate message_id — already collected


def sam_sent_in_thread(conn: sqlite3.Connection, thread_id: str, sam_user_id: str) -> Optional[sqlite3.Row]:
    """Check if Sam sent a message in the given thread. Returns Sam's message if found."""
    if not thread_id:
        return None
    return conn.execute(
        """SELECT id, message_id, text FROM raw_messages
           WHERE thread_id = ? AND sender_id = ?
           ORDER BY create_time ASC LIMIT 1""",
        (thread_id, sam_user_id),
    ).fetchone()


def message_exists(conn: sqlite3.Connection, message_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM raw_messages WHERE message_id = ?", (message_id,)
    ).fetchone()
    return row is not None


# ── Raw Emails ──

def insert_raw_email(conn: sqlite3.Connection, **kwargs):
    labels_json = json.dumps(kwargs.pop("labels", []))
    try:
        conn.execute(
            """INSERT OR IGNORE INTO raw_emails
               (gmail_id, from_addr, subject, date, snippet, labels, is_unread)
               VALUES (:gmail_id, :from_addr, :subject, :date, :snippet, :labels, :is_unread)""",
            {**kwargs, "labels": labels_json},
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass


def email_exists(conn: sqlite3.Connection, gmail_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM raw_emails WHERE gmail_id = ?", (gmail_id,)
    ).fetchone()
    return row is not None


# ── Gmail State ──

def get_gmail_history_id(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute("SELECT history_id FROM gmail_state WHERE id = 1").fetchone()
    return row["history_id"] if row else None


def set_gmail_history_id(conn: sqlite3.Connection, history_id: str):
    conn.execute(
        """INSERT INTO gmail_state (id, history_id) VALUES (1, ?)
           ON CONFLICT(id) DO UPDATE SET history_id=excluded.history_id,
           updated_at=datetime('now')""",
        (history_id,),
    )
    conn.commit()


# ── Calendar Events ──

def upsert_calendar_event(conn: sqlite3.Connection, **kwargs):
    attendees_json = json.dumps(kwargs.pop("attendees", []))
    conn.execute(
        """INSERT INTO calendar_events
           (event_id, calendar_id, summary, start_time, end_time, location, attendees, meet_link, status)
           VALUES (:event_id, :calendar_id, :summary, :start_time, :end_time, :location, :attendees, :meet_link, :status)
           ON CONFLICT(event_id) DO UPDATE SET
               calendar_id=excluded.calendar_id, summary=excluded.summary,
               start_time=excluded.start_time, end_time=excluded.end_time,
               location=excluded.location, attendees=excluded.attendees,
               meet_link=excluded.meet_link, status=excluded.status,
               last_updated=datetime('now')""",
        {**kwargs, "attendees": attendees_json},
    )
    conn.commit()


def get_upcoming_events(conn: sqlite3.Connection, hours: int = 48) -> list[sqlite3.Row]:
    now = datetime.now(timezone.utc)
    end = (now + timedelta(hours=hours)).isoformat()
    return conn.execute(
        """SELECT * FROM calendar_events
           WHERE start_time >= ? AND start_time <= ? AND status != 'cancelled'
           ORDER BY start_time""",
        (now.isoformat(), end),
    ).fetchall()


def get_events_needing_prep(conn: sqlite3.Connection, within_minutes: int = 65) -> list[sqlite3.Row]:
    """Events starting in 55-65 minutes that haven't had a reminder sent."""
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    window_start = (now + timedelta(minutes=55)).isoformat()
    window_end = (now + timedelta(minutes=within_minutes)).isoformat()
    return conn.execute(
        """SELECT ce.* FROM calendar_events ce
           LEFT JOIN calendar_reminders cr ON ce.event_id = cr.event_id AND cr.reminder_type = 'simple_reminder'
           WHERE ce.start_time BETWEEN ? AND ? AND cr.event_id IS NULL AND ce.status != 'cancelled'""",
        (window_start, window_end),
    ).fetchall()


def mark_reminder_sent(conn: sqlite3.Connection, event_id: str, reminder_type: str):
    conn.execute(
        "INSERT OR IGNORE INTO calendar_reminders (event_id, reminder_type, sent_at) VALUES (?, ?, datetime('now'))",
        (event_id, reminder_type),
    )
    conn.commit()


def count_meeting_preps_today(conn: sqlite3.Connection) -> int:
    from config import PHT
    today = datetime.now(PHT).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM calendar_reminders WHERE reminder_type = 'meeting_prep' AND sent_at LIKE ?",
        (f"{today}%",),
    ).fetchone()
    return row["cnt"] if row else 0


# ── Table Name Validation ──

_VALID_TABLES = {"raw_messages", "raw_emails"}


def _validate_table(table: str):
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table: {table}")


# ── Classification ──

def get_unclassified_messages(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM raw_messages WHERE classification IS NULL
           ORDER BY create_time ASC LIMIT ?""",
        (limit,),
    ).fetchall()


def get_unclassified_emails(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM raw_emails WHERE classification IS NULL
           ORDER BY date ASC LIMIT ?""",
        (limit,),
    ).fetchall()


def update_classification(conn: sqlite3.Connection, msg_id: int, classification: str,
                          reason: str, classified_by: str, table: str = "raw_messages"):
    _validate_table(table)
    conn.execute(
        f"""UPDATE {table} SET classification = ?, classification_reason = ?,
            classified_at = datetime('now'), classified_by = ? WHERE id = ?""",
        (classification, reason, classified_by, msg_id),
    )
    conn.commit()


# ── Briefing ──

def get_unbriefed_messages(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM raw_messages
           WHERE classification IN ('URGENT', 'ACTION', 'FYI')
           AND included_in_briefing IS NULL
           ORDER BY
               CASE classification WHEN 'URGENT' THEN 1 WHEN 'ACTION' THEN 2 ELSE 3 END,
               create_time ASC"""
    ).fetchall()


def get_unbriefed_emails(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM raw_emails
           WHERE classification IN ('URGENT', 'ACTION', 'FYI')
           AND included_in_briefing IS NULL
           ORDER BY date ASC"""
    ).fetchall()


def mark_briefed(conn: sqlite3.Connection, msg_ids: list[int], briefing_label: str,
                 table: str = "raw_messages"):
    _validate_table(table)
    if not msg_ids:
        return
    placeholders = ",".join("?" for _ in msg_ids)
    conn.execute(
        f"UPDATE {table} SET included_in_briefing = ? WHERE id IN ({placeholders})",
        [briefing_label] + msg_ids,
    )
    conn.commit()


# ── Unresolved Items ──

def get_unresolved_items(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM unresolved_items WHERE resolved_at IS NULL ORDER BY created_at ASC"
    ).fetchall()


def add_unresolved_item(conn: sqlite3.Connection, description: str, source_type: str = None,
                        source_id: str = None):
    conn.execute(
        "INSERT INTO unresolved_items (description, source_type, source_id) VALUES (?, ?, ?)",
        (description, source_type, source_id),
    )
    conn.commit()


def update_unresolved_briefing(conn: sqlite3.Connection, item_ids: list[int], briefing_label: str):
    if not item_ids:
        return
    placeholders = ",".join("?" for _ in item_ids)
    conn.execute(
        f"UPDATE unresolved_items SET last_briefing = ? WHERE id IN ({placeholders})",
        [briefing_label] + item_ids,
    )
    conn.commit()


def resolve_item(conn: sqlite3.Connection, item_id: int):
    """Mark an unresolved item as resolved."""
    conn.execute(
        "UPDATE unresolved_items SET resolved_at = datetime('now') WHERE id = ?",
        (item_id,),
    )
    conn.commit()


def get_pending_responses(conn: sqlite3.Connection, sam_user_id: str,
                          hours: int = 48) -> list[sqlite3.Row]:
    """
    Get Sam's messages from the last N hours that have no RESPONSE in the same thread.
    These are questions Sam asked that nobody has replied to yet.
    """
    return conn.execute(
        """SELECT rm.thread_id, rm.text, rm.space_name, rm.create_time
           FROM raw_messages rm
           WHERE rm.sender_id = ?
             AND rm.thread_id IS NOT NULL
             AND rm.create_time > datetime('now', ?)
             AND NOT EXISTS (
                 SELECT 1 FROM raw_messages reply
                 WHERE reply.thread_id = rm.thread_id
                   AND reply.sender_id != ?
                   AND reply.classification = 'RESPONSE'
                   AND reply.create_time > rm.create_time
             )
           ORDER BY rm.create_time DESC
           LIMIT 10""",
        (sam_user_id, f"-{hours} hours", sam_user_id),
    ).fetchall()


# ── Notifications ──

def record_notification(conn: sqlite3.Connection, notification_type: str,
                        trigger_message_id: str = None, trigger_source: str = None,
                        blip_message_id: str = None, preview: str = None,
                        content_hash: str = None):
    try:
        conn.execute(
            """INSERT INTO sent_notifications
               (notification_type, trigger_message_id, trigger_source, blip_message_id,
                notification_preview, notification_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (notification_type, trigger_message_id, trigger_source, blip_message_id,
             preview, content_hash),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Already sent this notification


def notification_already_sent(conn: sqlite3.Connection, notification_type: str,
                               trigger_message_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sent_notifications WHERE notification_type = ? AND trigger_message_id = ?",
        (notification_type, trigger_message_id),
    ).fetchone()
    return row is not None


# ── DND Queue ──

def flag_for_morning_briefing(conn: sqlite3.Connection, message_id: str):
    """Mark a message to be included in the morning briefing (DND-queued alert)."""
    conn.execute(
        """UPDATE raw_messages SET classification = 'URGENT',
           classification_reason = 'dnd_queued_mention',
           classified_at = datetime('now'), classified_by = 'dnd_queue'
           WHERE message_id = ?""",
        (message_id,),
    )
    conn.commit()


# ── Retention / Pruning ──

def prune_old_data(conn: sqlite3.Connection, days: int = DATA_RETENTION_DAYS):
    """Delete data older than retention period."""
    cutoff = f"-{days} days"
    deleted_msgs = conn.execute(
        "DELETE FROM raw_messages WHERE collected_at < datetime('now', ?)", (cutoff,)
    ).rowcount
    deleted_emails = conn.execute(
        "DELETE FROM raw_emails WHERE collected_at < datetime('now', ?)", (cutoff,)
    ).rowcount
    deleted_events = conn.execute(
        "DELETE FROM calendar_events WHERE last_updated < datetime('now', ?)", (cutoff,)
    ).rowcount
    deleted_notifs = conn.execute(
        "DELETE FROM sent_notifications WHERE sent_at < datetime('now', ?)", (cutoff,)
    ).rowcount
    resolved = conn.execute(
        "DELETE FROM unresolved_items WHERE resolved_at IS NOT NULL AND resolved_at < datetime('now', ?)",
        (cutoff,),
    ).rowcount
    conn.commit()

    log.info(
        "Pruned: %d messages, %d emails, %d events, %d notifications, %d resolved items",
        deleted_msgs, deleted_emails, deleted_events, deleted_notifs, resolved,
    )
    return {
        "messages": deleted_msgs, "emails": deleted_emails,
        "events": deleted_events, "notifications": deleted_notifs,
        "resolved_items": resolved,
    }


# ── Digest State ──

def get_last_digest_time(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute("SELECT last_digest_at FROM digest_state WHERE id = 1").fetchone()
    return row["last_digest_at"] if row else None


def set_last_digest_time(conn: sqlite3.Connection, ts: Optional[str] = None):
    if ts is None:
        # Use SQLite datetime('now') to match collected_at column format (YYYY-MM-DD HH:MM:SS)
        conn.execute(
            """INSERT INTO digest_state (id, last_digest_at) VALUES (1, datetime('now'))
               ON CONFLICT(id) DO UPDATE SET last_digest_at=datetime('now'),
               updated_at=datetime('now')""",
        )
    else:
        conn.execute(
            """INSERT INTO digest_state (id, last_digest_at) VALUES (1, ?)
               ON CONFLICT(id) DO UPDATE SET last_digest_at=excluded.last_digest_at,
               updated_at=datetime('now')""",
            (ts,),
        )
    conn.commit()


def get_messages_since(conn: sqlite3.Connection, since: str,
                       classifications: list[str] = None) -> list[sqlite3.Row]:
    """Get classified messages since a timestamp, grouped by space then time."""
    if classifications:
        placeholders = ",".join("?" for _ in classifications)
        return conn.execute(
            f"""SELECT * FROM raw_messages
               WHERE classification IS NOT NULL
               AND classification IN ({placeholders})
               AND collected_at > ?
               ORDER BY space_name, create_time ASC""",
            classifications + [since],
        ).fetchall()
    return conn.execute(
        """SELECT * FROM raw_messages
           WHERE classification IS NOT NULL
           AND collected_at > ?
           ORDER BY space_name, create_time ASC""",
        (since,),
    ).fetchall()


def get_emails_since(conn: sqlite3.Connection, since: str,
                     classifications: list[str] = None) -> list[sqlite3.Row]:
    """Get classified emails since a timestamp."""
    if classifications:
        placeholders = ",".join("?" for _ in classifications)
        return conn.execute(
            f"""SELECT * FROM raw_emails
               WHERE classification IS NOT NULL
               AND classification IN ({placeholders})
               AND collected_at > ?
               ORDER BY date ASC""",
            classifications + [since],
        ).fetchall()
    return conn.execute(
        """SELECT * FROM raw_emails
           WHERE classification IS NOT NULL
           AND collected_at > ?
           ORDER BY date ASC""",
        (since,),
    ).fetchall()


# ── User Name Cache ──

def upsert_user_name(conn: sqlite3.Connection, user_id: str, display_name: str, email: str = None):
    conn.execute(
        """INSERT INTO user_names (user_id, display_name, email)
           VALUES (?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name,
           email=excluded.email, updated_at=datetime('now')""",
        (user_id, display_name, email),
    )


def bulk_upsert_user_names(conn: sqlite3.Connection, users: list[dict]):
    """Bulk insert/update user names. Each dict: {user_id, display_name, email}."""
    for user in users:
        upsert_user_name(conn, user["user_id"], user["display_name"], user.get("email"))
    conn.commit()


def get_user_name(conn: sqlite3.Connection, user_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT display_name FROM user_names WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row["display_name"] if row else None


def get_all_user_names(conn: sqlite3.Connection) -> dict:
    """Return a dict mapping user_id -> display_name."""
    rows = conn.execute("SELECT user_id, display_name FROM user_names").fetchall()
    return {row["user_id"]: row["display_name"] for row in rows}


def backfill_sender_names(conn: sqlite3.Connection):
    """Update sender_name in raw_messages using the user_names cache."""
    conn.execute(
        """UPDATE raw_messages SET sender_name = (
               SELECT display_name FROM user_names WHERE user_names.user_id = raw_messages.sender_id
           )
           WHERE sender_id IN (SELECT user_id FROM user_names)
           AND (sender_name IS NULL OR sender_name = sender_id OR sender_name LIKE 'users/%')"""
    )
    conn.commit()


def get_sam_original_in_thread(conn: sqlite3.Connection, thread_id: str,
                               sam_user_id: str) -> Optional[str]:
    """Get Sam's original message text in a thread (for RESPONSE context display)."""
    if not thread_id:
        return None
    row = conn.execute(
        """SELECT text FROM raw_messages
           WHERE thread_id = ? AND sender_id = ?
           ORDER BY create_time ASC LIMIT 1""",
        (thread_id, sam_user_id),
    ).fetchone()
    if row:
        text = (row["text"] or "")[:60]
        return text
    return None


def get_digest_stats(conn: sqlite3.Connection, since: str) -> dict:
    """Get counts of messages by classification since timestamp."""
    rows = conn.execute(
        """SELECT classification, COUNT(*) as cnt FROM raw_messages
           WHERE classification IS NOT NULL AND collected_at > ?
           GROUP BY classification""",
        (since,),
    ).fetchall()
    return {row["classification"]: row["cnt"] for row in rows}
