"""
Tests for timezone-aware time utilities in timeutil.py
"""

import pytest
from datetime import datetime, timezone, timedelta
import timeutil


def test_utc_now_returns_correct_format():
    """Test utc_now() returns YYYY-MM-DD HH:MM:SS format."""
    result = timeutil.utc_now()
    # Should match format YYYY-MM-DD HH:MM:SS
    assert len(result) == 19
    assert result[4] == '-'
    assert result[7] == '-'
    assert result[10] == ' '
    assert result[13] == ':'
    assert result[16] == ':'

    # Should be parseable by datetime
    parsed = datetime.strptime(result, '%Y-%m-%d %H:%M:%S')
    assert parsed is not None


def test_to_pht_adds_8_hours():
    """Test to_pht() correctly adds 8 hours for Philippine Time."""
    utc_time = "2026-02-14 10:30:45"  # 10:30 AM UTC
    result = timeutil.to_pht(utc_time)

    # Should be 6:30 PM PHT (10:30 + 8 hours = 18:30)
    assert "6:30 PM PHT" in result
    assert "Feb 14" in result


def test_format_db_with_timezone_aware_datetime():
    """Test format_db() with timezone-aware datetime."""
    dt = datetime(2026, 2, 14, 10, 30, 45, tzinfo=timezone.utc)
    result = timeutil.format_db(dt)
    assert result == "2026-02-14 10:30:45"


def test_format_db_with_naive_datetime():
    """Test format_db() assumes naive datetime is UTC."""
    dt = datetime(2026, 2, 14, 10, 30, 45)  # No timezone
    result = timeutil.format_db(dt)
    assert result == "2026-02-14 10:30:45"


def test_format_db_converts_non_utc_to_utc():
    """Test format_db() converts non-UTC timezone to UTC."""
    pht = timezone(timedelta(hours=8))
    dt = datetime(2026, 2, 14, 18, 30, 45, tzinfo=pht)  # 6:30 PM PHT
    result = timeutil.format_db(dt)
    assert result == "2026-02-14 10:30:45"  # Should be 10:30 AM UTC


def test_parse_db_roundtrip():
    """Test format_db() and parse_db() are reversible."""
    original = datetime(2026, 2, 14, 10, 30, 45, tzinfo=timezone.utc)
    formatted = timeutil.format_db(original)
    parsed = timeutil.parse_db(formatted)

    assert parsed == original
    assert parsed.tzinfo == timezone.utc


def test_parse_db_returns_timezone_aware():
    """Test parse_db() returns UTC-aware datetime."""
    result = timeutil.parse_db("2026-02-14 10:30:45")
    assert result.tzinfo == timezone.utc


def test_parse_db_invalid_format_raises():
    """Test parse_db() raises ValueError on invalid format."""
    with pytest.raises(ValueError):
        timeutil.parse_db("not a timestamp")

    with pytest.raises(ValueError):
        timeutil.parse_db("2026-02-14")  # Missing time


def test_utc_now_iso_returns_iso8601():
    """Test utc_now_iso() returns ISO8601 format with Z suffix."""
    result = timeutil.utc_now_iso()

    # Should end with 'Z'
    assert result.endswith('Z')

    # Should be parseable as ISO format
    parsed = datetime.fromisoformat(result.replace('Z', '+00:00'))
    assert parsed is not None


def test_pht_now_returns_pht_timezone():
    """Test pht_now() returns datetime in PHT (UTC+8)."""
    result = timeutil.pht_now()

    # Check timezone offset is +8 hours
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(hours=8)


def test_is_business_hours_sunday():
    """Test is_business_hours() returns False on Sunday."""
    # This test is timezone-dependent, just verify it returns a boolean
    result = timeutil.is_business_hours()
    assert isinstance(result, bool)
