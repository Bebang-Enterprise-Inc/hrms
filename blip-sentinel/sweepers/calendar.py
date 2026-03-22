"""
Blip Sentinel v2.3 — Google Calendar Sweeper
Polls all calendars for events in next 48 hours.
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

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

log = logging.getLogger("sentinel.sweeper.calendar")


def get_calendar_service():
    """Build Google Calendar API service with domain-wide delegation."""
    creds = service_account.Credentials.from_service_account_file(
        config.SERVICE_ACCOUNT_FILE, scopes=config.SCOPES
    ).with_subject(config.DELEGATED_USER)
    return build('calendar', 'v3', credentials=creds)


def extract_datetime(event_time: dict) -> str:
    """Extract ISO datetime from event start/end object."""
    if 'dateTime' in event_time:
        return event_time['dateTime']
    elif 'date' in event_time:
        # All-day event - use date at midnight UTC
        return f"{event_time['date']}T00:00:00Z"
    return ''


def extract_attendees(attendees: list) -> list:
    """Extract attendee emails from event."""
    if not attendees:
        return []
    return [
        {
            'email': att.get('email'),
            'displayName': att.get('displayName'),
            'responseStatus': att.get('responseStatus')
        }
        for att in attendees
    ]


def sweep_calendar(conn: sqlite3.Connection):
    """
    Main calendar sweeper function.
    Polls all accessible calendars for events in next 48 hours.
    """
    # Acquire lock to prevent overlapping sweeps
    lock_file = open(config.CALENDAR_SWEEP_LOCK, 'w')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        log.warning("Calendar sweep already running, skipping")
        return

    try:
        log.info("Starting calendar sweep")
        calendar_service = get_calendar_service()

        # Get all calendars Sam has access to
        calendars = _list_calendars(calendar_service)
        log.info("Found %d calendars to poll", len(calendars))

        # Calculate time window (now to +48 hours)
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(hours=48)).isoformat()

        total_events = 0

        for calendar in calendars:
            calendar_id = calendar['id']
            calendar_name = calendar.get('summary', calendar_id)

            try:
                events = _get_calendar_events(
                    calendar_service,
                    calendar_id,
                    time_min,
                    time_max
                )

                for event in events:
                    _save_event(conn, event, calendar_id, calendar_name)
                    total_events += 1

                if events:
                    log.info("Calendar '%s': %d events", calendar_name, len(events))

            except HttpError as e:
                log.error("HTTP error polling calendar %s: %s", calendar_name, e)
            except Exception as e:
                log.error("Error polling calendar %s: %s", calendar_name, e, exc_info=True)

        log.info("Calendar sweep complete. Total events: %d", total_events)

    except Exception as e:
        log.error("Error during calendar sweep: %s", e, exc_info=True)

    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def _list_calendars(calendar_service) -> list:
    """
    List all calendars Sam has access to.
    Filters by accessRole (owner, writer, reader).
    """
    calendars = []

    try:
        request = calendar_service.calendarList().list(
            minAccessRole='reader',
            maxResults=100
        )

        while request is not None:
            response = request.execute()
            items = response.get('items', [])

            for item in items:
                # Include calendars where Sam has at least reader access
                access_role = item.get('accessRole')
                if access_role in ['owner', 'writer', 'reader']:
                    calendars.append({
                        'id': item['id'],
                        'summary': item.get('summary', item['id']),
                        'accessRole': access_role
                    })

            request = calendar_service.calendarList().list_next(request, response)

        return calendars

    except HttpError as e:
        log.error("HTTP error listing calendars: %s", e)
        return []


def _get_calendar_events(calendar_service, calendar_id: str,
                          time_min: str, time_max: str) -> list:
    """
    Get events from a specific calendar within time window.
    Uses singleEvents=True to expand recurring events.
    """
    events = []

    try:
        request = calendar_service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime',
            maxResults=100
        )

        while request is not None:
            response = request.execute()
            items = response.get('items', [])
            events.extend(items)

            request = calendar_service.events().list_next(request, response)

        return events

    except HttpError as e:
        # Re-raise to let caller handle
        raise


def _save_event(conn: sqlite3.Connection, event: dict,
                calendar_id: str, calendar_name: str):
    """Extract event details and upsert to database."""
    event_id = event.get('id')
    summary = event.get('summary', '(No title)')
    location = event.get('location', '')
    status = event.get('status', 'confirmed')

    start = event.get('start', {})
    end = event.get('end', {})
    start_time = extract_datetime(start)
    end_time = extract_datetime(end)

    # Extract attendees
    attendees = extract_attendees(event.get('attendees', []))

    # Extract Google Meet link
    meet_link = ''
    conference_data = event.get('conferenceData', {})
    if conference_data:
        entry_points = conference_data.get('entryPoints', [])
        for entry in entry_points:
            if entry.get('entryPointType') == 'video':
                meet_link = entry.get('uri', '')
                break

    # Alternatively, check hangoutLink
    if not meet_link:
        meet_link = event.get('hangoutLink', '')

    db.upsert_calendar_event(
        conn,
        event_id=event_id,
        calendar_id=calendar_id,
        summary=summary,
        start_time=start_time,
        end_time=end_time,
        location=location,
        attendees=attendees,
        meet_link=meet_link,
        status=status
    )

    log.debug("Saved event: %s at %s", summary, start_time)


if __name__ == "__main__":
    # Setup logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    with db.get_db() as conn:
        sweep_calendar(conn)
