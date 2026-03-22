"""
FastAPI webhook server for Sheets Receiver.

Handles incoming push notifications from Google Drive.
"""

import logging
from datetime import UTC, date, datetime
from datetime import time as dt_time
from typing import Any, Optional
from zoneinfo import ZoneInfo

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .config import get_config
from .processor import get_processor

logger = logging.getLogger(__name__)

PHT_TIMEZONE = ZoneInfo("Asia/Manila")
BASELINE_TARGET_PHT_TIME = dt_time(hour=7, minute=0)
MORNING_READY_DEADLINE_PHT_TIME = dt_time(hour=9, minute=0)
MORNING_HEALTH_SHEET_KEYS = (
	"inventory",
	"ap_opening_balance",
	"procurement_suppliers",
	"procurement_requisitions",
	"procurement_purchase_orders",
	"procurement_goods_receipts",
)


def _normalize_report_date(report_date: str | None) -> date:
	"""Normalize the requested report date in PHT."""
	if report_date:
		return date.fromisoformat(report_date)
	return datetime.now(PHT_TIMEZONE).date()


def _serialize_sync_log(sync_log: Any | None) -> dict[str, Any] | None:
	"""Serialize a sync log dataclass for API responses."""
	if not sync_log:
		return None

	created_at_utc = sync_log.created_at.replace(tzinfo=UTC)
	return {
		"id": sync_log.id,
		"trigger": sync_log.trigger,
		"status": sync_log.status,
		"rows_processed": sync_log.rows_processed,
		"rows_created": sync_log.rows_created,
		"rows_updated": sync_log.rows_updated,
		"rows_failed": sync_log.rows_failed,
		"error_message": sync_log.error_message,
		"duration_seconds": sync_log.duration_seconds,
		"created_at_utc": created_at_utc.isoformat(),
		"created_at_pht": created_at_utc.astimezone(PHT_TIMEZONE).isoformat(),
	}


def _build_lane_health(sheet_key: str, report_date_value: date) -> dict[str, Any]:
	"""Summarize one receiver lane for the morning health report."""
	from .config import get_sheet_config
	from .models import get_db

	sheet_config = get_sheet_config(sheet_key)
	if not sheet_config:
		return {
			"sheet_key": sheet_key,
			"status": "missing",
			"ready_before_deadline": False,
			"clean_success": False,
		}

	if not getattr(sheet_config, "enabled", True):
		return {
			"sheet_key": sheet_key,
			"name": sheet_config.name,
			"status": "disabled",
			"ready_before_deadline": False,
			"clean_success": False,
		}

	pht_day_start = datetime.combine(report_date_value, dt_time.min, tzinfo=PHT_TIMEZONE)
	pht_deadline = datetime.combine(report_date_value, MORNING_READY_DEADLINE_PHT_TIME, tzinfo=PHT_TIMEZONE)
	day_start_utc = pht_day_start.astimezone(UTC)
	deadline_utc = pht_deadline.astimezone(UTC)

	db = get_db()
	latest_today = db.get_latest_sync_since(
		sheet_config.spreadsheet_id,
		sheet_config.sheet_name,
		day_start_utc,
		trigger="daily_baseline",
	)
	latest_success_today = db.get_latest_sync_since(
		sheet_config.spreadsheet_id,
		sheet_config.sheet_name,
		day_start_utc,
		trigger="daily_baseline",
		status="success",
	)

	ready_before_deadline = bool(
		latest_success_today and latest_success_today.created_at.replace(tzinfo=UTC) <= deadline_utc
	)
	clean_success = bool(latest_success_today and latest_success_today.rows_failed == 0)

	if latest_today is None:
		status = "pending"
	elif latest_today.status == "success":
		status = "completed_with_exceptions" if latest_today.rows_failed else "completed"
	elif latest_success_today is not None:
		status = f"{latest_today.status}_after_success"
	else:
		status = latest_today.status or "unknown"

	return {
		"sheet_key": sheet_key,
		"name": sheet_config.name,
		"sheet_name": sheet_config.sheet_name,
		"owner_email": sheet_config.owner_email,
		"status": status,
		"ready_before_deadline": ready_before_deadline,
		"clean_success": clean_success,
		"latest_today": _serialize_sync_log(latest_today),
		"latest_success_today": _serialize_sync_log(latest_success_today),
		"completed_at_pht": (
			latest_success_today.created_at.replace(tzinfo=UTC).astimezone(PHT_TIMEZONE).isoformat()
			if latest_success_today
			else None
		),
	}


