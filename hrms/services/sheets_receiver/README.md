# Sheets Receiver Service

A sustainable Google Sheets sync service for BEI ERP - similar to ADMS Receiver.

**Temporary service for ERP migration period.** Easy to remove after go-live.

## Overview

This service provides **real-time synchronization** between Google Sheets and ERPNext:

- **Push notifications** from Google Drive when sheets change
- **Automatic sync** to ERPNext via Frappe API
- **Change detection** via checksums (only sync when data changes)
- **Watch management** (auto-renewal of 24h Google watches)
- **Full audit trail** in SQLite database

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
├── config.py           # Configuration and watched sheets
├── models.py           # SQLite database models
├── sheets_client.py    # Google Sheets/Drive API client
├── frappe_client.py    # Frappe REST API client
├── processor.py        # Change processor (with change tracking integration)
├── change_tracker.py   # Row-level change detection and alerts
├── webhook.py          # FastAPI webhook server
├── main.py             # Main entry point
├── Dockerfile          # Docker build
├── requirements.txt    # Python dependencies
└── README.md           # This file

hrms/api/
└── erp_sync.py         # Frappe-side sync endpoints
```

## Comparison with ADMS Receiver

| Feature | ADMS Receiver | Sheets Receiver |
|---------|--------------|-----------------|
| Data Source | ZKTeco devices | Google Sheets |
| Push Method | iClock protocol | Drive Watch API |
| Frequency | Real-time (per punch) | Real-time (per edit) |
| Fallback | None | 6-hour scheduled sync |
| Storage | Frappe DB | SQLite + Frappe DB |

## Security

- Service account credentials stored securely in `/app/credentials`
- Frappe API keys via environment variables (use Doppler)
- Webhook validates Google headers
- All sync operations logged

## Support

- Logs: `docker logs sheets-receiver`
- Database: `/app/data/sheets_receiver.db`
- Contact: sam@bebang.ph
