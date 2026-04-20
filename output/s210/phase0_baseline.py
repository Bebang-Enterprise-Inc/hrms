"""S210 Phase 0 baseline artifact writer."""
import json, subprocess, datetime, csv, os

ROOT = r'F:\Dropbox\Projects\BEI-ERP'
os.chdir(ROOT)

sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
prod_sha = subprocess.check_output(['git', 'rev-parse', 'origin/production'], text=True).strip()
now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

# ---- Remote-truth baseline ----
baseline = {
    'captured_utc': now_iso,
    'repo': 'hrms',
    'sprint_branch': 's210-tier-a-receipt-payment-infrastructure',
    'starting_sha_on_branch': sha,
    'origin_production_sha': prod_sha,
    'live_evidence_basis': {
        'procurement_appsheet_id': '1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q',
        '3md_dry_sheet_id': '1dNh1TnLRke7RfSavvjU1S2QP3rEJyFxf8RPURwI4rzg',
        '3md_cold_sheet_id': '1u582KeN8OfnrvO4LPs1zjvFkJ0LnsVIjjoHPKqoq2IQ',
        'pinnacle_channel': 'Viber group "Pinnacle x Bebang PH" (15 participants)',
        'master_workbook_2026_april': '1-QPBQ8B-iYWsqa1VbdF-g4LY3YsyxS5vAcQsqlpVeMM',
    },
    'canonical_scope': 'none',
    'canonical_scope_rationale': 'Google Workspace automation; no Frappe mutations',
}
with open('output/s210/state/S210_REMOTE_TRUTH_BASELINE.json', 'w', encoding='utf-8') as f:
    json.dump(baseline, f, indent=2)

# ---- Active run coordination ----
coord = {
    'sprint': 'S210',
    'claimed_utc': now_iso,
    'agent_session_id': 'claude-opus-4.7-2026-04-20-execution',
    'status': 'ACTIVE',
    'owned_surfaces': [
        'scripts/google_apps/s210_*.gs',
        'docs/plans/2026-04-20-sprint-210-tier-a-receipt-payment-infrastructure.md',
        'output/s210/**',
        'output/l3/s210/**',
        'New Google Sheets A/B/C/D owned by commissary.team@bebang.ph',
        'New Google Form BEI Supplier SI Upload',
    ],
    'protected_surfaces_touched': 'none',
    'overlap_check': 'S209 is separate branch + specs; no conflict',
}
with open('output/s210/state/S210_ACTIVE_RUN_COORDINATION.json', 'w', encoding='utf-8') as f:
    json.dump(coord, f, indent=2)

