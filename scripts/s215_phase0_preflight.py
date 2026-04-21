"""S215 Phase 0 preflight — P0-T3, P0-T4, P0-T5.

Writes:
  output/s215/preflight_s210_alive.json
  output/s215/preflight_procurement_counts.json
  output/s215/preflight_orphan_cleanup.json
  output/s215/agent_preflight.txt

Exit 0 = all green. Exit 1 = any red.
"""
import json
import pathlib
import subprocess
import sys
import urllib.request
import urllib.parse

sys.stdout.reconfigure(encoding='utf-8')

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SA = r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json'
OUT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s215\output\s215')
OUT.mkdir(parents=True, exist_ok=True)

# Ground-truth IDs from the plan
SHEET_A = '1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU'
SHEET_B = '10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw'
SHEET_C = '1_Ir5O5AW7hOjcvCTXsP06cF3sai9hcefDFrBOTRHOh0'
SHEET_D = '1mbJiLW9M9e-AmrXSRRTtbRP-xKI16ah5rakOt6qv2As'
APPS_SCRIPT_ID = '1lsvOlv1rGEvXl_1zms4SURlsLUZk7CxRhg2NyBDrDHh4fDjuioFZhi2S'
WEB_APP_URL = 'https://script.google.com/macros/s/AKfycbwHhE8wesatwrXdw8SYOFjm30zqG62wNgFUyC_GIB14zFQb1CHU4ov-jVm1wjGfqFj2/exec'
SHARED_TOKEN = 's210-b3i-a8F2kQ9mZv7RpYxLnCdT4wE6hG1jN5uH0sK3'
PROCUREMENT_SS = '1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q'
ORPHAN_SCRIPT_ID = '1LRS_XnRqEDQP2ux6a2xdmTCzcqHE_H_3cJKRJau4KzjqKwwHl7MfhEd7'

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/script.projects',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/cloud-platform',
]

creds = service_account.Credentials.from_service_account_file(SA, scopes=SCOPES).with_subject('sam@bebang.ph')
sheets = build('sheets', 'v4', credentials=creds, cache_discovery=False).spreadsheets()
script_api = build('script', 'v1', credentials=creds, cache_discovery=False)
drive = build('drive', 'v3', credentials=creds, cache_discovery=False)

results_alive = {'checks': [], 'all_pass': True}
results_counts = {}
results_orphan = {}
errors = []


def add_alive(name, ok, detail=''):
    results_alive['checks'].append({'name': name, 'pass': bool(ok), 'detail': str(detail)[:300]})
    if not ok:
        results_alive['all_pass'] = False
        errors.append(f'ALIVE CHECK FAIL: {name} — {detail}')


# === P0-T3a: Sheet C tabs 01-09 present ===
try:
    meta = sheets.get(spreadsheetId=SHEET_C).execute()
    tabs = [s['properties']['title'] for s in meta['sheets']]
    expected_prefixes = ['01_', '02_', '03_', '04_', '05_', '06_', '07_', '08_', '09_']
    found_prefixes = [p for p in expected_prefixes if any(t.startswith(p) for t in tabs)]
    add_alive('sheet_c_tabs_01_to_09_present', len(found_prefixes) == 9,
              f'found={len(found_prefixes)}/9 / total_tabs={len(tabs)}')
    results_alive['sheet_c_tab_list'] = tabs
except Exception as e:
    add_alive('sheet_c_tabs_01_to_09_present', False, str(e))

# === P0-T3b: Cloud Scheduler — list 4 jobs ===
try:
    GCLOUD = r'C:\Users\Sam\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
    result = subprocess.run(
        [GCLOUD, 'scheduler', 'jobs', 'list',
         '--location=asia-southeast1',
         '--project=quiet-walker-475722-s2',
         '--format=json'],
        capture_output=True, text=True, timeout=60, encoding='utf-8'
    )
    if result.returncode == 0:
        jobs = json.loads(result.stdout)
        job_names = [j['name'].split('/')[-1] for j in jobs]
        # Real job names use `s210-` prefix (not the Apps Script fn names).
        # Match by substring so plan text and live scheduler don't have to agree on exact naming.
        expected_patterns = ['poll-all', 'age-variance', 'refresh-masters', 'ceo-email']
        matched = {p: any(p in n for n in job_names) for p in expected_patterns}
        all_found = all(matched.values())
        add_alive('cloud_scheduler_4_jobs_live', all_found,
                  f'matched={matched} / all_jobs={sorted(job_names)}')
        results_alive['scheduler_jobs'] = job_names
    else:
        add_alive('cloud_scheduler_4_jobs_live', False, f'gcloud exit={result.returncode} stderr={result.stderr[:200]}')
except Exception as e:
    add_alive('cloud_scheduler_4_jobs_live', False, str(e))

# === P0-T3c: Web-app ping ===
try:
    # handler uses ?fn=ping&key=<token> (not action/token as plan text mistakenly suggested)
    params = urllib.parse.urlencode({'fn': 'ping', 'key': SHARED_TOKEN})
    req = urllib.request.Request(f'{WEB_APP_URL}?{params}')
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode('utf-8')
        try:
            js = json.loads(body)
            ok = bool(js.get('ok'))
        except Exception:
            ok = False
            js = {'raw_body': body[:300]}
        add_alive('web_app_ping_ok', ok, f'resp={js}')
