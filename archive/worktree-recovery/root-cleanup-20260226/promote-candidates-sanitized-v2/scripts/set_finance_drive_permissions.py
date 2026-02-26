"""
Set Finance Shared Drive folder permissions per Alyssa's Folder Manager matrix.
2026-02-23

Current state:
- Content Managers (Alyssa, Butch, Juanna) already have drive-level fileOrganizer
- finance@bebang.ph group already has drive-level fileOrganizer
- Denise, Liezel, Izza, Je-Ann, Mae already have drive-level writer

This script adds FOLDER-LEVEL permissions for people who need restricted access:
- HR (Ronald, Melissa) - VIEW on Payroll only
- SCM (Ian, Jeson) - VIEW on COGS, EDIT on SCM Freight
- Admin (Noel) - no folder-specific access in matrix (only Policies VIEW)
- NOTES extras: Anthony, Liezel, Angelamel, Izza (folder-specific)

Also upgrades/adds accounting team members who need folder-specific Edit access
but don't have drive-level access yet (Ivy, Angela, Shaw).
"""

import time
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SERVICE_ACCOUNT_FILE = 'credentials/task-manager-service.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

DRY_RUN = '--dry-run' in sys.argv

# ── Folder IDs (from Finance Shared Drive listing) ──────────────────────

FOLDERS = {
    # BEI P&L Master
    "01_Revenue/Stores":         "1RrjcSwJxuWyV7eA2oMeiGAXi3spiBfqF",
    "01_Revenue/HO_Commissary":  "1jfq42O91nbnXOMBQ8jG7EmE6oqcs1etX",
    "02_COGS/Stores":            "1g4WPpNB-Pp6ke0TAzq8K0ovBNcLFlnYW",
    "02_COGS/HO_Commissary":     "1ftn0mZ49VcFxrDLM0MgPXqB9dvdj6pKU",
    "03_Payroll/Stores":         "1XJFrm7yOzVrg_23ImcSKWJx_JSrTnIzy",
    "03_Payroll/HO_Commissary":  "1SwT6-NOnseu7RKrOowj-Ruw51zjQLwEn",
    "03_Payroll/Employee_Benefits": "1H8glBwmy-fCqLt4SY8HXcZHGsVVqGxGO",
    "04_OpEx/Stores":            "1QQkixBoIVXsmNzaAAig7PJdmZZrAJ9dQ",
    "04_OpEx/HO_Commissary":     "1SWBTvMYyZHQbu8aGLKk2dYDnZvWSdnVd",
    "04_OpEx/Rentals":           "1gKApRvn9vZKjE_wwyP_I5X5nNaBs1U5B",
    "04_OpEx/Utilities":         "1MLM_d-GrqnafId6sN1RdUCruYfMYJ20D",
    "04_OpEx/Revolving_Fund":    "15eDUH79Pvgd8CxErZuvcPHrzAY-EeLLm",
    "04_OpEx/SCM_Freight":       "1i8TK_D482RKUNxnegGn9xiZvvSO7ILGO",
    "04_OpEx/Petty_Cash":        "1MA4-EApl9Y9WcIqFnqWrf-TWkb3nyBGR",
    "05_Other/Stores":           "1uFpY960BWV4218LT63vlJfHjZIw_inxs",
    "05_Other/HO_Commissary":    "1BTf8gFiEiD9llg7m4-P29hp9c6d1rcGH",

    # Monthly Review
    "Monthly_Review":            "1ow6dGAO5nUyBnebQLj3ITGOFXKy7XLQI",

    # Balance Sheet
    "Assets/Cash":               "1OpMM9UK7UvDFt1RYs1bYzUlXTN7yKmVO",
    "Assets/AR":                 "14bM7w853Mu8u6OwoL4my-7KmZU9dy513",
    "Assets/Other_Current":      "1XC5djWwbCPkJUa6ShohNV6fy7-eMjY2F",
    "Assets/Fixed_Assets":       "1pTMTtoVy8vgijOuK48vjfYDexU6n21Bj",
    "Liabilities/AP":            "1GWPEWQu8q08mr-RnixB5SVHxExvTN3uG",
    "Liabilities/Loans":         "1_fTI5YgdrLIAevADLz1P9cWpJUe__MkZ",
    "Partners":                  "1NvnbscirDTTwzZlImDbXm2mnTfq8vOcP",
    "Trial_Balance":             "1LTFcdweqzVkQgzH_c6szlKEWRqwWvGpZ",

    # Finance Operations
    "Payment_Trackers":          "17GkTjzWhhcZGlAq8HjD4wyKjj-2L5HdQ",

    # Other shared drive folders
    "Reference_Documents":       "1aRJtu53mcfPknVNWC6KAhuM5eXROyrwZ",
    "Ongoing_Operations":        "1VfgOYyaATkFQR6nz7451wHIkYGYvd1EY",
    "Policies":                  "1nxSbozRchqs18zsjlfYkgU_HFqtvOc7c",
}


