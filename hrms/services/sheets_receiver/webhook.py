"""
FastAPI webhook server for Sheets Receiver.

Handles incoming push notifications from Google Drive.
"""

import logging
from typing import Optional

from fastapi import FastAPI, Request, Header, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from .config import get_config
from .processor import get_processor

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sheets Receiver",
    description="Google Sheets sync service for BEI ERP",
    version="1.0.0"
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "sheets-receiver"}


@app.post("/webhook/sheets")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_goog_channel_id: Optional[str] = Header(None, alias="X-Goog-Channel-ID"),
    x_goog_resource_id: Optional[str] = Header(None, alias="X-Goog-Resource-ID"),
    x_goog_resource_state: Optional[str] = Header(None, alias="X-Goog-Resource-State"),
    x_goog_changed: Optional[str] = Header(None, alias="X-Goog-Changed"),
    x_goog_message_number: Optional[str] = Header(None, alias="X-Goog-Message-Number"),
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
    if x_goog_resource_state == 'sync':
        # Initial sync notification - just acknowledge
        return {"status": "acknowledged"}

    # Get file ID from resource ID (it's the spreadsheet ID)
    # Note: We need to look up which spreadsheet this resource_id belongs to
    # Since we store the mapping in our database
    from .models import get_db
    db = get_db()

    # Find the spreadsheet by channel or resource
    # Try to find by looking up our watch channels
    watch = None
    if x_goog_channel_id:
        with db._connection() as conn:
            row = conn.execute(
                "SELECT spreadsheet_id FROM watch_channels WHERE channel_id = ?",
                (x_goog_channel_id,)
            ).fetchone()
            if row:
                spreadsheet_id = row['spreadsheet_id']
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
        channel_id=x_goog_channel_id
    )

    return {"status": "processing"}


async def process_change_background(
    spreadsheet_id: str,
    resource_state: str,
    channel_id: str
):
    """Background task to process the change."""
    try:
        processor = get_processor()
        processor.process_webhook(
            spreadsheet_id=spreadsheet_id,
            resource_state=resource_state,
            channel_id=channel_id
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")


@app.post("/api/sync/{sheet_key}")
async def trigger_sync(
    sheet_key: str,
    background_tasks: BackgroundTasks,
    force: bool = False
):
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

    background_tasks.add_task(
        sync_sheet_background,
        sheet_config=sheet_config,
        force=force
    )

    return {"status": "sync_queued", "sheet": sheet_config.name}


async def sync_sheet_background(sheet_config, force: bool):
    """Background task to sync a sheet."""
    try:
        processor = get_processor()
        processor.sync_sheet(sheet_config, trigger='manual', force=force)
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
        processor.sync_all_sheets(trigger='manual', force=force)
    except Exception as e:
        logger.error(f"Error in sync_all: {e}")


@app.get("/api/status")
async def get_status():
    """Get service status and recent sync history."""
    from .models import get_db
    from .config import get_watched_sheets

    db = get_db()
    recent_syncs = db.get_recent_syncs(limit=20)

    # Get watch status
    watches = []
    for key, sheet in get_watched_sheets().items():
        watch = db.get_watch(sheet.spreadsheet_id)
        watches.append({
            'name': sheet.name,
            'spreadsheet_id': sheet.spreadsheet_id,
            'has_watch': watch is not None,
            'watch_expires': watch.expiration.isoformat() if watch else None,
            'hours_until_expiry': watch.hours_until_expiry if watch else None
        })

    # Get change tracking summary
    processor = get_processor()
    change_summary = processor.get_change_summary(days=7)
    unacked_alerts = processor.get_unacknowledged_alerts()

    return {
        'service': 'sheets-receiver',
        'version': '1.0.0',
        'watches': watches,
        'change_tracking': {
            'summary_7_days': change_summary,
            'unacknowledged_alerts': len(unacked_alerts),
            'alerts': [
                {
                    'id': a['id'],
                    'type': a['alert_type'],
                    'message': a['alert_message'][:100] + '...' if len(a['alert_message']) > 100 else a['alert_message']
                }
                for a in unacked_alerts[:5]  # Show first 5
            ]
        },
        'recent_syncs': [
            {
                'spreadsheet_name': s.spreadsheet_name,
                'status': s.status,
                'trigger': s.trigger,
                'rows_processed': s.rows_processed,
                'created_at': s.created_at.isoformat()
            }
            for s in recent_syncs
        ]
    }


@app.post("/api/watches/setup")
async def setup_watches():
    """Set up watches for all configured sheets."""
    from .sheets_client import get_sheets_client

    client = get_sheets_client()
    watches = client.setup_all_watches()

    return {
        'status': 'success',
        'watches_created': len(watches),
        'watches': [
            {
                'name': w.spreadsheet_name,
                'channel_id': w.channel_id,
                'expires': w.expiration.isoformat()
            }
            for w in watches
        ]
    }


@app.post("/api/watches/renew")
async def renew_watches():
    """Renew expiring watches."""
    from .sheets_client import get_sheets_client

    client = get_sheets_client()
    renewed = client.renew_expiring_watches()

    return {
        'status': 'success',
        'watches_renewed': len(renewed)
    }


# ========================================
# CHANGE TRACKING ENDPOINTS
# ========================================

@app.get("/api/changes")
async def get_changes(
    spreadsheet_id: Optional[str] = None,
    change_type: Optional[str] = None,
    limit: int = 100
):
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
        spreadsheet_id=spreadsheet_id,
        limit=limit,
        change_type=change_type
    )

    return {
        'total': len(changes),
        'changes': changes
    }


@app.get("/api/changes/summary")
async def get_change_summary(
    spreadsheet_id: Optional[str] = None,
    days: int = 7
):
    """
    Get summary of changes over time.

    Query params:
        spreadsheet_id: Filter by spreadsheet (optional)
        days: How many days to look back (default 7)

    Returns:
        Summary with counts by type
    """
    processor = get_processor()
    return processor.get_change_summary(
        spreadsheet_id=spreadsheet_id,
        days=days
    )


@app.get("/api/changes/modified")
async def get_modified_rows(limit: int = 50):
    """
    Get recently modified rows (edits to existing data).

    This is the key endpoint for detecting when team members
    edit existing records instead of adding new ones.
    """
    processor = get_processor()
    changes = processor.get_recent_changes(
        change_type='modified',
        limit=limit
    )

    return {
        'total': len(changes),
        'message': 'These rows had existing data modified (not new entries)',
        'changes': changes
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

    return {
        'total': len(alerts),
        'alerts': alerts
    }


@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int):
    """Mark an alert as acknowledged."""
    processor = get_processor()
    success = processor.acknowledge_alert(alert_id)

    if success:
        return {'status': 'acknowledged', 'alert_id': alert_id}
    else:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")


def run_server():
    """Run the webhook server."""
    config = get_config()

    uvicorn.run(
        app,
        host=config.webhook_host,
        port=config.webhook_port,
        log_level=config.log_level.lower()
    )


if __name__ == "__main__":
    run_server()
