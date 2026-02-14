"""
Tests for feature flag system in feature_flags.py
"""

import pytest
import os
import feature_flags


def test_default_flag_values():
    """Test default flag values match expected states."""
    # Phase 0 flags should be ON by default
    assert feature_flags.is_enabled('ENABLE_RATE_LIMITING') is True
    assert feature_flags.is_enabled('ENABLE_CIRCUIT_BREAKER') is True
    assert feature_flags.is_enabled('ENABLE_CONTENT_GUARD') is True
    assert feature_flags.is_enabled('ENABLE_MESSAGE_DEDUP') is True

    # Phase 1 flags should be ON (Phase 1 activated)
    assert feature_flags.is_enabled('ENABLE_SELF_FILTER') is True


def test_env_var_override_true(monkeypatch):
    """Test env var can enable a flag."""
    monkeypatch.setenv('ENABLE_SELF_FILTER', '1')
    assert feature_flags.is_enabled('ENABLE_SELF_FILTER') is True

    monkeypatch.setenv('ENABLE_SELF_FILTER', 'true')
    assert feature_flags.is_enabled('ENABLE_SELF_FILTER') is True

    monkeypatch.setenv('ENABLE_SELF_FILTER', 'yes')
    assert feature_flags.is_enabled('ENABLE_SELF_FILTER') is True

    monkeypatch.setenv('ENABLE_SELF_FILTER', 'on')
    assert feature_flags.is_enabled('ENABLE_SELF_FILTER') is True


def test_env_var_override_false(monkeypatch):
    """Test env var can disable a flag."""
    monkeypatch.setenv('ENABLE_RATE_LIMITING', '0')
    assert feature_flags.is_enabled('ENABLE_RATE_LIMITING') is False

    monkeypatch.setenv('ENABLE_RATE_LIMITING', 'false')
    assert feature_flags.is_enabled('ENABLE_RATE_LIMITING') is False

    monkeypatch.setenv('ENABLE_RATE_LIMITING', 'no')
    assert feature_flags.is_enabled('ENABLE_RATE_LIMITING') is False


def test_get_all_flags_returns_complete_dict():
    """Test get_all_flags() returns all flag states."""
    flags = feature_flags.get_all_flags()

    # Should contain all default flags
    assert 'ENABLE_RATE_LIMITING' in flags
    assert 'ENABLE_SELF_FILTER' in flags
    assert 'ENABLE_PRE_RULES' in flags
    assert 'ENABLE_EVENING_BRIEFING' in flags

    # All values should be boolean
    for value in flags.values():
        assert isinstance(value, bool)


def test_is_enabled_with_invalid_flag():
    """Test is_enabled() raises ValueError for unknown flag."""
    with pytest.raises(ValueError, match="Unknown feature flag"):
        feature_flags.is_enabled('INVALID_FLAG_NAME')


def test_get_active_phase_default():
    """Test get_active_phase() returns 5 for default config (Phase 5 active)."""
    # With default flags (Phase 0-5 ON), should return 5
    phase = feature_flags.get_active_phase()
    assert phase == 5


def test_get_active_phase_with_phase_1(monkeypatch):
    """Test get_active_phase() returns 1 when only Phase 1 enabled."""
    monkeypatch.setenv('ENABLE_SELF_FILTER', '1')
    # Disable Phase 2-5 flags to isolate Phase 1
    monkeypatch.setenv('ENABLE_PRE_RULES', '0')
    monkeypatch.setenv('ENABLE_RESPONSE_DETECTION', '0')
    monkeypatch.setenv('ENABLE_ROUTINE_CLASSIFICATION', '0')
    monkeypatch.setenv('ENABLE_RESPONSE_FIRST_DIGEST', '0')
    monkeypatch.setenv('ENABLE_STORE_SUMMARY', '0')
    monkeypatch.setenv('ENABLE_EVENING_BRIEFING', '0')
    assert feature_flags.get_active_phase() == 1


def test_get_active_phase_with_phase_2(monkeypatch):
    """Test get_active_phase() returns 2 when Phase 2 enabled but higher phases disabled."""
    monkeypatch.setenv('ENABLE_PRE_RULES', '1')
    monkeypatch.setenv('ENABLE_RESPONSE_FIRST_DIGEST', '0')
    monkeypatch.setenv('ENABLE_STORE_SUMMARY', '0')
    monkeypatch.setenv('ENABLE_EVENING_BRIEFING', '0')
    assert feature_flags.get_active_phase() == 2


def test_get_active_phase_with_highest_phase(monkeypatch):
    """Test get_active_phase() returns highest enabled phase."""
    # Enable multiple phases
    monkeypatch.setenv('ENABLE_SELF_FILTER', '1')  # Phase 1
    monkeypatch.setenv('ENABLE_PRE_RULES', '1')  # Phase 2
    monkeypatch.setenv('ENABLE_STORE_SUMMARY', '1')  # Phase 4
    # Disable Phase 5 to isolate Phase 4 as highest
    monkeypatch.setenv('ENABLE_EVENING_BRIEFING', '0')

    # Should return highest (4)
    assert feature_flags.get_active_phase() == 4


def test_case_insensitive_env_values(monkeypatch):
    """Test env var parsing is case-insensitive."""
    monkeypatch.setenv('ENABLE_SELF_FILTER', 'TRUE')
    assert feature_flags.is_enabled('ENABLE_SELF_FILTER') is True

    monkeypatch.setenv('ENABLE_SELF_FILTER', 'Yes')
    assert feature_flags.is_enabled('ENABLE_SELF_FILTER') is True

    monkeypatch.setenv('ENABLE_SELF_FILTER', 'ON')
    assert feature_flags.is_enabled('ENABLE_SELF_FILTER') is True
