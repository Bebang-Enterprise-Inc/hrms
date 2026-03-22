"""
Blip Sentinel — Purge DM Forwards from ! Blip Notifications

One-time cleanup script to delete raw DM forward messages from the
Blip Notifications space. Keeps briefings, digests, and ads reports.

Usage:
    python scripts/purge_dm_forwards.py --dry-run   # Preview what would be deleted
    python scripts/purge_dm_forwards.py              # Actually delete messages
"""

import os
import sys
import re
import logging
import argparse
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger("purge_dm_forwards")

# The Blip Notifications space
NOTIFICATION_SPACE = os.environ.get(
    "BLIP_NOTIFICATION_SPACE",
    "spaces/AAQABiNmpBg",
)

# Patterns that identify messages to KEEP (everything else gets deleted)
KEEP_PATTERNS = [
    r'BRIEFING',
    r'DIGEST',
    r'MEETING PREP',
    r'UPCOMING MEETING',
    r'Meta Ads',
    r'Ads Report',
    r'Ad Performance',
    r'Weekly Performance',
]

# Patterns that identify DM forwards to DELETE
DM_FORWARD_PATTERNS = [
    r'^💬 DM from',
    r'^📣 MENTION from',
    r'^DM from \*\*',
    r'^\*\*[A-Z][a-z]+ [A-Z][a-z]+\*\* in \*DM\*:',
]


def get_bot_service():
    """Build Google Chat API service with bot credentials (for deleting bot messages)."""
    creds = service_account.Credentials.from_service_account_file(
        config.SERVICE_ACCOUNT_FILE,
        scopes=config.BOT_SCOPES,
    )
    return build('chat', 'v1', credentials=creds)


def get_dwd_service():
    """Build Google Chat API service with DWD (for listing messages)."""
    creds = service_account.Credentials.from_service_account_file(
        config.SERVICE_ACCOUNT_FILE,
        scopes=config.SCOPES,
    ).with_subject(config.DELEGATED_USER)
    return build('chat', 'v1', credentials=creds)


def should_keep(text: str) -> bool:
    """Check if message text matches a KEEP pattern (briefing, digest, etc.)."""
    if not text:
        return False
    for pattern in KEEP_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def is_dm_forward(text: str) -> bool:
    """Check if message text matches a DM forward pattern."""
    if not text:
        return False
    for pattern in DM_FORWARD_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def purge(dry_run: bool = True):
    """
    Scan all messages in Blip Notifications space and delete DM forwards.

    Args:
        dry_run: If True, only log what would be deleted without actually deleting.
    """
    log.info("Starting purge of DM forwards from %s (dry_run=%s)", NOTIFICATION_SPACE, dry_run)

    dwd_service = get_dwd_service()
    bot_service = get_bot_service()

    total_scanned = 0
    total_deleted = 0
    total_kept = 0
    total_skipped = 0

    try:
        request = dwd_service.spaces().messages().list(
            parent=NOTIFICATION_SPACE,
            pageSize=100,
        )

        while request is not None:
            response = request.execute()
            messages = response.get('messages', [])

            for msg in messages:
                total_scanned += 1
                message_name = msg.get('name', '')
                sender = msg.get('sender', {})
                sender_type = sender.get('type', '')
                text = msg.get('text', '')
                create_time = msg.get('createTime', '')

                # Only consider bot messages (Blip's own messages)
                if sender_type != 'BOT':
                    total_skipped += 1
                    continue

                # Keep briefings, digests, meeting preps, ads reports
                if should_keep(text):
                    total_kept += 1
                    log.debug("KEEP: %s (matched keep pattern)", message_name)
                    continue

                # Delete DM forwards and other raw alerts
                if is_dm_forward(text) or not should_keep(text):
                    text_preview = (text or '')[:80].replace('\n', ' ')
                    if dry_run:
                        log.info("WOULD DELETE: %s | %s | %s",
                                 message_name, create_time, text_preview)
                    else:
                        try:
                            bot_service.spaces().messages().delete(
                                name=message_name,
                            ).execute()
                            log.info("DELETED: %s | %s", message_name, text_preview)
                        except HttpError as e:
                            if e.resp.status == 403:
                                log.warning("Cannot delete %s (not bot's message)", message_name)
                            else:
                                log.error("Failed to delete %s: %s", message_name, e)
                    total_deleted += 1

            request = dwd_service.spaces().messages().list_next(request, response)

    except HttpError as e:
        log.error("HTTP error during purge: %s", e)
    except Exception as e:
        log.error("Error during purge: %s", e, exc_info=True)

    # Summary
    log.info("=" * 60)
    log.info("Purge Summary:")
    log.info("  Total scanned:  %d", total_scanned)
    log.info("  Kept (briefings/digests/ads):  %d", total_kept)
    log.info("  Skipped (non-bot):  %d", total_skipped)
    log.info("  %s:  %d", "Would delete" if dry_run else "Deleted", total_deleted)
    log.info("=" * 60)

    if dry_run and total_deleted > 0:
        log.info("Run without --dry-run to actually delete these messages.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Purge DM forwards from Blip Notifications space")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Preview deletions without actually deleting")
    args = parser.parse_args()

    purge(dry_run=args.dry_run)