def build_morning_health_report(report_date: str | None = None) -> dict[str, Any]:
	"""Build the receiver-side morning health report for Ian inventory + AP/procurement."""
	report_date_value = _normalize_report_date(report_date)
	lane_rows = [_build_lane_health(sheet_key, report_date_value) for sheet_key in MORNING_HEALTH_SHEET_KEYS]
	active_lanes = [lane for lane in lane_rows if lane.get("status") not in {"disabled", "missing"}]
	all_ready = bool(active_lanes) and all(lane.get("ready_before_deadline") for lane in active_lanes)
	all_clean = all(lane.get("clean_success") for lane in active_lanes) if active_lanes else False

	if all_ready and all_clean:
		status = "green"
	elif all_ready:
		status = "yellow"
	else:
		status = "red"

	return {
		"service": "sheets-receiver",
		"report_date": report_date_value.isoformat(),
		"generated_at_utc": datetime.now(UTC).isoformat(),
		"generated_at_pht": datetime.now(PHT_TIMEZONE).isoformat(),
		"baseline_target_pht_time": BASELINE_TARGET_PHT_TIME.strftime("%H:%M"),
		"ready_deadline_pht_time": MORNING_READY_DEADLINE_PHT_TIME.strftime("%H:%M"),
		"status": status,
		"ready_before_deadline": all_ready,
		"lanes": lane_rows,
	}


app = FastAPI(title="Sheets Receiver", description="Google Sheets sync service for BEI ERP", version="1.0.0")


@app.get("/health")
async def health_check():
	"""Health check endpoint."""
	return {"status": "healthy", "service": "sheets-receiver"}


@app.post("/webhook/sheets")
async def handle_webhook(
	request: Request,
	background_tasks: BackgroundTasks,
	x_goog_channel_id: str | None = Header(None, alias="X-Goog-Channel-ID"),
	x_goog_resource_id: str | None = Header(None, alias="X-Goog-Resource-ID"),
	x_goog_resource_state: str | None = Header(None, alias="X-Goog-Resource-State"),
	x_goog_changed: str | None = Header(None, alias="X-Goog-Changed"),
	x_goog_message_number: str | None = Header(None, alias="X-Goog-Message-Number"),
):
	"""
	Handle Google Drive push notification.

	Google sends these headers:
	- X-Goog-Channel-ID: The channel ID we specified
	- X-Goog-Resource-ID: Unique ID for the watched resource
	- X-Goog-Resource-State: 'sync', 'change', 'remove', etc.
	- X-Goog-Changed: What changed (e.g., 'content', 'properties')
	- X-Goog-Message-Number: Sequential message number

	We need to respond quickly (within 10 seconds) or Google will retry.
	So we process in background.
	"""
	logger.info(
		f"Webhook received: state={x_goog_resource_state}, "
		f"channel={x_goog_channel_id}, resource={x_goog_resource_id}"
	)

	# Acknowledge quickly - Google requires fast response
	if x_goog_resource_state == "sync":
		# Initial sync notification - just acknowledge
		return {"status": "acknowledged"}

	# Get file ID from resource ID (it's the spreadsheet ID)
	# Note: We need to look up which spreadsheet this resource_id belongs to
	# Since we store the mapping in our database
	from .models import get_db

	db = get_db()

	# Find the spreadsheet by channel or resource.
	# We currently look up the watched spreadsheet by the registered channel ID.
	if x_goog_channel_id:
		with db._connection() as conn:
			row = conn.execute(
				"SELECT spreadsheet_id FROM watch_channels WHERE channel_id = ?", (x_goog_channel_id,)
			).fetchone()
			if row:
				spreadsheet_id = row["spreadsheet_id"]
			else:
				logger.warning(f"Unknown channel: {x_goog_channel_id}")
				return {"status": "unknown_channel"}
	else:
		logger.warning("No channel ID in webhook")
		return {"status": "missing_channel_id"}

	# Process in background
	background_tasks.add_task(
		process_change_background,
		spreadsheet_id=spreadsheet_id,
		resource_state=x_goog_resource_state,
		channel_id=x_goog_channel_id,
	)

	return {"status": "processing"}


