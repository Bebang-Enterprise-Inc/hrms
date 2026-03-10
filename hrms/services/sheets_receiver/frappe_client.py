"""
Frappe/ERPNext API client for Sheets Receiver.

Handles syncing data to ERPNext via REST API.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import SheetConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
	"""Result of a sync operation."""

	success: bool
	rows_processed: int = 0
	rows_created: int = 0
	rows_updated: int = 0
	rows_failed: int = 0
	errors: list[str] | None = None

	def __post_init__(self):
		if self.errors is None:
			self.errors = []


class FrappeClient:
	"""Client for Frappe REST API."""

	def __init__(self):
		config = get_config()
		self.base_url = config.frappe_url.rstrip("/")
		self.api_key = config.frappe_api_key
		self.api_secret = config.frappe_api_secret
		self.request_timeout = config.frappe_request_timeout_seconds

		# Set up session with retry logic
		self.session = requests.Session()
		retry = Retry(
			total=config.sync_retry_attempts, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504]
		)
		adapter = HTTPAdapter(max_retries=retry)
		self.session.mount("https://", adapter)
		self.session.mount("http://", adapter)

		# Set auth headers
		self.session.headers.update(
			{"Authorization": f"token {self.api_key}:{self.api_secret}", "Content-Type": "application/json"}
		)

	def _request(
		self,
		method: str,
		endpoint: str,
		data: dict[str, Any] | None = None,
		params: dict[str, Any] | None = None,
	) -> dict[str, Any]:
		"""Make authenticated request to Frappe API."""
		url = f"{self.base_url}{endpoint}"

		try:
			response = self.session.request(
				method=method,
				url=url,
				json=data,
				params=params,
				timeout=self.request_timeout,
			)
			response.raise_for_status()
			return response.json()

		except requests.exceptions.RequestException as e:
			logger.error(f"Frappe API error: {method} {endpoint} - {e}")
			raise

	def get_doc(self, doctype: str, name: str) -> dict[str, Any] | None:
		"""Get a single document."""
		try:
			result = self._request("GET", f"/api/resource/{doctype}/{name}")
			return result.get("data")
		except requests.exceptions.HTTPError as e:
			if e.response.status_code == 404:
				return None
			raise

	def create_doc(self, doctype: str, data: dict[str, Any]) -> dict[str, Any]:
		"""Create a new document."""
		result = self._request("POST", f"/api/resource/{doctype}", data=data)
		return result.get("data", {})

	def update_doc(self, doctype: str, name: str, data: dict[str, Any]) -> dict[str, Any]:
		"""Update an existing document."""
		result = self._request("PUT", f"/api/resource/{doctype}/{name}", data=data)
		return result.get("data", {})

	def call_method(self, method: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
		"""Call a whitelisted Frappe method."""
		endpoint = f"/api/method/{method}"
		result = self._request("POST", endpoint, data=data or {})
		return result.get("message", result)

	def sync_sheet_data(
		self,
		sheet_config: SheetConfig,
		data: list[dict[str, Any]],
		checksum: str,
		related_data: dict[str, list[dict[str, Any]]] | None = None,
	) -> SyncResult:
		"""
		Sync sheet data to Frappe using the configured endpoint.

		Args:
		    sheet_config: Configuration for this sheet
		    data: List of row dictionaries
		    checksum: Data checksum for change detection

		Returns:
		    SyncResult with statistics
		"""
		try:
			# Call the sync endpoint with the data
			payload = {
				"sheet_name": sheet_config.name,
				"sheet_tab_name": sheet_config.sheet_name,
				"data": data,
				"checksum": checksum,
				"sync_mode": sheet_config.sync_mode,
				"key_column": sheet_config.key_column,
			}
			if related_data:
				payload["related_data"] = related_data

			result = self.call_method(sheet_config.sync_endpoint.replace("/api/method/", ""), data=payload)

			return SyncResult(
				success=True,
				rows_processed=result.get("rows_processed", len(data)),
				rows_created=result.get("rows_created", 0),
				rows_updated=result.get("rows_updated", 0),
				rows_failed=result.get("rows_failed", 0),
				errors=result.get("errors", []),
			)

		except Exception as e:
			logger.error(f"Sync failed for {sheet_config.name}: {e}")
			return SyncResult(success=False, rows_processed=len(data), errors=[str(e)])

	def sync_batch(
		self, doctype: str, data: list[dict[str, Any]], key_field: str, batch_size: int = 100
	) -> SyncResult:
		"""
		Batch upsert records to a DocType.

		Args:
		    doctype: Target DocType
		    data: List of records
		    key_field: Field to use for matching existing records
		    batch_size: Records per batch

		Returns:
		    SyncResult with statistics
		"""
		result = SyncResult(success=True, rows_processed=len(data))

		for i in range(0, len(data), batch_size):
			batch = data[i : i + batch_size]

			for record in batch:
				try:
					key_value = record.get(key_field)
					if not key_value:
						result.errors.append(f"Missing key field {key_field}")
						result.rows_failed += 1
						continue

					# Check if exists
					existing = self.get_doc(doctype, key_value)

					if existing:
						self.update_doc(doctype, key_value, record)
						result.rows_updated += 1
					else:
						self.create_doc(doctype, record)
						result.rows_created += 1

				except Exception as e:
					result.errors.append(f"{key_value}: {e!s}")
					result.rows_failed += 1

			# Small delay between batches to avoid overwhelming the server
			time.sleep(0.1)

		result.success = result.rows_failed == 0
		return result

	def send_notification(
		self,
		title: str,
		message: str,
		user: str = "Administrator",
		doctype: str | None = None,
		docname: str | None = None,
	):
		"""Send a Frappe notification."""
		try:
			self.call_method(
				"frappe.client.send_alert", {"message": message, "title": title, "indicator": "blue"}
			)
		except Exception as e:
			logger.warning(f"Failed to send notification: {e}")


# Singleton instance
_client: FrappeClient | None = None


def get_frappe_client() -> FrappeClient:
	"""Get Frappe client instance."""
	global _client
	if _client is None:
		_client = FrappeClient()
	return _client