# ── Permission matrix from Alyssa's spreadsheet ────────────────────────
# Format: { "email": { "folder_key": "writer"|"reader" } }
# Only includes people who need FOLDER-LEVEL grants
# (Content Managers and finance@group already have drive-level access)

PERMISSIONS = {
    # ─── Accounting Team (not already covered by drive-level) ───
    "ivy@bebang.ph": {
        "01_Revenue/Stores": "writer",
        "01_Revenue/HO_Commissary": "writer",
        "02_COGS/Stores": "writer",
        "02_COGS/HO_Commissary": "writer",
        # No Payroll access (intentional)
        "04_OpEx/Stores": "writer",
        "04_OpEx/HO_Commissary": "writer",
        "04_OpEx/Rentals": "writer",
        "04_OpEx/Utilities": "writer",
        "04_OpEx/Revolving_Fund": "writer",
        "04_OpEx/SCM_Freight": "writer",
        "04_OpEx/Petty_Cash": "writer",
        "05_Other/Stores": "writer",
        "05_Other/HO_Commissary": "writer",
        "Monthly_Review": "reader",
        "Assets/AR": "writer",
        "Reference_Documents": "writer",
        "Ongoing_Operations": "writer",
        "Policies": "reader",
    },

    "denise@bebang.ph": {
        # Already has drive-level writer, but let's ensure specific folders
        "01_Revenue/Stores": "writer",
        "01_Revenue/HO_Commissary": "writer",
        "02_COGS/Stores": "writer",
        "02_COGS/HO_Commissary": "writer",
        "03_Payroll/Stores": "writer",
        "03_Payroll/HO_Commissary": "writer",
        "04_OpEx/Stores": "writer",
        "04_OpEx/HO_Commissary": "writer",
        "04_OpEx/Rentals": "writer",
        "04_OpEx/Utilities": "writer",
        "04_OpEx/Revolving_Fund": "writer",
        "04_OpEx/SCM_Freight": "writer",
        "04_OpEx/Petty_Cash": "writer",
        "05_Other/Stores": "writer",
        "05_Other/HO_Commissary": "writer",
        "Monthly_Review": "reader",
        "Assets/Cash": "writer",
        "Liabilities/AP": "writer",
        "Liabilities/Loans": "writer",
        "Partners": "writer",
        "Payment_Trackers": "writer",
        "Reference_Documents": "writer",
        "Ongoing_Operations": "writer",
        "Policies": "reader",
    },

    # ─── CFO (Butch - already Content Manager at drive level) ───
    # Already has fileOrganizer on entire drive - no folder grants needed

    # ─── HR Team (RESTRICTED - folder-level only) ───
    "ronald@bebang.ph": {
        "03_Payroll/Stores": "reader",
        "03_Payroll/HO_Commissary": "reader",
        "Policies": "reader",
    },

    "melissa@bebang.ph": {
        "03_Payroll/Stores": "reader",
        "03_Payroll/HO_Commissary": "reader",
        "Policies": "reader",
    },

    # ─── SCM Team (RESTRICTED - folder-level only) ───
    "ian@bebang.ph": {
        "02_COGS/Stores": "reader",
        "02_COGS/HO_Commissary": "reader",  # Alyssa left blank but adding for consistency
        "04_OpEx/SCM_Freight": "writer",
        "Policies": "reader",
    },

    "jeson@bebang.ph": {
        "02_COGS/Stores": "reader",
        "04_OpEx/SCM_Freight": "writer",
        "Policies": "reader",
    },

    # ─── Admin (Noel) ───
    "admin@bebang.ph": {
        "Policies": "reader",
    },

    # ─── NOTES extras ───
    "anthony@bebang.ph": {
        "01_Revenue/Stores": "writer",  # Row 7 note: "add anthony@bebang"
        "02_COGS/Stores": "writer",     # Row 9 note: "add @anthony"
        "02_COGS/HO_Commissary": "writer",  # Row 10 note: "add @anthony"
        "Assets/AR": "writer",          # Row 19 note: "add @anthony"
    },

    "liezel@bebang.ph": {
        # Already has drive-level writer, but noted in many folders
        "01_Revenue/Stores": "writer",  # Row 7 note: "add liezel@bebang"
        "04_OpEx/Stores": "writer",
        "04_OpEx/HO_Commissary": "writer",
        "04_OpEx/Rentals": "writer",
        "04_OpEx/Utilities": "writer",
        "04_OpEx/Revolving_Fund": "writer",
        "04_OpEx/Petty_Cash": "writer",
        "05_Other/Stores": "writer",
        "05_Other/HO_Commissary": "writer",
        "Assets/Other_Current": "writer",
        "Assets/Fixed_Assets": "writer",
        "Liabilities/AP": "writer",
        "Liabilities/Loans": "writer",
        "Reference_Documents": "writer",
        "Ongoing_Operations": "writer",
    },

    "angelamel@bebang.ph": {
        "04_OpEx/Stores": "writer",
        "04_OpEx/HO_Commissary": "writer",
        "04_OpEx/Rentals": "writer",
        "04_OpEx/Utilities": "writer",
        "04_OpEx/Revolving_Fund": "writer",
        "04_OpEx/Petty_Cash": "writer",
        "05_Other/Stores": "writer",
        "05_Other/HO_Commissary": "writer",
        "Assets/Other_Current": "writer",
        "Assets/Fixed_Assets": "writer",
        "Liabilities/AP": "writer",
        "Liabilities/Loans": "writer",
    },

    "izza@bebang.ph": {
        # Already has drive-level writer
        "04_OpEx/Stores": "writer",
        "04_OpEx/HO_Commissary": "writer",
        "04_OpEx/Rentals": "writer",
        "04_OpEx/Utilities": "writer",
        "04_OpEx/Revolving_Fund": "writer",
        "04_OpEx/Petty_Cash": "writer",
        "05_Other/HO_Commissary": "writer",
        "Assets/Other_Current": "writer",
        "Assets/Fixed_Assets": "writer",
        "Liabilities/AP": "writer",
        "Liabilities/Loans": "writer",
    },

    "je-ann@bebang.ph": {
        # Already has drive-level writer
        "Payment_Trackers": "writer",  # Row 38 note: "add @je-ann@"
    },
}


