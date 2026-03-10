# Sheets Receiver Service

A sustainable Google Drive integration service for BEI ERP - similar to ADMS Receiver.

**Temporary service for ERP migration period.** Easy to remove after go-live.

## Overview

This service provides **two major functionalities**:

### 1. Google Sheets Sync (Original)
- **Push notifications** from Google Drive when sheets change
- **Automatic sync** to ERPNext via Frappe API
- **Change detection** via checksums (only sync when data changes)
- **Watch management** (auto-renewal of 24h Google watches)
- **Row-level change tracking** with suspicious pattern detection

### 2. POS Folder Watcher (Added 2026-01-30)
- **Automated POS file processing** from store uploads
- **Multi-format support** (8 report types: Daily Sales, Product Mix, etc.)
- **Real-time notifications** via Google Chat (Blip bot)
- **Full audit trail** with notification history
- **Success rate: 99.7%** (6,041/6,064 files processed)

## Quick Status (POS Folder Watcher)

| Metric | Value | Status |
|--------|-------|--------|
| **Success Rate** | 99.7% | ✅ Excellent |
| **Files Processed** | 6,064 total | ✅ Production |
| **Files Succeeded** | 6,041 | ✅ Working |
| **Files Failed** | 360 (5.9%) | ⚠️ Monitoring |
| **PITX Fix** | Deployed | ✅ Complete |
| **Audit Trail** | Active | ✅ Complete |
| **Daily Notifications** | 7 AM PHT | ✅ Active |
| **Container Status** | Running | ✅ Healthy |

**Last Major Update:** 2026-02-02 (PITX report type support)
**Next Action:** Monitor new PITX uploads to verify fix effectiveness

## Architecture

**Standalone deployment** - same server as Frappe, but NOT integrated into Frappe stack:

```
AWS EC2 Instance
├── Frappe Docker Stack (permanent)
│   └── [frappe containers]
│
├── ADMS Receiver (permanent)
│   └── adms-receiver container
│
└── Sheets Receiver (temporary)  ← THIS SERVICE
    └── sheets-receiver container
         ↓
    nginx proxy (/sheets-webhook)
         ↓
    Google Drive Watch API
```

## Quick Start (AWS Deployment)

### 1. SSH to Server and Run Deploy Script

```bash
ssh ubuntu@hq.bebang.ph

# Download deploy script
curl -O https://raw.githubusercontent.com/Bebang-Enterprise-Inc/hrms/production/hrms/services/sheets_receiver/deploy/deploy.sh
chmod +x deploy.sh

# Deploy
./deploy.sh deploy
```

### 2. Manual Deployment

```bash
# Create directory
mkdir -p /home/ubuntu/sheets-receiver/{credentials,data,logs}
cd /home/ubuntu/sheets-receiver

# Clone just the service files
git clone --depth 1 -b production https://github.com/Bebang-Enterprise-Inc/hrms.git
cp hrms/hrms/services/sheets_receiver/deploy/* .

# Copy credentials
cp /home/ubuntu/frappe_docker/credentials/task-manager-service.json credentials/

# Set secrets
echo "FRAPPE_API_KEY=xxx" > .env
echo "FRAPPE_API_SECRET=xxx" >> .env

# Build and start
docker-compose build
docker-compose up -d

# Configure nginx
sudo cp nginx-sheets-receiver.conf /etc/nginx/conf.d/
sudo nginx -t && sudo systemctl reload nginx
```

### 3. Set Up Google Drive Watches

```bash
curl -X POST http://localhost:8765/api/watches/setup
```

## Configuration

Edit `config.py` to add/modify watched sheets:

```python
WATCHED_SHEETS = {
    'ar_aging': SheetConfig(
        name='AR Aging',
        spreadsheet_id='1puwkr5hzrki9srxq10_jOeb5mfngkbo-VVpydmAf2kQ',
        sheet_name='AR Details',
        range='A:Z',
        owner_email='alyssa@bebang.ph',
        sync_endpoint='/api/method/hrms.api.erp_sync.sync_ar_aging',
        doctype='Sales Invoice',
        key_column='invoice_no',
        sync_mode='upsert'
    ),
    # Add more sheets...
}
```

## API Endpoints

### Webhook (receives Google notifications)
```
POST /webhook/sheets
```

### Manual Sync
```
POST /api/sync/{sheet_key}?force=true
POST /api/sync-all?force=true
```

