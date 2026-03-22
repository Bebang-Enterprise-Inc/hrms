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
from datetime import UTC, datetime
from datetime import time as dt_time
from zoneinfo import ZoneInfo

import schedule

from .ap_exception_reports import generate_ap_exception_report
from .config import get_config, get_sheet_config, get_watched_sheets
from .file_processor import get_file_processor
from .folder_watcher import get_folder_watcher
from .models import get_db
from .processor import get_processor
from .sheets_client import get_sheets_client
from .webhook import run_server

# Configure logging
logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
	handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

PHT_TIMEZONE = ZoneInfo("Asia/Manila")
DAILY_BASELINE_TRIGGER = "daily_baseline"
INTERVAL_BASELINE_TRIGGER = "interval_baseline"
DAILY_BASELINE_PHT_TIME = dt_time(hour=7, minute=0)
BASELINE_LOOP_SLEEP_SECONDS = 30
DAILY_BASELINE_SHEET_KEYS = (
	"inventory",
	"ap_opening_balance",
	"supplier_soa",
	"procurement_suppliers",
	"procurement_requisitions",
	"procurement_purchase_orders",
	"procurement_goods_receipts",
)
_baseline_sync_lock = threading.Lock()


def setup_file_logging():
	"""Set up file logging."""
	config = get_config()

	# Ensure log directory exists
	from pathlib import Path

	Path(config.log_file).parent.mkdir(parents=True, exist_ok=True)

	file_handler = logging.FileHandler(config.log_file)
	file_handler.setLevel(getattr(logging, config.log_level))
	file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

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
		processor.sync_all_sheets(trigger="scheduled", force=False)
	except Exception as e:
		logger.error(f"Scheduled sync failed: {e}")


def _normalize_now_utc(now_utc: datetime | None = None) -> datetime:
	"""Normalize a timestamp to timezone-aware UTC."""
	if now_utc is None:
		return datetime.now(UTC)
	if now_utc.tzinfo is None:
		return now_utc.replace(tzinfo=UTC)
	return now_utc.astimezone(UTC)


def get_daily_baseline_sheet_keys() -> tuple[str, ...]:
	"""Return the sheet keys that must be force-synced at 7:00 AM PHT."""
	return DAILY_BASELINE_SHEET_KEYS


def _maybe_generate_ap_exception_report(trigger: str) -> dict | None:
	"""Generate the current AP exception workbook when enabled."""
	config = get_config()
	if not config.generate_ap_exception_reports:
		return None

	try:
		report = generate_ap_exception_report(output_dir=config.ap_exception_report_dir)
		logger.info(
			"AP exception report generated after %s sync: %s",
			trigger,
			report["latest_files"].get("xlsx"),
		)
		return report
	except Exception as e:
		logger.error(f"AP exception report generation failed after {trigger}: {e}")
		return None


def _run_baseline_sync(
	*,
	trigger: str,
	force: bool,
	now_utc: datetime | None = None,
	enforce_daily_gate: bool,
) -> list:
	"""Run the AP + Procurement baseline sync set with optional daily gate enforcement."""
	normalized_now_utc = _normalize_now_utc(now_utc)
	now_pht = normalized_now_utc.astimezone(PHT_TIMEZONE)

	if enforce_daily_gate and now_pht.time() < DAILY_BASELINE_PHT_TIME:
		return []

	config = get_config()
	db = get_db()
	processor = get_processor()
	results = []

	pht_day_start = datetime.combine(now_pht.date(), dt_time.min, tzinfo=PHT_TIMEZONE)
	pht_day_start_utc = pht_day_start.astimezone(UTC)

	for sheet_key in get_daily_baseline_sheet_keys():
		sheet_config = get_sheet_config(sheet_key)
		if not sheet_config or not sheet_config.enabled:
			logger.warning(f"Daily baseline sync skipped missing/disabled sheet config: {sheet_key}")
			continue

		if enforce_daily_gate:
			already_synced = db.has_successful_sync_since(
				sheet_config.spreadsheet_id,
				sheet_config.sheet_name,
				DAILY_BASELINE_TRIGGER,
				pht_day_start_utc,
			)
			if already_synced:
				continue

		logger.info(
			"Running %s force sync for %s (%s)",
			trigger,
			getattr(sheet_config, "name", sheet_key),
			sheet_key,
		)
		results.append(
			processor.sync_sheet(
				sheet_config,
				trigger=trigger,
				force=force,
			)
		)

	if results and config.generate_ap_exception_reports:
		_maybe_generate_ap_exception_report(trigger)

	return results


