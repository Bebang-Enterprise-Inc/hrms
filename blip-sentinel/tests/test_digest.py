"""
Tests for Phase 3 response-first digest in digest.py
"""

import sqlite3
import unittest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db as db_module
from digest import _build_response_first_digest, _safe_text


def _make_msg(**kwargs):
    """Create a dict that mimics a sqlite3.Row for message data."""
    defaults = {
        "id": 1,
        "space_id": "spaces/123",
        "space_name": "Finance Directors",
        "space_type": "SPACE",
        "message_id": "msg_001",
        "sender_id": "users/alyssa",
        "sender_name": "Alyssa",
        "text": "Here is the report",
        "has_attachment": 0,
        "is_image_only": 0,
        "create_time": "2026-02-13T10:00:00Z",
        "thread_id": None,
        "mentions_sam": 0,
        "collected_at": "2026-02-13 10:00:00",
        "classification": "FYI",
        "classification_reason": "general",
        "classified_at": "2026-02-13 10:00:01",
        "classified_by": "haiku",
        "included_in_briefing": None,
        "text_hash": None,
        "contains_sensitive": 0,
        "parent_message_id": None,
        "parent_sender_id": None,
    }
    defaults.update(kwargs)
    return defaults


def _make_email(**kwargs):
    """Create a dict that mimics a sqlite3.Row for email data."""
    defaults = {
        "id": 1,
        "gmail_id": "email_001",
        "from_addr": "vendor@example.com",
        "subject": "Invoice attached",
        "date": "2026-02-13",
        "snippet": "Please find attached...",
        "labels": "INBOX",
        "is_unread": 1,
        "collected_at": "2026-02-13 10:00:00",
        "classification": "ACTION",
        "classification_reason": "invoice",
        "classified_at": "2026-02-13 10:00:01",
        "classified_by": "haiku",
        "included_in_briefing": None,
    }
    defaults.update(kwargs)
    return defaults


