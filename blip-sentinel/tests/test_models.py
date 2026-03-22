"""
Tests for MessageClassification enum in models.py
"""

import pytest
from models import MessageClassification


def test_all_enum_values_exist():
    """Test that all expected classification values are defined."""
    expected = {
        "SELF", "NOISE", "ROUTINE", "RESPONSE",
        "URGENT", "ACTION", "FYI", "DUPLICATE", "UNCLASSIFIED"
    }
    actual = {e.value for e in MessageClassification}
    assert actual == expected


def test_is_valid_with_valid_strings():
    """Test is_valid() returns True for valid classification strings."""
    assert MessageClassification.is_valid("URGENT") is True
    assert MessageClassification.is_valid("ACTION") is True
    assert MessageClassification.is_valid("FYI") is True
    assert MessageClassification.is_valid("NOISE") is True
    assert MessageClassification.is_valid("SELF") is True
    assert MessageClassification.is_valid("ROUTINE") is True
    assert MessageClassification.is_valid("DUPLICATE") is True


def test_is_valid_with_invalid_strings():
    """Test is_valid() returns False for invalid strings."""
    assert MessageClassification.is_valid("INVALID") is False
    assert MessageClassification.is_valid("urgent") is False  # lowercase
    assert MessageClassification.is_valid("") is False
    assert MessageClassification.is_valid("SPAM") is False


def test_actionable_returns_correct_list():
    """Test actionable() returns URGENT, ACTION, FYI."""
    actionable = MessageClassification.actionable()
    assert len(actionable) == 3
    assert MessageClassification.URGENT in actionable
    assert MessageClassification.ACTION in actionable
    assert MessageClassification.FYI in actionable
    assert MessageClassification.NOISE not in actionable


def test_excluded_from_digest_returns_correct_list():
    """Test excluded_from_digest() returns SELF, NOISE, ROUTINE, DUPLICATE."""
    excluded = MessageClassification.excluded_from_digest()
    assert len(excluded) == 4
    assert MessageClassification.SELF in excluded
    assert MessageClassification.NOISE in excluded
    assert MessageClassification.ROUTINE in excluded
    assert MessageClassification.DUPLICATE in excluded
    assert MessageClassification.URGENT not in excluded


def test_enum_string_comparison():
    """Test that enum values can be compared as strings."""
    assert MessageClassification.URGENT.value == "URGENT"
    assert MessageClassification.ACTION.value == "ACTION"
    assert str(MessageClassification.URGENT) == "URGENT"


def test_enum_members_have_unique_values():
    """Test that all enum members have unique values."""
    values = [e.value for e in MessageClassification]
    assert len(values) == len(set(values))  # No duplicates
