"""
Blip Sentinel v2.3 — Gmail Sweeper
Incremental sync using historyId, falls back to full inbox list on expiry.
"""

import os
import sys
import logging
import sqlite3
from datetime import datetime, timezone

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

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

log = logging.getLogger("sentinel.sweeper.gmail")


def get_gmail_service():
    """Build Gmail API service with domain-wide delegation."""
    creds = service_account.Credentials.from_service_account_file(
        config.SERVICE_ACCOUNT_FILE, scopes=config.SCOPES
    ).with_subject(config.DELEGATED_USER)
    return build('gmail', 'v1', credentials=creds)


def extract_header(headers: list, name: str) -> str:
    """Extract specific header value from email headers."""
    for header in headers:
        if header['name'].lower() == name.lower():
            return header['value']
    return ''


def sweep_gmail(conn: sqlite3.Connection):
    """
    Main Gmail sweeper function.
    Uses historyId for incremental sync, falls back to full list if expired.
    """
    # Acquire lock to prevent overlapping sweeps
    lock_file = open(config.GMAIL_SWEEP_LOCK, 'w')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        log.warning("Gmail sweep already running, skipping")
        return

    try:
        log.info("Starting Gmail sweep")
        gmail_service = get_gmail_service()
        total_new_emails = 0

        # Get current historyId from database
        current_history_id = db.get_gmail_history_id(conn)

        if current_history_id:
            log.info("Using incremental sync with historyId: %s", current_history_id)
            try:
                # Try incremental sync using history API
                total_new_emails = _incremental_sync(conn, gmail_service, current_history_id)

            except HttpError as e:
                error_message = str(e)
                if 'historyId is no longer valid' in error_message or 'invalid historyId' in error_message:
                    log.warning("historyId expired, falling back to full inbox list")
                    total_new_emails = _full_inbox_sync(conn, gmail_service)
                else:
                    log.error("HTTP error during Gmail sync: %s", e)
                    raise

        else:
            # First run or no historyId stored - do full inbox sync
            log.info("No historyId found, performing full inbox sync")
            total_new_emails = _full_inbox_sync(conn, gmail_service)

        log.info("Gmail sweep complete. New emails: %d", total_new_emails)

    except Exception as e:
        log.error("Error during Gmail sweep: %s", e, exc_info=True)

    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def _incremental_sync(conn: sqlite3.Connection, gmail_service, start_history_id: str) -> int:
    """
    Perform incremental sync using Gmail history API.
    Returns count of new emails collected.
    """
    new_count = 0

    try:
        request = gmail_service.users().history().list(
            userId='me',
            startHistoryId=start_history_id,
            historyTypes=['messageAdded'],
            labelId='INBOX',
            maxResults=100
        )

        latest_history_id = start_history_id

        while request is not None:
            response = request.execute()
            history_records = response.get('history', [])

            # Update historyId from response
            if 'historyId' in response:
                latest_history_id = response['historyId']

            for record in history_records:
                messages_added = record.get('messagesAdded', [])

                for msg_added in messages_added:
                    msg = msg_added.get('message', {})
                    msg_id = msg.get('id')

                    # Skip if already collected
                    if db.email_exists(conn, msg_id):
                        continue

                    # Fetch full message details
                    msg_detail = gmail_service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='metadata',
                        metadataHeaders=['From', 'Subject', 'Date']
                    ).execute()

                    _save_email(conn, msg_detail)
                    new_count += 1

            request = gmail_service.users().history().list_next(request, response)

        # Save latest historyId
        db.set_gmail_history_id(conn, latest_history_id)
        log.info("Updated historyId to: %s", latest_history_id)

        return new_count

    except HttpError as e:
        # Re-raise so caller can handle historyId expiry
        raise


def _full_inbox_sync(conn: sqlite3.Connection, gmail_service) -> int:
    """
    Perform full inbox sync (first run or after historyId expiry).
    Fetches latest 50 inbox messages, excluding auto-labeled emails.
    Returns count of new emails collected.
    """
    new_count = 0

    try:
        # List inbox messages, excluding auto-labeled (filters, promotions, etc.)
        request = gmail_service.users().messages().list(
            userId='me',
            q='is:inbox -label:Auto',
            maxResults=50
        )

        # Get profile to extract new historyId
        profile = gmail_service.users().getProfile(userId='me').execute()
        latest_history_id = profile.get('historyId')

        page_count = 0
        while request is not None and page_count < 2:  # Limit to 2 pages (100 emails max)
            response = request.execute()
            messages = response.get('messages', [])

            for msg in messages:
                msg_id = msg['id']

                # Skip if already collected
                if db.email_exists(conn, msg_id):
                    continue

                # Fetch full message details
                msg_detail = gmail_service.users().messages().get(
                    userId='me',
                    id=msg_id,
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()

                _save_email(conn, msg_detail)
                new_count += 1

            request = gmail_service.users().messages().list_next(request, response)
            page_count += 1

        # Save historyId for future incremental syncs
        if latest_history_id:
            db.set_gmail_history_id(conn, latest_history_id)
            log.info("Saved initial historyId: %s", latest_history_id)

        return new_count

    except HttpError as e:
        log.error("HTTP error during full inbox sync: %s", e)
        return new_count


def _save_email(conn: sqlite3.Connection, msg_detail: dict):
    """Extract email metadata and save to database."""
    msg_id = msg_detail.get('id')
    snippet = msg_detail.get('snippet', '')
    label_ids = msg_detail.get('labelIds', [])
    is_unread = 'UNREAD' in label_ids

    headers = msg_detail.get('payload', {}).get('headers', [])
    from_addr = extract_header(headers, 'From')
    subject = extract_header(headers, 'Subject')
    date_str = extract_header(headers, 'Date')

    db.insert_raw_email(
        conn,
        gmail_id=msg_id,
        from_addr=from_addr,
        subject=subject,
        date=date_str,
        snippet=snippet,
        labels=label_ids,
        is_unread=is_unread
    )

    log.debug("Saved email: %s from %s", msg_id, from_addr)


if __name__ == "__main__":
    # Setup logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    with db.get_db() as conn:
        sweep_gmail(conn)
