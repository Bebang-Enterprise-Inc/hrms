"""Google Drive upload tool for BEI Analytics Agent.

Uses service account with Domain-Wide Delegation to upload files
to Google Drive as sam@bebang.ph.
"""

import mimetypes
import os

from claude_agent_sdk import tool
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

CREDENTIALS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
DELEGATED_USER = "sam@bebang.ph"
SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_drive_service():
    """Build an authenticated Drive v3 service using DWD impersonation."""
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES
    )
    creds = creds.with_subject(DELEGATED_USER)
    return build("drive", "v3", credentials=creds)


@tool(
    "upload_to_drive",
    "Upload file to Google Drive shared folder",
    {
        "file_path": str,
        "folder_id": str,
        "filename": str,
    },
)
def upload_to_drive(
    file_path: str,
    folder_id: str = "",
    filename: str = "",
) -> dict:
    """Upload a local file to Google Drive and share it (anyone with link).

    Args:
        file_path: Local path to the file to upload.
        folder_id: Google Drive folder ID. Empty string means root.
        filename: Name for the file in Drive. Defaults to the local filename.

    Returns:
        Dict with file_id, web_view_link, and filename.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not filename:
        filename = os.path.basename(file_path)

    # Detect MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = "application/octet-stream"

    service = _get_drive_service()

    # Build file metadata
    file_metadata: dict = {"name": filename}
    if folder_id:
        file_metadata["parents"] = [folder_id]

    # Upload
    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
    created = (
        service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink",
        )
        .execute()
    )

    file_id = created["id"]
    web_view_link = created.get("webViewLink", "")

    # Share: anyone with the link can view
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id",
    ).execute()

    # Re-fetch link in case it wasn't populated before sharing
    if not web_view_link:
        updated = (
            service.files()
            .get(fileId=file_id, fields="webViewLink")
            .execute()
        )
        web_view_link = updated.get("webViewLink", "")

    return {
        "file_id": file_id,
        "web_view_link": web_view_link,
        "filename": filename,
    }
