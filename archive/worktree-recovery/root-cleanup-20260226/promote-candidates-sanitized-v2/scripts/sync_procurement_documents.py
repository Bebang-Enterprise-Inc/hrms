"""
Procurement Document Sync — Replaces the Apps Script trigger.

Scans Drive folders for new approved PDFs and writes them to:
1. Documents sheet in Procurement Compliance DB
2. RFP Approved PDF sheet in RFP App Database

Runs via GitHub Actions every 5 minutes (or manually).
Uses service account with domain-wide delegation (sam@bebang.ph).

Equivalent to: Document_Script_Procurement_App > updateDocumentsSheet()
"""

import json
import re
import sys
import os
from datetime import datetime

import httplib2
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Config
SA_FILE = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials", "task-manager-service.json"),
)
IMPERSONATE = "sam@bebang.ph"

PROCUREMENT_DB_ID = "1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q"
RFP_DB_ID = "1-2xvSVhEI1_U_P5s6rG1-LnSvFil7LzJcdjkADeWAcg"

FOLDER_NAMES = [
    "Purchase Requisition PDF",
    "Approved Purchase Orders",
    "Goods Receipts",
    "Supplier Invoices",
    "Approved RFP",
    "Payment Proofs",
]


def get_drive():
    creds = service_account.Credentials.from_service_account_file(
        SA_FILE, scopes=["https://www.googleapis.com/auth/drive"],
    ).with_subject(IMPERSONATE)
    import google_auth_httplib2
    http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http(timeout=60))
    return build("drive", "v3", http=http)


def get_sheets():
    creds = service_account.Credentials.from_service_account_file(
        SA_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"],
    ).with_subject(IMPERSONATE)
    import google_auth_httplib2
    http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http(timeout=60))
    return build("sheets", "v4", http=http)


def extract_date_from_filename(name):
    match = re.search(r'Approved(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', name)
    if match:
        year, mo, d, h, mi, s = match.groups()
        return f"{int(mo)}/{int(d)}/{year} {h}:{mi}:{s}"
    return ""


def find_folder(drive, folder_name):
    results = drive.files().list(
        q=f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id,name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = results.get("files", [])
    return files[0] if files else None


def list_folder_files(drive, folder_id):
    all_files = []
    page_token = None
    while True:
        results = drive.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id,name,webViewLink)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        all_files.extend(results.get("files", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return all_files


def share_file(drive, file_id):
    try:
        drive.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        ).execute()
    except HttpError:
        pass  # Already shared or transient error


def get_existing_names(sheets, spreadsheet_id, sheet_name):
    try:
        data = sheets.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A:A",
        ).execute()
        rows = data.get("values", [])
        return set(row[0] for row in rows[1:] if row)
    except HttpError:
        return set()


def main():
    start = datetime.now()
    print(f"[{start.isoformat()}] Procurement Document Sync starting...")

    drive = get_drive()
    sheets = get_sheets()

    existing_docs = get_existing_names(sheets, PROCUREMENT_DB_ID, "Documents")
    existing_rfp = get_existing_names(sheets, RFP_DB_ID, "RFP Approved PDF")

    new_docs = []
    new_rfp = []

    for folder_name in FOLDER_NAMES:
        folder = find_folder(drive, folder_name)
        if not folder:
            continue

        files = list_folder_files(drive, folder["id"])

        for f in files:
            name = f["name"]

            if name in existing_docs:
                if folder_name == "Approved RFP" and name not in existing_rfp:
                    share_file(drive, f["id"])
                    new_rfp.append([name, f.get("webViewLink", ""), folder_name, extract_date_from_filename(name)])
                    existing_rfp.add(name)
                continue

            share_file(drive, f["id"])
            new_docs.append([name, f.get("webViewLink", ""), folder_name])
            existing_docs.add(name)

            if folder_name == "Approved RFP" and name not in existing_rfp:
                new_rfp.append([name, f.get("webViewLink", ""), folder_name, extract_date_from_filename(name)])
                existing_rfp.add(name)

    if new_docs:
        sheets.spreadsheets().values().append(
            spreadsheetId=PROCUREMENT_DB_ID,
            range="'Documents'!A:C",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": new_docs},
        ).execute()

    if new_rfp:
        sheets.spreadsheets().values().append(
            spreadsheetId=RFP_DB_ID,
            range="'RFP Approved PDF'!A:D",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": new_rfp},
        ).execute()

    elapsed = (datetime.now() - start).total_seconds()
    print(f"[{datetime.now().isoformat()}] Done in {elapsed:.1f}s. "
          f"New documents: {len(new_docs)}, New RFP PDFs: {len(new_rfp)}")

    if new_docs:
        for row in new_docs:
            print(f"  + [{row[2]}] {row[0]}")

    return len(new_docs) + len(new_rfp)


if __name__ == "__main__":
    main()
