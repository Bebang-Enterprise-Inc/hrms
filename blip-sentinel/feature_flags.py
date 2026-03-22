"""
Blip Sentinel - Feature Flags

Environment-variable based feature flags for progressive rollout.
Phase 0-5 features can be toggled independently for testing.
"""

import os
import logging
from typing import Dict

logger = logging.getLogger("sentinel.feature_flags")

# Default flag states
DEFAULT_FLAGS = {
    # Phase 0: Foundation (default ON)
    "ENABLE_RATE_LIMITING": True,
    "ENABLE_CIRCUIT_BREAKER": True,
    "ENABLE_CONTENT_GUARD": True,
    "ENABLE_MESSAGE_DEDUP": True,

    # Phase 1: Self-filter (default ON — Phase 1 activated)
    "ENABLE_SELF_FILTER": True,

    # Phase 2: Classification (default ON — Phase 2 activated)
    "ENABLE_PRE_RULES": True,
    "ENABLE_RESPONSE_DETECTION": True,
    "ENABLE_ROUTINE_CLASSIFICATION": True,

    # Phase 3: Triage (default ON — Phase 3 activated)
    "ENABLE_RESPONSE_FIRST_DIGEST": True,

    # Phase 4: Summaries (default ON — Phase 4 activated)
    "ENABLE_STORE_SUMMARY": True,

    # Phase 5: Briefing (default ON — Phase 5 activated)
    "ENABLE_EVENING_BRIEFING": True,
}


def _parse_env_bool(value: str) -> bool:
    """
    Parse environment variable string to boolean.

    Args:
        value: Environment variable value

    Returns:
        True if value is '1', 'true', 'yes', 'on' (case-insensitive)
        False otherwise
    """
    return value.lower() in ('1', 'true', 'yes', 'on')


def is_enabled(flag_name: str) -> bool:
    """
    Check if a feature flag is enabled.

    Args:
        flag_name: Name of the feature flag (e.g., 'ENABLE_SELF_FILTER')

    Returns:
        True if flag is enabled, False otherwise

    Raises:
        ValueError: If flag_name is not a known feature flag

    Example:
        >>> is_enabled('ENABLE_RATE_LIMITING')
        True
        >>> is_enabled('ENABLE_SELF_FILTER')
        False
    """
    if flag_name not in DEFAULT_FLAGS:
        logger.warning(f"Unknown feature flag: {flag_name}")
        raise ValueError(f"Unknown feature flag: {flag_name}")

    # Check environment variable, fall back to default
    env_value = os.environ.get(flag_name)

    if env_value is not None:
        enabled = _parse_env_bool(env_value)
        logger.debug(f"Feature flag {flag_name} = {enabled} (from env)")
        return enabled
    else:
        default = DEFAULT_FLAGS[flag_name]
        logger.debug(f"Feature flag {flag_name} = {default} (default)")
        return default


def get_all_flags() -> Dict[str, bool]:
    """
    Get current state of all feature flags.

    Returns:
        Dictionary mapping flag names to their current enabled/disabled state

    Example:
        >>> flags = get_all_flags()
        >>> flags['ENABLE_RATE_LIMITING']
        True
    """
    flags = {}
    for flag_name in DEFAULT_FLAGS.keys():
        flags[flag_name] = is_enabled(flag_name)

    return flags


def get_active_phase() -> int:
    """
    Determine the highest active phase based on enabled flags.

    Returns:
        Integer from 0-5 representing the active phase

    Example:
        >>> get_active_phase()  # Only Phase 0 flags enabled
        0
    """
    if is_enabled('ENABLE_EVENING_BRIEFING'):
        return 5
    elif is_enabled('ENABLE_STORE_SUMMARY'):
        return 4
    elif is_enabled('ENABLE_RESPONSE_FIRST_DIGEST'):
        return 3
    elif is_enabled('ENABLE_PRE_RULES') or is_enabled('ENABLE_RESPONSE_DETECTION'):
        return 2
    elif is_enabled('ENABLE_SELF_FILTER'):
        return 1
    else:
        return 0


def log_active_flags():
    """
    Log all currently enabled feature flags.

    Useful for debugging and deployment verification.
    """
    active_flags = [name for name, enabled in get_all_flags().items() if enabled]
    phase = get_active_phase()

    logger.info(f"Active phase: {phase}")
    logger.info(f"Enabled flags ({len(active_flags)}): {', '.join(active_flags)}")


# Log flags on module import
if __name__ != "__main__":
    log_active_flags()