async def process_change_background(spreadsheet_id: str, resource_state: str, channel_id: str):
	"""Background task to process the change."""
	try:
		processor = get_processor()
		processor.process_webhook(
			spreadsheet_id=spreadsheet_id, resource_state=resource_state, channel_id=channel_id
		)
	except Exception as e:
		logger.error(f"Error processing webhook: {e}")


@app.post("/api/sync/{sheet_key}")
async def trigger_sync(sheet_key: str, background_tasks: BackgroundTasks, force: bool = False):
	"""
	Manually trigger sync for a specific sheet.

	Args:
	    sheet_key: Key from WATCHED_SHEETS config (e.g., 'ar_aging')
	    force: If True, sync even if no changes detected
	"""
	from .config import get_watched_sheets

	sheets = get_watched_sheets()
	if sheet_key not in sheets:
		raise HTTPException(status_code=404, detail=f"Unknown sheet: {sheet_key}")

	sheet_config = sheets[sheet_key]

	background_tasks.add_task(sync_sheet_background, sheet_config=sheet_config, force=force)

	return {"status": "sync_queued", "sheet": sheet_config.name}


async def sync_sheet_background(sheet_config, force: bool):
	"""Background task to sync a sheet."""
	try:
		processor = get_processor()
		processor.sync_sheet(sheet_config, trigger="manual", force=force)
	except Exception as e:
		logger.error(f"Error syncing {sheet_config.name}: {e}")


@app.post("/api/sync-all")
async def trigger_sync_all(background_tasks: BackgroundTasks, force: bool = False):
	"""Trigger sync for all configured sheets."""
	background_tasks.add_task(sync_all_background, force=force)
	return {"status": "sync_all_queued"}


async def sync_all_background(force: bool):
	"""Background task to sync all sheets."""
	try:
		processor = get_processor()
		processor.sync_all_sheets(trigger="manual", force=force)
	except Exception as e:
		logger.error(f"Error in sync_all: {e}")


@app.get("/api/status")
async def get_status():
	"""Get service status and recent sync history."""
	from .config import get_watched_sheets
	from .models import get_db

	db = get_db()
	recent_syncs = db.get_recent_syncs(limit=20)

	# Get watch status
	watches = []
	for _, sheet in get_watched_sheets().items():
		watch = db.get_watch(sheet.spreadsheet_id)
		watches.append(
			{
				"name": sheet.name,
				"spreadsheet_id": sheet.spreadsheet_id,
				"has_watch": watch is not None,
				"watch_expires": watch.expiration.isoformat() if watch else None,
				"hours_until_expiry": watch.hours_until_expiry if watch else None,
			}
		)

	# Get change tracking summary
	processor = get_processor()
	change_summary = processor.get_change_summary(days=7)
	unacked_alerts = processor.get_unacknowledged_alerts()

	return {
		"service": "sheets-receiver",
		"version": "1.0.0",
		"watches": watches,
		"change_tracking": {
			"summary_7_days": change_summary,
			"unacknowledged_alerts": len(unacked_alerts),
			"alerts": [
				{
					"id": a["id"],
					"type": a["alert_type"],
					"message": a["alert_message"][:100] + "..."
					if len(a["alert_message"]) > 100
					else a["alert_message"],
				}
				for a in unacked_alerts[:5]  # Show first 5
			],
		},
		"recent_syncs": [
			{
				"spreadsheet_name": s.spreadsheet_name,
				"status": s.status,
				"trigger": s.trigger,
				"rows_processed": s.rows_processed,
				"created_at": s.created_at.isoformat(),
			}
			for s in recent_syncs
		],
	}