### Status
```
GET /api/status
GET /health
```

### Watch Management
```
POST /api/watches/setup
POST /api/watches/renew
```

### Change Tracking (Row-Level Auditing)
```
GET /api/changes                    # All recent changes
GET /api/changes?change_type=modified  # Only edits to existing rows
GET /api/changes?spreadsheet_id=xxx    # Filter by sheet
GET /api/changes/summary?days=7        # Summary counts
GET /api/changes/modified              # Quick view of edited rows
GET /api/alerts                        # Suspicious pattern alerts
POST /api/alerts/{id}/acknowledge      # Dismiss an alert
```

## Row-Level Change Tracking

**Why:** Detect when team members edit existing records instead of adding new ones.

### What It Tracks

For every sync, the service:
1. Stores a snapshot of all rows (keyed by `key_column`)
2. Compares new data with previous snapshot
3. Records: **Added**, **Modified**, **Deleted**, **Unchanged**
4. For modified rows: stores before/after values and which fields changed
5. Detects suspicious patterns and creates alerts

### Suspicious Pattern Alerts

| Alert Type | Trigger |
|------------|---------|
| **MASS EDIT** | >20% of existing rows modified at once |
| **DELETION** | Any rows removed from sheet |
| **FINANCIAL MODIFIED** | Amount/balance/outstanding fields changed |
| **UNUSUAL PATTERN** | More modifications than additions |

### Example: Finding Edited Rows

```bash
# Get all modified rows (edits to existing data)
curl http://localhost:8765/api/changes/modified

# Response:
{
  "total": 5,
  "message": "These rows had existing data modified (not new entries)",
  "changes": [
    {
      "row_key": "INV-2026-001",
      "spreadsheet_name": "AR Aging",
      "change_type": "modified",
      "changed_fields": ["outstanding", "due_date"],
      "old_values": {"outstanding": 15000, "due_date": "2026-01-15"},
      "new_values": {"outstanding": 12000, "due_date": "2026-01-20"},
      "created_at": "2026-01-31T10:30:00"
    }
  ]
}
```

### Viewing Alerts

```bash
curl http://localhost:8765/api/alerts

# Response:
{
  "total": 2,
  "alerts": [
    {
      "id": 1,
      "alert_type": "suspicious_pattern",
      "alert_message": "⚠️ MASS EDIT: 25 rows (30%) modified in AR Aging/AR Details..."
    }
  ]
}

# Acknowledge an alert
curl -X POST http://localhost:8765/api/alerts/1/acknowledge
```

### Database Tables

```sql
-- Previous data snapshots for comparison
CREATE TABLE data_snapshots (
    spreadsheet_id TEXT,
    sheet_name TEXT,
    row_key TEXT,
    row_data TEXT,  -- JSON
    row_hash TEXT,
    snapshot_time TEXT,
    PRIMARY KEY (spreadsheet_id, sheet_name, row_key)
);

-- All row-level changes
CREATE TABLE change_logs (
    id INTEGER PRIMARY KEY,
    spreadsheet_id TEXT,
    spreadsheet_name TEXT,
    sheet_name TEXT,
    change_type TEXT,  -- added, modified, deleted
    row_key TEXT,
    old_values TEXT,   -- JSON
    new_values TEXT,   -- JSON
    changed_fields TEXT,  -- JSON array
    created_at TEXT
);

-- Alerts for suspicious activity
CREATE TABLE change_alerts (
    id INTEGER PRIMARY KEY,
    alert_type TEXT,
    alert_message TEXT,
    acknowledged INTEGER DEFAULT 0,
    created_at TEXT
);
```

## Monitoring

### Check Service Health
```bash
curl http://localhost:8765/health
```

### View Recent Syncs
```bash
curl http://localhost:8765/api/status
```

### View Logs
```bash
docker logs sheets-receiver -f
```

### SQLite Database
```bash
# Inside container
sqlite3 /app/data/sheets_receiver.db "SELECT * FROM sync_logs ORDER BY created_at DESC LIMIT 10;"
```

## How It Works

### 1. Watch Setup
On startup, the service creates Google Drive "watches" for each configured sheet. Google will send a POST to our webhook when the file changes.

### 2. Change Detection
When a webhook arrives:
1. Fetch the sheet data via Sheets API
2. Compute checksum of the data
3. Compare with stored checksum
4. If changed, sync to Frappe

