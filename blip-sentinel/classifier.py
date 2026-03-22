"""
Blip Sentinel v2.3 — Layer 2 Classifier
Cheap AI-powered message classification using Claude Haiku.
"""

import re
import time
import random
import logging
import anthropic
import hashlib
from typing import Optional

import config
import db
from models import MessageClassification
from rate_limiter import CircuitBreaker
from content_guard import is_sensitive, get_sensitivity_flags
from feature_flags import is_enabled

log = logging.getLogger("sentinel.classifier")

# Circuit breaker for Haiku classifier
_haiku_circuit = CircuitBreaker(
    name="haiku_classifier",
    failure_threshold=5,
    recovery_timeout=300,
)

# ── Pre-Classification Patterns ──

NOISE_PATTERNS = [
    r'^(ok|oki|okok|noted|done|got it|got this|sige|copy|yes|no|yep|nope)\s*[.!]*$',
    r'^(thank|thanks|ty|salamat)\s',
    r'^(thanks|thank you|ty|salamat|noted|copy)\s*[.!]*$',
    r'^👍|^👌|^✅|^🙏',
    r'^(haha|hahaha|lol|nice|alright)\s*[.!]*$',
    r'^(sige|ge|oo|opo)\s*[.!]*$',
]

URGENT_PATTERNS = [
    r'<users/115141803777443372092>.*\?',  # @Sam + question mark
    r'(approval|approve|sign off|urgent|asap|emergency)',
]

# Closing report template patterns (ROUTINE classification)
CLOSING_REPORT_PATTERNS = [
    r'CLOSING REPORT',
    r'Total Gross Sales:',
    r'Total Net Sales:',
    r'Total Cup Sold:',
    r'DAILY (?:SALES )?REPORT',
]


def pre_classify(msg: dict, conn=None) -> Optional[tuple[str, str]]:
    """
    Regex-based fast filter. Returns (category, reason) or None if needs AI.

    Rules (in priority order):
    0. SELF filter — Sam's own messages (Phase 1)
    1. Empty/whitespace text — NOISE (Phase 2)
    2. NOISE_PATTERNS — acknowledgements/greetings (Phase 0+)
    3. CLOSING_REPORT_PATTERNS — store reports → ROUTINE (Phase 2)
    4. RESPONSE detection — replies to Sam's thread messages (Phase 2)
    5. URGENT_PATTERNS — @Sam + question/approval (Phase 0+)
    6. Otherwise return None (needs AI)
    """
    # SELF filter — Sam's own messages (Phase 1)
    sender_id = msg.get("sender_id") or ""
    if is_enabled("ENABLE_SELF_FILTER") and sender_id == config.SAM_CHAT_USER_ID:
        return (MessageClassification.SELF.value, "sam_own_message")

    text = (msg.get("text") or "").strip()
    text_lower = text.lower()
    mentions_sam = bool(msg.get("mentions_sam"))

    # Empty/whitespace text — NOISE (Phase 2 enhanced rules)
    if is_enabled("ENABLE_PRE_RULES") and not text:
        return (MessageClassification.NOISE.value, "empty_text")

    # Check noise patterns
    for pattern in NOISE_PATTERNS:
        if re.match(pattern, text_lower, re.IGNORECASE):
            return (MessageClassification.NOISE.value, "acknowledgement/greeting")

    # Closing report detection → ROUTINE (Phase 2)
    if is_enabled("ENABLE_ROUTINE_CLASSIFICATION"):
        for pattern in CLOSING_REPORT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return (MessageClassification.ROUTINE.value, "store_closing_report")

    # RESPONSE detection — replies to Sam's thread messages (Phase 2)
    if is_enabled("ENABLE_RESPONSE_DETECTION") and conn is not None:
        thread_id = msg.get("thread_id")
        if thread_id and sender_id != config.SAM_CHAT_USER_ID:
            sam_msg = db.sam_sent_in_thread(conn, thread_id, config.SAM_CHAT_USER_ID)
            if sam_msg:
                return (MessageClassification.RESPONSE.value, "reply_to_sam_thread")

    # Check urgent patterns (only if @Sam)
    if mentions_sam:
        for pattern in URGENT_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return (MessageClassification.URGENT.value, "direct question/approval request")

    # Needs AI
    return None


