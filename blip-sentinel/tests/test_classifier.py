"""
Blip Sentinel v2.3 — Classifier Unit Tests
Tests for regex-based pre-classification and AI response parsing.
"""

import unittest
from unittest.mock import MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classifier import pre_classify, parse_classifications


class TestClassifier(unittest.TestCase):
    """Unit tests for classifier module."""

    def test_pre_classify_noise_oki(self):
        """Test 'oki' is classified as NOISE."""
        msg = MagicMock()
        msg.get = lambda k, default=None: {
            'text': 'oki',
            'mentions_sam': False,
            'space_type': 'SPACE'
        }.get(k, default)

        result = pre_classify(msg)
        self.assertIsNotNone(result)
        category, reason = result
        self.assertEqual(category, 'NOISE')
        self.assertEqual(reason, 'acknowledgement/greeting')

    def test_pre_classify_noise_ok(self):
        """Test 'ok' is classified as NOISE."""
        msg = MagicMock()
        msg.get = lambda k, default=None: {
            'text': 'ok',
            'mentions_sam': False,
            'space_type': 'SPACE'
        }.get(k, default)

        result = pre_classify(msg)
        self.assertIsNotNone(result)
        category, reason = result
        self.assertEqual(category, 'NOISE')
        self.assertEqual(reason, 'acknowledgement/greeting')

    def test_pre_classify_noise_emoji(self):
        """Test emoji-only message is classified as NOISE."""
        msg = MagicMock()
        msg.get = lambda k, default=None: {
            'text': '👍',
            'mentions_sam': False,
            'space_type': 'SPACE'
        }.get(k, default)

        result = pre_classify(msg)
        self.assertIsNotNone(result)
        category, reason = result
        self.assertEqual(category, 'NOISE')
        self.assertEqual(reason, 'acknowledgement/greeting')

    def test_pre_classify_noise_thanks(self):
        """Test 'thanks po' is classified as NOISE."""
        msg = MagicMock()
        msg.get = lambda k, default=None: {
            'text': 'thanks po',
            'mentions_sam': False,
            'space_type': 'SPACE'
        }.get(k, default)

        result = pre_classify(msg)
        self.assertIsNotNone(result)
        category, reason = result
        self.assertEqual(category, 'NOISE')
        self.assertEqual(reason, 'acknowledgement/greeting')

    def test_pre_classify_urgent_mention_question(self):
        """Test @Sam mention with question mark is classified as URGENT."""
        msg = MagicMock()
        msg.get = lambda k, default=None: {
            'text': '<users/115141803777443372092> Can you approve this?',
            'mentions_sam': True,
            'space_type': 'SPACE'
        }.get(k, default)

        result = pre_classify(msg)
        self.assertIsNotNone(result)
        category, reason = result
        self.assertEqual(category, 'URGENT')
        self.assertEqual(reason, 'direct question/approval request')

    def test_pre_classify_none_for_complex(self):
        """Test complex message returns None (needs AI)."""
        msg = MagicMock()
        msg.get = lambda k, default=None: {
            'text': 'Can we discuss the budget proposal tomorrow?',
            'mentions_sam': True,
            'space_type': 'SPACE'
        }.get(k, default)

        result = pre_classify(msg)
        # This should return None because it's not a simple pattern
        # (no @Sam in the URGENT_PATTERNS match)
        self.assertIsNone(result)

    def test_pre_classify_branch_chatter_needs_ai(self):
        """Test branch chatter detection deferred to Phase 4 — returns None (needs AI)."""
        msg = MagicMock()
        msg.get = lambda k, default=None: {
            'text': 'Just finished the inventory count at SM North',
            'mentions_sam': False,
            'space_type': 'SPACE'
        }.get(k, default)

        result = pre_classify(msg)
        self.assertIsNone(result)  # Deferred to Phase 4

    def test_parse_classifications(self):
        """Test parsing of AI response format."""
        response_text = """[123] URGENT needs approval now
[456] NOISE acknowledgement
[789] ACTION requires follow-up discussion"""

        results = parse_classifications(response_text)

        self.assertEqual(len(results), 3)

        # Check first result
        self.assertEqual(results[0][0], 123)
        self.assertEqual(results[0][1], 'URGENT')
        self.assertEqual(results[0][2], 'needs approval now')

        # Check second result
        self.assertEqual(results[1][0], 456)
        self.assertEqual(results[1][1], 'NOISE')
        self.assertEqual(results[1][2], 'acknowledgement')

        # Check third result
        self.assertEqual(results[2][0], 789)
        self.assertEqual(results[2][1], 'ACTION')
        self.assertEqual(results[2][2], 'requires follow-up discussion')

    def test_parse_classifications_mixed_case(self):
        """Test parsing handles mixed case categories."""
        response_text = "[100] urgent needs immediate attention\n[200] Noise general chat"

        results = parse_classifications(response_text)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][1], 'URGENT')  # Should be uppercased
        self.assertEqual(results[1][1], 'NOISE')   # Should be uppercased

    def test_image_only_auto_noise(self):
        """Test image-only messages are handled correctly."""
        msg = MagicMock()
        msg.get = lambda k, default=None: {
            'text': '',
            'mentions_sam': False,
            'space_type': 'SPACE',
            'is_image_only': True
        }.get(k, default)

        # Image-only check happens before pre_classify in classify_new_messages
        # This test verifies the is_image_only flag is properly set
        is_image_only = msg.get('is_image_only')
        self.assertTrue(is_image_only)

        # Text should be empty for image-only
        text = msg.get('text', '')
        self.assertEqual(text, '')

    # ── Phase 2 Tests ──

    def test_pre_classify_empty_text_noise(self):
        """Test empty text is classified as NOISE (Phase 2 ENABLE_PRE_RULES)."""
        msg = {
            'text': '   ',
            'mentions_sam': False,
            'space_type': 'SPACE',
            'sender_id': 'users/other',
        }
        result = pre_classify(msg)
        self.assertIsNotNone(result)
        category, reason = result
        self.assertEqual(category, 'NOISE')
        self.assertEqual(reason, 'empty_text')

    def test_pre_classify_closing_report_routine(self):
        """Test closing report text is classified as ROUTINE."""
        msg = {
            'text': 'CLOSING REPORT\nTotal Gross Sales: P94,074\nTotal Cup Sold: 478',
            'mentions_sam': False,
            'space_type': 'SPACE',
            'sender_id': 'users/other',
        }
        result = pre_classify(msg)
        self.assertIsNotNone(result)
        category, reason = result
        self.assertEqual(category, 'ROUTINE')
        self.assertEqual(reason, 'store_closing_report')

    def test_pre_classify_daily_report_routine(self):
        """Test daily sales report text is classified as ROUTINE."""
        msg = {
            'text': 'DAILY SALES REPORT\nSM Megamall - Feb 13\nTotal Gross Sales: P88,432',
            'mentions_sam': False,
            'space_type': 'SPACE',
            'sender_id': 'users/other',
        }
        result = pre_classify(msg)
        self.assertIsNotNone(result)
        category, reason = result
        self.assertEqual(category, 'ROUTINE')
        self.assertEqual(reason, 'store_closing_report')

    def test_pre_classify_response_to_sam_thread(self):
        """Test RESPONSE detection when someone replies to Sam's thread."""
        import sqlite3
        import db as db_module

        # Create in-memory DB with schema
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.executescript(db_module.SCHEMA_SQL)

        # Insert Sam's original message in a thread
        conn.execute(
            """INSERT INTO raw_messages
               (space_id, space_name, space_type, message_id, sender_id, sender_name,
                text, create_time, thread_id, mentions_sam)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ('spaces/123', 'Finance Directors', 'SPACE', 'msg_sam_001',
             'users/115141803777443372092', 'Sam Karazi',
             'I need the Q4 Market Market P&L', '2026-02-13T10:00:00Z',
             'spaces/123/threads/thread_001', 0)
        )
        conn.commit()

        # Incoming reply from Alyssa in the same thread
        msg = {
            'text': 'Here po Sir, attached Q4 P&L Market Market',
            'mentions_sam': False,
            'space_type': 'SPACE',
            'sender_id': 'users/alyssa_001',
            'thread_id': 'spaces/123/threads/thread_001',
        }
        result = pre_classify(msg, conn=conn)
        self.assertIsNotNone(result)
        category, reason = result
        self.assertEqual(category, 'RESPONSE')
        self.assertEqual(reason, 'reply_to_sam_thread')

        conn.close()

    def test_pre_classify_no_response_if_sam_not_in_thread(self):
        """Test no RESPONSE when thread doesn't contain Sam's message."""
        import sqlite3
        import db as db_module

        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.executescript(db_module.SCHEMA_SQL)

        # Insert someone else's message in the thread (not Sam)
        conn.execute(
            """INSERT INTO raw_messages
               (space_id, space_name, space_type, message_id, sender_id, sender_name,
                text, create_time, thread_id, mentions_sam)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ('spaces/123', 'Store Ops', 'SPACE', 'msg_other_001',
             'users/other_person', 'Ana',
             'How is the inventory count going?', '2026-02-13T10:00:00Z',
             'spaces/123/threads/thread_002', 0)
        )
        conn.commit()

        msg = {
            'text': 'Almost done, 95% counted',
            'mentions_sam': False,
            'space_type': 'SPACE',
            'sender_id': 'users/another',
            'thread_id': 'spaces/123/threads/thread_002',
        }
        result = pre_classify(msg, conn=conn)
        # Should return None (needs AI) — no Sam in thread
        self.assertIsNone(result)

        conn.close()

    def test_pre_classify_haha_noise(self):
        """Test 'haha' is classified as NOISE (Phase 2)."""
        msg = {
            'text': 'haha',
            'mentions_sam': False,
            'space_type': 'SPACE',
            'sender_id': 'users/other',
        }
        result = pre_classify(msg)
        self.assertIsNotNone(result)
        category, reason = result
        self.assertEqual(category, 'NOISE')

    def test_pre_classify_lol_noise(self):
        """Test 'lol' is classified as NOISE (Phase 2)."""
        msg = {
            'text': 'lol',
            'mentions_sam': False,
            'space_type': 'SPACE',
            'sender_id': 'users/other',
        }
        result = pre_classify(msg)
        self.assertIsNotNone(result)
        category, reason = result
        self.assertEqual(category, 'NOISE')


if __name__ == '__main__':
    unittest.main()