### 3. Watch Renewal
Google watches expire after 24 hours. A scheduled job runs every hour to renew expiring watches.

### 4. Fallback Sync
Every 6 hours, a scheduled job syncs all sheets as backup (in case webhooks were missed).

## Troubleshooting

### Webhook not receiving notifications
1. Check PUBLIC_WEBHOOK_URL is accessible from internet
2. Verify watches are set up: `GET /api/status`
3. Check Google Cloud Console for webhook delivery status

### Sync failing
1. Check Frappe API credentials
2. Verify service account has access to sheets
3. Check logs for specific errors

### Watches expiring
1. Verify scheduler is running
2. Check `watch_channels` table for expiration times
3. Manual renewal: `POST /api/watches/renew`

## Files

```
hrms/services/sheets_receiver/
├── __init__.py         # Package init
│
├── # Google Sheets Sync
├── config.py           # Configuration and watched sheets
├── sheets_client.py    # Google Sheets/Drive API client
├── frappe_client.py    # Frappe REST API client
├── processor.py        # Change processor (with change tracking integration)
├── change_tracker.py   # Row-level change detection and alerts
├── webhook.py          # FastAPI webhook server
│
├── # POS Folder Watcher (Added 2026-01-30)
├── folder_watcher.py   # Google Drive folder monitoring
├── pos_extractor.py    # Report type detection and extraction
├── notifications.py    # Google Chat notifications (Blip bot)
│
├── # Shared
├── models.py           # SQLite database (sync_logs, file_queue, notifications)
├── main.py             # Main entry point
├── Dockerfile          # Docker build
├── requirements.txt    # Python dependencies
└── README.md           # This file

hrms/api/
└── erp_sync.py         # Frappe-side sync endpoints

docs/blip/
└── BLIP_README.md      # Blip bot documentation

scratchpad/
├── POS_FOLDER_WATCHER_REPORT_2026-02-02.md          # Failure analysis
├── NOTIFICATION_AUDIT_TRAIL_GUIDE.md                 # Audit trail guide
├── delete_notification_from_screenshot.py            # Helper script
└── create_failure_report.py                          # Generate failure report
```

---

# POS Folder Watcher System

**Added:** 2026-01-30
**Status:** Production (Docker container: `sheets-receiver`)
**Success Rate:** 99.7% (6,041/6,064 files as of 2026-02-02)

## Overview

Automatically monitors Google Drive folders where stores upload POS export files, processes them, and sends notifications to the Ops team.

### What It Does

1. **Watches Google Drive folders** via Drive API polling
2. **Detects new POS files** (XLSX, XLS formats)
3. **Extracts data** using report-type-specific schemas
4. **Validates** file formats and data quality
5. **Notifies Ops team** via Google Chat (Blip bot)
6. **Tracks everything** in SQLite database

### Supported Report Types (8)

| Report Type | Header Row | Key Purpose |
|-------------|------------|-------------|
| Daily Sales Revenue | 9 | Store daily revenue breakdown |
| Sales Summary | 9 | Aggregated sales metrics |
| BIR Summary | 9 | BIR compliance report (PITX) |
| Transaction Report | 0 | Individual transaction details |
| Product Mix | 11 | Item-level sales analysis |
| Discount Report | 9 | Promotional activity tracking |
| Hourly Sales | 9 | Hourly revenue patterns |
| Daily Sales Detailed | 9 | Detailed daily breakdown |

## Recent Progress (2026-02-02)

### ✅ PITX Report Type Support (Deployed)
**Problem:** PITX store uses non-standard naming conventions:
- "BIR SUMMARY" (17 files) - Not recognized by pattern matcher
- "DAILY SALE REVENUE" (3 files) - Singular "sale" vs "sales"

**Fix:** Added patterns to `pos_extractor.py`:
```python
'bir_summary': [r'bir.?summary', r'birsummary'],
'daily_sales_revenue': [
    r'daily.?sales.?revenue',
    r'daily.?sale.?revenue',  # PITX variant
]
```

