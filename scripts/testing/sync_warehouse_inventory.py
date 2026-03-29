"""Sync Ian's warehouse inventory from Google Sheets to Frappe.
Run locally — reads sheet, transforms, calls Frappe API.
"""
import sys, json, hashlib, requests, subprocess

sys.stdout.reconfigure(encoding='utf-8')

from google.oauth2 import service_account
from googleapiclient.discovery import build

# === Config ===
SHEET_ID = '19Hm25vaj9gD8p6z_M6-4CPWvcXaPzAeOFKlUZ298V4s'
GOOGLE_SHEET_TAB = 'SUMMARY 2026'  # Tab name in Google Sheets
FRAPPE_SYNC_NAME = 'Inventory'  # Baseline sync — generates synthetic batches for batch-tracked items
WAREHOUSE_MAP = {
    "3MD": "3MD Logistics \u2013 Camangyanan - BKI",
    "JENTEC": "Jentec Storage Inc. - BKI",
    "RCS": "Royal Cold Storage \u2013 Taytay (RCS) - BKI",
    "PINNACLE": "Pinnacle Cold Storage Solutions - BKI",
    "SHAW": "Shaw BLVD - BKI",
}
SECTION_MARKERS = {"DRY", "COLD", "FROZEN", "CHILLED"}

# === Read Google Sheet ===
creds = service_account.Credentials.from_service_account_file(
    'credentials/task-manager-service.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
).with_subject('sam@bebang.ph')
service = build('sheets', 'v4', credentials=creds)
result = service.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range=f"'{GOOGLE_SHEET_TAB}'!A:Z"
).execute()
rows = result.get('values', [])
print(f'Read {len(rows)} rows from {GOOGLE_SHEET_TAB}')

# === Transform ===
def normalize(v):
    return str(v or '').strip().upper().replace(' ', '').replace('.', '')

def discover_columns(header):
    cols = {}
    for i, v in enumerate(header):
        label = normalize(v)
        if label in WAREHOUSE_MAP:
            cols[label] = i
    missing = [c for c in WAREHOUSE_MAP if c not in cols]
    if missing:
        print(f'WARNING: Missing columns: {missing}')
    return cols

def cell(row, i):
    if i >= len(row): return ''
    v = row[i]
    return '' if v is None else str(v).strip()

def coerce_qty(v):
    t = (v or '').strip()
    if not t or t == '-': return 0.0
    try: return float(t.replace(',', ''))
    except: return 0.0

if not rows:
    print('No data'); sys.exit(1)

# Row 0 is title ("SOH AS OF 3/27"), Row 1 is the actual header with warehouse names
header_row = rows[1] if len(rows) > 1 else rows[0]
print(f'Header row: {header_row[:10]}')
wh_cols = discover_columns(header_row)
print(f'Warehouse columns found: {wh_cols}')

transformed = []
section = ''
# Skip title row (0) and header rows (1, 2) — data starts at row 3
for row_num, row in enumerate(rows[3:], start=4):
    # Column layout: [0]=CATEGORY, [1]=ITEM DESCRIPTION, [2]=MATERIAL CODE, [3]=UOM, [4+]=warehouse qtys
    category = cell(row, 0)
    desc = cell(row, 1)
    item_code = cell(row, 2)
    uom = cell(row, 3) if len(row) > 3 else ''

    if not item_code:
        tok = (desc or category).strip().upper()
        if tok in SECTION_MARKERS:
            section = tok
        continue

    for wh_code, col_idx in wh_cols.items():
        qty = coerce_qty(cell(row, col_idx))
        if qty < 0:
            continue  # Skip negative quantities
        if item_code == 'OS096':
            continue  # Disabled item — causes SR validation failure
        transformed.append({
            'inventory_key': f'{wh_code}::{item_code}',
            'item_code': item_code,
            'item_description': desc,
            'category': category or section,
            'uom': uom,
            'warehouse_source_code': wh_code,
            'warehouse': WAREHOUSE_MAP[wh_code],
            'qty': qty,
            'source_row_number': row_num,
        })

print(f'Transformed: {len(transformed)} inventory entries')
warehouses = set(r['warehouse'] for r in transformed)
print(f'Warehouses: {warehouses}')

# Group by warehouse
by_wh = {}
for r in transformed:
    by_wh.setdefault(r['warehouse_source_code'], []).append(r)
print(f'Chunks: {[(k, len(v)) for k, v in by_wh.items()]}')

# === Sync to Frappe ===
api_key = subprocess.run(
    ['C:/Users/Sam/bin/doppler.exe', 'secrets', 'get', 'FRAPPE_API_KEY', '--plain', '--project', 'bei-erp', '--config', 'dev'],
    capture_output=True, text=True).stdout.strip()
api_secret = subprocess.run(
    ['C:/Users/Sam/bin/doppler.exe', 'secrets', 'get', 'FRAPPE_API_SECRET', '--plain', '--project', 'bei-erp', '--config', 'dev'],
    capture_output=True, text=True).stdout.strip()

s = requests.Session()
s.headers['Authorization'] = f'token {api_key}:{api_secret}'

total_created = 0
total_updated = 0
total_errors = 0

BATCH_SIZE = 15  # Small batches to avoid Gunicorn timeout

for wh_code, chunk in by_wh.items():
    # Split into small batches
    batches = [chunk[i:i+BATCH_SIZE] for i in range(0, len(chunk), BATCH_SIZE)]
    wh_created = 0
    wh_errors = 0
    for batch_idx, batch in enumerate(batches):
        cs = hashlib.sha256(json.dumps(batch).encode()).hexdigest()[:16]
        r = s.post('https://hq.bebang.ph/api/method/hrms.api.erp_sync.sync_inventory', json={
            'sheet_name': FRAPPE_SYNC_NAME,
            'data': batch,
            'checksum': f'{wh_code}_{batch_idx}_{cs}',
        }, timeout=120)

        if r.status_code == 200:
            body = r.json().get('message', {})
            created = int(body.get('rows_created', body.get('created', 0)) or 0)
            errors = body.get('errors', [])
            err_count = len(errors) if isinstance(errors, list) else int(errors or 0)
            wh_created += created
            wh_errors += err_count
            if isinstance(errors, list) and errors:
                for e in errors[:2]:
                    print(f'    ERR batch {batch_idx}: {e}')
        else:
            wh_errors += 1
            print(f'    HTTP {r.status_code} batch {batch_idx}: {r.text[:150]}')
    total_created += wh_created
    total_errors += wh_errors
    print(f'  {wh_code} ({len(chunk)} items, {len(batches)} batches): created={wh_created}, errors={wh_errors}')

print(f'\nTOTAL: created={total_created}, updated={total_updated}, errors={total_errors}')
