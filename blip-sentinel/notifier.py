"""
Blip Sentinel v2.3 — Notification Delivery Module
Sends messages via Blip bot to Sam's notification space.
Includes bot circuit breaker, content dedup, and notification rate limiting.
"""

import hashlib
import logging
import sqlite3
import requests
from datetime import datetime
from typing import Optional

import config
import db
from rate_limiter import TokenBucket

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

log = logging.getLogger("sentinel.notifier")

# Rate limiter for notification sends
_chat_api_limiter = TokenBucket(rate=50, per=60)  # Conservative for notification sends


def _content_hash(text: str) -> str:
    """SHA-256 hash of notification text for dedup."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _bot_window_check(conn: sqlite3.Connection) -> bool:
    """
    Phase 6.1: Bot circuit breaker.
    Returns True if under the per-window limit, False if limit hit.
    """
    row = conn.execute(
        """SELECT COUNT(*) FROM sent_notifications
           WHERE sent_at > datetime('now', ?)""",
        (f"-{config.BOT_WINDOW_SECONDS} seconds",),
    ).fetchone()
    count = row[0] if row else 0
    if count >= config.BOT_MAX_MESSAGES_PER_WINDOW:
        log.warning("Bot circuit breaker: %d msgs in last %ds (limit %d)",
                    count, config.BOT_WINDOW_SECONDS, config.BOT_MAX_MESSAGES_PER_WINDOW)
        return False
    return True


def _is_duplicate_notification(conn: sqlite3.Connection, text: str) -> bool:
    """
    Phase 6.2: Content-based dedup.
    Returns True if same content hash was sent in last 24h.
    """
    h = _content_hash(text)
    row = conn.execute(
        """SELECT 1 FROM sent_notifications
           WHERE notification_hash = ? AND sent_at > datetime('now', '-24 hours')""",
        (h,),
    ).fetchone()
    if row:
        log.info("Duplicate notification detected (hash=%s), skipping", h)
        return True
    return False


def _check_notification_rate_limit(conn: sqlite3.Connection, notification_type: str) -> bool:
    """
    Phase 6.4: DB-enforced rate limits per notification type.
    Returns True if allowed, False if rate-limited.
    """
    limits = {
        "digest": ("-30 minutes", 1),
        "morning_briefing": ("-24 hours", 1),
        "evening_briefing": ("-24 hours", 1),
        "store_summary": ("-24 hours", 1),
        "mention_alert": ("-1 hours", 3),
        "dm_alert": ("-1 hours", 3),
    }
    if notification_type not in limits:
        return True  # Unknown types are allowed

    window, max_count = limits[notification_type]
    row = conn.execute(
        """SELECT COUNT(*) FROM sent_notifications
           WHERE notification_type = ? AND sent_at > datetime('now', ?)""",
        (notification_type, window),
    ).fetchone()
    count = row[0] if row else 0
    if count >= max_count:
        log.warning("Rate limit hit for %s: %d/%d in window %s",
                    notification_type, count, max_count, window)
        return False
    return True


def _get_chat_service():
    """
    Create Google Chat API service using bot identity (no DWD impersonation).
    Messages are sent as Blip bot, not as Sam.
    """
    creds = service_account.Credentials.from_service_account_file(
        config.SERVICE_ACCOUNT_FILE, scopes=config.BOT_SCOPES
    )
    return build('chat', 'v1', credentials=creds)


def is_dnd_window() -> bool:
    """
    Check if current time is in DND window (11 PM - 7 AM PHT).
    Returns True between 11 PM and 7 AM PHT.
    """
    now_pht = datetime.now(config.PHT)
    hour = now_pht.hour
    return hour >= config.DND_START_HOUR or hour < config.DND_END_HOUR


def _split_message(text: str, limit: int = 4000) -> list[str]:
    """
    Split message at paragraph boundaries (double newline) to avoid mid-sentence breaks.
    Ensures no chunk exceeds the limit.

    Args:
        text: Message text to split
        limit: Character limit per chunk (default 4000 for Google Chat)

    Returns:
        List of message chunks
    """
    if len(text) <= limit:
        return [text]

    chunks = []
    paragraphs = text.split('\n\n')
    current_chunk = ""

    for para in paragraphs:
        # If a single paragraph exceeds the limit, split at single newlines
        if len(para) > limit:
            # Flush current chunk if not empty
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # Split long paragraph at single newlines
            lines = para.split('\n')
            for line in lines:
                # If a single line exceeds limit, hard split it
                if len(line) > limit:
                    # Flush current chunk first
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = ""
                    # Hard split the long line
                    for i in range(0, len(line), limit):
                        chunks.append(line[i:i+limit])
                elif len(current_chunk) + len(line) + 1 <= limit:
                    current_chunk += line + '\n'
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = line + '\n'
        else:
            # Try to add paragraph to current chunk
            if len(current_chunk) + len(para) + 2 <= limit:
                current_chunk += para + '\n\n'
            else:
                # Flush current chunk and start new one
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + '\n\n'

    # Add remaining content
    if current_chunk and current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text[:limit]]


def send_blip_message(
    conn: sqlite3.Connection,
    text: str,
    notification_type: str = "briefing",
    trigger_message_id: str = None
) -> Optional[str]:
    """
    Send message via Blip bot to Sam's notification space.

    Args:
        conn: Database connection
        text: Message text to send
        notification_type: Type of notification (briefing, mention_alert, dm_alert, etc.)
        trigger_message_id: ID of the message that triggered this notification

    Returns:
        Google Chat message ID if sent, None if skipped
    """
    # Check DND window for non-briefing notifications
    if is_dnd_window() and notification_type != "briefing":
        log.info("DND window active - skipping %s notification", notification_type)
        return None

    # Validate notification space is configured
    if not config.BLIP_NOTIFICATION_SPACE:
        log.error("BLIP_NOTIFICATION_SPACE not configured in environment")
        return None

    # Phase 6.1: Bot circuit breaker — don't flood the space
    if not _bot_window_check(conn):
        log.warning("Bot circuit breaker tripped — skipping %s", notification_type)
        return None

    # Phase 6.2: Content dedup — skip if same content sent in last 24h
    if _is_duplicate_notification(conn, text):
        return None

    # Phase 6.4: Per-type rate limiting
    if not _check_notification_rate_limit(conn, notification_type):
        return None

    try:
        chat_service = _get_chat_service()

        # Split message if it exceeds Google Chat limit (G9 fix)
        message_parts = _split_message(text, limit=config.CHAT_MESSAGE_CHAR_LIMIT)

        sent_message_ids = []

        for i, part in enumerate(message_parts):
            # Rate limit before sending
            if not _chat_api_limiter.consume():
                log.warning("Rate limited — waiting for token")
                _chat_api_limiter.wait_for_token()

            # Add part indicator if message was split
            if len(message_parts) > 1:
                part_text = f"[Part {i+1}/{len(message_parts)}]\n\n{part}"
            else:
                part_text = part

            # Send message via Google Chat API
            response = chat_service.spaces().messages().create(
                parent=config.BLIP_NOTIFICATION_SPACE,
                body={'text': part_text}
            ).execute()

            message_id = response.get('name')
            sent_message_ids.append(message_id)

            log.info("Sent %s notification part %d/%d (msg_id=%s)",
                    notification_type, i+1, len(message_parts), message_id)

        # Record notification in database (use first message ID as reference)
        if sent_message_ids:
            preview = text[:200] if len(text) > 200 else text
            db.record_notification(
                conn,
                notification_type=notification_type,
                trigger_message_id=trigger_message_id,
                trigger_source='chat' if trigger_message_id else None,
                blip_message_id=sent_message_ids[0],
                preview=preview,
                content_hash=_content_hash(text),
            )

            return sent_message_ids[0]

        return None

    except HttpError as e:
        log.error("HTTP error sending Blip message: %s", e)
        return None
    except Exception as e:
        log.error("Error sending Blip message: %s", e, exc_info=True)
        return None


def ping_healthcheck(url: str):
    """
    Ping healthchecks.io URL (fire and forget).
    Catches all exceptions to avoid breaking the main flow.

    Args:
        url: Healthchecks.io ping URL
    """
    if not url:
        return

    try:
        requests.get(url, timeout=10)
        log.debug("Healthcheck ping sent to %s", url)
    except requests.exceptions.Timeout:
        log.warning("Healthcheck ping timeout: %s", url)
    except Exception as e:
        log.warning("Healthcheck ping failed: %s (%s)", url, str(e))