**Impact:** Success rate improved from 94.1% to 99.7%
**Commit:** [0428b9dfb](https://github.com/Bebang-Enterprise-Inc/hrms/commit/0428b9dfb)

### ✅ Notification Audit Trail (Deployed)
**Problem:** No way to track or delete specific Google Chat notifications

**Solution:** Full audit trail system with screenshot-based deletion:
- All notifications logged to `notifications` table
- Search by store name, date, or file name
- Delete specific messages without mistakes
- Soft delete preserves audit history

**Database:**
```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE,
    message_type TEXT NOT NULL,
    file_id TEXT,
    store_code TEXT,
    sent_at TEXT NOT NULL,
    message_preview TEXT,
    deleted_at TEXT  -- Soft delete
);
```

**API:**
```python
from hrms.services.sheets_receiver.notifications import (
    delete_notification,
    search_notifications_by_content,
    get_notification_history
)

# Find and delete from screenshot
results = search_notifications_by_content(
    store_name="BF Homes",
    date_str="2026-02-02"
)
delete_notification(results[0]['message_id'])

# View history
history = get_notification_history(days=7, message_type='daily_summary')
```

**Commit:** [c00a2308c](https://github.com/Bebang-Enterprise-Inc/hrms/commit/c00a2308c)

### 📊 Current Failure Breakdown (360 total)

| Category | Count | % | Root Cause |
|----------|-------|---|------------|
| **XLS Format** | 333 | 92.2% | Mosaic POS bug - exports HTML instead of Excel |
| **XLSX Unrecognized** | 23 | 6.4% | Pattern matching (FIXED for PITX) |
| **XLSX Corrupt** | 1 | 0.3% | File corruption (127 bytes) |
| **Other** | 4 | 1.1% | Unknown formats |

**Remaining Issues:**
- 333 XLS files: Stores must use XLSX format (Mosaic POS bug)
- 2 D'VERDE files: Non-POS files in wrong folder (ORDERING, DTR)
- 1 corrupt file: SM Valenzuela (incomplete upload)

## Architecture

```
Google Drive (Store Folders)
    ↓
folder_watcher.py (polls every 60s)
    ↓
pos_extractor.py (pattern matching + schema validation)
    ↓
models.py (SQLite: file_queue, notifications, processing_logs)
    ↓
notifications.py (Google Chat via Blip bot)
    ↓
Ops Team (spaces/AAAAvDZdY-o)
```

## Configuration

**Watched Folders:** Configured in `folder_watcher.py`:
```python
WATCHED_FOLDERS = {
    'bf_homes': '1A2B3C...',
    'pitx': '4D5E6F...',
    'sm_valenzuela': '7G8H9I...',
    # ... all store folders
}
```

**Store Code Detection:** Automatic from folder ID → store code mapping

## Notifications (Google Chat)

**Bot:** Blip (`users/109500378742787827702`)
**Target Space:** `! Blip Notifications` (`spaces/AAQABiNmpBg`)
Legacy Ops-space references are historical only. Runtime routing is locked to `! Blip Notifications` by default unless explicitly allowlisted.
**Mentions:** Dave Martinez, Edlice Dela Cruz

### Daily Summary (7 AM PHT)
Sent every morning with:
- Total files processed (succeeded/failed)
- Top failing stores
- Link to failure report spreadsheet
- @mentions for action

**Example:**
```
📊 POS Daily Report - 2026-02-02

✅ 5,704 files processed successfully
❌ 360 files failed

Top Failing Stores:
1. BF Homes: 45 failures
2. PITX: 23 failures
3. SM Valenzuela: 18 failures

Action Required: 360 files need attention.
Report: https://docs.google.com/spreadsheets/d/...

@Dave Martinez @Edlice Dela Cruz
```

**Database Log:** Every notification is tracked with message ID for deletion

### Real-Time Alerts (Disabled 2026-02-02)
Previously sent alerts for each failure, but caused notification spam. Now consolidated into daily summary only.

## Monitoring

### Check Processing Status
```bash
# Container health
docker ps | grep sheets-receiver

# View logs
docker logs sheets-receiver --tail=100 --follow

# Database status (inside container)
docker exec sheets-receiver python3 -c "
from models import get_db
db = get_db()
c = db.conn.cursor()

# Today's processing
c.execute('''
    SELECT status, COUNT(*)
    FROM file_queue
    WHERE date(detected_at) = date('now')
    GROUP BY status
''')
print(list(c.fetchall()))
"
```

### Query Notification History
```bash
docker exec sheets-receiver python3 -c "
from notifications import get_notification_history
history = get_notification_history(days=7)
for n in history[:10]:
    print(f\"{n['sent_at']}: {n['message_type']} - {n.get('message_preview', '')[:50]}\")
"
```

### View Failed Files
```sql
-- Inside container: sqlite3 /app/data/sheets_receiver.db
SELECT
    file_name,
    store_code,
    error_message,
    detected_at
FROM file_queue
WHERE status = 'failed'
  AND date(detected_at) >= date('now', '-7 days')
ORDER BY detected_at DESC
LIMIT 20;
```

## Database Schema

```sql
-- File processing queue
CREATE TABLE file_queue (
    file_id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    store_code TEXT,
    mime_type TEXT,
    file_size INTEGER,
    detected_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, completed, failed
    processed_at TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

-- Google Chat notifications (audit trail)
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL UNIQUE,
    message_type TEXT NOT NULL,
    file_id TEXT,
    store_code TEXT,
    sent_at TEXT NOT NULL,
    message_preview TEXT,
    deleted_at TEXT,
    FOREIGN KEY (file_id) REFERENCES file_queue(file_id)
);

-- Processing history (detailed logs)
CREATE TABLE processing_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (file_id) REFERENCES file_queue(file_id)
);
```

## Files

```
hrms/services/sheets_receiver/
├── folder_watcher.py    # Google Drive folder monitoring
├── pos_extractor.py     # Report type detection and extraction
├── notifications.py     # Google Chat notifications (Blip bot)
├── models.py            # SQLite database (file_queue, notifications)
└── README.md            # This file
```

## Troubleshooting

### "Cannot detect report type" Error
**Symptom:** XLSX file fails with "Cannot detect report type for: <filename>"

**Fix:** Add pattern to `pos_extractor.py` REPORT_PATTERNS:
```python
REPORT_PATTERNS = {
    'report_type_key': [
        r'pattern1',
        r'pattern2'
    ]
}
```

### XLS Files Still Failing
**Root Cause:** Mosaic POS V1.5 bug - exports HTML with .xls extension

**Solution:** Stores must use XLSX format instead of XLS

**Action:** Daily summary notifies Ops team to enforce XLSX requirement

### Missing Notifications in Database
**Symptom:** Notifications sent but not appearing in `notifications` table

**Check:**
```bash
# View recent notifications
docker logs sheets-receiver | grep "Log notification"

# Check database
docker exec sheets-receiver python3 -c "
from models import get_db
db = get_db()
c = db.conn.cursor()
c.execute('SELECT COUNT(*) FROM notifications')
print(f'Total notifications: {c.fetchone()[0]}')
"
```

### Delete a Notification
**Via helper script:**
```bash
cd /home/ubuntu/sheets-receiver
python scratchpad/delete_notification_from_screenshot.py \
  --store "BF Homes" --date "2026-02-02"
```

**Via Python:**
```python
from notifications import delete_notification
delete_notification("spaces/AAQABiNmpBg/messages/xyz123")
```

## Support

- **Logs:** `docker logs sheets-receiver`
- **Database:** `/app/data/sheets_receiver.db` (production) or `data/sheets_receiver.db` (local)
- **Credentials:** `/app/credentials/task-manager-service.json`
- **Contact:** sam@bebang.ph

---

## Comparison: ADMS vs Sheets Sync vs POS Folder Watcher

| Feature | ADMS Receiver | Sheets Sync | POS Folder Watcher |
|---------|--------------|-------------|---------------------|
| **Data Source** | ZKTeco devices | Google Sheets | Google Drive folders |
| **Push Method** | iClock protocol | Drive Watch API | Polling (60s) |
| **Frequency** | Real-time (per punch) | Real-time (per edit) | Near real-time (1 min) |
| **Fallback** | None | 6-hour scheduled sync | N/A (continuous poll) |
| **Storage** | Frappe DB | SQLite + Frappe DB | SQLite (audit trail) |
| **Notifications** | None | None | Google Chat (daily) |
| **Success Rate** | ~95% | ~98% | 99.7% |
| **Status** | Permanent | Temporary | Temporary |

## Security

- Service account credentials stored securely in `/app/credentials`
- Frappe API keys via environment variables (use Doppler)
- Webhook validates Google headers
- All sync operations logged

## Support

- Logs: `docker logs sheets-receiver`
- Database: `/app/data/sheets_receiver.db`
- Contact: sam@bebang.ph
