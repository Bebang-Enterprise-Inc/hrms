"""Read messages about CFO replacement from relevant Google Chat spaces."""
import json
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

creds = service_account.Credentials.from_service_account_file(
    'credentials/task-manager-service.json',
    scopes=['https://www.googleapis.com/auth/chat.messages.readonly']
).with_subject('sam@bebang.ph')

chat = build('chat', 'v1', credentials=creds)

# Spaces to search
SPACES = {
    'Finance - Directors': 'spaces/AAAAMk0LBmE',
    'Mancom': 'spaces/AAQAVUxMOBM',
    'Accounting Private': 'spaces/AAAA9RN0JZQ',
    'Shot Callers': 'spaces/AAAAH6NWqxM',
    'Ana+Chimes+Ronald GC': 'spaces/AAQApf3sPAg',
    'Ana+Ronald GC': 'spaces/AAAAWDQ5WCE',
    'Ronald DM': 'spaces/xyFLZsAAAAE',
    'HR - Private': 'spaces/AAAAwAZK5LE',
    'HR': 'spaces/AAAA8P8RC0M',
}

KEYWORDS = ['cfo', 'controller', 'head of finance', 'accounting manager', 'hiring', 'candidate',
            'resume', 'applicant', 'interview', 'shortlist', 'jobstreet', 'seek', 'Ronald',
            'finance head', 'comptroller', 'replacement']

all_matches = []

for space_name, space_id in SPACES.items():
    try:
        messages = chat.spaces().messages().list(
            parent=space_id, pageSize=200
        ).execute()

        for msg in messages.get('messages', []):
            text = msg.get('text', '') or ''
            sender = msg.get('sender', {}).get('displayName', 'Unknown')
            created = msg.get('createTime', '')

            # Check if message is from last 60 days
            if created:
                msg_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
                if msg_date < datetime.now(msg_date.tzinfo) - timedelta(days=60):
                    continue

            # Check for keywords
            text_lower = text.lower()
            if any(kw in text_lower for kw in KEYWORDS):
                all_matches.append({
                    'space': space_name,
                    'sender': sender,
                    'date': created[:10] if created else '',
                    'text': text[:500],
                })
    except Exception as e:
        print(f"  {space_name}: {e}")

# Sort by date
all_matches.sort(key=lambda x: x['date'], reverse=True)

# Save
with open('recruitment/cfo_chat_messages.json', 'w', encoding='utf-8') as f:
    json.dump(all_matches, f, indent=2, ensure_ascii=False)

print(f"Found {len(all_matches)} relevant messages across {len(SPACES)} spaces")
for m in all_matches[:30]:
    print(f"\n[{m['date']}] {m['space']} | {m['sender']}:")
    print(f"  {m['text'][:200]}")
