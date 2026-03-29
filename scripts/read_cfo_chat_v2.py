"""Dump ALL recent messages from CFO-relevant spaces."""
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

creds = service_account.Credentials.from_service_account_file(
    'credentials/task-manager-service.json',
    scopes=['https://www.googleapis.com/auth/chat.messages.readonly']
).with_subject('sam@bebang.ph')

chat = build('chat', 'v1', credentials=creds)

SPACES = {
    'Finance - Directors': 'spaces/AAAAMk0LBmE',
    'Mancom': 'spaces/AAQAVUxMOBM',
    'Accounting Private': 'spaces/AAAA9RN0JZQ',
    'Shot Callers': 'spaces/AAAAH6NWqxM',
    'Ana+Chimes+Ronald GC': 'spaces/AAQApf3sPAg',
    'Ronald DM': 'spaces/xyFLZsAAAAE',
    'HR - Private': 'spaces/AAAAwAZK5LE',
}

all_msgs = []

for space_name, space_id in SPACES.items():
    try:
        results = chat.spaces().messages().list(
            parent=space_id, pageSize=100
        ).execute()
        msgs = results.get('messages', [])
        print(f"{space_name}: {len(msgs)} messages")
        for msg in msgs[-30:]:  # Last 30 per space
            text = msg.get('text', '') or ''
            if not text.strip():
                continue
            sender = msg.get('sender', {}).get('displayName', 'Unknown')
            created = msg.get('createTime', '')[:16]
            all_msgs.append({
                'space': space_name,
                'sender': sender,
                'date': created,
                'text': text[:600],
            })
    except Exception as e:
        print(f"{space_name}: ERROR - {str(e)[:100]}")

all_msgs.sort(key=lambda x: x['date'], reverse=True)

with open('recruitment/chat_dump.json', 'w', encoding='utf-8') as f:
    json.dump(all_msgs, f, indent=2, ensure_ascii=False)

print(f"\nTotal: {len(all_msgs)} text messages")
print("\n=== Last 20 messages (newest first) ===")
for m in all_msgs[:20]:
    print(f"\n[{m['date']}] {m['space']} | {m['sender']}:")
    print(f"  {m['text'][:200]}")
