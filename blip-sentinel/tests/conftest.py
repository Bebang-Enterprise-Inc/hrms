"""
Shared pytest fixtures for Blip Sentinel tests.
"""

import pytest
import sqlite3
import os
import sys

# Add parent directory to path so we can import blip-sentinel modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def db_conn():
    """Create an in-memory SQLite database with schema."""
    import db
    conn = db.init_db(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def sample_message():
    """Sample chat message dict for testing."""
    return {
        "id": 1,
        "space_id": "spaces/test",
        "space_name": "Test Space",
        "space_type": "SPACE",
        "message_id": "spaces/test/messages/1",
        "sender_id": "users/999",
        "sender_name": "Test User",
        "text": "Hello, can you review this?",
        "has_attachment": False,
        "is_image_only": False,
        "create_time": "2026-02-14T10:00:00Z",
        "thread_id": None,
        "mentions_sam": False,
    }


@pytest.fixture
def sam_message(sample_message):
    """Message from Sam (should be filtered as SELF)."""
    return {
        **sample_message,
        "sender_id": "users/115141803777443372092",
        "sender_name": "Sam Karazi",
    }


@pytest.fixture
def sensitive_message(sample_message):
    """Message with sensitive financial content."""
    return {
        **sample_message,
        "text": "We need to terminate John. His salary is P45,000 and this is extremely confidential.",
    }
