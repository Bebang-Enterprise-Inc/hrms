"""
Blip Sentinel v2.3 — Google Chat Sweeper
Auto-discovers spaces, polls for new messages, detects @mentions and DMs.
"""

import os
import sys
import logging
import sqlite3
from datetime import datetime, timezone, timedelta

if sys.platform == 'win32':
    class _FcntlStub:
        LOCK_EX = 0
        LOCK_NB = 0
        LOCK_UN = 0
        @staticmethod
        def flock(*args, **kwargs):
            pass
    fcntl = _FcntlStub()
else:
    import fcntl

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import db
from rate_limiter import TokenBucket

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

log = logging.getLogger("sentinel.sweeper.chat")

# Rate limiter for Chat API calls
_chat_api_limiter = TokenBucket(rate=1400, per=60)


def get_chat_service():
    """Build Google Chat API service with domain-wide delegation."""
    creds = service_account.Credentials.from_service_account_file(
        config.SERVICE_ACCOUNT_FILE, scopes=config.SCOPES
    ).with_subject(config.DELEGATED_USER)
    return build('chat', 'v1', credentials=creds)


def get_admin_service():
    """Build Admin Directory API service for user name resolution."""
    creds = service_account.Credentials.from_service_account_file(
        config.SERVICE_ACCOUNT_FILE, scopes=config.SCOPES
    ).with_subject(config.DELEGATED_USER)
    return build('admin', 'directory_v1', credentials=creds)


def sync_user_names(conn: sqlite3.Connection):
    """Sync user names from Google Admin Directory to local cache."""
    log.info("Syncing user names from Admin Directory...")
    try:
        admin_service = get_admin_service()
        users = []
        request = admin_service.users().list(
            domain='bebang.ph',
            projection='basic',
            maxResults=500,
            orderBy='email',
        )
        while request is not None:
            response = request.execute()
            for user in response.get('users', []):
                user_id = f"users/{user['id']}"
                full_name = user.get('name', {}).get('fullName', '')
                email = user.get('primaryEmail', '')
                if full_name:
                    users.append({
                        "user_id": user_id,
                        "display_name": full_name,
                        "email": email,
                    })
            request = admin_service.users().list_next(request, response)

        if users:
            db.bulk_upsert_user_names(conn, users)
            db.backfill_sender_names(conn)
            log.info("Synced %d user names from Admin Directory", len(users))
        else:
            log.warning("No users found in Admin Directory")
        return len(users)

    except HttpError as e:
        log.error("HTTP error syncing user names: %s", e)
        return 0
    except Exception as e:
        log.error("Error syncing user names: %s", e, exc_info=True)
        return 0


# In-memory name cache populated from DB at sweep start
_name_cache = {}


def resolve_name(sender: dict, conn: sqlite3.Connection = None) -> str:
    """Extract display name from sender object, using local cache as fallback."""
    if not sender:
        return "Unknown"

    # Try Chat API displayName first
    display_name = sender.get('displayName')
    if display_name:
        return display_name

    # Fall back to local cache
    user_id = sender.get('name', '')
    if user_id and _name_cache:
        cached = _name_cache.get(user_id)
        if cached:
            return cached

    # If we have a DB connection, try the DB
    if conn and user_id:
        cached = db.get_user_name(conn, user_id)
        if cached:
            return cached

    return user_id or "Unknown"


def discover_spaces(conn: sqlite3.Connection) -> int:
    """
    Auto-discover all spaces Sam is in via chat.spaces().list().
    Returns count of newly discovered spaces.
    """
    log.info("Starting space discovery")
    chat_service = get_chat_service()
    new_count = 0

    try:
        # List all spaces Sam is a member of
        request = chat_service.spaces().list(pageSize=100)

        while request is not None:
            response = request.execute()
            spaces = response.get('spaces', [])

            for space in spaces:
                space_id = space.get('name')
                space_name = space.get('displayName', 'Unnamed Space')
                space_type = space.get('spaceType', 'UNKNOWN')

                # Check if already tracked
                existing = conn.execute(
                    "SELECT 1 FROM sweep_state WHERE space_id = ?", (space_id,)
                ).fetchone()

                if not existing:
                    log.info("Discovered new space: %s (%s)", space_name, space_type)
                    db.upsert_space(conn, space_id, space_name, space_type)
                    new_count += 1
                else:
                    # Update name/type if changed
                    db.upsert_space(conn, space_id, space_name, space_type)

            request = chat_service.spaces().list_next(request, response)

        log.info("Space discovery complete. New spaces: %d", new_count)

        # Also sync user names from Admin Directory
        sync_user_names(conn)

        return new_count

    except HttpError as e:
        log.error("HTTP error during space discovery: %s", e)
        return new_count
    except Exception as e:
        log.error("Error during space discovery: %s", e, exc_info=True)
        return new_count


def is_dnd_window() -> bool:
    """Check if current time is in DND window (11 PM - 7 AM PHT)."""
    now_pht = datetime.now(config.PHT)
    hour = now_pht.hour
    return hour >= config.DND_START_HOUR or hour < config.DND_END_HOUR


