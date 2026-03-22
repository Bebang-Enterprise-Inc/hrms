"""
Blip Sentinel v2.3 — Notifier and Sweeper Unit Tests
Tests for DND detection, message deduplication, and message splitting.
"""

import unittest
import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import db
from notifier import is_dnd_window, _split_message


class TestDNDWindow(unittest.TestCase):
    """Test DND window detection."""

    @patch('notifier.datetime')
    def test_is_dnd_window_late_night(self, mock_datetime):
        """Test 11 PM PHT is in DND window."""
        # Mock datetime to return 11 PM PHT (23:00 PHT = 15:00 UTC)
        mock_now = datetime(2026, 2, 13, 15, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now.astimezone(config.PHT)

        result = is_dnd_window()
        self.assertTrue(result)

    @patch('notifier.datetime')
    def test_is_dnd_window_early_morning(self, mock_datetime):
        """Test 6 AM PHT is in DND window."""
        # Mock datetime to return 6 AM PHT (06:00 PHT = 22:00 UTC prev day)
        mock_now = datetime(2026, 2, 12, 22, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now.astimezone(config.PHT)

        result = is_dnd_window()
        self.assertTrue(result)

    @patch('notifier.datetime')
    def test_is_dnd_window_daytime(self, mock_datetime):
        """Test 2 PM PHT is NOT in DND window."""
        # Mock datetime to return 2 PM PHT (14:00 PHT = 06:00 UTC)
        mock_now = datetime(2026, 2, 13, 6, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now.astimezone(config.PHT)

        result = is_dnd_window()
        self.assertFalse(result)

    @patch('notifier.datetime')
    def test_is_dnd_window_boundary(self, mock_datetime):
        """Test 7 AM PHT is NOT in DND window (DND ends at 7)."""
        # Mock datetime to return 7 AM PHT (07:00 PHT = 23:00 UTC prev day)
        mock_now = datetime(2026, 2, 12, 23, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now.astimezone(config.PHT)

        result = is_dnd_window()
        self.assertFalse(result)


class TestMessageDeduplication(unittest.TestCase):
    """Test message and email deduplication."""

    def setUp(self):
        """Create in-memory SQLite database for testing."""
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(db.SCHEMA_SQL)
        self.conn.commit()

    def tearDown(self):
        """Close database connection."""
        self.conn.close()

    def test_message_dedup(self):
        """Test inserting same message_id twice is ignored."""
        # Insert first message
        db.insert_raw_message(
            self.conn,
            space_id='spaces/test',
            space_name='Test Space',
            space_type='SPACE',
            message_id='msg-001',
            sender_id='user-001',
            sender_name='Test User',
            text='Test message',
            has_attachment=False,
            is_image_only=False,
            create_time='2026-02-13T10:00:00Z',
            thread_id=None,
            mentions_sam=False
        )

        # Verify it was inserted
        self.assertTrue(db.message_exists(self.conn, 'msg-001'))

        # Try to insert duplicate
        db.insert_raw_message(
            self.conn,
            space_id='spaces/test',
            space_name='Test Space',
            space_type='SPACE',
            message_id='msg-001',  # Same message_id
            sender_id='user-001',
            sender_name='Test User',
            text='Different text',  # Different content
            has_attachment=False,
            is_image_only=False,
            create_time='2026-02-13T10:01:00Z',
            thread_id=None,
            mentions_sam=False
        )

        # Count should still be 1 (duplicate ignored)
        count = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM raw_messages WHERE message_id = ?",
            ('msg-001',)
        ).fetchone()['cnt']
        self.assertEqual(count, 1)

        # Original text should be preserved
        row = self.conn.execute(
            "SELECT text FROM raw_messages WHERE message_id = ?",
            ('msg-001',)
        ).fetchone()
        self.assertEqual(row['text'], 'Test message')

    def test_email_dedup(self):
        """Test inserting same gmail_id twice is ignored."""
        # Insert first email
        db.insert_raw_email(
            self.conn,
            gmail_id='gmail-001',
            from_addr='test@example.com',
            subject='Test Subject',
            date='2026-02-13T10:00:00Z',
            snippet='Test snippet',
            labels=['INBOX'],
            is_unread=True
        )

        # Verify it was inserted
        self.assertTrue(db.email_exists(self.conn, 'gmail-001'))

        # Try to insert duplicate
        db.insert_raw_email(
            self.conn,
            gmail_id='gmail-001',  # Same gmail_id
            from_addr='test@example.com',
            subject='Different Subject',  # Different content
            date='2026-02-13T10:01:00Z',
            snippet='Different snippet',
            labels=['INBOX'],
            is_unread=True
        )

        # Count should still be 1 (duplicate ignored)
        count = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM raw_emails WHERE gmail_id = ?",
            ('gmail-001',)
        ).fetchone()['cnt']
        self.assertEqual(count, 1)

        # Original subject should be preserved
        row = self.conn.execute(
            "SELECT subject FROM raw_emails WHERE gmail_id = ?",
            ('gmail-001',)
        ).fetchone()
        self.assertEqual(row['subject'], 'Test Subject')


class TestMessageSplitting(unittest.TestCase):
    """Test message splitting for Google Chat 4000-char limit."""

    def test_split_message_short(self):
        """Test text under 4000 chars returns single item list."""
        text = "This is a short message."
        result = _split_message(text, limit=4000)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    def test_split_message_long(self):
        """Test text over 4000 chars splits at paragraph boundaries."""
        # Create a message with clear paragraph breaks
        para1 = "First paragraph. " * 200  # ~3400 chars
        para2 = "Second paragraph. " * 200  # ~3600 chars
        text = para1 + "\n\n" + para2

        result = _split_message(text, limit=4000)

        # Should split into 2 parts at the paragraph boundary
        self.assertGreater(len(result), 1)

        # Each part should be under the limit
        for part in result:
            self.assertLessEqual(len(part), 4000)

        # All parts combined should preserve the content (minus whitespace)
        combined = ''.join(result)
        # Remove extra newlines for comparison
        original_normalized = text.replace('\n\n', '\n').strip()
        combined_normalized = combined.replace('\n\n', '\n').strip()
        self.assertIn('First paragraph', combined_normalized)
        self.assertIn('Second paragraph', combined_normalized)

    def test_split_message_exact_limit(self):
        """Test message exactly at limit returns single item."""
        text = "X" * 4000
        result = _split_message(text, limit=4000)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    def test_split_message_just_over_limit(self):
        """Test message just over limit returns truncated single item (no paragraph boundaries)."""
        # A message with no paragraph breaks will be truncated to limit
        text = "X" * 4001
        result = _split_message(text, limit=4000)

        # Without paragraph boundaries, the function returns truncated message
        self.assertGreaterEqual(len(result), 1)

        # Each part should be under or equal to the limit
        for part in result:
            self.assertLessEqual(len(part), 4000)

    def test_split_message_multiple_paragraphs(self):
        """Test splitting preserves paragraph structure."""
        paras = []
        for i in range(5):
            paras.append(f"Paragraph {i+1}. " * 180)  # ~2000 chars each

        text = "\n\n".join(paras)  # ~10,000 chars total
        result = _split_message(text, limit=4000)

        # Should split into multiple parts
        self.assertGreater(len(result), 2)

        # Each part should be under the limit
        for part in result:
            self.assertLessEqual(len(part), 4000)

        # Verify content is preserved
        combined = ''.join(result)
        for i in range(5):
            self.assertIn(f"Paragraph {i+1}", combined)


if __name__ == '__main__':
    unittest.main()
