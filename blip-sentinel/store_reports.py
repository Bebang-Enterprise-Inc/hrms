"""
Blip Sentinel v2.3 — Store Report Aggregation (Phase 4)

Parses ROUTINE-classified store closing reports, aggregates daily data,
and sends a nightly summary to ! Blip Notifications.

Gated by feature flag: ENABLE_STORE_SUMMARY
"""

import logging
import re
from datetime import datetime, timedelta, timezone

import config
import db
import notifier
from timeutil import utc_now, to_pht
from feature_flags import is_enabled

log = logging.getLogger("sentinel.store_reports")

# ── Regex Parsers for Closing Report Fields ──

GROSS_SALES_RE = re.compile(
    r"Total\s+Gross\s+Sales[:\s]*[P₱]?\s*([\d,]+(?:\.\d{2})?)",
    re.IGNORECASE,
)
NET_SALES_RE = re.compile(
    r"Total\s+Net\s+Sales[:\s]*[P₱]?\s*([\d,]+(?:\.\d{2})?)",
    re.IGNORECASE,
)
CUP_SOLD_RE = re.compile(
    r"Total\s+Cup\s+Sold[:\s]*\s*([\d,]+)",
    re.IGNORECASE,
)

# Fund issue keywords
FUND_ISSUE_KEYWORDS = [
    "depleted", "overused", "borrowed", "negative",
    "short", "insufficient", "exceeded",
]

FUND_ISSUE_RE = re.compile(
    r"(PCF|Delivery\s+Fund|Petty\s+Cash|Fund)[^.]*("
    + "|".join(FUND_ISSUE_KEYWORDS)
    + r")",
    re.IGNORECASE,
)


def _parse_amount(s: str) -> float:
    """Parse a Philippine-formatted amount string to float."""
    return float(s.replace(",", ""))


def parse_store_report(text: str) -> dict:
    """
    Extract structured data from a store closing report.

    Returns dict with keys: gross_sales, net_sales, cups_sold, fund_issues
    All values may be None if not found in text.
    """
    result = {
        "gross_sales": None,
        "net_sales": None,
        "cups_sold": None,
        "fund_issues": [],
    }

    m = GROSS_SALES_RE.search(text)
    if m:
        result["gross_sales"] = _parse_amount(m.group(1))

    m = NET_SALES_RE.search(text)
    if m:
        result["net_sales"] = _parse_amount(m.group(1))

    m = CUP_SOLD_RE.search(text)
    if m:
        result["cups_sold"] = int(m.group(1).replace(",", ""))

    # Find fund issues (line-by-line)
    for line in text.split("\n"):
        if FUND_ISSUE_RE.search(line):
            result["fund_issues"].append(line.strip())

    return result


def _extract_store_name(text: str, space_name: str) -> str:
    """Try to extract the store name from the report text or fall back to space name."""
    # Look for store name in common patterns
    # "CLOSING REPORT\nSM Megamall" or "DAILY SALES REPORT\nSM Megamall - Feb 13"
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if re.match(r"(CLOSING|DAILY)", line, re.IGNORECASE):
            # Next non-empty line is likely the store name
            if i + 1 < len(lines):
                name_line = lines[i + 1]
                # Strip date suffix: "SM Megamall - Feb 13" -> "SM Megamall"
                name_line = re.sub(r"\s*-\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+.*",
                                   "", name_line, flags=re.IGNORECASE)
                return name_line.strip()
    return space_name


def generate_store_summary(conn):
    """
    Generate nightly store report summary.

    Collects all ROUTINE messages from today, parses them,
    and sends a consolidated summary.

    Gated by ENABLE_STORE_SUMMARY feature flag.
    """
    if not is_enabled("ENABLE_STORE_SUMMARY"):
        log.info("Store summary disabled (ENABLE_STORE_SUMMARY=false)")
        return

    # Look back 24 hours for today's reports
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    routine_msgs = db.get_messages_since(conn, since, ["ROUTINE"])

    if not routine_msgs:
        log.info("No store reports found in last 24h")
        return

    log.info("Processing %d store reports for nightly summary", len(routine_msgs))

    # Parse each report
    stores = []
    for msg in routine_msgs:
        text = msg["text"] or ""
        parsed = parse_store_report(text)
        store_name = _extract_store_name(text, msg["space_name"] or "Unknown")
        stores.append({
            "name": store_name,
            "gross_sales": parsed["gross_sales"],
            "net_sales": parsed["net_sales"],
            "cups_sold": parsed["cups_sold"],
            "fund_issues": parsed["fund_issues"],
            "space_name": msg["space_name"],
        })

    # Build summary
    summary = _build_store_summary(stores)

    if not summary:
        log.warning("Store summary generation produced empty text")
        return

    # Send
    now_pht = datetime.now(config.PHT)
    header = f"📊 **STORE REPORTS** — {now_pht.strftime('%b %d')}\n\n"

    result = notifier.send_blip_message(
        conn, header + summary, notification_type="store_summary"
    )

    if result is None:
        log.warning("Store summary send failed")
    else:
        log.info("Store summary sent successfully (%d stores)", len(stores))


def _build_store_summary(stores: list) -> str:
    """Build the store report summary text."""
    if not stores:
        return ""

    parts = []
    reported_count = len(stores)

    # Top 5 by gross sales (only those with parsed data)
    with_sales = [s for s in stores if s["gross_sales"] is not None]
    with_sales.sort(key=lambda s: s["gross_sales"], reverse=True)

    if with_sales:
        parts.append(f"**Top 5 by Gross Sales** ({reported_count} stores reported):")
        for i, store in enumerate(with_sales[:5]):
            gross = store["gross_sales"]
            cups = store["cups_sold"]
            cup_str = f" ({cups:,} cups)" if cups else ""
            parts.append(f"  {i+1}. {store['name']}: P{gross:,.0f}{cup_str}")
    else:
        parts.append(f"{reported_count} store reports received (no sales data parsed)")

    # Fund issues
    stores_with_issues = [s for s in stores if s["fund_issues"]]
    if stores_with_issues:
        parts.append("")
        parts.append(f"**Fund Issues** ({len(stores_with_issues)} stores):")
        for store in stores_with_issues:
            for issue in store["fund_issues"][:2]:  # Max 2 issues per store
                parts.append(f"  {store['name']}: {issue}")

    return "\n".join(parts)
