"""
Blip Memory System

Provides long-term memory storage for the Blip agent.
Supports both Redis (production) and in-memory (development) backends.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BlipMemory:
    """
    Long-term memory storage for Blip.

    Stores facts about users that persist across conversations.
    Uses Redis in production, falls back to in-memory dict for development.
    """

    def __init__(self, redis_client=None):
        """
        Initialize memory store.

        Args:
            redis_client: Optional async Redis client. If not provided,
                          uses in-memory storage (suitable for dev/testing).
        """
        self.redis = redis_client
        self.local_cache: Dict[str, Dict] = {}
        self._use_redis = redis_client is not None

        if self._use_redis:
            logger.info("BlipMemory initialized with Redis backend")
        else:
            logger.info("BlipMemory initialized with in-memory backend")

    async def remember(
        self,
        user_email: str,
        key: str,
        value: Any,
        ttl_days: int = 90
    ) -> bool:
        """
        Store a fact about a user.

        Args:
            user_email: User's email address
            key: Unique key for this fact
            value: The fact to store (will be JSON serialized)
            ttl_days: How long to remember (default 90 days)

        Returns:
            True if stored successfully
        """
        memory_key = f"blip:memory:{user_email}:{key}"
        data = {
            "value": value,
            "stored_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=ttl_days)).isoformat()
        }

        try:
            if self._use_redis:
                await self.redis.setex(
                    memory_key,
                    timedelta(days=ttl_days),
                    json.dumps(data, default=str)
                )
            else:
                self.local_cache[memory_key] = data

            logger.debug(f"Stored memory: {memory_key}")
            return True

        except Exception as e:
            logger.exception(f"Error storing memory {memory_key}: {e}")
            return False

    async def recall(self, user_email: str, key: str) -> Optional[Any]:
        """
        Recall a specific fact about a user.

        Args:
            user_email: User's email address
            key: Key for the fact to recall

        Returns:
            The stored value, or None if not found
        """
        memory_key = f"blip:memory:{user_email}:{key}"

        try:
            if self._use_redis:
                data_str = await self.redis.get(memory_key)
                if data_str:
                    data = json.loads(data_str)
                    return data.get("value")
            else:
                data = self.local_cache.get(memory_key)
                if data:
                    # Check if expired (for local cache)
                    expires_at = data.get("expires_at")
                    if expires_at:
                        if datetime.fromisoformat(expires_at) < datetime.now():
                            del self.local_cache[memory_key]
                            return None
                    return data.get("value")

            return None

        except Exception as e:
            logger.exception(f"Error recalling memory {memory_key}: {e}")
            return None

    async def forget(self, user_email: str, key: str) -> bool:
        """
        Forget a specific fact about a user.

        Args:
            user_email: User's email address
            key: Key for the fact to forget

        Returns:
            True if forgotten successfully
        """
        memory_key = f"blip:memory:{user_email}:{key}"

        try:
            if self._use_redis:
                await self.redis.delete(memory_key)
            else:
                self.local_cache.pop(memory_key, None)

            logger.debug(f"Forgot memory: {memory_key}")
            return True

        except Exception as e:
            logger.exception(f"Error forgetting memory {memory_key}: {e}")
            return False

    async def get_all_memories(self, user_email: str) -> Dict[str, Any]:
        """
        Get all stored memories for a user.

        Args:
            user_email: User's email address

        Returns:
            Dict of key -> value for all stored memories
        """
        prefix = f"blip:memory:{user_email}:"
        memories = {}

        try:
            if self._use_redis:
                # Use SCAN to find all keys (safer than KEYS for large datasets)
                cursor = 0
                while True:
                    cursor, keys = await self.redis.scan(
                        cursor,
                        match=f"{prefix}*",
                        count=100
                    )
                    for key in keys:
                        short_key = key.decode().replace(prefix, "")
                        value = await self.recall(user_email, short_key)
                        if value is not None:
                            memories[short_key] = value

                    if cursor == 0:
                        break
            else:
                for key, data in list(self.local_cache.items()):
                    if key.startswith(prefix):
                        short_key = key.replace(prefix, "")
                        # Check expiration
                        expires_at = data.get("expires_at")
                        if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
                            del self.local_cache[key]
                            continue
                        memories[short_key] = data.get("value")

            return memories

        except Exception as e:
            logger.exception(f"Error getting all memories for {user_email}: {e}")
            return {}

    async def forget_all(self, user_email: str) -> int:
        """
        Forget all memories for a user.

        Args:
            user_email: User's email address

        Returns:
            Number of memories forgotten
        """
        prefix = f"blip:memory:{user_email}:"
        count = 0

        try:
            if self._use_redis:
                cursor = 0
                while True:
                    cursor, keys = await self.redis.scan(
                        cursor,
                        match=f"{prefix}*",
                        count=100
                    )
                    if keys:
                        count += await self.redis.delete(*keys)

                    if cursor == 0:
                        break
            else:
                keys_to_delete = [k for k in self.local_cache if k.startswith(prefix)]
                for key in keys_to_delete:
                    del self.local_cache[key]
                count = len(keys_to_delete)

            logger.info(f"Forgot {count} memories for {user_email}")
            return count

        except Exception as e:
            logger.exception(f"Error forgetting all memories for {user_email}: {e}")
            return 0

    async def get_memory_stats(self, user_email: str) -> Dict[str, Any]:
        """
        Get statistics about a user's memories.

        Returns:
            Dict with count, categories, oldest, newest dates
        """
        memories = await self.get_all_memories(user_email)

        if not memories:
            return {
                "count": 0,
                "categories": [],
                "oldest": None,
                "newest": None
            }

        categories = set()
        oldest = None
        newest = None

        for key, value in memories.items():
            # Extract category from key (format: category_hash)
            if "_" in key:
                category = key.split("_")[0]
                categories.add(category)

            # Track dates if value is a dict with stored_at
            if isinstance(value, dict) and "stored_at" in value:
                stored_at = value["stored_at"]
                if oldest is None or stored_at < oldest:
                    oldest = stored_at
                if newest is None or stored_at > newest:
                    newest = stored_at

        return {
            "count": len(memories),
            "categories": list(categories),
            "oldest": oldest,
            "newest": newest
        }


class ConversationMemory:
    """
    Short-term conversation memory.

    Stores recent messages for conversation context.
    This is separate from long-term memory (BlipMemory).
    """

    def __init__(self, max_messages: int = 10, ttl_hours: int = 24):
        """
        Initialize conversation memory.

        Args:
            max_messages: Maximum messages to keep per conversation
            ttl_hours: Time to live for conversations
        """
        self.max_messages = max_messages
        self.ttl = timedelta(hours=ttl_hours)
        self.conversations: Dict[str, Dict] = {}

    def _get_key(self, space_name: str, user_email: str) -> str:
        """Generate conversation key."""
        return f"{space_name}:{user_email}"

    def _cleanup_expired(self):
        """Remove expired conversations."""
        now = datetime.now()
        expired = [
            key for key, conv in self.conversations.items()
            if now - conv.get("updated_at", now) > self.ttl
        ]
        for key in expired:
            del self.conversations[key]

    def add_user_message(self, space_name: str, user_email: str, message: str):
        """Add a user message to conversation history."""
        self._cleanup_expired()
        key = self._get_key(space_name, user_email)

        if key not in self.conversations:
            self.conversations[key] = {
                "messages": [],
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }

        self.conversations[key]["messages"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })

        # Trim to max messages
        self.conversations[key]["messages"] = \
            self.conversations[key]["messages"][-self.max_messages:]
        self.conversations[key]["updated_at"] = datetime.now()

    def add_assistant_message(self, space_name: str, user_email: str, message: str):
        """Add an assistant message to conversation history."""
        key = self._get_key(space_name, user_email)

        if key not in self.conversations:
            self.conversations[key] = {
                "messages": [],
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }

        self.conversations[key]["messages"].append({
            "role": "assistant",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })

        # Trim to max messages
        self.conversations[key]["messages"] = \
            self.conversations[key]["messages"][-self.max_messages:]
        self.conversations[key]["updated_at"] = datetime.now()

    def get_messages(self, space_name: str, user_email: str) -> list:
        """
        Get conversation history as list of message dicts.

        Returns:
            List of {"role": "user/assistant", "content": "..."}
        """
        self._cleanup_expired()
        key = self._get_key(space_name, user_email)

        conv = self.conversations.get(key)
        if not conv:
            return []

        return [
            {"role": m["role"], "content": m["content"]}
            for m in conv["messages"]
        ]

    def get_history(self, space_name: str, user_email: str) -> str:
        """
        Get conversation history as formatted string.

        Returns:
            String formatted as "User: ...\nAssistant: ..."
        """
        messages = self.get_messages(space_name, user_email)
        if not messages:
            return ""

        lines = []
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Blip"
            lines.append(f"{role}: {msg['content']}")

        return "\n".join(lines)

    def get_message_count(self, space_name: str, user_email: str) -> int:
        """Get number of messages in conversation."""
        key = self._get_key(space_name, user_email)
        conv = self.conversations.get(key)
        return len(conv["messages"]) if conv else 0

    def clear(self, space_name: str, user_email: str):
        """Clear conversation history."""
        key = self._get_key(space_name, user_email)
        self.conversations.pop(key, None)


# Global conversation manager instance
conversation_manager = ConversationMemory()
