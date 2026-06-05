"""S258 Phase 6.8b — Upload Bridge handoff package to Google Drive.

Creates 'BEI COA Handoff' folder (sibling of '2025 Apex Turnover files'),
grants Editor access to known Bridge contacts + BEI finance, uploads all
deliverables. XLSX + DOCX get BOTH native and Google-format versions.
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


SERVICE_ACCOUNT_FILE = "credentials/task-manager-service.json"
IMPERSONATE = "sam@bebang.ph"

FOLDER_NAME = "BEI COA Handoff"
APEX_TURNOVER_FOLDER = "1L32rgBa_NCK66afkcW-oawqBCFo7AWcF"  # 2025 Apex Turnover files (sibling parent for context)

# Editor access list
EDITORS = [
    # Bridge Consulting (from 2025 Apex Turnover folder perms)
    "anna.r@bridge-ph.com",
    "kim.c@bridge-ph.com",
    "flor.a@bridge-ph.com",
    "accountant.outsource@bridge-ph.com",
    # BEI Finance / Stakeholders
    "denise@bebang.ph",
    "anthony@bebang.ph",
    "sheena@bebang.ph",
    "drew@bebang.ph",
]

# Files to upload from output/s258/bridge_handoff/
# (filename, mime_type, convert_to_google_format)
UPLOADS = [
    ("per_company_coa.zip", "application/zip", None),
    ("coa_export_zip_manifest.csv", "text/csv", None),
    ("upload_manifest.json", "application/json", None),
    ("master_reconciliation.xlsx",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", None),
    ("master_reconciliation.xlsx",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
     "application/vnd.google-apps.spreadsheet"),  # Google Sheets convert
    ("SIGNOFF.docx",
     "application/vnd.openxmlformats-officedocument.wordprocessingml.document", None),
    ("SIGNOFF.docx",
     "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
     "application/vnd.google-apps.document"),  # Google Docs convert
    ("validation.md", "text/plain",
     "application/vnd.google-apps.document"),  # MD → Google Doc
    ("BRIDGE_READINESS_ASSESSMENT.md", "text/plain",
     "application/vnd.google-apps.document"),  # Bonus: full assessment
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"],
    ).with_subject(IMPERSONATE)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    # Find or create the BEI COA Handoff folder
    res = drive.files().list(
        q=f"name = '{FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    matches = res.get("files", [])

    if len(matches) == 1:
        folder_id = matches[0]["id"]
        print(f"[OK] Using existing folder: {FOLDER_NAME} id={folder_id}")
    elif len(matches) == 0:
        # Create new folder under root (same level as 2025 Apex Turnover)
        meta = {
            "name": FOLDER_NAME,
            "mimeType": "application/vnd.google-apps.folder",
            "description": "S258 Chart of Accounts handoff for Bridge Consulting QBO migration. Generated 2026-06-04 from BEI ERP sprint S258.",
        }
        folder = drive.files().create(body=meta, fields="id", supportsAllDrives=True).execute()
        folder_id = folder["id"]
        print(f"[OK] Created folder: {FOLDER_NAME} id={folder_id}")
    else:
        print(f"[STOP] {len(matches)} folders match name {FOLDER_NAME!r}; ambiguous")
        for m in matches:
            print(f"  id={m['id']} name={m['name']!r}")
        sys.exit(1)

    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
    print(f"     {folder_url}")

    # Grant access to editors (idempotent — skip on 409 duplicate)
    print("\n=== Granting editor access ===")
    for email in EDITORS:
        try:
            drive.permissions().create(
                fileId=folder_id,
                body={"type": "user", "role": "writer", "emailAddress": email},
                sendNotificationEmail=False,
                supportsAllDrives=True,
            ).execute()
            print(f"  [OK] writer: {email}")
        except HttpError as e:
            if "duplicate" in str(e).lower() or "already" in str(e).lower() or e.resp.status == 409:
                print(f"  [SKIP] already shared: {email}")
            else:
                print(f"  [ERR] {email}: {e}")

    # Upload files
    print("\n=== Uploading files ===")
    base = Path("output/s258")
    bh = base / "bridge_handoff"
    uploaded = []
    for fname, mime, convert_to in UPLOADS:
        # Resolve path — most are in bridge_handoff/, BRIDGE_READINESS_ASSESSMENT is in output/s258/
        if fname == "BRIDGE_READINESS_ASSESSMENT.md":
            src = base / fname
        else:
            src = bh / fname
        if not src.exists():
            print(f"  [SKIP] {src} missing")
            continue

        # Build name with suffix to disambiguate native vs Google-format
        target_name = fname
        if convert_to:
            if convert_to.endswith("spreadsheet"):
                target_name = fname.replace(".xlsx", " (Google Sheets)")
            elif convert_to.endswith("document"):
                if fname.endswith(".docx"):
                    target_name = fname.replace(".docx", " (Google Doc)")
                elif fname.endswith(".md"):
                    target_name = fname.replace(".md", "") + " (Google Doc)"
        body = {"name": target_name, "parents": [folder_id]}
        if convert_to:
            body["mimeType"] = convert_to

        media = MediaFileUpload(str(src), mimetype=mime, resumable=False)
        try:
            f = drive.files().create(
                body=body, media_body=media,
                fields="id, name, webViewLink, mimeType",
                supportsAllDrives=True,
            ).execute()
            kind = "Google" if convert_to else "Native"
            print(f"  [OK] {kind} | {f['name']!r} → {f['webViewLink']}")
            uploaded.append({"name": f["name"], "url": f["webViewLink"],
                             "mime": f["mimeType"], "id": f["id"]})
        except HttpError as e:
            print(f"  [ERR] {fname}: {e}")

    # Write index
    index = {
        "folder_id": folder_id,
        "folder_url": folder_url,
        "folder_name": FOLDER_NAME,
        "editors": EDITORS,
        "files": uploaded,
        "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (base / "bridge_handoff" / "drive_upload_index.json").write_text(json.dumps(index, indent=2))
    print(f"\n[OK] Wrote drive_upload_index.json")
    print(f"\nFolder URL: {folder_url}")
    print(f"Uploaded: {len(uploaded)} files")


if __name__ == "__main__":
    main()