@app.get("/api/morning-health")
async def get_morning_health(report_date: str | None = None):
	"""Get same-day baseline readiness for Ian inventory and AP/procurement."""
	try:
		return build_morning_health_report(report_date=report_date)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/watches/setup")
async def setup_watches():
	"""Set up watches for all configured sheets."""
	from .sheets_client import get_sheets_client

	client = get_sheets_client()
	watches = client.setup_all_watches()

	return {
		"status": "success",
		"watches_created": len(watches),
		"watches": [
			{"name": w.spreadsheet_name, "channel_id": w.channel_id, "expires": w.expiration.isoformat()}
			for w in watches
		],
	}


@app.post("/api/watches/renew")
async def renew_watches():
	"""Renew expiring watches."""
	from .sheets_client import get_sheets_client

	client = get_sheets_client()
	renewed = client.renew_expiring_watches()

	return {"status": "success", "watches_renewed": len(renewed)}


# ========================================
# CHANGE TRACKING ENDPOINTS
# ========================================


@app.get("/api/changes")
async def get_changes(spreadsheet_id: str | None = None, change_type: str | None = None, limit: int = 100):
	"""
	Get recent row-level changes.

	Query params:
	    spreadsheet_id: Filter by spreadsheet (optional)
	    change_type: Filter by type - added, modified, deleted (optional)
	    limit: Max records (default 100)

	Returns:
	    List of changes with before/after values
	"""
	processor = get_processor()
	changes = processor.get_recent_changes(
		spreadsheet_id=spreadsheet_id, limit=limit, change_type=change_type
	)

	return {"total": len(changes), "changes": changes}


@app.get("/api/changes/summary")
async def get_change_summary(spreadsheet_id: str | None = None, days: int = 7):
	"""
	Get summary of changes over time.

	Query params:
	    spreadsheet_id: Filter by spreadsheet (optional)
	    days: How many days to look back (default 7)

	Returns:
	    Summary with counts by type
	"""
	processor = get_processor()
	return processor.get_change_summary(spreadsheet_id=spreadsheet_id, days=days)


@app.get("/api/changes/modified")
async def get_modified_rows(limit: int = 50):
	"""
	Get recently modified rows (edits to existing data).

	This is the key endpoint for detecting when team members
	edit existing records instead of adding new ones.
	"""
	processor = get_processor()
	changes = processor.get_recent_changes(change_type="modified", limit=limit)

	return {
		"total": len(changes),
		"message": "These rows had existing data modified (not new entries)",
		"changes": changes,
	}


@app.get("/api/alerts")
async def get_alerts():
	"""
	Get unacknowledged alerts.

	Alerts are generated for suspicious patterns:
	- Mass edits (many rows modified at once)
	- Deletions
	- Financial field changes
	- More modifications than additions
	"""
	processor = get_processor()
	alerts = processor.get_unacknowledged_alerts()

	return {"total": len(alerts), "alerts": alerts}


@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int):
	"""Mark an alert as acknowledged."""
	processor = get_processor()
	success = processor.acknowledge_alert(alert_id)

	if success:
		return {"status": "acknowledged", "alert_id": alert_id}
	else:
		raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")


# ========================================
# FOLDER WATCHING ENDPOINTS (POS Files)
# ========================================