def sweep_chat(conn: sqlite3.Connection):
    """
    Main chat sweeper function.
    Polls all monitored spaces for new messages since last check.
    """
    # Acquire lock to prevent overlapping sweeps
    lock_file = open(config.CHAT_SWEEP_LOCK, 'w')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        log.warning("Chat sweep already running, skipping")
        return

    try:
        global _name_cache
        log.info("Starting chat sweep")

        # Only discover on first run (no spaces in DB yet)
        spaces = db.get_all_monitored_spaces(conn)
        if not spaces:
            discover_spaces(conn)
            spaces = db.get_all_monitored_spaces(conn)

        # Load user name cache from DB (synced during discover_spaces)
        _name_cache = db.get_all_user_names(conn)
        if not _name_cache:
            # No names cached yet — sync now
            sync_user_names(conn)
            _name_cache = db.get_all_user_names(conn)
        log.info("Polling %d spaces, name cache: %d users", len(spaces), len(_name_cache))

        chat_service = get_chat_service()
        total_new_messages = 0
        mentions_found = 0
        dms_found = 0

        for space in spaces:
            space_id = space['space_id']

            # Never sweep the notification target space (prevents infinite loop)
            if config.BLIP_NOTIFICATION_SPACE and space_id == config.BLIP_NOTIFICATION_SPACE:
                continue

            space_name = space['space_name']
            space_type = space['space_type']
            last_checked = db.get_last_checked(conn, space_id)
            is_first_sweep = last_checked is None

            try:
                # Build filter for messages since last check
                filter_str = None
                if last_checked:
                    filter_str = f'createTime > "{last_checked}"'
                else:
                    # First sweep: only pull last 24 hours to avoid massive historical backfill
                    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
                    filter_str = f'createTime > "{cutoff}"'
                    log.info("First sweep for %s — limiting to last 24h", space_name)

                # Rate limit before API call
                if not _chat_api_limiter.consume():
                    _chat_api_limiter.wait_for_token()

                # List messages in this space
                request = chat_service.spaces().messages().list(
                    parent=space_id,
                    filter=filter_str,
                    pageSize=100,
                    orderBy='createTime desc'
                )

                space_msg_count = 0
                latest_msg_time = last_checked

                while request is not None:
                    response = request.execute()
                    messages = response.get('messages', [])

                    for msg in messages:
                        message_id = msg.get('name')
                        sender = msg.get('sender', {})
                        sender_type = sender.get('type')

                        # Skip bot messages
                        if sender_type == 'BOT':
                            continue

                        sender_id = sender.get('name')
                        sender_name = resolve_name(sender, conn)

                        text = msg.get('text', '')
                        create_time = msg.get('createTime')
                        thread_id = msg.get('thread', {}).get('name')

                        # Check for attachments (image detection)
                        attachments = msg.get('attachedGifs', []) + msg.get('attachment', [])
                        has_attachment = len(attachments) > 0
                        is_image_only = has_attachment and not text.strip()

                        # Detect @mentions of Sam
                        mentions_sam = config.SAM_CHAT_MENTION in text

                        # Track latest message time for this space
                        if create_time and (not latest_msg_time or create_time > latest_msg_time):
                            latest_msg_time = create_time

                        # Save message to database
                        db.insert_raw_message(
                            conn,
                            space_id=space_id,
                            space_name=space_name,
                            space_type=space_type,
                            message_id=message_id,
                            sender_id=sender_id,
                            sender_name=sender_name,
                            text=text,
                            has_attachment=has_attachment,
                            is_image_only=is_image_only,
                            create_time=create_time,
                            thread_id=thread_id,
                            mentions_sam=mentions_sam
                        )

                        space_msg_count += 1

                        # Track mentions and DMs for logging
                        if mentions_sam:
                            mentions_found += 1
                        if space_type == 'DIRECT_MESSAGE' and text.strip():
                            dms_found += 1

                    # Rate limit before next page
                    if chat_service.spaces().messages().list_next(request, response) is not None:
                        if not _chat_api_limiter.consume():
                            _chat_api_limiter.wait_for_token()

                    request = chat_service.spaces().messages().list_next(request, response)

                # Update last checked timestamp for this space
                if latest_msg_time:
                    db.update_last_checked(conn, space_id, latest_msg_time)
                else:
                    db.update_last_checked(conn, space_id)

                if space_msg_count > 0:
                    log.info("Space %s: %d new messages", space_name, space_msg_count)
                    total_new_messages += space_msg_count

            except HttpError as e:
                log.error("HTTP error polling space %s: %s", space_name, e)
            except Exception as e:
                log.error("Error polling space %s: %s", space_name, e, exc_info=True)

        log.info("Chat sweep complete. Total new: %d, Mentions: %d, DMs: %d",
                total_new_messages, mentions_found, dms_found)

    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


if __name__ == "__main__":
    # Setup logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    with db.get_db() as conn:
        sweep_chat(conn)
