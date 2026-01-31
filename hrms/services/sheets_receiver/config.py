"""
Configuration for Sheets Receiver Service.

Defines which sheets to watch, sync mappings, and service settings.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class SheetConfig:
    """Configuration for a single watched sheet."""
    name: str
    spreadsheet_id: str
    sheet_name: str  # Tab name within spreadsheet
    range: str  # A1 notation range to sync
    owner_email: str
    sync_endpoint: str  # Frappe API endpoint to call
    doctype: Optional[str] = None  # Target ERPNext DocType
    key_column: str = "name"  # Column to use as unique key
    enabled: bool = True
    sync_mode: str = "upsert"  # upsert, replace, append


@dataclass
class ServiceConfig:
    """Main service configuration."""

    # Google API
    service_account_file: str = field(
        default_factory=lambda: os.environ.get(
            'GOOGLE_SERVICE_ACCOUNT_FILE',
            '/app/credentials/task-manager-service.json'
        )
    )
    impersonate_user: str = field(
        default_factory=lambda: os.environ.get('IMPERSONATE_USER', 'sam@bebang.ph')
    )

    # Frappe API
    frappe_url: str = field(
        default_factory=lambda: os.environ.get('FRAPPE_URL', 'https://hq.bebang.ph')
    )
    frappe_api_key: str = field(
        default_factory=lambda: os.environ.get('FRAPPE_API_KEY', '')
    )
    frappe_api_secret: str = field(
        default_factory=lambda: os.environ.get('FRAPPE_API_SECRET', '')
    )

    # Webhook server
    webhook_host: str = field(
        default_factory=lambda: os.environ.get('SHEETS_RECEIVER_HOST', '0.0.0.0')
    )
    webhook_port: int = field(
        default_factory=lambda: int(os.environ.get('SHEETS_RECEIVER_PORT', '8765'))
    )
    webhook_path: str = "/webhook/sheets"

    # Public URL for Google to send webhooks to
    # Uses nginx proxy directly - NOT routed through Frappe
    public_webhook_url: str = field(
        default_factory=lambda: os.environ.get(
            'PUBLIC_WEBHOOK_URL',
            'https://hq.bebang.ph/sheets-webhook'
        )
    )

    # Database
    db_path: str = field(
        default_factory=lambda: os.environ.get(
            'SHEETS_RECEIVER_DB',
            '/app/data/sheets_receiver.db'
        )
    )

    # Watch settings
    watch_expiry_hours: int = 24  # Google limit
    watch_renewal_buffer_hours: int = 1  # Renew this many hours before expiry

    # Sync settings
    sync_retry_attempts: int = 3
    sync_retry_delay_seconds: int = 5
    batch_size: int = 100  # Rows per API call

    # Logging
    log_level: str = field(
        default_factory=lambda: os.environ.get('LOG_LEVEL', 'INFO')
    )
    log_file: str = field(
        default_factory=lambda: os.environ.get(
            'SHEETS_RECEIVER_LOG',
            '/app/logs/sheets_receiver.log'
        )
    )


# Sheets to watch and sync
WATCHED_SHEETS: Dict[str, SheetConfig] = {
    'ar_aging': SheetConfig(
        name='AR Aging',
        spreadsheet_id='1puwkr5hzrki9srxq10_jOeb5mfngkbo-VVpydmAf2kQ',
        sheet_name='AR',  # Actual tab name
        range='A:Z',
        owner_email='alyssa@bebang.ph',
        sync_endpoint='/api/method/hrms.api.erp_sync.sync_ar_aging',
        doctype='Sales Invoice',
        key_column='invoice_no',
        sync_mode='upsert'
    ),
    'inventory': SheetConfig(
        name='Inventory',
        spreadsheet_id='1Eh_BhDK_LgdOzJ002F7XUYLBsd4EM8ec7sPz43mudGc',
        sheet_name='SUMMARY 2026',  # Case-sensitive tab name
        range='A:Z',
        owner_email='ian@bebang.ph',
        sync_endpoint='/api/method/hrms.api.erp_sync.sync_inventory',
        doctype='Stock Reconciliation',
        key_column='item_code',
        sync_mode='replace'
    ),
    'coa': SheetConfig(
        name='Chart of Accounts',
        spreadsheet_id='1EXCd4Ah2n6Q42vQvTG3dYLFzPsPFhdbzmHp_2wBpN7g',
        sheet_name='01 - Chart of Accounts (217)',  # Actual tab name
        range='A:I',
        owner_email='sam@bebang.ph',
        sync_endpoint='/api/method/hrms.api.erp_sync.sync_coa',
        doctype='Account',
        key_column='gl_code',
        sync_mode='upsert'
    ),
    'bank_directory': SheetConfig(
        name='Bank Directory',
        spreadsheet_id='1rkQDLREjTG8eyqB7wO5rRsnkjvaasOgmnPcKnqjXNnY',
        sheet_name='02 - Bank Directory (53)',  # Actual tab name
        range='A:G',
        owner_email='sam@bebang.ph',
        sync_endpoint='/api/method/hrms.api.erp_sync.sync_bank_accounts',
        doctype='Bank Account',
        key_column='account_number',
        sync_mode='upsert'
    ),
    'supplier_soa': SheetConfig(
        name='Supplier SOA (AP)',
        spreadsheet_id='1TmENuP8HgCVbo3lJtTpe4PVemLCkPnGL',  # Update with actual ID
        sheet_name='SUPPLIERS SOA',
        range='A:Z',
        owner_email='izza@bebang.ph',
        sync_endpoint='/api/method/hrms.api.erp_sync.sync_ap_opening',
        doctype='Purchase Invoice',
        key_column='invoice_no',
        sync_mode='upsert',
        enabled=False  # Enable when ready
    ),
}


def get_config() -> ServiceConfig:
    """Get service configuration."""
    return ServiceConfig()


def get_watched_sheets() -> Dict[str, SheetConfig]:
    """Get all enabled watched sheets."""
    return {k: v for k, v in WATCHED_SHEETS.items() if v.enabled}


def get_sheet_by_spreadsheet_id(spreadsheet_id: str) -> Optional[SheetConfig]:
    """Look up sheet config by Google spreadsheet ID."""
    for sheet in WATCHED_SHEETS.values():
        if sheet.spreadsheet_id == spreadsheet_id:
            return sheet
    return None
