"""S120 Phase 0: Extract Compliance App data from Google Sheets.

Run this BEFORE item_analysis.py. It pulls the 4 key tabs from the
Procurement Compliance Appsheet Database into tmp/ CSVs.

Usage:
    python tmp/s120_extract_compliance_data.py

Requires:
    - credentials/task-manager-service.json (Google API service account)
    - google-api-python-client, google-auth packages
"""
import csv
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), '..', 'credentials', 'task-manager-service.json')
SHEET_ID = '1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q'  # Procurement Compliance Appsheet Database (sam@bebang.ph)
IMPERSONATE = 'sam@bebang.ph'
OUTPUT_DIR = os.path.join(os.path.dirname(__file__))

TABS = {
    'Item List': {'range': 'Item List!A:K', 'output': 'compliance_item_list.csv'},
    'PO Items': {'range': 'PO Items!A:O', 'output': 'compliance_po_items.csv'},
    'GR Items': {'range': 'GR Items!A:J', 'output': 'compliance_gr_items.csv'},
    'Suppliers': {'range': 'Suppliers!A:Z', 'output': 'compliance_suppliers.csv'},
}


def main():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    ).with_subject(IMPERSONATE)
    sheets = build('sheets', 'v4', credentials=creds, cache_discovery=False)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for tab_name, config in TABS.items():
        print(f'Extracting {tab_name}...')
        result = sheets.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=config['range']
        ).execute()
        rows = result.get('values', [])
        if not rows:
            print(f'  WARNING: No data in {tab_name}')
            continue

        output_path = os.path.join(OUTPUT_DIR, config['output'])
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerows(rows)

        data_rows = len(rows) - 1  # minus header
        print(f'  -> {output_path} ({data_rows} data rows)')

    print('\nDone. Now run: python tmp/item_analysis.py')


if __name__ == '__main__':
    main()