class TestResponseFirstDigest(unittest.TestCase):

    def _get_conn(self):
        """Create in-memory DB with schema."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(db_module.SCHEMA_SQL)
        return conn

    def test_responses_section_with_sam_context(self):
        """Test RESPONSES TO YOU section shows Sam's original question."""
        conn = self._get_conn()

        # Insert Sam's original message in thread
        conn.execute(
            """INSERT INTO raw_messages
               (space_id, space_name, space_type, message_id, sender_id, sender_name,
                text, create_time, thread_id, mentions_sam)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("spaces/123", "Finance Directors", "SPACE", "msg_sam_001",
             "users/115141803777443372092", "Sam Karazi",
             "I need the Q4 Market Market P&L", "2026-02-13T09:00:00Z",
             "spaces/123/threads/t1", 0),
        )
        conn.commit()

        responses = [_make_msg(
            classification="RESPONSE",
            sender_name="Alyssa",
            text="Here po Sir, attached Q4 P&L Market Market",
            thread_id="spaces/123/threads/t1",
        )]

        result = _build_response_first_digest(
            conn, responses=responses, urgent_action=[], fyi=[], emails=[],
            noise_count=10, routine_count=5,
        )
        conn.close()

        self.assertIn("**RESPONSES TO YOU** (1)", result)
        self.assertIn('Re: "I need the Q4 Market Market P&L"', result)
        self.assertIn("**Alyssa**", result)

    def test_responses_section_without_sam_context(self):
        """Test RESPONSES section when Sam's original is not found."""
        conn = self._get_conn()

        responses = [_make_msg(
            classification="RESPONSE",
            sender_name="Andrew",
            text="SEC certs pending, pricing ready for your review",
            thread_id="spaces/456/threads/t2",
        )]

        result = _build_response_first_digest(
            conn, responses=responses, urgent_action=[], fyi=[], emails=[],
            noise_count=0, routine_count=0,
        )
        conn.close()

        self.assertIn("**RESPONSES TO YOU** (1)", result)
        self.assertIn("**Andrew**: SEC certs pending", result)
        self.assertNotIn('Re: "', result)

    def test_needs_your_decision_section(self):
        """Test NEEDS YOUR DECISION section with urgent and action items."""
        conn = self._get_conn()

        urgent_action = [
            _make_msg(
                classification="URGENT",
                sender_name="Chimes",
                text="Alpha Law payment for approval in UB-BEI",
                space_name="Sam and Chimes",
                mentions_sam=0,
            ),
            _make_msg(
                id=2,
                message_id="msg_002",
                classification="ACTION",
                sender_name="Mae",
                text="PO needs your signature",
                space_name="Procurement",
                mentions_sam=0,
            ),
        ]

        result = _build_response_first_digest(
            conn, responses=[], urgent_action=urgent_action, fyi=[], emails=[],
            noise_count=0, routine_count=0,
        )
        conn.close()

        self.assertIn("**NEEDS YOUR DECISION** (2)", result)
        self.assertIn("🔴 **Chimes**", result)
        self.assertIn("🟡 **Mae**", result)

    def test_mentions_subsection(self):
        """Test MENTIONS sub-section within NEEDS YOUR DECISION."""
        conn = self._get_conn()

        urgent_action = [
            _make_msg(
                classification="URGENT",
                sender_name="Archie",
                text="@Sam need your approval on biometric reset",
                space_name="ERP Committee",
                mentions_sam=1,
            ),
        ]

        result = _build_response_first_digest(
            conn, responses=[], urgent_action=urgent_action, fyi=[], emails=[],
            noise_count=0, routine_count=0,
        )
        conn.close()

        self.assertIn("**MENTIONS** (1)", result)
        self.assertIn("**Archie** in ERP Committee", result)

    def test_fyi_section_capped_at_10(self):
        """Test FYI section is capped at 10 items."""
        conn = self._get_conn()

        fyi = [
            _make_msg(
                id=i,
                message_id=f"msg_fyi_{i:03d}",
                classification="FYI",
                sender_name=f"Person {i}",
                text=f"FYI message number {i}",
            )
            for i in range(15)
        ]

        result = _build_response_first_digest(
            conn, responses=[], urgent_action=[], fyi=fyi, emails=[],
            noise_count=0, routine_count=0,
        )
        conn.close()

        self.assertIn("**FYI** (15)", result)
        self.assertIn("Person 9", result)
        self.assertNotIn("Person 10", result)
        self.assertIn("...and 5 more", result)

    def test_emails_section(self):
        """Test EMAILS section with different classifications."""
        conn = self._get_conn()

        emails = [
            _make_email(classification="URGENT", from_addr="cfo@company.com", subject="Cash flow critical"),
            _make_email(id=2, gmail_id="email_002", classification="FYI", from_addr="newsletter@biz.com", subject="Weekly update"),
        ]

        result = _build_response_first_digest(
            conn, responses=[], urgent_action=[], fyi=[], emails=emails,
            noise_count=0, routine_count=0,
        )
        conn.close()

        self.assertIn("📧 **EMAILS** (2)", result)
        self.assertIn("🔴 **cfo@company.com**: Cash flow critical", result)
        self.assertIn("📝 **newsletter@biz.com**: Weekly update", result)

    def test_footer_with_noise_and_routine(self):
        """Test footer shows filtered counts."""
        conn = self._get_conn()

        fyi = [_make_msg(classification="FYI", text="Something informational")]

        result = _build_response_first_digest(
            conn, responses=[], urgent_action=[], fyi=fyi, emails=[],
            noise_count=125, routine_count=12,
        )
        conn.close()

        self.assertIn("125 noise", result)
        self.assertIn("12 store reports", result)

    def test_footer_omitted_when_no_filtered(self):
        """Test footer omitted when no noise or routine."""
        conn = self._get_conn()

        fyi = [_make_msg(classification="FYI", text="Just an FYI")]

        result = _build_response_first_digest(
            conn, responses=[], urgent_action=[], fyi=fyi, emails=[],
            noise_count=0, routine_count=0,
        )
        conn.close()

        self.assertNotIn("Filtered:", result)

    def test_empty_digest_returns_empty_string(self):
        """Test empty digest returns empty string."""
        conn = self._get_conn()

        result = _build_response_first_digest(
            conn, responses=[], urgent_action=[], fyi=[], emails=[],
            noise_count=0, routine_count=0,
        )
        conn.close()

        self.assertEqual(result, "")

    def test_full_digest_ordering(self):
        """Test sections appear in correct order: RESPONSES, DECISIONS, FYI, EMAILS."""
        conn = self._get_conn()

        responses = [_make_msg(classification="RESPONSE", sender_name="Alyssa", text="Reply text")]
        urgent = [_make_msg(id=2, message_id="msg_002", classification="URGENT", sender_name="Chimes",
                            text="Payment needed", space_name="DM", mentions_sam=0)]
        fyi = [_make_msg(id=3, message_id="msg_003", classification="FYI", sender_name="HR", text="Leave approved")]
        emails = [_make_email(classification="ACTION", from_addr="a@b.com", subject="Review")]

        result = _build_response_first_digest(
            conn, responses=responses, urgent_action=urgent, fyi=fyi, emails=emails,
            noise_count=5, routine_count=3,
        )
        conn.close()

        # Verify ordering
        idx_responses = result.index("RESPONSES TO YOU")
        idx_decision = result.index("NEEDS YOUR DECISION")
        idx_fyi = result.index("**FYI**")
        idx_email = result.index("**EMAILS**")

        self.assertLess(idx_responses, idx_decision)
        self.assertLess(idx_decision, idx_fyi)
        self.assertLess(idx_fyi, idx_email)


class TestSafeText(unittest.TestCase):

    def test_truncates_to_max_len(self):
        """Test text is truncated to max_len."""
        msg = _make_msg(text="A" * 300)
        result = _safe_text(msg, 100)
        self.assertEqual(len(result), 100)

    def test_handles_none_text(self):
        """Test None text returns empty string."""
        msg = _make_msg(text=None)
        result = _safe_text(msg)
        self.assertEqual(result, "")

    @patch("digest.is_enabled", return_value=True)
    @patch("digest.redact_for_notification", return_value="[REDACTED]")
    def test_redacts_sensitive_when_enabled(self, mock_redact, mock_flag):
        """Test sensitive content is redacted when content guard is enabled."""
        msg = _make_msg(text="Salary is P150,000", contains_sensitive=1, space_name="HR DM")
        result = _safe_text(msg, 200)
        self.assertEqual(result, "[REDACTED]")
        mock_redact.assert_called_once()

    def test_no_redaction_when_not_sensitive(self):
        """Test non-sensitive content is not redacted."""
        msg = _make_msg(text="Regular message", contains_sensitive=0)
        result = _safe_text(msg, 200)
        self.assertEqual(result, "Regular message")


if __name__ == "__main__":
    unittest.main()
