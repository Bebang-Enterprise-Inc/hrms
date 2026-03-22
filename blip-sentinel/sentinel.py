#!/usr/bin/env python3
"""
Blip Sentinel v2.3 — Main CLI Entry Point

Commands:
  --sweep {chat,gmail,calendar}  Run a specific sweeper
  --classify                     Run classifier on new messages and emails
  --briefing {morning,evening}   Generate and send briefing
  --remind meetings              Check and send meeting reminders
  --discover spaces              Discover all Google Chat spaces
  --prune [--days N]             Prune old data (default: 90 days)
"""

import argparse
import logging
import sys
import signal
import threading
from logging.handlers import RotatingFileHandler

import config
from db import get_db, prune_old_data
from sweepers.chat import sweep_chat, discover_spaces
from sweepers.gmail import sweep_gmail
from sweepers.calendar import sweep_calendar
from classifier import classify_new_messages, classify_emails
from briefing import generate_briefing, check_and_send_meeting_reminders
from digest import generate_digest
from store_reports import generate_store_summary
from notifier import ping_healthcheck
from metrics import track_job


_shutting_down = threading.Event()


def _handle_shutdown(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    sig_name = signal.Signals(signum).name
    logging.getLogger(__name__).warning("Received %s — initiating graceful shutdown", sig_name)
    _shutting_down.set()


def is_shutting_down() -> bool:
    return _shutting_down.is_set()


def setup_logging():
    """Configure logging with rotating file handler and stdout."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        config.LOG_PATH,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
    )
    file_handler.setLevel(logging.INFO)

    # Stdout handler for Docker logs
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


def main():
    parser = argparse.ArgumentParser(description="Blip Sentinel v2.3 CLI")
    parser.add_argument(
        "--sweep",
        choices=["chat", "gmail", "calendar"],
        help="Run a specific sweeper",
    )
    parser.add_argument(
        "--classify",
        action="store_true",
        help="Run classifier on new messages and emails",
    )
    parser.add_argument(
        "--digest",
        action="store_true",
        help="Generate 30-minute digest of actionable messages",
    )
    parser.add_argument(
        "--briefing",
        choices=["morning", "evening"],
        help="Generate and send briefing",
    )
    parser.add_argument(
        "--remind",
        choices=["meetings"],
        help="Check and send meeting reminders",
    )
    parser.add_argument(
        "--discover",
        choices=["spaces"],
        help="Discover all Google Chat spaces",
    )
    parser.add_argument(
        "--store-summary",
        action="store_true",
        help="Generate nightly store report summary",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Prune old data (default: 90 days)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of days to retain (use with --prune)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    try:
        # Sweep commands
        if args.sweep == "chat":
            logger.info("Starting chat sweep...")
            with get_db() as conn:
                with track_job(conn, "chat_sweep") as m:
                    sweep_chat(conn)
            ping_healthcheck(config.HC_CHAT_SWEEP)
            logger.info("Chat sweep completed successfully")

        elif args.sweep == "gmail":
            logger.info("Starting Gmail sweep...")
            with get_db() as conn:
                with track_job(conn, "gmail_sweep") as m:
                    sweep_gmail(conn)
            ping_healthcheck(config.HC_GMAIL_SWEEP)
            logger.info("Gmail sweep completed successfully")

        elif args.sweep == "calendar":
            logger.info("Starting calendar sweep...")
            with get_db() as conn:
                with track_job(conn, "calendar_sweep") as m:
                    sweep_calendar(conn)
            ping_healthcheck(config.HC_CALENDAR_SWEEP)
            logger.info("Calendar sweep completed successfully")

        # Classify command
        elif args.classify:
            logger.info("Starting classification...")
            with get_db() as conn:
                with track_job(conn, "classify") as m:
                    classify_new_messages(conn)
                    classify_emails(conn)
            ping_healthcheck(config.HC_CLASSIFY)
            logger.info("Classification completed successfully")

        # Digest command (30-min consolidated notification)
        elif args.digest:
            logger.info("Generating digest...")
            with get_db() as conn:
                with track_job(conn, "digest") as m:
                    generate_digest(conn)
            logger.info("Digest completed successfully")

        # Briefing commands
        elif args.briefing:
            briefing_type = args.briefing
            logger.info(f"Generating {briefing_type} briefing...")
            with get_db() as conn:
                with track_job(conn, f"{briefing_type}_briefing") as m:
                    generate_briefing(conn, briefing_type)
            healthcheck_url = (
                config.HC_MORNING_BRIEFING
                if briefing_type == "morning"
                else config.HC_EVENING_BRIEFING
            )
            ping_healthcheck(healthcheck_url)
            logger.info(f"{briefing_type.capitalize()} briefing completed successfully")

        # Remind meetings command
        elif args.remind == "meetings":
            logger.info("Checking meeting reminders...")
            with get_db() as conn:
                with track_job(conn, "meeting_reminders") as m:
                    check_and_send_meeting_reminders(conn)
            logger.info("Meeting reminders completed successfully")

        # Discover spaces command
        elif args.discover == "spaces":
            logger.info("Discovering Google Chat spaces...")
            with get_db() as conn:
                discover_spaces(conn)
            logger.info("Space discovery completed successfully")

        # Store summary command (nightly)
        elif args.store_summary:
            logger.info("Generating store report summary...")
            with get_db() as conn:
                with track_job(conn, "store_summary") as m:
                    generate_store_summary(conn)
            logger.info("Store summary completed successfully")

        # Prune command
        elif args.prune:
            logger.info(f"Pruning data older than {args.days} days...")
            with get_db() as conn:
                prune_old_data(conn, args.days)
            logger.info("Data pruning completed successfully")

        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error during execution: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
