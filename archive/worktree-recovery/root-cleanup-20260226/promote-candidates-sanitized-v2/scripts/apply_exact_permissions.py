"""
Apply EXACT folder permissions from Alyssa's Excel matrix.
Source: ACCTG AND FINANCE - FOLDER MANAGER (NEW STRUCTURE).xlsx
2026-02-23

Drive-level: ONLY Sam(Manager), Alyssa(CM), Butch(CM), Juanna(CM)
Everyone else: folder-level grants ONLY, per the matrix below.
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

# ── Folder IDs ──────────────────────────────────────────────────────
FOLDERS = {
    # BEI P&L Master subfolders
    "01_Revenue/Stores":           "1RrjcSwJxuWyV7eA2oMeiGAXi3spiBfqF",
    "01_Revenue/HO_Commissary":    "1jfq42O91nbnXOMBQ8jG7EmE6oqcs1etX",
    "02_COGS/Stores":              "1g4WPpNB-Pp6ke0TAzq8K0ovBNcLFlnYW",
    "02_COGS/HO_Commissary":       "1ftn0mZ49VcFxrDLM0MgPXqB9dvdj6pKU",
    "03_Payroll/Stores":           "1XJFrm7yOzVrg_23ImcSKWJx_JSrTnIzy",
    "03_Payroll/HO_Commissary":    "1SwT6-NOnseu7RKrOowj-Ruw51zjQLwEn",
    "04_OpEx/Stores":              "1QQkixBoIVXsmNzaAAig7PJdmZZrAJ9dQ",
    "04_OpEx/HO_Commissary":       "1SWBTvMYyZHQbu8aGLKk2dYDnZvWSdnVd",
    "04_OpEx/Rentals":             "1gKApRvn9vZKjE_wwyP_I5X5nNaBs1U5B",
    "04_OpEx/Utilities":           "1MLM_d-GrqnafId6sN1RdUCruYfMYJ20D",
    "04_OpEx/Revolving_Fund":      "15eDUH79Pvgd8CxErZuvcPHrzAY-EeLLm",
    "04_OpEx/SCM_Freight":         "1i8TK_D482RKUNxnegGn9xiZvvSO7ILGO",
    "04_OpEx/Petty_Cash":          "1MA4-EApl9Y9WcIqFnqWrf-TWkb3nyBGR",
    "05_Other/Stores":             "1uFpY960BWV4218LT63vlJfHjZIw_inxs",
    "05_Other/HO_Commissary":      "1BTf8gFiEiD9llg7m4-P29hp9c6d1rcGH",
    # Monthly Review
    "Monthly_Review":              "1ow6dGAO5nUyBnebQLj3ITGOFXKy7XLQI",
    # Balance Sheet
    "Assets/Cash":                 "1OpMM9UK7UvDFt1RYs1bYzUlXTN7yKmVO",
    "Assets/AR":                   "14bM7w853Mu8u6OwoL4my-7KmZU9dy513",
    "Assets/Other_Current":        "1XC5djWwbCPkJUa6ShohNV6fy7-eMjY2F",
    "Assets/Fixed_Assets":         "1pTMTtoVy8vgijOuK48vjfYDexU6n21Bj",
    "Liabilities/AP":              "1GWPEWQu8q08mr-RnixB5SVHxExvTN3uG",
    "Liabilities/Loans":           "1_fTI5YgdrLIAevADLz1P9cWpJUe__MkZ",
    "Partners":                    "1NvnbscirDTTwzZlImDbXm2mnTfq8vOcP",
    "Trial_Balance":               "1LTFcdweqzVkQgzH_c6szlKEWRqwWvGpZ",
    # Finance Operations
    "Payment_Trackers":            "17GkTjzWhhcZGlAq8HjD4wyKjj-2L5HdQ",
    # Other shared drive folders
    "Reference_Documents":         "1aRJtu53mcfPknVNWC6KAhuM5eXROyrwZ",
    "Ongoing_Operations":          "1VfgOYyaATkFQR6nz7451wHIkYGYvd1EY",
    "Policies":                    "1nxSbozRchqs18zsjlfYkgU_HFqtvOc7c",
}

# ── EXACT permission matrix from Alyssa's Excel ────────────────────
# Transcribed cell-by-cell from the spreadsheet
# E = writer, V = reader, blank = no access
# Content Managers (Alyssa D, Butch E/K, Juanna F) already have drive-level CM

PERMISSIONS = {
    # ── Column G: Angela (accounting.bei@bebang.ph) ──
    # NO marks in any row — Angela has no column permissions
    # BUT rows 41-42 NOTES say "ADD ALL ACCTG AND FINANCE"
    # Angela gets Reference_Documents + Ongoing_Operations only
    "accounting.bei@bebang.ph": {
        "Reference_Documents": "writer",
        "Ongoing_Operations": "writer",
    },

    # ── Column H: Denise (denise@bebang.ph) ──
    "denise@bebang.ph": {
        "01_Revenue/Stores": "writer",         # Row 7: E
        "01_Revenue/HO_Commissary": "writer",  # Row 8: E
        "02_COGS/Stores": "writer",            # Row 9: E
        "02_COGS/HO_Commissary": "writer",     # Row 10: E
        "03_Payroll/Stores": "writer",         # Row 11: E
        "03_Payroll/HO_Commissary": "writer",  # Row 12: E
        "04_OpEx/Stores": "writer",            # Row 13: E
        "04_OpEx/HO_Commissary": "writer",     # Row 14: E
        "04_OpEx/Rentals": "writer",           # Row 15: E
        "04_OpEx/Utilities": "writer",         # Row 16: E
        "04_OpEx/Revolving_Fund": "writer",    # Row 17: E
        "04_OpEx/SCM_Freight": "writer",       # Row 18: E
        "04_OpEx/Petty_Cash": "writer",        # Row 19: E
        "05_Other/Stores": "writer",           # Row 20: E
        "05_Other/HO_Commissary": "writer",    # Row 21: E
        "Monthly_Review": "reader",            # Row 24: V
        "Assets/Cash": "writer",               # Row 28: E
        "Liabilities/AP": "writer",            # Row 32: E
        "Liabilities/Loans": "writer",         # Row 33: E
        "Partners": "writer",                  # Row 34: E
        "Payment_Trackers": "writer",          # Row 38: E
        "Reference_Documents": "writer",       # Row 41: E
        "Ongoing_Operations": "writer",        # Row 42: E
        "Policies": "reader",                  # Row 43: V
    },

    # ── Column I: Ivy (ivy@bebang.ph) ──
    "ivy@bebang.ph": {
        "01_Revenue/Stores": "writer",         # Row 7: E
        "01_Revenue/HO_Commissary": "writer",  # Row 8: E
        "02_COGS/Stores": "writer",            # Row 9: E
        "02_COGS/HO_Commissary": "writer",     # Row 10: E
        # Row 11-12: BLANK — NO Payroll access
        "04_OpEx/Stores": "writer",            # Row 13: E
        "04_OpEx/HO_Commissary": "writer",     # Row 14: E
        "04_OpEx/Rentals": "writer",           # Row 15: E
        "04_OpEx/Utilities": "writer",         # Row 16: E
        "04_OpEx/Revolving_Fund": "writer",    # Row 17: E
        "04_OpEx/SCM_Freight": "writer",       # Row 18: E
        "04_OpEx/Petty_Cash": "writer",        # Row 19: E
        "05_Other/Stores": "writer",           # Row 20: E
        "05_Other/HO_Commissary": "writer",    # Row 21: E
        "Monthly_Review": "reader",            # Row 24: V
        "Assets/AR": "writer",                 # Row 29: E
        "Reference_Documents": "writer",       # Row 41: E
        "Ongoing_Operations": "writer",        # Row 42: E
        "Policies": "reader",                  # Row 43: V
    },

    # ── Column J: Shaw (accounting.shaw@bebang.ph) ──
    # NO marks in any row — Shaw has no column permissions
    # Rows 41-42 NOTES: "ADD ALL ACCTG AND FINANCE"
    "accounting.shaw@bebang.ph": {
        "Reference_Documents": "writer",
        "Ongoing_Operations": "writer",
    },

    # ── Column K: Butch as CFO (butch@bebang.ph) ──
    # Already has CM at drive level, BUT column K shows specific marks
    # E on rows 7-21 (already covered by CM)
    # V on rows 24-25, 28-35, 38 (CM already gives more than V)
    # E on row 41 (already covered)
    # V on row 43 (CM already gives more)
    # → No additional grants needed, drive-level CM covers everything

    # ── Column L: Ronald (ronald@bebang.ph) ──
    "ronald@bebang.ph": {
        "03_Payroll/Stores": "reader",         # Row 11: V
        "03_Payroll/HO_Commissary": "reader",  # Row 12: V
        "Policies": "reader",                  # Row 43: V
    },

    # ── Column M: Melissa (melissa@bebang.ph) ──
    "melissa@bebang.ph": {
        "03_Payroll/Stores": "reader",         # Row 11: V
        "03_Payroll/HO_Commissary": "reader",  # Row 12: V
        "Policies": "reader",                  # Row 43: V
    },

    # ── Column N: Ian (ian@bebang.ph) ──
    "ian@bebang.ph": {
        "02_COGS/Stores": "reader",            # Row 9: V
        "04_OpEx/SCM_Freight": "writer",       # Row 18: E
        "Policies": "reader",                  # Row 43: V
    },

    # ── Column O: Jeson (jeson@bebang.ph) ──
    "jeson@bebang.ph": {
        "02_COGS/Stores": "reader",            # Row 9: V
        "04_OpEx/SCM_Freight": "writer",       # Row 18: E
        "Policies": "reader",                  # Row 43: V
    },

    # ── Column P: Noel (admin@bebang.ph) ──
    "admin@bebang.ph": {
        "Policies": "reader",                  # Row 43: V
    },

    # ── NOTES column extras ──

    # Row 7: "add anthony@bebang, liezel@bebang"
    "anthony@bebang.ph": {
        "01_Revenue/Stores": "writer",         # Row 7 note
        "02_COGS/Stores": "writer",            # Row 9 note: "add @anthony"
        "02_COGS/HO_Commissary": "writer",     # Row 10 note: "add @anthony"
        "Assets/AR": "writer",                 # Row 29 note: "add @anthony"
    },

    # Row 7 + rows 13-19, 20, 30-33, 41-42
    "liezel@bebang.ph": {
        "01_Revenue/Stores": "writer",         # Row 7 note
        "04_OpEx/Stores": "writer",            # Row 13 note
        "04_OpEx/HO_Commissary": "writer",     # Row 14 note
        "04_OpEx/Rentals": "writer",           # Row 15 note
        "04_OpEx/Utilities": "writer",         # Row 16 note
        "04_OpEx/Revolving_Fund": "writer",    # Row 17 note
        "04_OpEx/Petty_Cash": "writer",        # Row 19 note
        "05_Other/Stores": "writer",           # Row 20 note
        "Assets/Other_Current": "writer",      # Row 30 note
        "Assets/Fixed_Assets": "writer",       # Row 31 note
        "Liabilities/AP": "writer",            # Row 32 note
        "Liabilities/Loans": "writer",         # Row 33 note
        "Reference_Documents": "writer",       # Row 41: ADD ALL ACCTG
        "Ongoing_Operations": "writer",        # Row 42: ADD ALL ACCTG
    },

    # Rows 13-19, 20-21, 30-33
    "angelamel@bebang.ph": {
        "04_OpEx/Stores": "writer",            # Row 13 note
        "04_OpEx/HO_Commissary": "writer",     # Row 14 note
        "04_OpEx/Rentals": "writer",           # Row 15 note
        "04_OpEx/Utilities": "writer",         # Row 16 note
        "04_OpEx/Revolving_Fund": "writer",    # Row 17 note
        "04_OpEx/Petty_Cash": "writer",        # Row 19 note (implied from pattern)
        "05_Other/Stores": "writer",           # Row 20 note
        "05_Other/HO_Commissary": "writer",    # Row 21 note: "angelamel@.izza@"
        "Assets/Other_Current": "writer",      # Row 30 note
        "Assets/Fixed_Assets": "writer",       # Row 31 note
        "Liabilities/AP": "writer",            # Row 32 note
        "Liabilities/Loans": "writer",         # Row 33 note
    },

    # Rows 13-19 (not all), 21, 30-33
    "izza@bebang.ph": {
        "04_OpEx/Stores": "writer",            # Row 13 note
        "04_OpEx/HO_Commissary": "writer",     # Row 14 note
        "04_OpEx/Rentals": "writer",           # Row 15 note
        "04_OpEx/Utilities": "writer",         # Row 16 note
        "04_OpEx/Revolving_Fund": "writer",    # Row 17 note
        "04_OpEx/Petty_Cash": "writer",        # Row 19 note
        "05_Other/HO_Commissary": "writer",    # Row 21 note: "angelamel@.izza@"
        "Assets/Other_Current": "writer",      # Row 30 note
        "Assets/Fixed_Assets": "writer",       # Row 31 note
        "Liabilities/AP": "writer",            # Row 32 note
        "Liabilities/Loans": "writer",         # Row 33 note
    },

    # Row 38 note: "add @je-ann@"
    "je-ann@bebang.ph": {
        "Payment_Trackers": "writer",          # Row 38 note
    },
}


def main():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    ).with_subject('sam@bebang.ph')
    drive = build('drive', 'v3', credentials=creds)

    total = sum(len(folders) for folders in PERMISSIONS.values())
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Applying {total} folder permissions for {len(PERMISSIONS)} users\n")

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
                print(f"  WARNING: Unknown folder: {folder_key}")
                errors += 1
                continue

            role_display = "EDIT" if role == "writer" else "VIEW"
            print(f"  {folder_key:35s} -> {role_display}", end="")

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
                print(" OK")
                success += 1
                time.sleep(0.4)

            except HttpError as e:
                if 'already has access' in str(e).lower() or 'sharing' in str(e).lower():
                    print(" (already set)")
                    skipped += 1
                else:
                    print(f" ERROR {e.resp.status}: {e._get_reason()}")
                    errors += 1
                time.sleep(0.3)

    print(f"\n{'='*60}")
    print(f"SUMMARY: {success} applied, {skipped} already set, {errors} errors")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
