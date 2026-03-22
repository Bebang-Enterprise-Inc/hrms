"""
Blip Sentinel - Time Utilities

Provides timezone-aware time handling for UTC (storage) and PHT (display).
All database timestamps use UTC. User-facing displays use PHT (UTC+8).
"""

from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger("sentinel.timeutil")

# Philippine Time is UTC+8
PHT_OFFSET = timezone(timedelta(hours=8))


def utc_now() -> str:
    """
    Get current UTC timestamp in SQLite-compatible format.

    Returns:
        UTC timestamp string in format 'YYYY-MM-DD HH:MM:SS'

    Example:
        >>> utc_now()
        '2026-02-14 10:30:45'
    """
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def utc_now_iso() -> str:
    """
    Get current UTC timestamp in ISO8601 format for API calls.

    Returns:
        UTC timestamp in ISO8601 format with 'Z' suffix

    Example:
        >>> utc_now_iso()
        '2026-02-14T10:30:45Z'
    """
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def format_db(dt: datetime) -> str:
    """
    Format a datetime object to database storage format (UTC).

    Args:
        dt: datetime object (timezone-aware or naive)

    Returns:
        UTC timestamp string in format 'YYYY-MM-DD HH:MM:SS'

    Example:
        >>> dt = datetime(2026, 2, 14, 10, 30, 45)
        >>> format_db(dt)
        '2026-02-14 10:30:45'
    """
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC if timezone-aware
        dt = dt.astimezone(timezone.utc)

    return dt.strftime('%Y-%m-%d %H:%M:%S')


def parse_db(s: str) -> datetime:
    """
    Parse a database timestamp string to a timezone-aware datetime object.

    Args:
        s: UTC timestamp string in format 'YYYY-MM-DD HH:MM:SS'

    Returns:
        Timezone-aware datetime object in UTC

    Raises:
        ValueError: If string format is invalid

    Example:
        >>> dt = parse_db('2026-02-14 10:30:45')
        >>> dt.tzinfo
        datetime.timezone.utc
    """
    try:
        dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
        return dt.replace(tzinfo=timezone.utc)
    except ValueError as e:
        logger.error(f"Failed to parse timestamp '{s}': {e}")
        raise


def to_pht(utc_str: str) -> str:
    """
    Convert UTC timestamp string to PHT display format.

    Args:
        utc_str: UTC timestamp string in format 'YYYY-MM-DD HH:MM:SS'

    Returns:
        Human-readable PHT timestamp (e.g., 'Jan 14, 6:30 PM PHT')

    Example:
        >>> to_pht('2026-02-14 10:30:45')
        'Feb 14, 6:30 PM PHT'
    """
    try:
        dt_utc = parse_db(utc_str)
        dt_pht = dt_utc.astimezone(PHT_OFFSET)

        # Format: "Feb 14, 6:30 PM PHT"
        month = dt_pht.strftime('%b')
        day = dt_pht.day
        hour = dt_pht.hour
        minute = dt_pht.minute

        # 12-hour format
        period = 'AM' if hour < 12 else 'PM'
        hour_12 = hour % 12
        if hour_12 == 0:
            hour_12 = 12

        return f"{month} {day}, {hour_12}:{minute:02d} {period} PHT"

    except ValueError as e:
        logger.error(f"Failed to convert UTC to PHT: {e}")
        return f"[Invalid timestamp: {utc_str}]"


def pht_now() -> datetime:
    """
    Get current datetime in Philippine Time.

    Returns:
        Timezone-aware datetime object in PHT
    """
    return datetime.now(PHT_OFFSET)


def is_business_hours() -> bool:
    """
    Check if current PHT time is within business hours (8 AM - 6 PM Mon-Sat).

    Returns:
        True if currently business hours in PHT, False otherwise
    """
    now_pht = pht_now()

    # Sunday = 6 in Python's weekday()
    if now_pht.weekday() == 6:
        return False

    # Business hours: 8 AM to 6 PM
    return 8 <= now_pht.hour < 18