except Exception as e:
    add_alive('web_app_ping_ok', False, str(e))

# === P0-T4: Procurement row counts ===
try:
    for tab, threshold in [('Item List', 380), ('PO Items', 2200), ('Purchase Order', 680)]:
        rv = sheets.values().get(
            spreadsheetId=PROCUREMENT_SS,
            range=f'{tab}!A:A'
        ).execute()
        n = max(0, len(rv.get('values', [])) - 1)
        results_counts[tab] = {'rows': n, 'threshold': threshold, 'pass': n >= threshold}
        if n < threshold:
            errors.append(f'PROCUREMENT FAIL: {tab}={n} < {threshold}')
    results_counts['all_pass'] = all(v['pass'] for v in results_counts.values() if isinstance(v, dict) and 'pass' in v)
except Exception as e:
    results_counts['error'] = str(e)
    results_counts['all_pass'] = False
    errors.append(f'PROCUREMENT PROBE ERROR: {e}')

# === P0-T5: Orphan bound script cleanup ===
try:
    # Try to fetch project metadata — if it errors 404, the orphan is gone
    try:
        p = script_api.projects().get(scriptId=ORPHAN_SCRIPT_ID).execute()
        # Still exists; try to delete via drive
        results_orphan['orphan_still_exists'] = True
        results_orphan['orphan_title'] = p.get('title', '')
        results_orphan['orphan_parentId'] = p.get('parentId', '')
        try:
            drive.files().delete(fileId=ORPHAN_SCRIPT_ID, supportsAllDrives=True).execute()
            results_orphan['delete_attempt'] = 'OK — deleted via drive'
            results_orphan['clean'] = True
        except HttpError as de:
            results_orphan['delete_attempt'] = f'FAILED — {de.resp.status}: {str(de)[:200]}'
            results_orphan['clean'] = False
            errors.append(f'ORPHAN CLEANUP FAIL: cannot delete scriptId {ORPHAN_SCRIPT_ID} via drive — {de.resp.status}. Ask Sam to delete manually.')
    except HttpError as e:
        if e.resp.status == 404:
            results_orphan['orphan_still_exists'] = False
            results_orphan['clean'] = True
            results_orphan['note'] = 'Orphan already deleted — good.'
        else:
            raise
except Exception as e:
    results_orphan['error'] = str(e)
    results_orphan['clean'] = False
    errors.append(f'ORPHAN PROBE ERROR: {e}')

# === Write artifacts ===
(OUT / 'preflight_s210_alive.json').write_text(json.dumps(results_alive, indent=2), encoding='utf-8')
(OUT / 'preflight_procurement_counts.json').write_text(json.dumps(results_counts, indent=2), encoding='utf-8')
(OUT / 'preflight_orphan_cleanup.json').write_text(json.dumps(results_orphan, indent=2), encoding='utf-8')

summary_lines = [
    'S215 Phase 0 Preflight — agent self-attestation',
    '',
    f'Branch: s215-s210-ops-polish',
    f'Worktree: F:/Dropbox/Projects/BEI-ERP-s215',
    f'Plan read: docs/plans/2026-04-21-sprint-215-s210-ops-polish.md',
    '',
    '=== P0-T3 S210 alive ===',
]
for c in results_alive['checks']:
    summary_lines.append(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['name']}: {c['detail']}")
summary_lines.append('')
summary_lines.append('=== P0-T4 Procurement counts ===')
for k, v in results_counts.items():
    if isinstance(v, dict) and 'rows' in v:
        summary_lines.append(f"  [{'PASS' if v['pass'] else 'FAIL'}] {k}: {v['rows']} (threshold {v['threshold']})")
summary_lines.append('')
summary_lines.append('=== P0-T5 Orphan cleanup ===')
summary_lines.append(f"  orphan_clean: {results_orphan.get('clean', False)} — {results_orphan}")
summary_lines.append('')
summary_lines.append(f"ERRORS: {len(errors)}")
for e in errors:
    summary_lines.append(f"  - {e}")
(OUT / 'agent_preflight.txt').write_text('\n'.join(summary_lines), encoding='utf-8')

print('\n'.join(summary_lines))

# Orphan cleanup failure does NOT block Phases 1-3; it's a narrower Phase 4 gate.
# Phases 1-3 can proceed in parallel while Sam deletes the orphan script manually.
phases_1_3_ok = results_alive['all_pass'] and results_counts.get('all_pass')
phase_4_ok = results_orphan.get('clean', False)
results_alive['phases_1_3_preflight_ok'] = phases_1_3_ok
results_alive['phase_4_preflight_ok'] = phase_4_ok
(OUT / 'preflight_s210_alive.json').write_text(json.dumps(results_alive, indent=2), encoding='utf-8')

if not phases_1_3_ok:
    print('\nBLOCKED: Phases 1-3 cannot start (S210 alive or procurement counts failed).')
    sys.exit(1)
if not phase_4_ok:
    print('\nPARTIAL GREEN: Phases 1-3 green; Phase 4 blocked on orphan cleanup (needs Sam).')
    sys.exit(2)
print('\nALL GREEN — Phases 1-6 clear to proceed.')
sys.exit(0)
