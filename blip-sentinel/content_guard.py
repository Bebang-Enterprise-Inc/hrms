"""
Blip Sentinel - Content Guard

Detects sensitive content in messages to prevent accidental exposure.
Screens for financial data, personnel matters, and profanity.
"""

import re
import logging
from typing import Dict

logger = logging.getLogger("sentinel.content_guard")

# Financial patterns (Philippine peso, USD, generic currency)
FINANCIAL_PATTERNS = [
    r'P\d{1,3}(,\d{3})*(\.\d{2})?',  # P1,000.00, P50,000, etc.
    r'PHP\s*\d[\d,]*(\.\d{2})?',      # PHP 1000, PHP 50000.00
    r'\$\d[\d,]*(\.\d{2})?',          # $1000, $50,000.00
    r'₱\d[\d,]*(\.\d{2})?',           # ₱1000, ₱50,000.00
    r'\d{1,3}(,\d{3})+(\.\d{2})?',    # Generic large numbers with commas
]

# Personnel/HR keywords (case-insensitive)
PERSONNEL_KEYWORDS = [
    'terminate', 'termination', 'terminated', 'firing', 'fired',
    'suspension', 'suspended', 'disciplinary action',
    'salary', 'compensation', 'bonus', 'incentive',
    'performance review', 'performance improvement',
    'confidential', 'extremely confidential', 'private',
    'resignation', 'resigned', 'separation',
    'demotion', 'demoted', 'promotion denied',
    'investigation', 'misconduct', 'violation',
    'warning', 'written warning', 'final warning',
]

# Profanity words (basic list - can be expanded)
PROFANITY_WORDS = [
    'fuck', 'shit', 'bullshit', 'damn', 'ass', 'bitch',
    'bastard', 'crap', 'piss', 'asshole',
    'gago', 'putang ina', 'tangina', 'tarantado',
    'ulol', 'bobo', 'tanga', 'leche',
]


def _check_financial(text: str) -> bool:
    """
    Check if text contains financial information.

    Args:
        text: Text to analyze

    Returns:
        True if financial patterns detected
    """
    for pattern in FINANCIAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger.debug(f"Financial pattern detected: {pattern}")
            return True
    return False


def _check_personnel(text: str) -> bool:
    """
    Check if text contains personnel/HR sensitive keywords.

    Args:
        text: Text to analyze

    Returns:
        True if personnel keywords detected
    """
    text_lower = text.lower()
    for keyword in PERSONNEL_KEYWORDS:
        if keyword.lower() in text_lower:
            logger.debug(f"Personnel keyword detected: {keyword}")
            return True
    return False


def _check_profanity(text: str) -> bool:
    """
    Check if text contains profanity.

    Args:
        text: Text to analyze

    Returns:
        True if profanity detected
    """
    text_lower = text.lower()
    for word in PROFANITY_WORDS:
        # Use word boundaries to avoid false positives
        pattern = r'\b' + re.escape(word.lower()) + r'\b'
        if re.search(pattern, text_lower):
            logger.debug(f"Profanity detected: {word}")
            return True
    return False


def is_sensitive(text: str) -> bool:
    """
    Check if text contains any sensitive content.

    Args:
        text: Text to analyze

    Returns:
        True if any sensitivity detected (financial, personnel, or profanity)

    Example:
        >>> is_sensitive("Salary increase to P50,000")
        True
        >>> is_sensitive("Meeting at 3pm")
        False
    """
    if not text or not text.strip():
        return False

    return (_check_financial(text) or
            _check_personnel(text) or
            _check_profanity(text))


def get_sensitivity_flags(text: str) -> Dict[str, bool]:
    """
    Get detailed sensitivity analysis.

    Args:
        text: Text to analyze

    Returns:
        Dictionary with keys 'financial', 'personnel', 'profanity'

    Example:
        >>> get_sensitivity_flags("Termination with P100,000 separation pay")
        {'financial': True, 'personnel': True, 'profanity': False}
    """
    if not text or not text.strip():
        return {'financial': False, 'personnel': False, 'profanity': False}

    flags = {
        'financial': _check_financial(text),
        'personnel': _check_personnel(text),
        'profanity': _check_profanity(text),
    }

    return flags


def redact_for_notification(text: str, space_name: str) -> str:
    """
    Redact sensitive content for notifications.

    If text is sensitive, return a redaction notice.
    Otherwise, return original text.

    Args:
        text: Original message text
        space_name: Name of the Google Chat space (for context)

    Returns:
        Redacted text or original text

    Example:
        >>> redact_for_notification("P50,000 bonus approved", "HR - Leadership")
        '[Sensitive — check DM directly in HR - Leadership]'
        >>> redact_for_notification("Meeting at 3pm", "Store Ops")
        'Meeting at 3pm'
    """
    if not text or not text.strip():
        return text

    if is_sensitive(text):
        logger.info(f"Redacting sensitive content for notification (space: {space_name})")
        return f"[Sensitive — check DM directly in {space_name}]"

    return text


def get_redaction_stats(text: str) -> Dict[str, any]:
    """
    Get detailed redaction analysis for logging/debugging.

    Args:
        text: Text to analyze

    Returns:
        Dictionary with sensitivity flags, is_sensitive bool, and redacted text

    Example:
        >>> stats = get_redaction_stats("Salary: P50,000")
        >>> stats['is_sensitive']
        True
        >>> stats['flags']['financial']
        True
    """
    flags = get_sensitivity_flags(text)
    sensitive = any(flags.values())

    return {
        'is_sensitive': sensitive,
        'flags': flags,
        'original_length': len(text) if text else 0,
        'redacted': sensitive,
    }


# Compile regex patterns on module load for performance
_compiled_patterns = {
    'financial': [re.compile(p, re.IGNORECASE) for p in FINANCIAL_PATTERNS]
}

logger.info(f"ContentGuard initialized: {len(FINANCIAL_PATTERNS)} financial patterns, "
            f"{len(PERSONNEL_KEYWORDS)} personnel keywords, {len(PROFANITY_WORDS)} profanity words")
