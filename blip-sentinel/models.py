"""
Blip Sentinel - Message Classification Models

Defines the classification taxonomy for Google Chat messages.
"""

from enum import Enum


class MessageClassification(str, Enum):
    """
    Classification categories for Google Chat messages.

    Categories are ordered from highest to lowest priority for triage:
    - URGENT: Immediate attention required
    - ACTION: Requires action from Sam (explicit @mention or request)
    - FYI: Informational, no action required but should be aware
    - RESPONSE: Reply to a message Sam sent (may need follow-up)
    - ROUTINE: Regular operational messages (team updates, status reports)
    - NOISE: Low-value messages (spam, notifications, automated messages)
    - DUPLICATE: Identical or near-identical to a recent message
    - SELF: Messages sent by Sam himself
    - UNCLASSIFIED: Classification failed or pending
    """

    SELF = "SELF"
    NOISE = "NOISE"
    ROUTINE = "ROUTINE"
    RESPONSE = "RESPONSE"
    URGENT = "URGENT"
    ACTION = "ACTION"
    FYI = "FYI"
    DUPLICATE = "DUPLICATE"
    UNCLASSIFIED = "UNCLASSIFIED"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """
        Check if a string value is a valid classification.

        Args:
            value: String to validate

        Returns:
            True if value is a valid classification, False otherwise
        """
        return value in cls._value2member_map_

    @classmethod
    def actionable(cls) -> list:
        """
        Get list of classifications that require action.

        Returns:
            List of MessageClassification values that need Sam's attention
        """
        return [cls.URGENT, cls.ACTION, cls.FYI]

    @classmethod
    def excluded_from_digest(cls) -> list:
        """
        Get list of classifications excluded from daily digest.

        Returns:
            List of MessageClassification values to filter out of summaries
        """
        return [cls.SELF, cls.NOISE, cls.ROUTINE, cls.DUPLICATE]

    def __str__(self) -> str:
        """Return the enum value as a string."""
        return self.value