@app.post("/webhook/folder")
async def handle_folder_webhook(
	request: Request,
	background_tasks: BackgroundTasks,
	x_goog_channel_id: str | None = Header(None, alias="X-Goog-Channel-ID"),
	x_goog_resource_id: str | None = Header(None, alias="X-Goog-Resource-ID"),
	x_goog_resource_state: str | None = Header(None, alias="X-Goog-Resource-State"),
	x_goog_changed: str | None = Header(None, alias="X-Goog-Changed"),
):
	"""
	Handle Google Drive folder push notification.

	When files are added/modified in a watched folder, Google sends a notification.
	We respond quickly and process in background.
	"""
	logger.info(
		f"Folder webhook received: state={x_goog_resource_state}, "
		f"channel={x_goog_channel_id}, changed={x_goog_changed}"
	)

	if x_goog_resource_state == "sync":
		return {"status": "sync_acknowledged"}

	if not x_goog_channel_id:
		logger.warning("No channel ID in folder webhook")
		return {"status": "missing_channel_id"}

	# Look up folder watch
	from .models import get_db

	db = get_db()
	watch = db.get_folder_watch_by_channel(x_goog_channel_id)

	if not watch:
		logger.warning(f"Unknown folder channel: {x_goog_channel_id}")
		return {"status": "unknown_channel"}

	# Process in background
	background_tasks.add_task(
		process_folder_change_background,
		folder_id=watch["folder_id"],
		folder_name=watch["folder_name"],
		store_code=watch.get("store_code"),
		resource_state=x_goog_resource_state,
	)

	return {"status": "processing", "folder": watch["folder_name"]}


async def process_folder_change_background(
	folder_id: str, folder_name: str, store_code: str, resource_state: str
):
	"""Background task to check for new files in folder."""
	try:
		from .folder_watcher import get_folder_watcher
		from .models import get_db

		watcher = get_folder_watcher()
		db = get_db()

		# Get files modified in last hour (Google doesn't tell us which file changed)
		from datetime import datetime, timedelta

		since = datetime.utcnow() - timedelta(hours=1)

		new_files = watcher.list_new_files(folder_id, since=since)

		queued_count = 0
		for file_info in new_files:
			if not db.is_file_processed(file_info["id"]):
				file_info["folder_id"] = folder_id
				db.queue_file(file_info, store_code=store_code)
				queued_count += 1
				logger.info(f"Queued new file: {file_info['name']} from {folder_name}")

		logger.info(f"Folder change processed: {folder_name}, {queued_count} files queued")

	except Exception as e:
		logger.error(f"Error processing folder change for {folder_name}: {e}")


@app.post("/api/folders/seed")
async def seed_existing_files():
	"""
	Mark all existing files in watched folders as 'already processed'.

	CRITICAL: Run this BEFORE setting up watches to prevent reprocessing
	files that were already extracted (e.g., January 2026 data).

	Files are marked with report_type='seeded' and record_count=0 to
	distinguish them from actually processed files.
	"""
	from datetime import datetime

	from .config import get_watched_folders
	from .folder_watcher import get_folder_watcher
	from .models import get_db

	watcher = get_folder_watcher()
	db = get_db()
	folders = get_watched_folders()

	total_seeded = 0
	folder_counts = {}

	for store_code, folder_config in folders.items():
		try:
			# Get ALL files in folder (no time filter)
			files = watcher.list_new_files(folder_config.folder_id, since=None)

			seeded = 0
			for file_info in files:
				if not db.is_file_processed(file_info["id"]):
					# Mark as processed WITHOUT extracting data
					db.mark_file_processed(
						file_id=file_info["id"],
						file_name=file_info["name"],
						folder_id=folder_config.folder_id,
						store_code=store_code,
						md5_checksum=file_info.get("md5Checksum", ""),
						record_count=0,  # 0 = seeded, not extracted
						report_type="seeded",
						extracted_data={
							"seeded_at": datetime.utcnow().isoformat(),
							"reason": "pre-existing file, already processed in Jan 2026 extraction",
						},
					)
					seeded += 1

			folder_counts[folder_config.name] = seeded
			total_seeded += seeded
			logger.info(f"Seeded {seeded} existing files in {folder_config.name}")

		except Exception as e:
			logger.error(f"Error seeding {folder_config.name}: {e}")
			folder_counts[folder_config.name] = f"ERROR: {e!s}"

	return {
		"status": "success",
		"message": "Existing files marked as processed - will NOT be re-extracted",
		"total_seeded": total_seeded,
		"by_folder": folder_counts,
	}


