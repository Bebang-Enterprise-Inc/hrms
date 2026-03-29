"""Search ALL spaces for CFO/hiring messages from 2026."""
import json, sys
from google.oauth2 import service_account
from googleapiclient.discovery import build

sys.stdout.reconfigure(encoding='utf-8')

creds = service_account.Credentials.from_service_account_file(
    'credentials/task-manager-service.json',
    scopes=['https://www.googleapis.com/auth/chat.messages.readonly']
).with_subject('sam@bebang.ph')

chat = build('chat', 'v1', credentials=creds)

# First list ALL spaces to find the right one
spaces_result = service_account.Credentials.from_service_account_file(
    'credentials/task-manager-service.json',
    scopes=['https://www.googleapis.com/auth/chat.spaces.readonly']
).with_subject('sam@bebang.ph')

chat_spaces = build('chat', 'v1', credentials=spaces_result)
all_spaces = []
page_token = None
while True:
    result = chat_spaces.spaces().list(pageSize=100, pageToken=page_token).execute()
    all_spaces.extend(result.get('spaces', []))
    page_token = result.get('nextPageToken')
    if not page_token:
        break

print(f"Total spaces: {len(all_spaces)}")

# Search every space for CFO/hiring keywords in recent messages
KEYWORDS = ['cfo', 'controller', 'head of finance', 'accounting manager', 'hiring',
            'candidate', 'resume', 'applicant', 'interview', 'shortlist', 'jobstreet',
            'seek.com', 'finance head', 'comptroller', 'replacement', 'caringal']

found = []
for i, space in enumerate(all_spaces):
    sid = space.get('name', '')
    sname = space.get('displayName', sid)
    try:
        msgs = chat.spaces().messages().list(parent=sid, pageSize=50).execute()
        for msg in msgs.get('messages', []):
            text = (msg.get('text', '') or '').lower()
            created = msg.get('createTime', '')
            # Only 2026 messages
            if not created.startswith('2026'):
                continue
            if any(kw in text for kw in KEYWORDS):
                sender = msg.get('sender', {}).get('displayName', 'Unknown')
                found.append({
                    'space': sname,
                    'space_id': sid,
                    'sender': sender,
                    'date': created[:16],
                    'text': (msg.get('text', '') or '')[:500],
                })
    except:
        pass
    if (i+1) % 20 == 0:
        print(f"  Searched {i+1}/{len(all_spaces)} spaces, {len(found)} matches so far...")

found.sort(key=lambda x: x['date'], reverse=True)

with open('recruitment/cfo_chat_messages.json', 'w', encoding='utf-8') as f:
    json.dump(found, f, indent=2, ensure_ascii=False)

print(f"\nFound {len(found)} relevant messages in 2026")
for m in found[:30]:
    print(f"\n[{m['date']}] {m['space']} | {m['sender']}:")
    text = m['text'][:200].encode('ascii', 'replace').decode()
    print(f"  {text}")
