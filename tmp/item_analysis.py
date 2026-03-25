"""Cross-reference Compliance App, SKU Master, Frappe Items, and stock data."""
import csv, json, subprocess, sys
from datetime import datetime, timedelta
from collections import defaultdict

def _get_frappe_auth():
    """Get Frappe API credentials from Doppler (bei-erp/dev)."""
    import os, shutil
    doppler = shutil.which('doppler') or os.path.expanduser(r'C:\Users\Sam\bin\doppler.exe')
    try:
        key = subprocess.run([doppler, 'secrets', 'get', 'FRAPPE_API_KEY', '--project', 'bei-erp', '--config', 'dev', '--plain'],
                             capture_output=True, text=True).stdout.strip()
        secret = subprocess.run([doppler, 'secrets', 'get', 'FRAPPE_API_SECRET', '--project', 'bei-erp', '--config', 'dev', '--plain'],
                                capture_output=True, text=True).stdout.strip()
        if key and secret:
            return f'token {key}:{secret}'
    except Exception:
        pass
    # Fallback: environment variable
    auth = os.environ.get('FRAPPE_AUTH')
    if auth:
        return auth
    raise RuntimeError('Cannot get Frappe API creds. Set FRAPPE_AUTH env var or install Doppler.')

FRAPPE_AUTH = _get_frappe_auth()
FRAPPE_URL = 'https://hq.bebang.ph'

def curl_frappe(payload):
    r = subprocess.run([
        'curl', '-s', '-k', f'{FRAPPE_URL}/api/method/frappe.client.get_list',
        '-H', 'Content-Type: application/json',
        '-H', f'Authorization: {FRAPPE_AUTH}',
        '-d', json.dumps(payload)
    ], capture_output=True, text=True)
    return json.loads(r.stdout).get('message', [])

