"""
Blip Sentinel v2.3 — Layer 3 Briefing Engine
Opus-powered executive briefings and meeting prep.
"""

import re
import logging
import anthropic
from datetime import datetime, timedelta

import config
import db
import notifier
from timeutil import utc_now, to_pht
from content_guard import redact_for_notification
from feature_flags import is_enabled

log = logging.getLogger("sentinel.briefing")


def generate_briefing(conn, briefing_type: str):
    """
    Generate morning or evening briefing via Opus.

    Flow:
    1. Collect unbriefed messages, emails, calendar events, unresolved items
    2. Format into Opus prompt
    3. Call Opus API
    4. Send result via notifier.send_blip_message()
    5. Mark all included messages as briefed with label like "2026-02-13-morning"
    6. Parse unresolved items from response and save to DB
    """
    if briefing_type not in ("morning", "evening"):
        raise ValueError(f"Invalid briefing_type: {briefing_type}")

    log.info("Generating %s briefing", briefing_type)

    # Collect data
    messages = db.get_unbriefed_messages(conn)
    emails = db.get_unbriefed_emails(conn)
    events = db.get_upcoming_events(conn, hours=48)
    unresolved = db.get_unresolved_items(conn)

    if not messages and not emails and not events and not unresolved:
        log.info("No unbriefed content, skipping %s briefing", briefing_type)
        return

    # Generate briefing label
    now = datetime.now(config.PHT)
    briefing_label = now.strftime(f"%Y-%m-%d-{briefing_type}")

    # Last briefing time (estimate)
    if briefing_type == "morning":
        last_briefing_time = (now - timedelta(hours=12)).strftime("%Y-%m-%d 19:00 PHT")
    else:
        last_briefing_time = (now - timedelta(hours=12)).strftime("%Y-%m-%d 07:00 PHT")

    # Build prompt based on briefing type
    if briefing_type == "morning":
        system_prompt = _morning_system_prompt(now, last_briefing_time)
    else:
        system_prompt = _evening_system_prompt(now, last_briefing_time)

    # Collect pending responses for morning briefing
    pending_responses = []
    if briefing_type == "morning":
        pending_responses = db.get_pending_responses(conn, config.SAM_CHAT_USER_ID, hours=48)

    user_prompt = _format_briefing_prompt(messages, emails, events, unresolved,
                                          pending_responses=pending_responses)

    # Call Opus
    try:
        briefing_text = _call_opus(system_prompt, user_prompt)
    except Exception as e:
        log.error("Failed to generate %s briefing: %s", briefing_type, e)
        notifier.send_blip_message(conn, f"⚠️ {briefing_type.capitalize()} briefing failed: {e}")
        return

    # Send briefing
    header = f"📋 **{briefing_type.upper()} BRIEFING** — {now.strftime('%B %d, %Y')}\n\n"
    full_message = header + briefing_text

    notifier.send_blip_message(conn, full_message)
    log.info("Sent %s briefing", briefing_type)

    # Mark messages as briefed
    msg_ids = [msg["id"] for msg in messages]
    email_ids = [email["id"] for email in emails]

    db.mark_briefed(conn, msg_ids, briefing_label, table="raw_messages")
    db.mark_briefed(conn, email_ids, briefing_label, table="raw_emails")

    # Update unresolved items
    unresolved_ids = [item["id"] for item in unresolved]
    if unresolved_ids:
        db.update_unresolved_briefing(conn, unresolved_ids, briefing_label)

    # Parse new unresolved items from briefing
    new_unresolved = _parse_unresolved_items(briefing_text)
    for item_desc in new_unresolved:
        db.add_unresolved_item(conn, item_desc, source_type="briefing", source_id=briefing_label)
        log.debug("Added unresolved item: %s", item_desc[:50])

    log.info("Briefing complete: %d messages, %d emails, %d events, %d unresolved",
             len(messages), len(emails), len(events), len(unresolved))


