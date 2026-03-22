"""
Tests for Phase 6 safety features in notifier.py:
- Bot circuit breaker (6.1)
- Content dedup (6.2)
- Rate limiting (6.4)
"""

import sqlite3
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from notifier import _content_hash, _bot_window_check, _is_duplicate_notification, _check_notification_rate_limit


def _make_db():
    """Create in-memory SQLite with sent_notifications table."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE sent_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_type TEXT NOT NULL,
            trigger_message_id TEXT,
            trigger_source TEXT,
            blip_message_id TEXT,
            notification_preview TEXT,
            notification_hash TEXT,
            sent_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(notification_type, trigger_message_id)
        )
    """)
    conn.commit()
    return conn


class TestContentHash:
    def test_hash_deterministic(self):
        assert _content_hash("hello") == _content_hash("hello")

    def test_hash_different_for_different_input(self):
        assert _content_hash("hello") != _content_hash("world")

    def test_hash_length(self):
        h = _content_hash("test message")
        assert len(h) == 16


class TestBotWindowCheck:
    def test_allows_when_under_limit(self):
        conn = _make_db()
        assert _bot_window_check(conn) is True

    def test_blocks_when_at_limit(self):
        conn = _make_db()
        # Insert 3 recent notifications (default limit)
        for i in range(3):
            conn.execute(
                "INSERT INTO sent_notifications (notification_type, sent_at) VALUES (?, datetime('now'))",
                (f"test_{i}",),
            )
        conn.commit()
        assert _bot_window_check(conn) is False

    def test_allows_after_window_expires(self):
        conn = _make_db()
        # Insert 3 old notifications (6 minutes ago, outside 5-min window)
        for i in range(3):
            conn.execute(
                "INSERT INTO sent_notifications (notification_type, sent_at) VALUES (?, datetime('now', '-6 minutes'))",
                (f"old_{i}",),
            )
        conn.commit()
        assert _bot_window_check(conn) is True


class TestDuplicateNotification:
    def test_not_duplicate_when_no_prior(self):
        conn = _make_db()
        assert _is_duplicate_notification(conn, "unique message") is False

    def test_duplicate_when_same_hash_recent(self):
        conn = _make_db()
        text = "This is a test notification"
        h = _content_hash(text)
        conn.execute(
            "INSERT INTO sent_notifications (notification_type, notification_hash, sent_at) VALUES (?, ?, datetime('now'))",
            ("test", h),
        )
        conn.commit()
        assert _is_duplicate_notification(conn, text) is True

    def test_not_duplicate_when_hash_old(self):
        conn = _make_db()
        text = "Old notification"
        h = _content_hash(text)
        conn.execute(
            "INSERT INTO sent_notifications (notification_type, notification_hash, sent_at) VALUES (?, ?, datetime('now', '-25 hours'))",
            ("test", h),
        )
        conn.commit()
        assert _is_duplicate_notification(conn, text) is False


class TestNotificationRateLimit:
    def test_allows_first_digest(self):
        conn = _make_db()
        assert _check_notification_rate_limit(conn, "digest") is True

    def test_blocks_second_digest_in_30_min(self):
        conn = _make_db()
        conn.execute(
            "INSERT INTO sent_notifications (notification_type, sent_at) VALUES ('digest', datetime('now'))"
        )
        conn.commit()
        assert _check_notification_rate_limit(conn, "digest") is False

    def test_allows_digest_after_30_min(self):
        conn = _make_db()
        conn.execute(
            "INSERT INTO sent_notifications (notification_type, sent_at) VALUES ('digest', datetime('now', '-31 minutes'))"
        )
        conn.commit()
        assert _check_notification_rate_limit(conn, "digest") is True

    def test_blocks_second_morning_briefing_same_day(self):
        conn = _make_db()
        conn.execute(
            "INSERT INTO sent_notifications (notification_type, sent_at) VALUES ('morning_briefing', datetime('now'))"
        )
        conn.commit()
        assert _check_notification_rate_limit(conn, "morning_briefing") is False

    def test_allows_fourth_mention_alert_after_first_three(self):
        """3 per hour limit — 4th should be blocked."""
        conn = _make_db()
        for i in range(3):
            conn.execute(
                "INSERT INTO sent_notifications (notification_type, trigger_message_id, sent_at) VALUES ('mention_alert', ?, datetime('now'))",
                (f"msg_{i}",),
            )
        conn.commit()
        assert _check_notification_rate_limit(conn, "mention_alert") is False

    def test_allows_unknown_notification_type(self):
        conn = _make_db()
        assert _check_notification_rate_limit(conn, "custom_type") is True

    def test_blocks_second_store_summary(self):
        conn = _make_db()
        conn.execute(
            "INSERT INTO sent_notifications (notification_type, sent_at) VALUES ('store_summary', datetime('now'))"
        )
        conn.commit()
        assert _check_notification_rate_limit(conn, "store_summary") is False
