import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, ClassVar

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import get_config, get_watched_sheets
from .models import WatchChannel, get_db

logger = logging.getLogger(__name__)


class SheetsClient:
	"""Client for Google Sheets and Drive APIs."""

	SCOPES: ClassVar[list[str]] = [
		"https://www.googleapis.com/auth/spreadsheets.readonly",
		"https://www.googleapis.com/auth/drive.readonly",
	]

	def __init__(self):
		config = get_config()
		self.config = config

		self.credentials = service_account.Credentials.from_service_account_file(
			config.service_account_file, scopes=self.SCOPES
		).with_subject(config.impersonate_user)

		self._sheets_service = None
		self._drive_service = None

	@property
	def sheets(self):
		"""Lazy-load Sheets API service."""
		if self._sheets_service is None:
			self._sheets_service = build("sheets", "v4", credentials=self.credentials)
		return self._sheets_service

	@property
	def drive(self):
		"""Lazy-load Drive API service."""
		if self._drive_service is None:
			self._drive_service = build("drive", "v3", credentials=self.credentials)
		return self._drive_service

	def fetch_sheet_values(self, spreadsheet_id: str, range_name: str) -> tuple[list[list[Any]], str]:
		"""Fetch raw sheet values and return them with a checksum."""
		try:
			result = (
				self.sheets.spreadsheets()
				.values()
				.get(
					spreadsheetId=spreadsheet_id,
					range=range_name,
					valueRenderOption="UNFORMATTED_VALUE",  # Critical for numbers/dates
					dateTimeRenderOption="FORMATTED_STRING",
				)
				.execute()
			)

			rows = result.get("values", [])
			return rows, self.compute_checksum(rows)

		except HttpError as e:
			logger.error(f"Failed to fetch sheet {spreadsheet_id}: {e}")
			raise

	def fetch_sheet_data(
		self, spreadsheet_id: str, range_name: str, include_headers: bool = True
	) -> tuple[list[dict[str, Any]], str]:
		"""
		Fetch sheet data and return as list of dicts with checksum.

		Args:
		    spreadsheet_id: Google Spreadsheet ID
		    range_name: A1 notation range (e.g., "Sheet1!A:Z")
		    include_headers: If True, first row is headers

		Returns:
		    Tuple of (list of row dicts, data checksum)
		"""
		rows, _raw_checksum = self.fetch_sheet_values(spreadsheet_id, range_name)
		if not rows:
			return [], self.compute_checksum([])

		if include_headers:
			headers = [str(h).strip().lower().replace(" ", "_") for h in rows[0]]
			data = []
			for row in rows[1:]:
				# Pad row to match headers length
				padded = row + [""] * (len(headers) - len(row))
				data.append(dict(zip(headers, padded, strict=False)))
		else:
			data = [{"col_" + str(i): v for i, v in enumerate(row)} for row in rows]

		checksum = self.compute_checksum(data)
		return data, checksum

	def get_spreadsheet_metadata(self, spreadsheet_id: str) -> dict[str, Any]:
		"""Get spreadsheet title and sheet names."""
		try:
			meta = (
				self.sheets.spreadsheets()
				.get(spreadsheetId=spreadsheet_id, fields="properties.title,sheets.properties.title")
				.execute()
			)

			return {
				"title": meta["properties"]["title"],
				"sheets": [s["properties"]["title"] for s in meta.get("sheets", [])],
			}
		except HttpError as e:
			logger.error(f"Failed to get metadata for {spreadsheet_id}: {e}")
			raise

	def get_file_modified_time(self, file_id: str) -> datetime:
		"""Get last modified time of a Drive file."""
		try:
			file = (
				self.drive.files()
				.get(fileId=file_id, fields="modifiedTime", supportsAllDrives=True)
				.execute()
			)

			return datetime.fromisoformat(file["modifiedTime"].replace("Z", "+00:00"))
		except HttpError as e:
			logger.error(f"Failed to get modified time for {file_id}: {e}")
			raise

	# Watch Management
	def create_watch(self, spreadsheet_id: str, spreadsheet_name: str) -> WatchChannel:
		"""
		Create a Drive push notification watch for a file.

		Watches expire after 24 hours and must be renewed.
		"""
		config = self.config
		channel_id = str(uuid.uuid4())

		# Expiration: 24 hours from now (Google's max)
		expiration_time = datetime.utcnow() + timedelta(hours=config.watch_expiry_hours)
		expiration_ms = int(expiration_time.timestamp() * 1000)

		try:
			result = (
				self.drive.files()
				.watch(
					fileId=spreadsheet_id,
					supportsAllDrives=True,
					body={
						"id": channel_id,
						"type": "web_hook",
						"address": config.public_webhook_url,
						"expiration": expiration_ms,
					},
				)
				.execute()
			)

			watch = WatchChannel(
				channel_id=channel_id,
				spreadsheet_id=spreadsheet_id,
				spreadsheet_name=spreadsheet_name,
				resource_id=result.get("resourceId", ""),
				expiration=expiration_time,
			)

			# Save to database
			db = get_db()
			db.save_watch(watch)

			logger.info(
				f"Created watch for {spreadsheet_name} ({spreadsheet_id}), "
				f"expires in {config.watch_expiry_hours}h"
			)

			return watch

		except HttpError as e:
			logger.error(f"Failed to create watch for {spreadsheet_id}: {e}")
			raise

	def stop_watch(self, channel_id: str, resource_id: str):
		"""Stop a Drive watch channel."""
		try:
			self.drive.channels().stop(body={"id": channel_id, "resourceId": resource_id}).execute()

			# Remove from database
			db = get_db()
			db.delete_watch(channel_id)

			logger.info(f"Stopped watch channel {channel_id}")

		except HttpError as e:
			# 404 is expected if channel already expired
			if e.resp.status != 404:
				logger.error(f"Failed to stop watch {channel_id}: {e}")

	def setup_all_watches(self) -> list[WatchChannel]:
		"""Set up watches for all configured sheets."""
		watches = []
		db = get_db()

		for sheet_config in get_watched_sheets().values():
			# Check if watch already exists and is valid
			existing = db.get_watch(sheet_config.spreadsheet_id)
			if existing and not existing.is_expired and existing.hours_until_expiry > 2:
				logger.info(
					f"Watch for {sheet_config.name} still valid "
					f"({existing.hours_until_expiry:.1f}h remaining)"
				)
				watches.append(existing)
				continue

			# Create new watch
			try:
				watch = self.create_watch(sheet_config.spreadsheet_id, sheet_config.name)
				watches.append(watch)
			except Exception as e:
				logger.error(f"Failed to set up watch for {sheet_config.name}: {e}")

		return watches

	def renew_expiring_watches(self, hours_before: int = 2) -> list[WatchChannel]:
		"""Renew watches that are about to expire."""
		db = get_db()
		expiring = db.get_expiring_watches(hours=hours_before)

		renewed = []
		for old_watch in expiring:
			try:
				# Stop old watch
				self.stop_watch(old_watch.channel_id, old_watch.resource_id)

				# Create new watch
				new_watch = self.create_watch(old_watch.spreadsheet_id, old_watch.spreadsheet_name)
				renewed.append(new_watch)

				logger.info(f"Renewed watch for {old_watch.spreadsheet_name}")

			except Exception as e:
				logger.error(f"Failed to renew watch for {old_watch.spreadsheet_name}: {e}")

		return renewed

	def compute_checksum(self, data: Any) -> str:
		"""Compute MD5 checksum of data for change detection."""
		content = json.dumps(data, sort_keys=True, default=str)
		return hashlib.md5(content.encode()).hexdigest()


# Singleton instance
_client: SheetsClient | None = None


def get_sheets_client() -> SheetsClient:
	"""Get Sheets client instance."""
	global _client
	if _client is None:
		_client = SheetsClient()
	return _client