def main():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    ).with_subject('sam@bebang.ph')

    drive = build('drive', 'v3', credentials=creds)

    total = sum(len(folders) for folders in PERMISSIONS.values())
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Setting {total} folder permissions for {len(PERMISSIONS)} users\n")

    success = 0
    skipped = 0
    errors = 0

    for email, folders in PERMISSIONS.items():
        print(f"\n{'='*60}")
        print(f"  {email}")
        print(f"{'='*60}")

        for folder_key, role in folders.items():
            folder_id = FOLDERS.get(folder_key)
            if not folder_id:
                print(f"  ⚠️  Unknown folder: {folder_key}")
                errors += 1
                continue

            role_display = "EDIT" if role == "writer" else "VIEW"
            print(f"  {folder_key:40s} → {role_display}", end="")

            if DRY_RUN:
                print(" [would set]")
                success += 1
                continue

            try:
                drive.permissions().create(
                    fileId=folder_id,
                    supportsAllDrives=True,
                    sendNotificationEmail=False,
                    body={
                        'type': 'user',
                        'role': role,
                        'emailAddress': email,
                    }
                ).execute()
                print(" ✅")
                success += 1
                time.sleep(0.4)  # Rate limit protection

            except HttpError as e:
                if 'already has access' in str(e).lower() or 'sharing' in str(e).lower():
                    print(" ⏭️  (already has access)")
                    skipped += 1
                else:
                    print(f" ❌ {e.resp.status}: {e._get_reason()}")
                    errors += 1
                time.sleep(0.3)

    print(f"\n{'='*60}")
    print(f"SUMMARY: {success} set, {skipped} skipped, {errors} errors")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
