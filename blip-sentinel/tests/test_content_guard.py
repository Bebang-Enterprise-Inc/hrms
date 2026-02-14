"""
Tests for sensitive content detection in content_guard.py
"""

import pytest
import content_guard


def test_financial_pattern_peso_with_comma():
    """Test detection of Philippine peso amounts with commas."""
    assert content_guard.is_sensitive("Salary increase to P45,000") is True
    assert content_guard.is_sensitive("Budget is P1,500,000") is True


def test_financial_pattern_php():
    """Test detection of PHP currency prefix."""
    assert content_guard.is_sensitive("Transfer PHP 100,000 to savings") is True
    assert content_guard.is_sensitive("PHP 50000.00 approved") is True


def test_financial_pattern_usd():
    """Test detection of USD amounts."""
    assert content_guard.is_sensitive("Payment of $500 due") is True
    assert content_guard.is_sensitive("Budget: $10,000") is True


def test_financial_pattern_peso_sign():
    """Test detection of peso sign."""
    assert content_guard.is_sensitive("₱1,000 bonus") is True


def test_personnel_keyword_termination():
    """Test detection of termination keywords."""
    assert content_guard.is_sensitive("We need to terminate John") is True
    assert content_guard.is_sensitive("Employee was terminated") is True


def test_personnel_keyword_salary():
    """Test detection of salary/compensation keywords."""
    assert content_guard.is_sensitive("His salary is too high") is True
    assert content_guard.is_sensitive("Compensation review needed") is True


def test_personnel_keyword_confidential():
    """Test detection of confidentiality markers."""
    assert content_guard.is_sensitive("This is extremely confidential") is True
    assert content_guard.is_sensitive("Private personnel matter") is True


def test_non_sensitive_text_passes():
    """Test that normal text is not flagged as sensitive."""
    assert content_guard.is_sensitive("Meeting at 3pm today") is False
    assert content_guard.is_sensitive("Can you review the report?") is False
    assert content_guard.is_sensitive("Thanks for the update") is False


def test_empty_text():
    """Test that empty text is not sensitive."""
    assert content_guard.is_sensitive("") is False
    assert content_guard.is_sensitive("   ") is False


def test_redact_for_notification_with_sensitive_content():
    """Test redact_for_notification() redacts sensitive text."""
    text = "Salary increase to P50,000"
    space = "HR - Leadership"
    result = content_guard.redact_for_notification(text, space)

    assert result == "[Sensitive — check DM directly in HR - Leadership]"


def test_redact_for_notification_with_clean_content():
    """Test redact_for_notification() passes through clean text."""
    text = "Meeting at 3pm"
    space = "Store Ops"
    result = content_guard.redact_for_notification(text, space)

    assert result == "Meeting at 3pm"


def test_get_sensitivity_flags_with_financial():
    """Test get_sensitivity_flags() detects financial content."""
    text = "Budget is P100,000"
    flags = content_guard.get_sensitivity_flags(text)

    assert flags['financial'] is True
    assert flags['personnel'] is False
    assert flags['profanity'] is False


def test_get_sensitivity_flags_with_personnel():
    """Test get_sensitivity_flags() detects personnel content."""
    text = "Termination letter ready"
    flags = content_guard.get_sensitivity_flags(text)

    assert flags['financial'] is False
    assert flags['personnel'] is True
    assert flags['profanity'] is False


def test_get_sensitivity_flags_with_multiple():
    """Test get_sensitivity_flags() detects multiple types."""
    text = "Termination with P100,000 separation pay"
    flags = content_guard.get_sensitivity_flags(text)

    assert flags['financial'] is True
    assert flags['personnel'] is True
    assert flags['profanity'] is False


def test_get_sensitivity_flags_with_clean_text():
    """Test get_sensitivity_flags() returns all False for clean text."""
    text = "Meeting tomorrow at 2pm"
    flags = content_guard.get_sensitivity_flags(text)

    assert flags['financial'] is False
    assert flags['personnel'] is False
    assert flags['profanity'] is False


def test_profanity_detection():
    """Test profanity detection works."""
    assert content_guard.is_sensitive("This is bullshit") is True
    assert content_guard.is_sensitive("Gago talaga yan") is True


def test_profanity_word_boundaries():
    """Test profanity uses word boundaries (no false positives)."""
    # "class" contains "ass" but shouldn't be flagged
    assert content_guard.is_sensitive("The class starts at 2pm") is False
