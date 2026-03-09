"""
Configuration for Sheets Receiver Service.

Defines which sheets/folders to watch, sync mappings, and service settings.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FolderConfig:
	"""Configuration for a watched folder."""

	name: str
	folder_id: str
	parent_folder_id: str | None = None  # For subfolders
	store_code: str | None = None  # Normalized store identifier
	owner_email: str = "ops@bebang.ph"
	enabled: bool = True
	file_patterns: list[str] = field(default_factory=lambda: ["*.xlsx", "*.pdf"])
	processor: str = "pos"  # Processor type: pos, invoice, etc.


@dataclass
class SheetConfig:
	"""Configuration for a single watched sheet."""

	name: str
	spreadsheet_id: str
	sheet_name: str  # Tab name within spreadsheet
	range: str  # A1 notation range to sync
	owner_email: str
	sync_endpoint: str  # Frappe API endpoint to call
	doctype: str | None = None  # Target ERPNext DocType
	key_column: str = "name"  # Column to use as unique key
	enabled: bool = True
	sync_mode: str = "upsert"  # upsert, replace, append
	related_sheet_keys: list[str] = field(default_factory=list)


@dataclass
class ServiceConfig:
	"""Main service configuration."""

	# Google API
	service_account_file: str = field(
		default_factory=lambda: os.environ.get(
			"GOOGLE_SERVICE_ACCOUNT_FILE", "/app/credentials/task-manager-service.json"
		)
	)
	impersonate_user: str = field(default_factory=lambda: os.environ.get("IMPERSONATE_USER", "sam@bebang.ph"))

	# Frappe API
	frappe_url: str = field(default_factory=lambda: os.environ.get("FRAPPE_URL", "https://hq.bebang.ph"))
	frappe_api_key: str = field(default_factory=lambda: os.environ.get("FRAPPE_API_KEY", ""))
	frappe_api_secret: str = field(default_factory=lambda: os.environ.get("FRAPPE_API_SECRET", ""))

	# Webhook server
	webhook_host: str = field(default_factory=lambda: os.environ.get("SHEETS_RECEIVER_HOST", "0.0.0.0"))
	webhook_port: int = field(default_factory=lambda: int(os.environ.get("SHEETS_RECEIVER_PORT", "8765")))
	webhook_path: str = "/webhook/sheets"

	# Public URL for Google to send webhooks to
	# Uses nginx proxy directly - NOT routed through Frappe
	public_webhook_url: str = field(
		default_factory=lambda: os.environ.get("PUBLIC_WEBHOOK_URL", "https://hq.bebang.ph/sheets-webhook")
	)

	# Database
	db_path: str = field(
		default_factory=lambda: os.environ.get("SHEETS_RECEIVER_DB", "/app/data/sheets_receiver.db")
	)

	# Watch settings
	watch_expiry_hours: int = 24  # Google limit
	watch_renewal_buffer_hours: int = 1  # Renew this many hours before expiry

	# Sync settings
	sync_retry_attempts: int = 3
	sync_retry_delay_seconds: int = 5
	batch_size: int = 100  # Rows per API call

	# Logging
	log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))
	log_file: str = field(
		default_factory=lambda: os.environ.get("SHEETS_RECEIVER_LOG", "/app/logs/sheets_receiver.log")
	)


# Sheets to watch and sync
PROCUREMENT_COMPLIANCE_SPREADSHEET_ID = "1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q"

WATCHED_SHEETS: dict[str, SheetConfig] = {
	"ar_aging": SheetConfig(
		name="AR Aging",
		spreadsheet_id="1puwkr5hzrki9srxq10_jOeb5mfngkbo-VVpydmAf2kQ",
		sheet_name="AR",  # Actual tab name
		range="A:Z",
		owner_email="alyssa@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_ar_aging",
		doctype="Sales Invoice",
		key_column="invoice_no",
		sync_mode="upsert",
	),
	"inventory": SheetConfig(
		name="Inventory",
		spreadsheet_id="1Eh_BhDK_LgdOzJ002F7XUYLBsd4EM8ec7sPz43mudGc",
		sheet_name="SUMMARY 2026",  # Case-sensitive tab name
		range="A:Z",
		owner_email="ian@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_inventory",
		doctype="Stock Reconciliation",
		key_column="item_code",
		sync_mode="replace",
	),
	"coa": SheetConfig(
		name="Chart of Accounts",
		spreadsheet_id="1EXCd4Ah2n6Q42vQvTG3dYLFzPsPFhdbzmHp_2wBpN7g",
		sheet_name="01 - Chart of Accounts (217)",  # Actual tab name
		range="A:I",
		owner_email="sam@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_coa",
		doctype="Account",
		key_column="gl_code",
		sync_mode="upsert",
	),
	"bank_directory": SheetConfig(
		name="Bank Directory",
		spreadsheet_id="1rkQDLREjTG8eyqB7wO5rRsnkjvaasOgmnPcKnqjXNnY",
		sheet_name="02 - Bank Directory (53)",  # Actual tab name
		range="A:G",
		owner_email="sam@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_bank_accounts",
		doctype="Bank Account",
		key_column="account_number",
		sync_mode="upsert",
	),
	"ap_opening_balance": SheetConfig(
		name="AP Opening Balance",
		spreadsheet_id="1ZHe2VoAFa94ET4I68C1jWM7nMzTdTCvttwZbICaLtB4",
		sheet_name="05 - AP Opening Balance (PHP 24.4M)",
		range="A:Z",
		owner_email="alyssa@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_ap_opening",
		doctype="Purchase Invoice",
		key_column="invoice_no",
		sync_mode="upsert",
		enabled=True,
	),
	"supplier_soa": SheetConfig(
		name="Supplier SOA",
		spreadsheet_id="1ZHe2VoAFa94ET4I68C1jWM7nMzTdTCvttwZbICaLtB4",
		sheet_name="SUPPLIERS SOA",
		range="A:Z",
		owner_email="alyssa@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_supplier_soa",
		doctype="Supplier",
		key_column="supplier_name",
		sync_mode="upsert",
		enabled=True,
	),
	"procurement_suppliers": SheetConfig(
		name="Procurement Suppliers",
		spreadsheet_id=PROCUREMENT_COMPLIANCE_SPREADSHEET_ID,
		sheet_name="Suppliers",
		range="A:Z",
		owner_email="aldrin@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_procurement_suppliers",
		doctype="BEI Supplier",
		key_column="supplier_code",
		sync_mode="upsert",
		enabled=True,
	),
	"procurement_pr_items": SheetConfig(
		name="Procurement PR Items",
		spreadsheet_id=PROCUREMENT_COMPLIANCE_SPREADSHEET_ID,
		sheet_name="PR Items",
		range="A:Z",
		owner_email="aldrin@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_procurement_requisitions",
		doctype="BEI PR Item",
		key_column="unique_id",
		sync_mode="upsert",
		enabled=False,
	),
	"procurement_requisitions": SheetConfig(
		name="Procurement Requisitions",
		spreadsheet_id=PROCUREMENT_COMPLIANCE_SPREADSHEET_ID,
		sheet_name="Purchase Requisitions",
		range="A:Z",
		owner_email="aldrin@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_procurement_requisitions",
		doctype="BEI Purchase Requisition",
		key_column="pr_no",
		sync_mode="upsert",
		enabled=True,
		related_sheet_keys=["procurement_pr_items"],
	),
	"procurement_po_items": SheetConfig(
		name="Procurement PO Items",
		spreadsheet_id=PROCUREMENT_COMPLIANCE_SPREADSHEET_ID,
		sheet_name="PO Items",
		range="A:Z",
		owner_email="aldrin@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_procurement_purchase_orders",
		doctype="BEI PO Item",
		key_column="uniqueid",
		sync_mode="upsert",
		enabled=False,
	),
	"procurement_purchase_orders": SheetConfig(
		name="Procurement Purchase Orders",
		spreadsheet_id=PROCUREMENT_COMPLIANCE_SPREADSHEET_ID,
		sheet_name="Purchase Order",
		range="A:Z",
		owner_email="aldrin@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_procurement_purchase_orders",
		doctype="BEI Purchase Order",
		key_column="po_no",
		sync_mode="upsert",
		enabled=True,
		related_sheet_keys=["procurement_po_items"],
	),
	"procurement_gr_items": SheetConfig(
		name="Procurement GR Items",
		spreadsheet_id=PROCUREMENT_COMPLIANCE_SPREADSHEET_ID,
		sheet_name="GR Items",
		range="A:Z",
		owner_email="aldrin@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_procurement_goods_receipts",
		doctype="BEI GR Item",
		key_column="unique_id",
		sync_mode="upsert",
		enabled=False,
	),
	"procurement_goods_receipts": SheetConfig(
		name="Procurement Goods Receipts",
		spreadsheet_id=PROCUREMENT_COMPLIANCE_SPREADSHEET_ID,
		sheet_name="Goods Receipts",
		range="A:Z",
		owner_email="aldrin@bebang.ph",
		sync_endpoint="/api/method/hrms.api.erp_sync.sync_procurement_goods_receipts",
		doctype="BEI Goods Receipt",
		key_column="gr_no",
		sync_mode="upsert",
		enabled=True,
		related_sheet_keys=["procurement_gr_items"],
	),
}


def get_config() -> ServiceConfig:
	"""Get service configuration."""
	return ServiceConfig()


def get_all_sheet_configs() -> dict[str, SheetConfig]:
	"""Get all configured sheets, including helper tabs used for bundle sync."""
	return dict(WATCHED_SHEETS)


def get_watched_sheets() -> dict[str, SheetConfig]:
	"""Get all enabled watched sheets."""
	return {k: v for k, v in WATCHED_SHEETS.items() if v.enabled}


def get_sheet_config(sheet_key: str) -> SheetConfig | None:
	"""Get a sheet config by key."""
	return WATCHED_SHEETS.get(sheet_key)


def get_sheets_by_spreadsheet_id(spreadsheet_id: str) -> dict[str, SheetConfig]:
	"""Get all enabled watched sheets for a spreadsheet/workbook."""
	return {
		key: sheet
		for key, sheet in WATCHED_SHEETS.items()
		if sheet.enabled and sheet.spreadsheet_id == spreadsheet_id
	}


def get_sheet_by_spreadsheet_id(spreadsheet_id: str) -> SheetConfig | None:
	"""Look up sheet config by Google spreadsheet ID."""
	matching = get_sheets_by_spreadsheet_id(spreadsheet_id)
	for sheet in matching.values():
		return sheet
	return None


# ============================================================================
# POS Folder Watch Configuration
# ============================================================================

# Root folder containing all store POS exports
POS_ROOT_FOLDER_ID = "1z5_26svRHFmrCujWEY4oQH8eEg6d5YqT"
POS_ROOT_FOLDER_NAME = "Operations - ERPNEXT Project"

# Store folders - loaded from JSON or discovered via Drive API
_store_folders_cache: dict[str, FolderConfig] | None = None


def _normalize_store_code(folder_name: str) -> str:
	"""
	Convert folder name to normalized store code.

	Examples:
	    'SM Megamall' -> 'sm_megamall'
	    'Ayala Market! Market!' -> 'ayala_market_market'
	    'D'VERDE' -> 'd_verde'
	"""
	import re

	# Remove special characters, replace spaces/punctuation with underscore
	code = re.sub(r"[^a-zA-Z0-9\s]", "", folder_name)
	code = re.sub(r"\s+", "_", code.strip())
	return code.lower()


def load_store_folders() -> dict[str, FolderConfig]:
	"""
	Load store folder configurations.

	First tries to load from cached JSON file, falls back to empty dict
	(folders will be discovered via Drive API on service startup).
	"""
	global _store_folders_cache

	if _store_folders_cache is not None:
		return _store_folders_cache

	config = get_config()
	json_path = Path(config.db_path).parent / "store_folders.json"

	# Also check local development path
	if not json_path.exists():
		json_path = (
			Path(__file__).parent.parent.parent.parent / "data" / "POS_Extraction" / "store_folders.json"
		)

	if json_path.exists():
		try:
			with open(json_path) as f:
				data = json.load(f)

			_store_folders_cache = {}
			for store in data.get("stores", []):
				# Skip non-store folders
				if store["name"].startswith("01. Sample") or "Finance Validation" in store["name"]:
					continue

				store_code = _normalize_store_code(store["name"])
				_store_folders_cache[store_code] = FolderConfig(
					name=store["name"],
					folder_id=store["folder_id"],
					parent_folder_id=POS_ROOT_FOLDER_ID,
					store_code=store_code,
					owner_email="ops@bebang.ph",
					enabled=True,
					processor="pos",
				)

			return _store_folders_cache
		except Exception as e:
			print(f"Warning: Failed to load store folders from {json_path}: {e}")

	_store_folders_cache = {}
	return _store_folders_cache


def get_watched_folders() -> dict[str, FolderConfig]:
	"""Get all enabled watched folders."""
	folders = load_store_folders()
	return {k: v for k, v in folders.items() if v.enabled}


def get_folder_by_id(folder_id: str) -> FolderConfig | None:
	"""Look up folder config by Google Drive folder ID."""
	for folder in load_store_folders().values():
		if folder.folder_id == folder_id:
			return folder
	return None
