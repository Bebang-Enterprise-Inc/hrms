#!/usr/bin/env python3
"""
Sheets Receiver Service - Main Entry Point

A sustainable Google Sheets sync service similar to ADMS Receiver.
Runs as a Docker container alongside Frappe.

Features:
- Receives Google Drive push notifications for real-time sync
- Automatic watch renewal (watches expire every 24h)
- Change detection via checksums (only sync when data changes)
- Full audit trail in SQLite database
- REST API for manual triggers and status

Usage:
    # Run as service
    python -m hrms.services.sheets_receiver.main

    # With environment variables
    FRAPPE_URL=https://hq.bebang.ph \
    FRAPPE_API_KEY=xxx \
    FRAPPE_API_SECRET=xxx \
    python -m hrms.services.sheets_receiver.main

    # Docker
    docker run -d --name sheets-receiver \
        -e FRAPPE_URL=https://hq.bebang.ph \
        -e FRAPPE_API_KEY=xxx \
        -e FRAPPE_API_SECRET=xxx \
        -v ./credentials:/app/credentials \
        -p 8765:8765 \
        sheets-receiver:latest
"""

import logging
import signal
import sys
import threading
import time
from datetime import datetime

import schedule

from .config import get_config, get_watched_sheets
from .models import get_db
from .sheets_client import get_sheets_client
from .processor import get_processor
from .webhook import run_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def setup_file_logging():
    """Set up file logging."""
    config = get_config()

    # Ensure log directory exists
    from pathlib import Path
    Path(config.log_file).parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(config.log_file)
    file_handler.setLevel(getattr(logging, config.log_level))
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

    logging.getLogger().addHandler(file_handler)


def renew_watches_job():
    """Scheduled job to renew expiring watches."""
    logger.info("Running watch renewal job...")
    try:
        client = get_sheets_client()
        renewed = client.renew_expiring_watches(hours_before=2)
        if renewed:
            logger.info(f"Renewed {len(renewed)} watches")
    except Exception as e:
        logger.error(f"Watch renewal failed: {e}")


def scheduled_sync_job():
    """
    Scheduled job to sync all sheets.

    This is a backup in case webhooks are missed.
    Runs less frequently since webhooks should catch most changes.
    """
    logger.info("Running scheduled sync job...")
    try:
        processor = get_processor()
        processor.sync_all_sheets(trigger='scheduled', force=False)
    except Exception as e:
        logger.error(f"Scheduled sync failed: {e}")


def run_scheduler():
    """Run the scheduler in a background thread."""
    config = get_config()

    # Renew watches every hour (they expire after 24h)
    schedule.every(1).hour.do(renew_watches_job)

    # Backup sync every 6 hours (in case webhooks missed)
    schedule.every(6).hours.do(scheduled_sync_job)

    logger.info("Scheduler started")

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


def initial_setup():
    """Perform initial setup on startup."""
    logger.info("=" * 60)
    logger.info("Sheets Receiver Service Starting")
    logger.info("=" * 60)

    config = get_config()

    # Initialize database
    logger.info("Initializing database...")
    db = get_db()

    # Log configuration
    logger.info(f"Frappe URL: {config.frappe_url}")
    logger.info(f"Webhook URL: {config.public_webhook_url}")
    logger.info(f"Webhook port: {config.webhook_port}")

    # Log watched sheets
    sheets = get_watched_sheets()
    logger.info(f"Watching {len(sheets)} sheets:")
    for key, sheet in sheets.items():
        logger.info(f"  - {sheet.name} ({sheet.spreadsheet_id})")

    # Set up watches
    logger.info("Setting up Google Drive watches...")
    try:
        client = get_sheets_client()
        watches = client.setup_all_watches()
        logger.info(f"Created/verified {len(watches)} watches")
    except Exception as e:
        logger.error(f"Failed to set up watches: {e}")
        logger.warning("Service will continue without real-time notifications")
        logger.warning("Using scheduled sync as fallback")

    # Initial sync
    logger.info("Performing initial sync check...")
    try:
        processor = get_processor()
        processor.sync_all_sheets(trigger='startup', force=False)
    except Exception as e:
        logger.error(f"Initial sync failed: {e}")

    logger.info("Initial setup complete")
    logger.info("=" * 60)


def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Shutdown signal received, cleaning up...")

    # Could stop watches here if needed
    # (but they'll expire anyway after 24h)

    sys.exit(0)


def main():
    """Main entry point."""
    # Set up logging
    setup_file_logging()

    # Handle shutdown signals
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Initial setup
    initial_setup()

    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    # Run webhook server (this blocks)
    logger.info("Starting webhook server...")
    run_server()


if __name__ == "__main__":
    main()
