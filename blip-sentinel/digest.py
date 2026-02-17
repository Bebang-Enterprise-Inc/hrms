"""
Blip Sentinel v2.3 — 30-Minute Digest Module
Sends ONE consolidated notification every 30 minutes with context-rich summaries.
Uses Haiku to summarize conversations, not raw message forwarding.
"""

import logging
from datetime import datetime, timedelta

import config
import db
import notifier
from timeutil import utc_now, parse_db, to_pht
from feature_flags import is_enabled
from content_guard import redact_for_notification

log = logging.getLogger("sentinel.digest")


def generate_digest(conn):
    """
    Generate a 30-minute digest of all actionable messages and emails.

    Flow (Phase 3 — Response-First):
    1. Get last digest time (or default to 30 min ago)
    2. Collect messages by classification type
    3. Build response-first digest structure
    4. Send ONE message to ! Blip Notifications
    5. Update digest timestamp (idempotent pattern)
    """
    # Get time window
    last_digest = db.get_last_digest_time(conn)
    if not last_digest:
        dt = parse_db(utc_now()) - timedelta(minutes=30)
        last_digest = dt.strftime('%Y-%m-%d %H:%M:%S')
        log.info("First digest — looking back 30 min from now")

    # Collect all classified messages since last digest
    stats = db.get_digest_stats(conn, last_digest)
    noise_count = stats.get("NOISE", 0)
    routine_count = stats.get("ROUTINE", 0)
    self_count = stats.get("SELF", 0)

    if is_enabled("ENABLE_RESPONSE_FIRST_DIGEST"):
        # Phase 3: Response-first digest
        responses = db.get_messages_since(conn, last_digest, ["RESPONSE"])
        urgent_action = db.get_messages_since(conn, last_digest, ["URGENT", "ACTION"])
        fyi = db.get_messages_since(conn, last_digest, ["FYI"])
        emails = db.get_emails_since(conn, last_digest, ["URGENT", "ACTION", "FYI"])

        total_actionable = len(responses) + len(urgent_action) + len(fyi) + len(emails)

        if total_actionable == 0:
            log.info("No actionable messages since last digest. Noise: %d, Routine: %d, Self: %d",
                     noise_count, routine_count, self_count)
            db.set_last_digest_time(conn)
            return

        log.info("Digest: %d responses, %d urgent/action, %d fyi, %d emails",
                 len(responses), len(urgent_action), len(fyi), len(emails))

        digest_text = _build_response_first_digest(
            conn, responses, urgent_action, fyi, emails,
            noise_count, routine_count
        )
    if not digest_text:
        log.warning("Digest generation produced empty text")
        db.set_last_digest_time(conn)
        return

    # Send ONE consolidated notification
    now_pht = datetime.now(config.PHT)
    header = f"📋 **DIGEST** — {now_pht.strftime('%I:%M %p PHT')}\n\n"

    # Save timestamp BEFORE sending (idempotent pattern)
    saved_time = utc_now()
    db.set_last_digest_time(conn, saved_time)

    result = notifier.send_blip_message(conn, header + digest_text, notification_type="digest")

    if result is None:
        db.set_last_digest_time(conn, last_digest)
        log.warning("Digest send failed, rolled back timestamp")
        return

    log.info("Digest sent successfully")


def _build_response_first_digest(conn, responses, urgent_action, fyi, emails,
                                  noise_count, routine_count) -> str:
    """
    Build Phase 3 response-first digest.

    Structure:
    1. RESPONSES TO YOU — replies to Sam's messages (highest priority)
    2. NEEDS YOUR DECISION — URGENT + ACTION items
    3. FYI — informational items
    4. EMAILS — if any
    5. Footer — filtered counts
    """
    parts = []

    # Section 1: RESPONSES TO YOU
    if responses:
        parts.append(f"**RESPONSES TO YOU** ({len(responses)})")
        for msg in responses:
            sender = msg["sender_name"] or "Unknown"
            text = _safe_text(msg, 150)
            # Get Sam's original question for context
            sam_original = db.get_sam_original_in_thread(
                conn, msg["thread_id"], config.SAM_CHAT_USER_ID
            )
            if sam_original:
                parts.append(f'  Re: "{sam_original}" → **{sender}**: {text}')
            else:
                parts.append(f"  **{sender}**: {text}")

    # Section 2: NEEDS YOUR DECISION
    if urgent_action:
        parts.append("")
        parts.append(f"**NEEDS YOUR DECISION** ({len(urgent_action)})")

        # Split mentions from non-mentions for sub-grouping
        mentions = [m for m in urgent_action if m["mentions_sam"]]
        decisions = [m for m in urgent_action if not m["mentions_sam"]]

        for msg in decisions:
            sender = msg["sender_name"] or "Unknown"
            text = _safe_text(msg, 150)
            space = msg["space_name"] or "DM"
            icon = "🔴" if msg["classification"] == "URGENT" else "🟡"
            parts.append(f"  {icon} **{sender}** in {space}: {text}")

        if mentions:
            parts.append(f"\n**MENTIONS** ({len(mentions)})")
            for msg in mentions:
                sender = msg["sender_name"] or "Unknown"
                text = _safe_text(msg, 150)
                space = msg["space_name"] or "DM"
                parts.append(f"  **{sender}** in {space}: {text}")

    # Section 3: FYI
    if fyi:
        parts.append("")
        parts.append(f"**FYI** ({len(fyi)})")
        for msg in fyi[:10]:  # Cap at 10 FYI items
            sender = msg["sender_name"] or "Unknown"
            text = _safe_text(msg, 120)
            parts.append(f"  {sender}: {text}")
        if len(fyi) > 10:
            parts.append(f"  _...and {len(fyi) - 10} more_")

    # Section 4: Emails
    if emails:
        parts.append("")
        parts.append(f"📧 **EMAILS** ({len(emails)})")
        for email in emails:
            cat_icon = {"URGENT": "🔴", "ACTION": "🟡", "FYI": "📝"}.get(
                email["classification"], "📝"
            )
            from_addr = email["from_addr"] or "Unknown"
            subject = email["subject"] or "(no subject)"
            parts.append(f"  {cat_icon} **{from_addr}**: {subject}")

    # Footer
    filtered_parts = []
    if noise_count > 0:
        filtered_parts.append(f"{noise_count} noise")
    if routine_count > 0:
        filtered_parts.append(f"{routine_count} store reports")
    if filtered_parts:
        parts.append(f"\n_Filtered: {', '.join(filtered_parts)}_")

    return "\n".join(parts)


def _safe_text(msg, max_len: int = 200) -> str:
    """Get message text, redacting if sensitive."""
    text = (msg["text"] or "")[:max_len]
    if msg.get("contains_sensitive") and is_enabled("ENABLE_CONTENT_GUARD"):
        text = redact_for_notification(text, msg.get("space_name", "DM"))
    return text


