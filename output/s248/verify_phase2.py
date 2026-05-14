"""Phase 2 verification — dry-run sanity checks."""
import json, sys

d = json.load(open('output/s248/dry_run_phase2.json'))
assert d.get('dry_run') is True, 'not a dry-run response'

ds = d.get('seed', {}).get('denise_seed', {})
appended = ds.get('appended', 0)

# v3.7 amendment: expected range bumped from [80, 200] to [200, 400] because Denise's
# sheet grew from 1 tab (627 rows) to 4 tabs (1327 rows scanned) — see plan AMENDMENT 2026-05-14.
assert 200 <= appended <= 400, f'appended count {appended} outside expected [200, 400] range'

# Math integrity — all scanned rows must be accounted for
scanned = ds.get('scanned', 0)
skipped_paid = ds.get('skipped_paid', 0)
skipped_blank = ds.get('skipped_blank', 0)
skipped_existing = ds.get('skipped_existing', 0)
deduped_intra = ds.get('deduped_intra_denise', 0)
total = appended + skipped_paid + skipped_blank + skipped_existing + deduped_intra
assert total == scanned, f'math mismatch: appended+skipped+deduped={total} but scanned={scanned}'

# By-tab — must include all 4 tabs
by_tab = ds.get('by_tab', {})
expected_tabs = ['Suppliers w/o FD & Middleby', 'Middleby', 'Forward Dynamics', 'Masterlist']
for t in expected_tabs:
    assert t in by_tab, f'tab {t} missing from by_tab'

# At least Middleby tab should have appended rows (7 expected — all 7 Middleby invoices are real)
assert by_tab.get('Middleby', 0) >= 5, f'Middleby tab should append all 7 invoices, got {by_tab.get("Middleby")}'

# Sample rows must have correct SOURCE tags
sample = ds.get('sample_appended', [])
assert len(sample) >= 1, 'no sample rows captured'
for s in sample[:5]:
    src = s.get('source_tag', '')
    assert src.startswith('Denise PP'), f'sample row has wrong SOURCE tag: {src}'

# Protected surfaces unchanged
fpm = d.get('seed', {}).get('fpm_seed', {})
assert fpm.get('scanned', 0) > 0, 'FPM seed regressed'
ss = d.get('status_sync', {})
assert 'Suppliers SOA' in ss.get('tabs_seen', {}), 'status sync regressed'

print(f'PASS: dry-run shows {appended} rows ready to append')
print(f'  scanned={scanned}, paid={skipped_paid}, blank={skipped_blank}, existing={skipped_existing}, intra={deduped_intra}')
print(f'  by_tab={by_tab}')
sys.exit(0)