@app.post("/api/folders/setup")
async def setup_folder_watches(seed_existing: bool = True):
	"""
	Set up watches for all POS store folders.

	Args:
	    seed_existing: If True (default), mark all existing files as processed
	                  BEFORE creating watches. This prevents reprocessing
	                  files from January 2026 that were already extracted.

	Process:
	    1. Seed existing files (if enabled) - marks ~6000 files as 'seeded'
	    2. Create folder watches for all 43 stores
	    3. Only NEW uploads after this point will be processed
	"""
	from .folder_watcher import get_folder_watcher

	result = {"status": "success", "seeding": None, "watches_created": 0, "watches": []}

	# Step 1: Seed existing files first (CRITICAL - prevents reprocessing)
	if seed_existing:
		logger.info("Seeding existing files before creating watches...")
		seed_result = await seed_existing_files()
		result["seeding"] = {
			"total_seeded": seed_result["total_seeded"],
			"message": "Existing files marked as processed - only NEW uploads will be extracted",
		}

	# Step 2: Create folder watches
	watcher = get_folder_watcher()
	watches = watcher.setup_all_folder_watches()

	result["watches_created"] = len(watches)
	result["watches"] = [
		{
			"folder_name": w.get("folder_name"),
			"store_code": w.get("store_code"),
			"channel_id": w.get("channel_id"),
			"expires": w.get("expiration").isoformat()
			if hasattr(w.get("expiration"), "isoformat")
			else w.get("expiration"),
		}
		for w in watches
	]

	return result


@app.post("/api/folders/renew")
async def renew_folder_watches():
	"""Renew expiring folder watches."""
	from .folder_watcher import get_folder_watcher

	watcher = get_folder_watcher()
	renewed = watcher.renew_expiring_folder_watches()

	return {"status": "success", "watches_renewed": len(renewed)}


@app.get("/api/folders/status")
async def get_folder_status():
	"""Get status of all folder watches."""
	from .models import get_db

	db = get_db()
	watches = db.get_all_folder_watches()
	queue_summary = db.get_file_queue_summary()

	from datetime import datetime

	now = datetime.utcnow()

	return {
		"service": "folder-watcher",
		"total_folders": len(watches),
		"watches": [
			{
				"folder_name": w["folder_name"],
				"store_code": w["store_code"],
				"hours_until_expiry": (w["expiration"] - now).total_seconds() / 3600,
			}
			for w in watches
		],
		"file_queue": queue_summary,
	}


@app.get("/api/files/queue")
async def get_file_queue(status: str | None = None, limit: int = 50):
	"""Get files in processing queue."""
	from .models import get_db

	db = get_db()

	if status == "pending":
		files = db.get_pending_files(limit=limit)
	else:
		# Get all files from queue
		with db._connection() as conn:
			if status:
				rows = conn.execute(
					"SELECT * FROM file_queue WHERE status = ? ORDER BY detected_at DESC LIMIT ?",
					(status, limit),
				).fetchall()
			else:
				rows = conn.execute(
					"SELECT * FROM file_queue ORDER BY detected_at DESC LIMIT ?", (limit,)
				).fetchall()
			files = [dict(row) for row in rows]

	return {"total": len(files), "files": files}


@app.get("/api/files/processed")
async def get_processed_files(store_code: str | None = None, limit: int = 100):
	"""Get list of processed files."""
	from .models import get_db

	db = get_db()
	files = db.get_processed_files(store_code=store_code, limit=limit)

	return {"total": len(files), "files": files}


@app.post("/api/files/{file_id}/reprocess")
async def reprocess_file(file_id: str, background_tasks: BackgroundTasks):
	"""Reprocess a failed file."""
	from .models import get_db

	db = get_db()

	# Update status back to pending
	db.update_file_status(file_id, "pending")

	return {"status": "requeued", "file_id": file_id}


