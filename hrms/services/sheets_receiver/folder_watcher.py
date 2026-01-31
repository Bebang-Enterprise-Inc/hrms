"""
Google Drive Folder Watcher for POS File Processing.

Watches store folders for new file uploads and queues them for processing.
Uses Google Drive Watch API with auto-renewal (24h expiry).
"""

import io
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

from .config import (
    get_config,
    get_watched_folders,
    get_folder_by_id,
    FolderConfig,
    POS_ROOT_FOLDER_ID,
    POS_ROOT_FOLDER_NAME,
    load_store_folders,
)
from .models import get_db

logger = logging.getLogger(__name__)


class FolderWatcher:
    """
    Manages Google Drive folder watches for POS file processing.

    Watches 42+ store folders and detects new file uploads.
    """

    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
    ]

    def __init__(self):
        config = get_config()
        self.config = config

        self.credentials = service_account.Credentials.from_service_account_file(
            config.service_account_file,
            scopes=self.SCOPES
        ).with_subject(config.impersonate_user)

        self._drive_service = None

    @property
    def drive(self):
        """Lazy-load Drive API service."""
        if self._drive_service is None:
            self._drive_service = build('drive', 'v3', credentials=self.credentials)
        return self._drive_service

    # =========================================================================
    # Folder Discovery
    # =========================================================================

    def list_subfolders(self, parent_folder_id: str) -> List[Dict[str, str]]:
        """
        List all subfolders in a folder.

        Args:
            parent_folder_id: Google Drive folder ID

        Returns:
            List of {id, name} dicts for each subfolder
        """
        try:
            results = self.drive.files().list(
                q=f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'",
                fields="files(id, name)",
                pageSize=100,
                orderBy="name",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="allDrives"
            ).execute()

            return results.get('files', [])

        except HttpError as e:
            logger.error(f"Failed to list subfolders for {parent_folder_id}: {e}")
            raise

    def discover_store_folders(self) -> Dict[str, FolderConfig]:
        """
        Discover all store folders from Google Drive.

        Used on first startup to populate store folder config.
        """
        from .config import _normalize_store_code

        folders = self.list_subfolders(POS_ROOT_FOLDER_ID)

        configs = {}
        for folder in folders:
            # Skip non-store folders
            if folder["name"].startswith("01. Sample") or "Finance Validation" in folder["name"]:
                continue

            store_code = _normalize_store_code(folder["name"])
            configs[store_code] = FolderConfig(
                name=folder["name"],
                folder_id=folder["id"],
                parent_folder_id=POS_ROOT_FOLDER_ID,
                store_code=store_code,
                owner_email="ops@bebang.ph",
                enabled=True,
                processor="pos"
            )

        logger.info(f"Discovered {len(configs)} store folders")
        return configs

    # =========================================================================
    # Watch Management
    # =========================================================================

    def create_folder_watch(self, folder_id: str, folder_name: str, store_code: str) -> Dict[str, Any]:
        """
        Create a Drive push notification watch for a folder.

        Watches expire after 24 hours and must be renewed.

        Args:
            folder_id: Google Drive folder ID
            folder_name: Human-readable folder name
            store_code: Normalized store identifier

        Returns:
            Watch channel info dict
        """
        config = self.config
        channel_id = str(uuid.uuid4())

        # Expiration: 24 hours from now (Google's max)
        expiration_time = datetime.utcnow() + timedelta(hours=config.watch_expiry_hours)
        expiration_ms = int(expiration_time.timestamp() * 1000)

        # Use folder-specific webhook path
        webhook_url = config.public_webhook_url.replace("/sheets", "/folder")

        try:
            result = self.drive.files().watch(
                fileId=folder_id,
                supportsAllDrives=True,
                body={
                    'id': channel_id,
                    'type': 'web_hook',
                    'address': webhook_url,
                    'expiration': expiration_ms,
                }
            ).execute()

            watch_info = {
                'channel_id': channel_id,
                'folder_id': folder_id,
                'folder_name': folder_name,
                'store_code': store_code,
                'resource_id': result.get('resourceId', ''),
                'expiration': expiration_time,
                'created_at': datetime.utcnow()
            }

            # Save to database
            db = get_db()
            db.save_folder_watch(watch_info)

            logger.info(f"Created watch for folder '{folder_name}' ({folder_id}), "
                       f"expires in {config.watch_expiry_hours}h")

            return watch_info

        except HttpError as e:
            logger.error(f"Failed to create watch for folder {folder_id}: {e}")
            raise

    def stop_folder_watch(self, channel_id: str, resource_id: str):
        """Stop a Drive watch channel for a folder."""
        try:
            self.drive.channels().stop(body={
                'id': channel_id,
                'resourceId': resource_id
            }).execute()

            db = get_db()
            db.delete_folder_watch(channel_id)

            logger.info(f"Stopped folder watch channel {channel_id}")

        except HttpError as e:
            if e.resp.status != 404:
                logger.error(f"Failed to stop folder watch {channel_id}: {e}")

    def setup_all_folder_watches(self) -> List[Dict[str, Any]]:
        """
        Set up watches for all configured store folders.

        Returns:
            List of watch info dicts
        """
        watches = []
        db = get_db()
        folders = get_watched_folders()

        if not folders:
            # Discover folders if not loaded
            logger.info("No folders configured, discovering from Drive...")
            folders = self.discover_store_folders()

        for store_code, folder_config in folders.items():
            # Check if watch already exists and is valid
            existing = db.get_folder_watch(folder_config.folder_id)
            if existing and not self._is_watch_expired(existing):
                hours_remaining = self._hours_until_expiry(existing)
                if hours_remaining > 2:
                    logger.info(f"Watch for {folder_config.name} still valid "
                               f"({hours_remaining:.1f}h remaining)")
                    watches.append(existing)
                    continue

            # Create new watch
            try:
                watch = self.create_folder_watch(
                    folder_config.folder_id,
                    folder_config.name,
                    store_code
                )
                watches.append(watch)
            except Exception as e:
                logger.error(f"Failed to set up watch for {folder_config.name}: {e}")

        logger.info(f"Set up {len(watches)} folder watches")
        return watches

    def renew_expiring_folder_watches(self, hours_before: int = 2) -> List[Dict[str, Any]]:
        """Renew folder watches that are about to expire."""
        db = get_db()
        expiring = db.get_expiring_folder_watches(hours=hours_before)

        renewed = []
        for old_watch in expiring:
            try:
                # Stop old watch
                self.stop_folder_watch(old_watch['channel_id'], old_watch['resource_id'])

                # Create new watch
                new_watch = self.create_folder_watch(
                    old_watch['folder_id'],
                    old_watch['folder_name'],
                    old_watch.get('store_code', '')
                )
                renewed.append(new_watch)

                logger.info(f"Renewed watch for folder {old_watch['folder_name']}")

            except Exception as e:
                logger.error(f"Failed to renew folder watch for {old_watch['folder_name']}: {e}")

        return renewed

    def _is_watch_expired(self, watch: Dict) -> bool:
        """Check if a watch has expired."""
        expiration = watch.get('expiration')
        if isinstance(expiration, str):
            expiration = datetime.fromisoformat(expiration)
        return datetime.utcnow() > expiration

    def _hours_until_expiry(self, watch: Dict) -> float:
        """Calculate hours until watch expires."""
        expiration = watch.get('expiration')
        if isinstance(expiration, str):
            expiration = datetime.fromisoformat(expiration)
        delta = expiration - datetime.utcnow()
        return delta.total_seconds() / 3600

    # =========================================================================
    # File Detection & Download
    # =========================================================================

    def list_new_files(
        self,
        folder_id: str,
        since: Optional[datetime] = None,
        file_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List files in folder, optionally filtered by modification time.

        Args:
            folder_id: Google Drive folder ID
            since: Only return files modified after this time
            file_types: List of MIME types to include (default: Excel, PDF)

        Returns:
            List of file info dicts
        """
        if file_types is None:
            file_types = [
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
                'application/vnd.ms-excel',  # .xls
                'application/pdf',
            ]

        # Build query
        query_parts = [f"'{folder_id}' in parents", "trashed = false"]

        if since:
            query_parts.append(f"modifiedTime > '{since.isoformat()}Z'")

        if file_types:
            type_clauses = [f"mimeType = '{t}'" for t in file_types]
            query_parts.append(f"({' or '.join(type_clauses)})")

        query = " and ".join(query_parts)

        try:
            results = self.drive.files().list(
                q=query,
                fields="files(id, name, mimeType, modifiedTime, size, md5Checksum)",
                orderBy="modifiedTime desc",
                pageSize=100,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="allDrives"
            ).execute()

            return results.get('files', [])

        except HttpError as e:
            logger.error(f"Failed to list files in folder {folder_id}: {e}")
            raise

    def download_file(self, file_id: str, dest_path: Path) -> Path:
        """
        Download a file from Google Drive.

        Args:
            file_id: Google Drive file ID
            dest_path: Local path to save file

        Returns:
            Path to downloaded file
        """
        try:
            request = self.drive.files().get_media(fileId=file_id)

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            with open(dest_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.debug(f"Download {int(status.progress() * 100)}%")

            logger.info(f"Downloaded file to {dest_path}")
            return dest_path

        except HttpError as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            raise

    def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get metadata for a file."""
        try:
            return self.drive.files().get(
                fileId=file_id,
                fields="id, name, mimeType, modifiedTime, size, md5Checksum, parents",
                supportsAllDrives=True
            ).execute()

        except HttpError as e:
            logger.error(f"Failed to get metadata for file {file_id}: {e}")
            raise


# Singleton instance
_watcher: Optional[FolderWatcher] = None


def get_folder_watcher() -> FolderWatcher:
    """Get FolderWatcher instance."""
    global _watcher
    if _watcher is None:
        _watcher = FolderWatcher()
    return _watcher
