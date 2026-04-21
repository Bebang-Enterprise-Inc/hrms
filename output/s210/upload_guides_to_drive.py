"""Upload the 6 S210 guide DOCX to Google Drive Training folder as
native Google Docs. Returns local paths + Drive shareable URLs.

Run:
    python output/s210/upload_guides_to_drive.py
"""
import json, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = pathlib.Path(__file__).resolve().parents[2]
SA = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')

GUIDES_DIR = ROOT / 'output/s210/guides'
TRAINING_FOLDER_ID = '1zTUtXk4SfWekqv1bNbPybZZKCheIcPru'
DATE_PREFIX = '2026-04-21'

UPLOADS = [
    ('1_MASTER_INDEX.docx', 'S210 Master Index — Team-by-Team Guide'),
    ('2_3PL_DOCK_QUICK_CARD.docx', 'S210 Guide — 3PL Dock Quick Card (3MD + Pinnacle)'),
    ('3_SUPPLIER_FAQ.docx', 'S210 Guide — Supplier SI Upload FAQ (for supplier emails)'),
    ('4_SUPPLIER_ROLLOUT_GUIDE.docx', 'S210 Guide — Supplier Rollout Playbook (Cayla)'),
    ('5_IAN_DAILY_OPS_PLAYBOOK.docx', 'S210 Guide — Ian Daily Ops Playbook'),
    ('6_FINANCE_RECONCILIATION_GUIDE.docx', 'S210 Guide — Finance Reconciliation (Denise)'),
]

creds = service_account.Credentials.from_service_account_file(
    str(SA),
    scopes=['https://www.googleapis.com/auth/drive'],
).with_subject('sam@bebang.ph')
drive = build('drive', 'v3', credentials=creds, cache_discovery=False)

print('=== Upload S210 guides to Google Drive Training folder ===\n')

out = []
for filename, drive_name in UPLOADS:
    local = GUIDES_DIR / filename
    if not local.exists():
        print(f'  [SKIP] {filename} not found')
        continue

    # Upload as native Google Doc (converts .docx on upload)
    media = MediaFileUpload(
        str(local),
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        resumable=True,
    )
    metadata = {
        'name': f'{DATE_PREFIX} - {drive_name}',
        'mimeType': 'application/vnd.google-apps.document',
        'parents': [TRAINING_FOLDER_ID],
    }
    resp = drive.files().create(
        body=metadata, media_body=media, fields='id,name,webViewLink',
        supportsAllDrives=True,
    ).execute()

    file_id = resp['id']
    view_url = resp.get('webViewLink') or f'https://docs.google.com/document/d/{file_id}/edit'
    print(f'  [OK] {filename}')
    print(f'       {resp["name"]}')
    print(f'       {view_url}')

    # Share with BEI team
    bei_editors = [
        'sam@bebang.ph', 'ian@bebang.ph', 'cayla@bebang.ph',
        'luwi@bebang.ph', 'mae@bebang.ph', 'denise@bebang.ph', 'jay@bebang.ph',
    ]
    for email in bei_editors:
        try:
            drive.permissions().create(
                fileId=file_id,
                body={'type': 'user', 'role': 'writer', 'emailAddress': email},
                sendNotificationEmail=False,
                supportsAllDrives=True,
            ).execute()
        except Exception as e:
            pass  # don't block on already-granted

    out.append({
        'local': str(local),
        'drive_name': resp['name'],
        'drive_url': view_url,
        'file_id': file_id,
    })

# Persist manifest
manifest_path = ROOT / 'output/s210/GUIDES_DRIVE_MANIFEST.json'
manifest_path.write_text(json.dumps(out, indent=2), encoding='utf-8')
print(f'\nUploaded {len(out)} guides. Manifest: {manifest_path}')
