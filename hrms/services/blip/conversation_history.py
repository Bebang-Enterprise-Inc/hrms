"""
Conversation History Manager

Stores last N messages per conversation for context-aware responses.
Uses in-memory storage with TTL for automatic cleanup.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Configuration
MAX_MESSAGES_PER_CONVERSATION = 10  # Keep last 10 messages
CONVERSATION_TTL_HOURS = 24  # Clear conversations after 24 hours of inactivity


@dataclass
class Message:
    """A single message in conversation history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Conversation:
    """A conversation with message history."""
    messages: List[Message] = field(default_factory=list)
    last_activity: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str):
        """Add a message and trim to max size."""
        self.messages.append(Message(role=role, content=content))
        self.last_activity = datetime.now()

        # Keep only last N messages
        if len(self.messages) > MAX_MESSAGES_PER_CONVERSATION:
            self.messages = self.messages[-MAX_MESSAGES_PER_CONVERSATION:]

    def get_history_for_prompt(self) -> str:
        """Format history for inclusion in AI prompt."""
        if not self.messages:
            return ""

        lines = ["Previous conversation:"]
        for msg in self.messages[:-1]:  # Exclude current message (will be sent separately)
            prefix = "User" if msg.role == "user" else "Blip"
            lines.append(f"{prefix}: {msg.content}")

        return "\n".join(lines)

    def is_expired(self) -> bool:
        """Check if conversation has expired."""
        return datetime.now() - self.last_activity > timedelta(hours=CONVERSATION_TTL_HOURS)


class ConversationManager:
    """
    Manages conversation history across all users/spaces.

    Conversation key format: "{space_name}:{user_email}" or just "{user_email}" for DMs
    """

    def __init__(self):
        self._conversations: Dict[str, Conversation] = defaultdict(Conversation)
        self._last_cleanup = datetime.now()

    def _get_key(self, space_name: Optional[str], user_email: str) -> str:
        """Generate conversation key."""
        if space_name and space_name != "DM":
            return f"{space_name}:{user_email}"
        return user_email

    def add_user_message(self, space_name: Optional[str], user_email: str, content: str):
        """Add a user message to conversation."""
        key = self._get_key(space_name, user_email)
        self._conversations[key].add_message("user", content)
        self._maybe_cleanup()

    def add_assistant_message(self, space_name: Optional[str], user_email: str, content: str):
        """Add an assistant response to conversation."""
        key = self._get_key(space_name, user_email)
        self._conversations[key].add_message("assistant", content)

    def get_history(self, space_name: Optional[str], user_email: str) -> str:
        """Get formatted conversation history for AI prompt."""
        key = self._get_key(space_name, user_email)
        conv = self._conversations.get(key)

        if not conv or conv.is_expired():
            return ""

        return conv.get_history_for_prompt()

    def get_message_count(self, space_name: Optional[str], user_email: str) -> int:
        """Get number of messages in conversation."""
        key = self._get_key(space_name, user_email)
        conv = self._conversations.get(key)
        return len(conv.messages) if conv else 0

    def clear_conversation(self, space_name: Optional[str], user_email: str):
        """Clear a specific conversation."""
        key = self._get_key(space_name, user_email)
        if key in self._conversations:
            del self._conversations[key]

    def _maybe_cleanup(self):
        """Periodically clean up expired conversations."""
        # Only cleanup every hour
        if datetime.now() - self._last_cleanup < timedelta(hours=1):
            return

        self._last_cleanup = datetime.now()
        expired_keys = [
            key for key, conv in self._conversations.items()
            if conv.is_expired()
        ]

        for key in expired_keys:
            del self._conversations[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired conversations")


# Global instance
conversation_manager = ConversationManager()