def classify_new_messages(conn):
    """
    Main classification function for chat messages.

    Flow:
    1. Get unclassified messages (limit 50)
    2. For each: check is_image_only → NOISE; then pre_classify(); collect remaining
    3. Batch remaining into single Haiku API call
    4. Parse response and update classifications
    """
    messages = db.get_unclassified_messages(conn, limit=config.CLASSIFIER_BATCH_SIZE)
    if not messages:
        log.debug("No unclassified messages")
        return

    log.info("Classifying %d messages", len(messages))

    needs_ai = []

    for msg in messages:
        msg_id = msg["id"]

        # Image-only messages are NOISE
        if msg["is_image_only"]:
            db.update_classification(conn, msg_id, MessageClassification.NOISE.value, "image-only", "regex")
            log.debug("Message %d → NOISE (image-only)", msg_id)
            continue

        # Try pre-classification (convert Row to dict for regex matching)
        result = pre_classify(dict(msg), conn=conn)
        if result:
            category, reason = result
            db.update_classification(conn, msg_id, category, reason, "regex")
            log.debug("Message %d → %s (regex: %s)", msg_id, category, reason)
            continue

        # Message deduplication (BLOCKER-14)
        if is_enabled("ENABLE_MESSAGE_DEDUP"):
            text = (msg["text"] or "")[:200]
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            # Store hash
            conn.execute("UPDATE raw_messages SET text_hash = ? WHERE id = ?", (text_hash, msg_id))
            conn.commit()
            # Check for duplicate
            if db.check_duplicate_hash(conn, text_hash, hours=24):
                db.update_classification(conn, msg_id, MessageClassification.DUPLICATE.value, "duplicate_content", "dedup")
                log.debug("Message %d → DUPLICATE (text_hash match)", msg_id)
                continue

        # Content guard (BLOCKER-9)
        if is_enabled("ENABLE_CONTENT_GUARD"):
            flags = get_sensitivity_flags(msg["text"] or "")
            if any(flags.values()):
                conn.execute("UPDATE raw_messages SET contains_sensitive = 1 WHERE id = ?", (msg_id,))
                conn.commit()

        # Needs AI
        needs_ai.append(msg)

    if not needs_ai:
        log.info("All messages classified via regex")
        return

    # Batch classify via Haiku
    log.info("Sending %d messages to Haiku", len(needs_ai))
    classifications = _batch_classify_haiku(needs_ai)

    for msg_id, category, reason in classifications:
        # Phase 6.3: Guard Haiku summaries — redact if reason leaks sensitive content
        if is_enabled("ENABLE_CONTENT_GUARD") and is_sensitive(reason):
            reason = "[sensitive — see original message]"
            log.info("Redacted Haiku reason for message %d (contained sensitive keywords)", msg_id)
        db.update_classification(conn, msg_id, category, reason, "haiku")
        log.debug("Message %d → %s (haiku: %s)", msg_id, category, reason)

    log.info("Classification complete")


def classify_emails(conn):
    """
    Similar flow for raw_emails table.
    """
    emails = db.get_unclassified_emails(conn, limit=config.CLASSIFIER_BATCH_SIZE)
    if not emails:
        log.debug("No unclassified emails")
        return

    log.info("Classifying %d emails", len(emails))

    # For emails, we always use AI (no simple regex shortcuts)
    classifications = _batch_classify_haiku_emails(emails)

    for email_id, category, reason in classifications:
        db.update_classification(conn, email_id, category, reason, "haiku", table="raw_emails")
        log.debug("Email %d → %s (haiku: %s)", email_id, category, reason)

    log.info("Email classification complete")


