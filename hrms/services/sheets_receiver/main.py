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
from .file_processor import get_file_processor
from .folder_watcher import get_folder_watcher

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


# =============================================================================
# POS File Processing Jobs (Automatic - No Manual Intervention Required)
# =============================================================================

def process_pending_files_job():
    """
    Automatic job to process pending POS files from the queue.

    Runs every 2 minutes to pick up newly queued files.
    Uses parallel processing (10 workers) for fast throughput.
    """
    try:
        processor = get_file_processor()
        db = get_db()

        # Get pending count first
        pending_count = db.get_pending_count()
        if pending_count == 0:
            return  # Nothing to do, skip logging

        logger.info(f"Processing {pending_count} pending files...")

        # Process up to 50 files per batch with parallel processing
        result = processor.process_pending_files(limit=50, parallel=True)

        if result['processed'] > 0 or result['failed'] > 0:
            logger.info(
                f"File processing complete: {result['processed']} processed, "
                f"{result['failed']} failed, {result['total_records']} records extracted"
            )

    except Exception as e:
        logger.error(f"File processing job failed: {e}")


def retry_failed_files_job():
    """
    Automatic job to retry failed POS files.

    Runs every 15 minutes to retry files that failed processing.
    Only retries files that failed less than 3 times.
    """
    try:
        db = get_db()

        # Get failed files that haven't exceeded retry limit
        failed_files = db.get_failed_files(max_retries=3)
        if not failed_files:
            return  # Nothing to retry

        logger.info(f"Retrying {len(failed_files)} failed files...")

        # Reset status to pending for retry
        retry_count = 0
        for entry in failed_files:
            db.reset_for_retry(entry['file_id'])
            retry_count += 1

        if retry_count > 0:
            logger.info(f"Reset {retry_count} files for retry")

            # Immediately process the reset files
            processor = get_file_processor()
            result = processor.process_pending_files(limit=retry_count, parallel=True)
            logger.info(
                f"Retry results: {result['processed']} succeeded, "
                f"{result['failed']} still failing"
            )

    except Exception as e:
        logger.error(f"Failed files retry job failed: {e}")


def scan_for_new_files_job():
    """
    Automatic job to scan all store folders for new files.

    Runs every 30 minutes as a backup to webhook notifications.
    Discovers new files that might have been missed by push notifications.
    """
    try:
        watcher = get_folder_watcher()
        logger.info("Scanning all store folders for new files...")

        result = watcher.scan_all_stores()

        if result['total_queued'] > 0:
            logger.info(
                f"Folder scan: {result['total_found']} files found, "
                f"{result['total_queued']} queued for processing, "
                f"{result['stores_with_files']} stores with new files"
            )
        else:
            logger.debug("Folder scan: No new files found")

    except Exception as e:
        logger.error(f"Folder scan job failed: {e}")


def renew_folder_watches_job():
    """
    Scheduled job to renew expiring folder watches.

    Folder watches expire after 24 hours. This runs hourly
    to renew any watches expiring in the next 2 hours.
    """
    logger.info("Running folder watch renewal job...")
    try:
        watcher = get_folder_watcher()
        renewed = watcher.renew_expiring_folder_watches(hours_before=2)
        if renewed:
            logger.info(f"Renewed {len(renewed)} folder watches")
    except Exception as e:
        logger.error(f"Folder watch renewal failed: {e}")


def run_scheduler():
    """Run the scheduler in a background thread."""
    config = get_config()

    # ==========================================================================
    # Sheets Processing (Original)
    # ==========================================================================

    # Renew sheet watches every hour (they expire after 24h)
    schedule.every(1).hour.do(renew_watches_job)

    # Backup sync every 6 hours (in case webhooks missed)
    schedule.every(6).hours.do(scheduled_sync_job)

    # ==========================================================================
    # POS File Processing (Automatic - No Manual Intervention)
    # ==========================================================================

    # Process pending files every 2 minutes (fast turnaround)
    schedule.every(2).minutes.do(process_pending_files_job)

    # Retry failed files every 15 minutes (give time for transient issues)
    schedule.every(15).minutes.do(retry_failed_files_job)

    # Scan all folders every 30 minutes (backup to webhooks)
    schedule.every(30).minutes.do(scan_for_new_files_job)

    # Renew folder watches every hour (they expire after 24h)
    schedule.every(1).hour.do(renew_folder_watches_job)

    logger.info("Scheduler started with jobs:")
    logger.info("  - Sheet watch renewal: every 1 hour")
    logger.info("  - Sheet backup sync: every 6 hours")
    logger.info("  - POS file processing: every 2 minutes")
    logger.info("  - Failed file retry: every 15 minutes")
    logger.info("  - Folder scan (backup): every 30 minutes")
    logger.info("  - Folder watch renewal: every 1 hour")

    while True:
        schedule.run_pending()
        time.sleep(30)  # Check every 30 seconds for faster response


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

    # Set up sheet watches
    logger.info("Setting up Google Drive watches for sheets...")
    try:
        client = get_sheets_client()
        watches = client.setup_all_watches()
        logger.info(f"Created/verified {len(watches)} sheet watches")
    except Exception as e:
        logger.error(f"Failed to set up sheet watches: {e}")
        logger.warning("Service will continue without real-time notifications")
        logger.warning("Using scheduled sync as fallback")

    # Set up folder watches for POS files
    logger.info("Setting up Google Drive watches for POS folders...")
    try:
        watcher = get_folder_watcher()
        folder_watches = watcher.setup_all_folder_watches()
        logger.info(f"Created/verified {len(folder_watches)} folder watches")
    except Exception as e:
        logger.error(f"Failed to set up folder watches: {e}")
        logger.warning("Using scheduled folder scan as fallback")

    # Initial sync for sheets
    logger.info("Performing initial sheet sync check...")
    try:
        processor = get_processor()
        processor.sync_all_sheets(trigger='startup', force=False)
    except Exception as e:
        logger.error(f"Initial sheet sync failed: {e}")

    # Initial scan for POS files
    logger.info("Performing initial POS folder scan...")
    try:
        watcher = get_folder_watcher()
        scan_result = watcher.scan_all_stores()
        logger.info(
            f"Initial scan: {scan_result['total_found']} files found, "
            f"{scan_result['total_queued']} queued"
        )

        # Process any pending files immediately
        file_processor = get_file_processor()
        pending_count = db.get_pending_count()
        if pending_count > 0:
            logger.info(f"Processing {pending_count} pending files on startup...")
            result = file_processor.process_pending_files(limit=100, parallel=True)
            logger.info(
                f"Startup processing: {result['processed']} processed, "
                f"{result['failed']} failed"
            )
    except Exception as e:
        logger.error(f"Initial POS scan failed: {e}")

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