@app.post("/api/folders/scan")
async def scan_folder(folder_id: str, background_tasks: BackgroundTasks):
	"""
	Manually scan a folder for new files.

	Useful for initial setup or if webhooks missed something.
	"""
	from .config import get_folder_by_id
	from .folder_watcher import get_folder_watcher
	from .models import get_db

	watcher = get_folder_watcher()
	db = get_db()

	folder_config = get_folder_by_id(folder_id)
	store_code = folder_config.store_code if folder_config else None

	# Get all files in folder
	files = watcher.list_new_files(folder_id, since=None)

	queued = 0
	skipped = 0
	for file_info in files:
		if db.is_file_processed(file_info["id"]):
			skipped += 1
		else:
			file_info["folder_id"] = folder_id
			db.queue_file(file_info, store_code=store_code)
			queued += 1

	return {"status": "scanned", "folder_id": folder_id, "files_queued": queued, "files_skipped": skipped}


@app.post("/api/folders/scan-all")
async def scan_all_folders(background_tasks: BackgroundTasks):
	"""
	Scan ALL store folders (including date subfolders) for new files.

	This recursively scans each store folder and its date subfolders
	(e.g., Store/2026-01-31/files) to find all unprocessed files.

	Use this to catch up on missed files or after initial setup.
	"""
	from .folder_watcher import get_folder_watcher

	watcher = get_folder_watcher()
	result = watcher.scan_all_stores()

	return {
		"status": "scanned",
		"total_found": result["total_found"],
		"total_queued": result["total_queued"],
		"stores_with_files": result["stores_with_files"],
		"stores": result["stores"],
	}


@app.post("/api/files/process")
async def process_pending_files(
	background_tasks: BackgroundTasks, limit: int = 50, parallel: bool = True, workers: int = 10
):
	"""
	Process pending files from the queue with parallel processing.

	Downloads files from Google Drive, extracts POS data, and updates
	the database. Uses parallel workers to overcome Google Drive API latency.

	Args:
	    limit: Maximum files to process (default 50)
	    parallel: Use parallel processing (default True)
	    workers: Number of parallel workers (default 10)

	Performance:
	    Sequential: ~1.3s/file (Google Drive latency bottleneck)
	    Parallel (10 workers): ~0.13s/file effective throughput
	"""
	from .file_processor import FileProcessor

	processor = FileProcessor(max_workers=workers)
	result = processor.process_pending_files(limit=limit, parallel=parallel)

	return result


@app.post("/api/files/process-all")
async def process_all_pending_files(
	background_tasks: BackgroundTasks, batch_size: int = 50, workers: int = 10
):
	"""
	Process ALL pending files in the queue with parallel processing.

	Uses parallel workers for high throughput processing of large queues.

	Args:
	    batch_size: Files per batch (default 50)
	    workers: Parallel workers per batch (default 10)

	Performance estimate:
	    - 6,300 files with 10 workers at 1.3s/file
	    - Effective: ~13 files/sec = ~8 minutes total
	    - vs Sequential: ~2.3 hours
	"""
	import time

	from .file_processor import FileProcessor
	from .models import get_db

	db = get_db()
	queue_summary = db.get_file_queue_summary()
	pending_count = queue_summary.get("pending", 0)

	if pending_count == 0:
		return {"status": "no_pending_files", "message": "No files in queue to process"}

	start_time = time.time()

	# Process synchronously for now to get accurate timing
	processor = FileProcessor(max_workers=workers)
	result = processor.process_all_pending(batch_size=batch_size)

	elapsed = time.time() - start_time
	files_per_sec = result["processed"] / elapsed if elapsed > 0 else 0

	return {
		"status": "completed",
		"processed": result["processed"],
		"failed": result["failed"],
		"total_records": result["total_records"],
		"batches": result["batches"],
		"elapsed_seconds": round(elapsed, 1),
		"files_per_second": round(files_per_sec, 2),
		"parallel_workers": workers,
	}


def run_server():
	"""Run the webhook server."""
	config = get_config()

	uvicorn.run(app, host=config.webhook_host, port=config.webhook_port, log_level=config.log_level.lower())


if __name__ == "__main__":
	run_server()