def generate_meeting_prep(conn, event):
    """
    Generate Opus-powered meeting prep for a specific event.
    Returns True if prep was sent, False if skipped.
    """
    # Check daily cap
    if db.count_meeting_preps_today(conn) >= config.MAX_MEETING_PREPS_PER_DAY:
        log.info("Meeting prep daily cap reached, skipping prep for event %s", event["event_id"])
        return False

    log.info("Generating meeting prep for: %s", event["summary"])

    # Build prompt
    now = datetime.now(config.PHT)
    if not event["start_time"]:
        log.warning("Event %s has no start_time, skipping prep", event["event_id"])
        return False
    event_start = datetime.fromisoformat(event["start_time"]).astimezone(config.PHT)

    system_prompt = f"""You are Blip Sentinel, Sam Karazi's AI chief of staff.
{config.ORG_CONTEXT}

Sam has a meeting starting at {event_start.strftime("%I:%M %p PHT")}.
Provide a brief meeting prep (max 200 words) covering:
1. Meeting details (time, attendees, location/link)
2. Likely agenda or context (infer from title and Sam's role)
3. Suggested talking points or decisions needed

Be concise and actionable."""

    attendees = event["attendees"] or "[]"
    user_prompt = f"""Meeting: {event['summary']}
Time: {event_start.strftime('%I:%M %p PHT')}
Duration: {event['end_time'] or 'Unknown'}
Location: {event['location'] or 'N/A'}
Meet Link: {event['meet_link'] or 'N/A'}
Attendees: {attendees}

Generate meeting prep."""

    try:
        prep_text = _call_opus(system_prompt, user_prompt)
    except Exception as e:
        log.error("Failed to generate meeting prep: %s", e)
        return False

    # Send prep
    header = f"🎯 **MEETING PREP** — {event['summary']}\n\n"
    full_message = header + prep_text

    notifier.send_blip_message(conn, full_message)

    # Mark prep sent
    db.mark_reminder_sent(conn, event["event_id"], "meeting_prep")
    log.info("Sent meeting prep for: %s", event["summary"])

    return True


def check_and_send_meeting_reminders(conn):
    """
    Check for events starting in 55-65 min, send simple reminders + Opus prep if under cap.
    """
    events = db.get_events_needing_prep(conn, within_minutes=65)
    if not events:
        log.debug("No upcoming events needing reminders")
        return

    log.info("Found %d events needing reminders", len(events))

    for event in events:
        if not event["start_time"]:
            log.warning("Event %s has no start_time, skipping reminder", event["event_id"])
            continue
        event_start = datetime.fromisoformat(event["start_time"]).astimezone(config.PHT)
        summary = event["summary"] or "Untitled Event"
        meet_link = event["meet_link"]

        # Send simple reminder
        reminder_text = f"⏰ **UPCOMING MEETING** in ~1 hour\n\n"
        reminder_text += f"**{summary}**\n"
        reminder_text += f"Time: {event_start.strftime('%I:%M %p PHT')}\n"
        if meet_link:
            reminder_text += f"Link: {meet_link}\n"

        notifier.send_blip_message(conn, reminder_text)
        db.mark_reminder_sent(conn, event["event_id"], "simple_reminder")
        log.info("Sent simple reminder for: %s", summary)

        # Try to send Opus prep if under cap
        generate_meeting_prep(conn, event)


def _morning_system_prompt(now, last_briefing_time) -> str:
    """Morning briefing prompt — focused on decisions and responses."""
    return f"""You are Blip Sentinel, Sam Karazi's AI chief of staff.
{config.ORG_CONTEXT}

Today is {now.strftime("%Y-%m-%d %A")}. Here is everything that happened since {last_briefing_time}.

Produce a MORNING briefing with sections:
1. CRITICAL — Requires immediate action (respond within 1 hour). Max 3 items.
2. DECISIONS NEEDED — Needs Sam's decision but not urgent (respond today/tomorrow)
3. RESPONSES PENDING — Things Sam asked about that haven't been answered yet
4. CALENDAR — Next 48 hours of scheduled events
5. UNRESOLVED — Carry-forward items from previous briefings (show age in days)

Rules:
- Be concise. No filler. Max {config.BRIEFING_MAX_WORDS} words.
- Include specific names, spaces, times
- Suggest responses or actions where applicable
- EXCLUDE operational details: barrel counts, store visit grades, commissary inventory, food prep quantities
- Focus on DECISIONS and BLOCKED items, not status reports
- For UNRESOLVED section, prefix each item with its age: "[Day N]"
- List each unresolved item as "- UNRESOLVED: [Day N] description"
- Format for readability (use **bold** for names, *italic* for context)"""


def _evening_system_prompt(now, last_briefing_time) -> str:
    """Evening briefing prompt — short summary of the day."""
    return f"""You are Blip Sentinel, Sam Karazi's AI chief of staff.
{config.ORG_CONTEXT}

Today is {now.strftime("%Y-%m-%d %A")}. Here is everything that happened since {last_briefing_time}.

Produce a SHORT evening briefing (max 10 lines total) with sections:
1. COMPLETED TODAY — Things resolved or done today (meetings attended, decisions made, items approved)
2. STILL PENDING — Carry-forward items not yet resolved (show age: "[Day N]")
3. TOMORROW — Key events or deadlines for tomorrow

Rules:
- Be extremely concise. MAX 10 lines total across all sections.
- For STILL PENDING, prefix each with "[Day N]" showing how many days it's been pending
- List each pending item as "- UNRESOLVED: [Day N] description"
- No filler, no explanations, just the facts
- Format: plain text with **bold** for names only"""