# === 1. COMPLIANCE APP ITEMS ===
compliance_items = {}
with open('tmp/compliance_item_list.csv', 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        code = (row.get('Item Code') or '').strip()
        if not code:
            continue
        compliance_items[code] = {
            'name': (row.get('Item Name') or '').strip(),
            'uom': (row.get('UOM') or '').strip(),
            'price_vat_inc': (row.get('Unit Price (Vat Inc)') or '0').strip(),
            'price_vat_ex': (row.get('Unit Price (Vat ex)') or '0').strip(),
            'vat_remarks': (row.get('REMARKS') or '').strip(),
            'category': (row.get('Category') or '').strip(),
        }

# === 2. GR received items ===
gr_received = defaultdict(list)
with open('tmp/compliance_gr_items.csv', 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        code = (row.get('Item Code') or '').strip()
        if code:
            gr_received[code].append((row.get('Timestamp') or ''))

# === 3. PO prices ===
po_prices = defaultdict(list)
with open('tmp/compliance_po_items.csv', 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        code = (row.get('Item Code') or '').strip()
        cost_str = (row.get('Unit Cost') or '0').strip().replace(',', '')
        if code:
            try:
                po_prices[code].append({'ts': row.get('Timestamp', ''), 'cost': float(cost_str)})
            except ValueError:
                pass

# === 4. Frappe items ===
frappe_items = {r['name']: r for r in curl_frappe({
    'doctype': 'Item',
    'fields': ['name', 'item_name', 'item_group', 'valuation_rate', 'standard_rate', 'stock_uom', 'disabled'],
    'limit_page_length': 0
})}

# === 5. Frappe stock ===
stock = {r['item_code']: float(r['total_qty']) for r in curl_frappe({
    'doctype': 'Bin',
    'fields': ['item_code', 'sum(actual_qty) as total_qty'],
    'group_by': 'item_code',
    'limit_page_length': 0
})}

# === 6. Stock movements last 30d ===
cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
recent = {r['item_code'] for r in curl_frappe({
    'doctype': 'Stock Ledger Entry',
    'fields': ['item_code', 'max(posting_date) as last_move'],
    'filters': [['posting_date', '>=', cutoff]],
    'group_by': 'item_code',
    'limit_page_length': 0
})}

# === ANALYSIS ===
comp_in_frappe = set(compliance_items) & set(frappe_items)
comp_not_in_frappe = set(compliance_items) - set(frappe_items)

print('=== DATA SOURCES ===')
print(f'Compliance App Item List: {len(compliance_items)} items (with pricing)')
print(f'Compliance App GR Items: {len(gr_received)} unique items received')
print(f'Compliance App PO Items: {len(po_prices)} unique items ordered')
print(f'Frappe Item master: {len(frappe_items)} items')
print(f'Frappe items with stock > 0: {sum(1 for v in stock.values() if v > 0)}')
print(f'Frappe items with movement in last 30d: {len(recent)}')

print(f'\n=== ITEM OVERLAP ===')
print(f'Compliance items in Frappe: {len(comp_in_frappe)}/{len(compliance_items)}')
print(f'Compliance items NOT in Frappe: {len(comp_not_in_frappe)}')
print(f'Frappe items NOT in Compliance: {len(set(frappe_items) - set(compliance_items))}')

# Price gap
gap = 0
for c in comp_in_frappe:
    ci = compliance_items[c]
    fi = frappe_items[c]
    try:
        p = float(ci['price_vat_ex'] or ci['price_vat_inc'] or '0')
    except ValueError:
        p = 0
    if p > 0 and float(fi.get('standard_rate') or 0) == 0:
        gap += 1
print(f'\nCompliance has price but Frappe standard_rate=0: {gap}')
print(f'Frappe Item Price records: 8 (basically empty)')

# Stale items
stale = []
for code, fi in frappe_items.items():
    qty = stock.get(code, 0)
    if qty <= 0 and code not in recent and not fi.get('disabled'):
        stale.append((code, fi.get('item_name', ''), fi.get('item_group', '')))

print(f'\n=== STALE ITEMS (zero stock + no 30d movement) ===')
print(f'Total: {len(stale)}/{len(frappe_items)}')
by_group = defaultdict(int)
for c, n, g in stale:
    by_group[g] += 1
for g, c in sorted(by_group.items(), key=lambda x: -x[1]):
    print(f'  {g:30s} {c}')

if comp_not_in_frappe:
    print(f'\n=== COMPLIANCE ITEMS NOT IN FRAPPE ({len(comp_not_in_frappe)}) ===')
    for code in sorted(comp_not_in_frappe)[:25]:
        ci = compliance_items[code]
        print(f'  {code:15s} {ci["name"]:35s} {ci["uom"]:10s} Price={ci["price_vat_inc"]:>8s} {ci["category"]}')
    if len(comp_not_in_frappe) > 25:
        print(f'  ... and {len(comp_not_in_frappe) - 25} more')

# Active items (have stock OR recent movement)
active = set()
for code in frappe_items:
    if stock.get(code, 0) > 0 or code in recent:
        active.add(code)
print(f'\n=== ACTIVE vs INACTIVE ===')
print(f'Active items (stock>0 or moved in 30d): {len(active)}')
print(f'Inactive items: {len(frappe_items) - len(active)}')

# Write detailed CSV for plan
with open('tmp/item_master_full_analysis.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['item_code', 'item_name', 'item_group', 'frappe_valuation_rate', 'frappe_standard_rate',
                'compliance_price_vat_inc', 'compliance_price_vat_ex', 'compliance_vat_remarks',
                'current_stock', 'has_30d_movement', 'in_compliance_app', 'has_po_history',
                'has_gr_history', 'status'])
    for code, fi in sorted(frappe_items.items()):
        ci = compliance_items.get(code, {})
        qty = stock.get(code, 0)
        moved = code in recent
        in_comp = code in compliance_items
        has_po = code in po_prices
        has_gr = code in gr_received
        if qty > 0 or moved:
            status = 'ACTIVE'
        elif in_comp or has_po or has_gr:
            status = 'DORMANT_BUT_KNOWN'
        else:
            status = 'STALE_REMOVE'
        w.writerow([code, fi.get('item_name',''), fi.get('item_group',''),
                     fi.get('valuation_rate',0), fi.get('standard_rate',0),
                     ci.get('price_vat_inc',''), ci.get('price_vat_ex',''), ci.get('vat_remarks',''),
                     qty, moved, in_comp, has_po, has_gr, status])

print(f'\nDetailed CSV: tmp/item_master_full_analysis.csv')
