"""Sync store inventory from Google Sheets to Frappe via API.
Reads each store's '3. INVENTORY' tab, extracts items, pushes via sync_inventory API.
Run locally — no SSM needed.
"""
import sys, json, hashlib, requests, subprocess, time

sys.stdout.reconfigure(encoding='utf-8')

from google.oauth2 import service_account
from googleapiclient.discovery import build

# === Config ===
STORES = [
    ('AFT', '1yqww-pFFtGoSNGSCbROoXc1DkyADip_cHyXMZ4qlQi0', 'Ayala Malls Fairview Terraces - BEI'),
    ('AMM', '1V0_zLyKHzKw3-r0DwxED1treOucuBXmnA29UXJPZzRw', 'Ayala Market Market - BEI'),
    ('ARGW', '1aYhdmGhoHuq06OyjX4HpEafnrTOraotHFeC8sjnp9aU', 'Araneta Gateway - BEI'),
    ('AYEVO', '1MaDg1lto7GijXv043e_Og7gxaJw0pMBmATbMBqjw9hw', 'Ayala Evo - BEI'),
    ('AYSOL', '1xtJMMD8RJG-Ax7qSzfK-XNLOCMbKqdHBLQ5xEG7BNcw', 'Ayala Solenad - BEI'),
    ('AYVER', '1dtRN6O6F3vrvzlBkjbgeIw8maZzecaHBmAG6JMNWofE', 'Ayala Vermosa - BEI'),
    ('BFH', '1kr6xuUwZQNh7F85G6GPP-ZvqLnoY9P9PjxrA1GcxKrU', 'BF Homes - BEI'),
    ('CTTM', '1bqNwE71RWrXuS_ehh1Y_oWAxZnqLl2V6olBahT3Yk3k', 'CTTM Tomas Morato - BEI'),
    ('DVCAL', '1XeauhRccyw9Y4Y1zo3etdT448tA0haajbsO0Mbq7J2E', "D'verde Laguna - BEI"),
]

INV_TAB = '3. INVENTORY'
SECTION_MARKERS = {'RAW MATERIALS', 'PACKAGING', 'FINISH GOODS', 'FINISHED GOODS',
                   'OFFICE SUPPLIES', 'FROZEN', 'COLD', 'DRY', 'CHILLED',
                   'RAW MATERIAL', 'CLEANING SUPPLIES'}
BATCH_SIZE = 15

# === Setup ===
creds = service_account.Credentials.from_service_account_file(
    'credentials/task-manager-service.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
).with_subject('sam@bebang.ph')
sheets = build('sheets', 'v4', credentials=creds)

api_key = subprocess.run(
    ['C:/Users/Sam/bin/doppler.exe', 'secrets', 'get', 'FRAPPE_API_KEY', '--plain',
     '--project', 'bei-erp', '--config', 'dev'],
    capture_output=True, text=True).stdout.strip()
api_secret = subprocess.run(
    ['C:/Users/Sam/bin/doppler.exe', 'secrets', 'get', 'FRAPPE_API_SECRET', '--plain',
     '--project', 'bei-erp', '--config', 'dev'],
    capture_output=True, text=True).stdout.strip()
api = requests.Session()
api.headers['Authorization'] = f'token {api_key}:{api_secret}'


def coerce(v):
    t = (v or '').strip().replace(',', '')
    if not t or t == '-':
        return 0.0
    try:
        return float(t)
    except ValueError:
        return 0.0


def cell(row, i):
    if i >= len(row):
        return ''
    v = row[i]
    return '' if v is None else str(v).strip()


def extract_store(code, sheet_id, warehouse):
    """Read one store sheet and return list of inventory items."""
    result = sheets.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"'{INV_TAB}'!A:K"
    ).execute()
    rows = result.get('values', [])

    # Find the CODE header row (look for 'CODE' in column B)
    data_start = None
    for i, row in enumerate(rows):
        if len(row) > 1 and str(row[1]).strip().upper() == 'CODE':
            data_start = i + 1
            break

    if data_start is None:
        # Fallback: data usually starts at row 7
        data_start = 7

    items = []
    for row in rows[data_start:]:
        ic = cell(row, 1)
        if not ic or len(ic) < 2:
            continue
        if ic.upper() in SECTION_MARKERS:
            continue

        # ENCODE = col 9, Total/END = col 8
        encode = coerce(cell(row, 9))
        total = coerce(cell(row, 8))
        qty = encode if encode > 0 else total
        if qty < 0:
            qty = 0.0

        items.append({
            'inventory_key': f'{code}::{ic}',
            'item_code': ic,
            'warehouse': warehouse,
            'qty': qty,
            'store_code': code,
        })

    return items


def sync_items(code, warehouse, items):
    """Push items to Frappe sync_inventory API in small batches."""
    created = 0
    errors = 0
    error_msgs = []

    for bi in range(0, len(items), BATCH_SIZE):
        batch = items[bi:bi + BATCH_SIZE]
        cs = hashlib.sha256(json.dumps(batch).encode()).hexdigest()[:12]
        r = api.post('https://hq.bebang.ph/api/method/hrms.api.erp_sync.sync_inventory', json={
            'sheet_name': 'Store Inventory Shadow Sync',
            'data': batch,
            'checksum': f'{code}_{bi}_{cs}_{int(time.time())}',
        }, timeout=120)

        if r.status_code == 200:
            body = r.json().get('message', {})
            created += int(body.get('rows_created', 0) or 0)
            errs = body.get('errors', [])
            if isinstance(errs, list) and errs:
                errors += len(errs)
                error_msgs.extend(errs[:2])
        else:
            errors += 1
            error_msgs.append(f'HTTP {r.status_code}: {r.text[:80]}')

    return created, errors, error_msgs


# === Main ===
grand_created = 0
grand_errors = 0

for code, sheet_id, warehouse in STORES:
    try:
        items = extract_store(code, sheet_id, warehouse)
        with_stock = sum(1 for i in items if i['qty'] > 0)
        print(f'{code} ({warehouse}): {len(items)} items, {with_stock} with stock > 0')

        if not items:
            continue

        created, errors, msgs = sync_items(code, warehouse, items)
        grand_created += created
        grand_errors += errors
        status = 'OK' if errors == 0 else f'{errors} errors'
        print(f'  -> synced: created={created}, {status}')
        for m in msgs[:2]:
            print(f'     ERR: {m}')

    except Exception as e:
        print(f'{code}: EXCEPTION {str(e)[:100]}')
        grand_errors += 1

print(f'\n=== TOTAL: created={grand_created}, errors={grand_errors} ===')