def _run_baseline_sync_guarded(
	*,
	trigger: str,
	force: bool,
	now_utc: datetime | None = None,
	enforce_daily_gate: bool,
) -> list:
	"""Prevent overlapping baseline runs across the daily and interval lanes."""
	if not _baseline_sync_lock.acquire(blocking=False):
		logger.info("Skipping %s baseline sync because another baseline run is already in progress", trigger)
		return []

	try:
		return _run_baseline_sync(
			trigger=trigger,
			force=force,
			now_utc=now_utc,
			enforce_daily_gate=enforce_daily_gate,
		)
	finally:
		_baseline_sync_lock.release()


def run_daily_baseline_sync_if_due(now_utc: datetime | None = None):
	"""
	Force-sync Inventory, AP, and Procurement baseline sheets once per PHT day after 7:00 AM.

	This does not rely on the host/container timezone. It checks whether each target
	sheet already has a successful `daily_baseline` sync logged for the current PHT
	day and only re-syncs missing sheets.
	"""
	return _run_baseline_sync_guarded(
		trigger=DAILY_BASELINE_TRIGGER,
		force=True,
		now_utc=now_utc,
		enforce_daily_gate=True,
	)


def run_interval_baseline_sync_job():
	"""Optional short-interval force sync for migration shadow-run testing."""
	config = get_config()
	if config.baseline_test_interval_minutes <= 0:
		return []
	return _run_baseline_sync_guarded(
		trigger=INTERVAL_BASELINE_TRIGGER,
		force=True,
		enforce_daily_gate=False,
	)


def run_daily_baseline_loop(
	*,
	stop_event: threading.Event | None = None,
	sleep_seconds: int = BASELINE_LOOP_SLEEP_SECONDS,
):
	"""Run the 8AM PHT baseline gate in a dedicated loop so long jobs cannot starve it."""
	stop_event = stop_event or threading.Event()
	logger.info(
		"Daily AP/procurement baseline loop started: every %s seconds, target 7 AM PHT",
		sleep_seconds,
	)

	while not stop_event.is_set():
		try:
			run_daily_baseline_sync_if_due()
		except Exception as e:
			logger.error(f"Daily baseline sync check failed: {e}")

		if stop_event.wait(max(1, sleep_seconds)):
			break


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

		if result["processed"] > 0 or result["failed"] > 0:
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
			db.reset_for_retry(entry["file_id"])
			retry_count += 1

		if retry_count > 0:
			logger.info(f"Reset {retry_count} files for retry")

			# Immediately process the reset files
			processor = get_file_processor()
			result = processor.process_pending_files(limit=retry_count, parallel=True)
			logger.info(f"Retry results: {result['processed']} succeeded, {result['failed']} still failing")

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

		if result["total_queued"] > 0:
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


def daily_summary_job():
	"""
	Scheduled job to send daily summary report via Google Chat.

	Runs at 7 AM Philippines time (23:00 UTC previous day).
	Reports on the previous day's file processing.
	"""
	try:
		from . import notifications

		db = get_db()

		logger.info("Sending daily POS file summary report...")
		result = notifications.send_daily_summary(db)

		if result:
			logger.info(f"Daily summary sent: {result}")
		else:
			logger.warning("Failed to send daily summary")

	except Exception as e:
		logger.error(f"Daily summary job failed: {e}")


def configure_scheduled_jobs(schedule_module=schedule):
	"""Register all recurring jobs on the provided schedule module."""
	config = get_config()
	# ==========================================================================
	# Sheets Processing (Original)
	# ==========================================================================

	# Google Sheets/Drive watches — DISABLED 2026-03-14
	# Watches consumed ~2,400 API calls/day and caused rate-limit outages on restart.
	# The daily 8 AM baseline cron + 6-hour backup sync handle all operational needs.
	# schedule_module.every(1).hour.do(renew_watches_job)

	# Backup sync every 6 hours (catches any changes between daily baselines)
	schedule_module.every(6).hours.do(scheduled_sync_job)

	if config.baseline_test_interval_minutes > 0:
		schedule_module.every(config.baseline_test_interval_minutes).minutes.do(
			run_interval_baseline_sync_job
		)

	# ==========================================================================
	# POS File Processing (Automatic - No Manual Intervention)
	# ==========================================================================

	# Process pending files every 2 minutes (fast turnaround)
	schedule_module.every(2).minutes.do(process_pending_files_job)

	# Retry failed files every 15 minutes (give time for transient issues)
	schedule_module.every(15).minutes.do(retry_failed_files_job)

	# Scan all folders every 30 minutes (backup to webhooks)
	schedule_module.every(30).minutes.do(scan_for_new_files_job)

	# Folder watches — DISABLED 2026-03-14 (same reason as sheet watches)
	# POS folders are scanned every 30 minutes via scan_for_new_files_job above.
	# schedule_module.every(1).hour.do(renew_folder_watches_job)

	# ==========================================================================
	# Notifications & Reporting
	# ==========================================================================

	# POS file upload daily summary — DISABLED 2026-03-14
	# POS data now flows via Mosaic API (daily-pos-sync.yml GitHub Action),
	# the manual XLSX upload pipeline and its daily report are retired.
	# schedule_module.every().day.at("23:00").do(daily_summary_job)


