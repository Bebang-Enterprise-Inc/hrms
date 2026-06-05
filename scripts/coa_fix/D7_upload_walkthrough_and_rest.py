"""Upload WALKTHROUGH + COMPANY_REGISTER + migration maps to existing Drive folder."""
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
FOLDER_ID = "1GnrFKICFYN6xz9IKeAFCM0xYtFN02OcE"  # BEI COA Handoff folder

UPLOADS = [
    # (src_path, mime, convert_to_google_format)
    ("output/s258/bridge_handoff/WALKTHROUGH.docx",
     "application/vnd.openxmlformats-officedocument.wordprocessingml.document", None),
    ("output/s258/bridge_handoff/WALKTHROUGH.docx",
     "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
     "application/vnd.google-apps.document"),
    ("output/s258/bridge_handoff/COMPANY_REGISTER.xlsx",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", None),
    ("output/s258/bridge_handoff/COMPANY_REGISTER.xlsx",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
     "application/vnd.google-apps.spreadsheet"),
    ("tmp/s258/migration_map_BEI.csv", "text/csv", None),
    ("tmp/s258/migration_map_BKI.csv", "text/csv", None),
    ("tmp/s258/migration_map_III.csv", "text/csv", None),
    # Also upload DECISIONS.md as Google Doc for the full policy ledger
    ("data/_CONSOLIDATED/01_FINANCE/DECISIONS.md", "text/plain",
     "application/vnd.google-apps.document"),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"],
    ).with_subject(IMPERSONATE)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    uploaded = []
    for src, mime, convert_to in UPLOADS:
        p = Path(src)
        if not p.exists():
            print(f"  [SKIP] {p} missing")
            continue
        name = p.name
        if convert_to:
            if convert_to.endswith("document"):
                if name.endswith(".docx"):
                    name = name.replace(".docx", " (Google Doc)")
                elif name.endswith(".md"):
                    name = name.replace(".md", "") + " (Google Doc)"
            elif convert_to.endswith("spreadsheet"):
                name = name.replace(".xlsx", " (Google Sheets)")
        body = {"name": name, "parents": [FOLDER_ID]}
        if convert_to:
            body["mimeType"] = convert_to
        media = MediaFileUpload(str(p), mimetype=mime, resumable=False)
        try:
            f = drive.files().create(
                body=body, media_body=media,
                fields="id, name, webViewLink, mimeType",
                supportsAllDrives=True,
            ).execute()
            kind = "Google" if convert_to else "Native"
            print(f"  [OK] {kind} | {f['name']!r}")
            print(f"           {f['webViewLink']}")
            uploaded.append({"name": f["name"], "url": f["webViewLink"], "id": f["id"]})
        except HttpError as e:
            print(f"  [ERR] {src}: {e}")

    # Append to existing drive_upload_index.json
    idx_path = "output/s258/bridge_handoff/drive_upload_index.json"
    try:
        idx = json.load(open(idx_path))
    except FileNotFoundError:
        idx = {"folder_id": FOLDER_ID, "files": []}
    idx["files"].extend(uploaded)
    idx["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    open(idx_path, "w").write(json.dumps(idx, indent=2))
    print(f"\n[OK] Updated {idx_path}")
    print(f"     Newly uploaded: {len(uploaded)} files")


if __name__ == "__main__":
    main()