# ---- Ownership matrix ----
with open('output/s210/S210_SURFACE_OWNERSHIP.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['Surface', 'Type', 'Owner', 'Mutability', 'Notes'])
    for row in [
        ('docs/plans/2026-04-20-sprint-210-tier-a-receipt-payment-infrastructure.md', 'plan', 'S210', 'mutable-by-S210', 'This plan file'),
        ('docs/plans/SPRINT_REGISTRY.md', 'registry', 'shared', 'append-only-by-S210', 'Append S210 row + bump Next counter'),
        ('scripts/google_apps/s210_master_handler.gs', 'code', 'S210', 'mutable-by-S210', 'Bound to Sheet C'),
        ('scripts/google_apps/s210_common.gs', 'code', 'S210', 'mutable-by-S210', 'Shared helpers'),
        ('scripts/google_apps/s210_si_upload_handler.gs', 'code', 'S210', 'mutable-by-S210', 'Form submit handler'),
        ('output/s210/**', 'artifacts', 'S210', 'mutable-by-S210', 'Baseline, state, evidence'),
        ('output/l3/s210/**', 'artifacts', 'S210', 'mutable-by-S210', 'L3 test evidence'),
        ('Google Sheet A (3MD Receiving Log 2026)', 'google-resource', 'commissary.team@bebang.ph', 'new-resource', '3MD editor access'),
        ('Google Sheet B (Pinnacle Receiving Log 2026)', 'google-resource', 'commissary.team@bebang.ph', 'new-resource', 'Pinnacle editor access'),
        ('Google Sheet C (Receiving Master 2026)', 'google-resource', 'commissary.team@bebang.ph', 'new-resource', 'BEI-internal only'),
        ('Google Sheet D (Shaw Transitional)', 'google-resource', 'commissary.team@bebang.ph', 'new-resource', 'BEI-internal only'),
        ('Google Form (BEI Supplier SI Upload)', 'google-resource', 'commissary.team@bebang.ph', 'new-resource', 'Tier A suppliers'),
        ('Procurement AppSheet 1QWdoZlT Google Sheet', 'google-resource', 'sam@bebang.ph', 'READ-ONLY', 'We only READ for dropdowns'),
        ('3MD-owned sheets 1dNh1/1u582', 'google-resource', 'bebang3md@gmail.com', 'READ-ONLY', 'Never write'),
        ('2026 APRIL BEBANG INVENTORY 1-QPBQ', 'google-resource', 'ian@bebang.ph', 'READ-ONLY', 'Ian owns; reference'),
    ]:
        w.writerow(row)

# ---- Protected surfaces registry ----
with open('output/s210/S210_PROTECTED_SURFACES.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['Surface', 'Why Protected', 'S210 Action'])
    for row in [
        ('hrms/api/*.py', 'No Frappe code changes', 'No modifications'),
        ('hrms/hr/doctype/bei_*', 'No DocType changes', 'No modifications'),
        ('bei-tasks/**', 'No frontend changes', 'No modifications'),
        ('3MD-owned Google Sheets', 'Owned by 3MD', 'Read-only via Sheets API'),
        ('Procurement AppSheet underlying sheet', 'Owned by Ashish/procurement', 'Read-only for dropdowns'),
        ('2026 APRIL BEBANG INVENTORY', 'Ian owns', 'Read-only reference'),
        ('Procurement App Notifications chat space', 'Shared space', 'Post notifications only'),
        ('SCM chat space', 'Shared team space', 'Post notifications only'),
    ]:
        w.writerow(row)

# ---- Library audit ----
lib = """# Library Audit - S210

Scanned scripts/, hrms/utils/, and existing Apps Script references.

## Existing helpers (referenced in codebase)

| Helper | Location | Use in S210 |
|---|---|---|
| Chat space posting pattern | hrms/api/google_chat.py, hrms/api/mcp.py | Reference for Apps Script UrlFetchApp POST to chat.googleapis.com/v1/spaces/ |
| Service account credential pattern | credentials/task-manager-service.json | Not directly used by Apps Script (runs as user); commissary.team owns |
| Sheets API batch read pattern | data/_tools/pull_store_registry_from_sheet.py | Reference for batch Sheets ops |
| Supplier Master parsing | hrms/api/erp_sync.py, hrms/services/sheets_receiver/ | Validation reference |
| Tier A / Payment Terms policy | docs/plans/2026-04-18-AppSheet-Consolidated-Fix-Memo (Ashish memo) | Payment Terms enum + Tier A criteria |

## Gaps filled by this sprint

- No BEI-owned 3PL receiving data feed (Sheets A + B)
- No supplier SI upload channel (Google Form)
- No onEdit Chat notification (Apps Script)
- No CEO daily receiving KPI email (07:00 cron)
- No variance queue for SI-DR mismatches (Sheet C 04_Match_Queue + 05_Variance_Queue)

## Reusable helpers to extract

- postChatNotification(spaceId, text) -> s210_common.gs
- getPoBalance(poNumber) -> s210_common.gs
- validateReceipt(row) -> s210_common.gs
- ageVarianceQueue() -> s210_master_handler.gs
"""
with open('output/s210/LIBRARY_AUDIT.md', 'w', encoding='utf-8') as f:
    f.write(lib)

print('Phase 0 baseline artifacts written:')
for p in [
    'output/s210/state/S210_REMOTE_TRUTH_BASELINE.json',
    'output/s210/state/S210_ACTIVE_RUN_COORDINATION.json',
    'output/s210/S210_SURFACE_OWNERSHIP.csv',
    'output/s210/S210_PROTECTED_SURFACES.csv',
    'output/s210/LIBRARY_AUDIT.md',
    'output/s210/PROCUREMENT_APPSHEET_BASELINE.json',
    'output/s210/verify_canonical_preflight.log',
]:
    size = os.path.getsize(p) if os.path.exists(p) else 0
    print(f'  [{size:>6}B] {p}')
