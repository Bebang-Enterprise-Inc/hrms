"""
Sheets Receiver Service

A sustainable Google Sheets sync service similar to ADMS Receiver.
Receives push notifications from Google Drive and syncs to Frappe/ERPNext.

Architecture:
- FastAPI webhook endpoint receives Google Drive push notifications
- Change processor fetches updated sheet data via Sheets API
- Frappe writer syncs data to ERPNext via API
- Watch manager maintains Drive watches (they expire every 24h)
- SQLite database for sync logs and change tracking

Usage:
    python -m hrms.services.sheets_receiver.main

Environment Variables:
    GOOGLE_SERVICE_ACCOUNT_FILE: Path to service account JSON
    FRAPPE_URL: Frappe instance URL (e.g., https://hq.bebang.ph)
    FRAPPE_API_KEY: Frappe API key
    FRAPPE_API_SECRET: Frappe API secret
    SHEETS_RECEIVER_PORT: Port to run webhook server (default: 8765)
    IMPERSONATE_USER: Google user to impersonate (default: sam@bebang.ph)
"""

__version__ = "1.0.0"