def run_scheduler():
	"""Run the scheduler in a background thread."""
	configure_scheduled_jobs()
	config = get_config()

	logger.info("Scheduler started with jobs:")
	logger.info("  - Sheet backup sync: every 6 hours (watches disabled)")
	logger.info("  - Daily AP/procurement baseline sync: dedicated loop, target 7 AM PHT")
	if config.baseline_test_interval_minutes > 0:
		logger.info(
			"  - Interval AP/procurement baseline sync: every %s minutes (test mode)",
			config.baseline_test_interval_minutes,
		)
	logger.info("  - POS file processing: every 2 minutes")
	logger.info("  - Failed file retry: every 15 minutes")
	logger.info("  - Folder scan (backup): every 30 minutes")
	logger.info("  - Folder scan (no watches): every 30 minutes")

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
	for _key, sheet in sheets.items():
		logger.info(f"  - {sheet.name} ({sheet.spreadsheet_id})")

	# Google Drive watches — DISABLED 2026-03-14
	# Watch setup on startup triggered 55 API calls in seconds, causing rate-limit
	# outages that blocked ALL Google API operations (including data reads).
	# Data sync relies on 8 AM daily baseline + 6-hour backup cron.
	# POS folders are scanned every 30 minutes via scheduled job.
	logger.info("Google Drive watches DISABLED — using scheduled sync only")

	# Initial sync for sheets
	logger.info("Performing initial sheet sync check...")
	try:
		processor = get_processor()
		processor.sync_all_sheets(trigger="startup", force=False)
	except Exception as e:
		logger.error(f"Initial sheet sync failed: {e}")

	logger.info("Checking whether daily AP/procurement baseline sync is due...")
	try:
		run_daily_baseline_sync_if_due()
	except Exception as e:
		logger.error(f"Daily baseline sync check failed: {e}")

	# Initial scan for POS files
	logger.info("Performing initial POS folder scan...")
	try:
		watcher = get_folder_watcher()
		scan_result = watcher.scan_all_stores()
		logger.info(
			f"Initial scan: {scan_result['total_found']} files found, {scan_result['total_queued']} queued"
		)

		# Process any pending files immediately
		file_processor = get_file_processor()
		pending_count = db.get_pending_count()
		if pending_count > 0:
			logger.info(f"Processing {pending_count} pending files on startup...")
			result = file_processor.process_pending_files(limit=100, parallel=True)
			logger.info(f"Startup processing: {result['processed']} processed, {result['failed']} failed")
	except Exception as e:
		logger.error(f"Initial POS scan failed: {e}")

	logger.info("Initial setup complete")
	logger.info("=" * 60)


def run_initial_setup_background():
	"""Run expensive startup setup without blocking the webhook server."""
	try:
		initial_setup()
	except Exception:
		logger.exception("Background initial setup failed")


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

	# Keep startup health checks responsive by running the heavy Google setup,
	# initial syncs, and POS scans in the background.
	initial_setup_thread = threading.Thread(target=run_initial_setup_background, daemon=True)
	initial_setup_thread.start()

	# Keep the 8AM baseline independent from the shared schedule loop so it cannot
	# be delayed by long-running watch-renewal or file-processing work.
	baseline_thread = threading.Thread(target=run_daily_baseline_loop, daemon=True)
	baseline_thread.start()

	# Start scheduler in background thread
	scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
	scheduler_thread.start()

	# Run webhook server (this blocks)
	logger.info("Starting webhook server...")
	run_server()


if __name__ == "__main__":
	main()