def _batch_classify_haiku(messages: list) -> list[tuple[int, str, str]]:
    """
    Batch classify chat messages via Haiku.
    Returns list of (msg_id, category, reason).
    """
    system_prompt = f"""You are a message classifier for Sam Karazi, CEO of Bebang Enterprise Inc.
Classify each message into exactly one category:
URGENT - Needs Sam's immediate response (direct question to Sam, approval request, escalation, deadline today)
ACTION - Needs Sam's decision but not immediately (request for input, FYI that requires follow-up)
FYI - Worth mentioning in daily briefing (important update, project milestone, significant news)
NOISE - Not worth mentioning (acknowledgements, general chatter, screenshots without context, automated notifications)

Context:
- Sam is CEO. He cares about: finance decisions, key hires, major project updates, client issues, compliance
- Chimes Marco is his Executive Assistant — her schedule posts and "oki" messages are NOISE
- Store branch general chatter is NOISE unless emergency or @mentions Sam
- Direct questions with "?" from key people (Ana, Mae, Herdie, Alessandro) are usually ACTION or URGENT

For each message, respond with ONLY: [message_id] CATEGORY reason (10 words max)"""

    user_prompt = "Classify these messages:\n\n"
    for msg in messages:
        sender = msg["sender_name"] or "Unknown"
        text = (msg["text"] or "")[:500]  # Truncate long messages
        space = msg["space_name"] or "DM"
        mentions_sam = " [@Sam]" if msg["mentions_sam"] else ""

        user_prompt += f"[{msg['id']}] From: {sender} | Space: {space}{mentions_sam}\n{text}\n\n"

    response = call_haiku_with_retry(system_prompt, user_prompt)
    if response is None:
        return []
    return parse_classifications(response)


def _batch_classify_haiku_emails(emails: list) -> list[tuple[int, str, str]]:
    """
    Batch classify emails via Haiku.
    Returns list of (email_id, category, reason).
    """
    system_prompt = f"""You are an email classifier for Sam Karazi, CEO of Bebang Enterprise Inc.
Classify each email into exactly one category:
URGENT - Needs Sam's immediate attention (escalation, critical issue, contract/legal, deadline today)
ACTION - Needs Sam's response but not urgent (requires decision, input requested, follow-up needed)
FYI - Worth mentioning in briefing (industry news, updates, newsletters)
NOISE - Not worth mentioning (marketing spam, automated notifications, LinkedIn invites)

Context:
{config.ORG_CONTEXT}

For each email, respond with ONLY: [email_id] CATEGORY reason (10 words max)"""

    user_prompt = "Classify these emails:\n\n"
    for email in emails:
        from_addr = email.get("from_addr") or "Unknown"
        subject = email.get("subject") or "(no subject)"
        snippet = (email.get("snippet") or "")[:300]

        user_prompt += f"[{email['id']}] From: {from_addr}\nSubject: {subject}\n{snippet}\n\n"

    response = call_haiku_with_retry(system_prompt, user_prompt)
    if response is None:
        return []
    return parse_classifications(response)


def call_haiku_with_retry(system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
    """
    Call Haiku API with exponential backoff retry and circuit breaker.
    """
    # Check circuit breaker
    if not _haiku_circuit.can_execute():
        log.warning("Haiku circuit breaker OPEN — skipping AI classification")
        return None

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=config.HAIKU_MODEL,
                max_tokens=config.HAIKU_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            _haiku_circuit.record_success()
            return response.content[0].text
        except Exception as e:
            _haiku_circuit.record_failure()
            if attempt == max_retries - 1:
                log.error("Haiku API call failed after %d retries: %s", max_retries, e)
                return None

            # Exponential backoff with jitter
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            log.warning("Haiku API call failed (attempt %d/%d), retrying in %.2fs: %s",
                       attempt + 1, max_retries, wait_time, e)
            time.sleep(wait_time)

    return None


def parse_classifications(response_text: str) -> list[tuple[int, str, str]]:
    """
    Parse "[msg_id] CATEGORY reason" format.
    Returns list of (msg_id, category, reason).
    """
    results = []
    for line in response_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Expected format: [123] URGENT direct question from Mae
        match = re.match(r'\[(\d+)\]\s+(URGENT|ACTION|FYI|NOISE|ROUTINE|RESPONSE)\s+(.+)', line, re.IGNORECASE)
        if match:
            msg_id = int(match.group(1))
            category_str = match.group(2).upper()
            reason = match.group(3).strip()[:200]  # Cap reason length

            # Validate category
            if MessageClassification.is_valid(category_str):
                results.append((msg_id, category_str, reason))
            else:
                log.warning("Invalid classification category: %s", category_str)
        else:
            log.warning("Failed to parse classification line (length=%d)", len(line))

    return results