def _format_briefing_prompt(messages, emails, events, unresolved,
                            pending_responses=None) -> str:
    """Format all data into a single Opus prompt."""
    parts = []

    if messages:
        parts.append("## MESSAGES\n" + _format_messages_for_prompt(messages))

    if emails:
        parts.append("## EMAILS\n" + _format_emails_for_prompt(emails))

    if events:
        parts.append("## CALENDAR\n" + _format_calendar_for_prompt(events))

    if pending_responses:
        lines = ["## RESPONSES PENDING (Sam asked, no reply yet)"]
        for resp in pending_responses:
            text = (resp["text"] or "")[:80]
            space = resp["space_name"] or "DM"
            lines.append(f"- In *{space}*: \"{text}\"")
        parts.append("\n".join(lines))

    if unresolved:
        lines = ["## UNRESOLVED FROM PREVIOUS BRIEFINGS"]
        now = datetime.now(config.PHT)
        for item in unresolved:
            created = item["created_at"]
            age_days = 0
            if created:
                try:
                    created_dt = datetime.fromisoformat(created)
                    age_days = (now.replace(tzinfo=None) - created_dt).days
                except (ValueError, TypeError):
                    pass
            age_str = f"[Day {age_days}] " if age_days > 0 else ""
            lines.append(f"- {age_str}{item['description']}")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def _format_messages_for_prompt(messages) -> str:
    """Format classified messages grouped by category."""
    output = []

    # Group by category
    by_category = {"URGENT": [], "ACTION": [], "FYI": []}
    for msg in messages:
        cat = msg["classification"]
        if cat in by_category:
            by_category[cat].append(msg)

    for category in ["URGENT", "ACTION", "FYI"]:
        msgs = by_category[category]
        if not msgs:
            continue

        output.append(f"### {category} ({len(msgs)})")
        for msg in msgs:
            sender = msg["sender_name"] or "Unknown"
            space = msg["space_name"] or "DM"
            text = (msg["text"] or "")[:300]

            # Redact sensitive messages in briefing
            if msg.get("contains_sensitive") and is_enabled("ENABLE_CONTENT_GUARD"):
                text = f"[Sensitive — check DM directly in {space}]"

            reason = msg["classification_reason"] or ""

            output.append(f"- **{sender}** in *{space}*: {text}")
            if reason:
                output.append(f"  _({reason})_")

    return "\n".join(output)


def _format_emails_for_prompt(emails) -> str:
    """Format email digest."""
    output = []

    # Group by category
    by_category = {"URGENT": [], "ACTION": [], "FYI": []}
    for email in emails:
        cat = email["classification"]
        if cat in by_category:
            by_category[cat].append(email)

    for category in ["URGENT", "ACTION", "FYI"]:
        msgs = by_category[category]
        if not msgs:
            continue

        output.append(f"### {category} ({len(msgs)})")
        for email in msgs:
            from_addr = email["from_addr"] or "Unknown"
            subject = email["subject"] or "(no subject)"
            snippet = (email["snippet"] or "")[:200]

            output.append(f"- **{from_addr}**: {subject}")
            output.append(f"  {snippet}")

    return "\n".join(output)


def _format_calendar_for_prompt(events) -> str:
    """Format upcoming events."""
    output = []

    now = datetime.now(config.PHT)
    today = now.date()
    for event in events[:10]:  # Limit to next 10 events
        if not event["start_time"]:
            continue
        start_time = datetime.fromisoformat(event["start_time"]).astimezone(config.PHT)
        summary = event["summary"] or "Untitled"

        # Relative time using calendar dates
        event_date = start_time.date()
        if event_date == today:
            time_str = f"Today {start_time.strftime('%I:%M %p')}"
        elif event_date == today + timedelta(days=1):
            time_str = f"Tomorrow {start_time.strftime('%I:%M %p')}"
        else:
            time_str = start_time.strftime("%b %d %I:%M %p")

        output.append(f"- **{summary}** — {time_str}")

    return "\n".join(output)


def _call_opus(system_prompt: str, user_prompt: str) -> str:
    """
    Call Opus API with error handling.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    try:
        response = client.messages.create(
            model=config.OPUS_MODEL,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except Exception as e:
        log.error("Opus API call failed: %s", e)
        raise


def _parse_unresolved_items(briefing_text: str) -> list[str]:
    """
    Parse unresolved items from briefing response.
    Expected format: "- UNRESOLVED: description"
    """
    items = []
    for line in briefing_text.split("\n"):
        line = line.strip()
        match = re.match(r'^-\s*UNRESOLVED:\s*(.+)', line, re.IGNORECASE)
        if match:
            items.append(match.group(1).strip())

    return items
