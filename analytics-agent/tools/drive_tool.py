"""Google Drive upload tool for BEI Analytics Agent.

Uses service account with Domain-Wide Delegation to upload files
to Google Drive as sam@bebang.ph.
"""

import mimetypes
import os
from typing import Any

from claude_agent_sdk import tool
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_CREDENTIALS_PATH", "credentials/task-manager-service.json"
)
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
async def upload_to_drive(args: dict[str, Any]) -> dict[str, Any]:
    """Upload a local file to Google Drive and share it (anyone with link)."""
    file_path = args["file_path"]
    folder_id = args.get("folder_id", "")
    filename = args.get("filename", "")

    if not os.path.isfile(file_path):
        return {
            "content": [{"type": "text", "text": f"Error: File not found: {file_path}"}],
            "is_error": True,
        }

    if not filename:
        filename = os.path.basename(file_path)

    # Detect MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = "application/octet-stream"

    try:
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
            "content": [
                {
                    "type": "text",
                    "text": f"Uploaded to Google Drive: {filename} (ID: {file_id})\nLink: {web_view_link}",
                }
            ]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error uploading to Drive: {e}"}],
            "is_error": True,
        }


async def upload_to_drive_impl(args: dict[str, Any]) -> dict[str, Any]:
    """Plain async function for the direct Anthropic API agentic loop."""
    return await upload_to_drive(args)
