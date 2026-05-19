# Permissions Matrix — Who Can Edit What

Snapshot as of 2026-05-12. Use this when someone says "I'm blocked" or "I can't see X."

## BEI AP Master (`1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c`) — POST 2026-05-12 cleanup

| Email | Role | Notes |
|---|---|---|
| sam@bebang.ph | Owner | Container-bound Apps Script runs as Sam |
| bethina@bebang.ph | Writer | Active |
| denise@bebang.ph | Writer | Finance lead since 2026-04-28 |
| izza@bebang.ph | Writer | Active |
| angelamel@bebang.ph | Writer | Ms. Mel — Active. Types in Suppliers SOA / Head Office / CAPEX |
| je-ann@bebang.ph | Writer | Active |
| **avislyndelle@bebang.ph** | Writer | **Added 2026-05-12** (was commenter, upgraded). Avis Lyndelle Principe |
| drew@bebang.ph | Reader | Manager visibility |

**REMOVED 2026-05-12 (resigned):**
- ~~juanna@bebang.ph~~ — Resigned 2026-04-27 (Finance lead) — REMOVED
- ~~alyssa@bebang.ph~~ — Resigned 2026-05-07 (Head accountant) — REMOVED
- ~~butch@bebang.ph~~ — Resigned 2026-05-07 (CFO) — was never on AP Master directly

**Tab-level protections (post 2026-05-12):**
All 14 auto-rebuilt tabs are STRICT-locked (editors=sam@bebang.ph). The team CAN see them (reader/writer at sheet level) but CANNOT type in them. The 3 data-entry tabs (Suppliers SOA, Head Office, CAPEX) remain UNLOCKED for writers.

| Tab | Lock state | Who can edit |
|---|---|---|
| Suppliers SOA, Head Office, CAPEX | UNLOCKED | All sheet writers |
| All Liabilities, Summary, Commissary, Head Office (BEI), Needs Attention | 🔒 STRICT | sam@bebang.ph only |
| Needs RFP, With Finance (No RFP), Check Released, In Pipeline, VAT Gaps, PAID | 🔒 STRICT | sam@bebang.ph only |
| _sync_log, _sync_log_v3, _dry_run_preview | 🔒 STRICT | sam@bebang.ph only |

## Archived sheet A1 — 05 - AP Opening Balance (`1ZHe...`)

⚠️ This is the WRONG sheet for new entries but the team still treats it as live. Permissions are scattered:

| Email | Role |
|---|---|
| sam@bebang.ph | organizer |
| kath@bebang.ph | fileOrganizer |
| james.tamaca@bebang.ph | fileOrganizer |
| bethina@bebang.ph | fileOrganizer |
| juanna@bebang.ph | fileOrganizer (resigned) |
| alyssa@bebang.ph | fileOrganizer (resigned) |
| butch@bebang.ph | fileOrganizer (resigned) |
| marco@bebang.ph | fileOrganizer |
| anthony@bebang.ph | writer |
| Google Chat room | writer |
| cayla@bebang.ph | reader |
| dom@bebang.ph | reader |

**No Avis here either.** Owner field is empty.

## FPM (`1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw`)

- **Owner:** denise@bebang.ph
- Editors mostly Denise, Juanna (legacy), plus internal accounting team
- Read by: AP Master script (as Sam)

## Compliance AppSheet Database (`1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q`)

- **Owner:** sam@bebang.ph
- Maintained by: Ashish (schema) + Cayla / Luwi (tagging)
- Read by: AP Master script + Sheets Receiver (for Frappe sync)

## Cashflow Tracker (`1W2GERTwbODqfbHM70XpJJEtFwL-jIPbb2zzwC0Rcfeg`)

- **Owner:** sam@bebang.ph
- Read-only for everyone else by default

## Permission discipline

When a new BEI finance team member joins, **add them as Writer to** (in this order):
1. BEI AP Master (`1bQ6mO1FXD...`)
2. FPM (`1t4wJLi...`) — coordinate with Denise (she owns it)
3. Compliance AppSheet (read only)
4. Cashflow Tracker (read only)
5. PCM (`1_5BSZeNL...`) — only if they touch CAPEX
6. BGF Investments (`1dfIyAeGH_...`) — only if they touch partner reserves
7. BEI Bank Balances (`19kSR8HQ...`) — only if they manage bank reconciliation

When someone resigns:
1. Revoke from all of the above
2. **Reassign FPM ownership** if it was theirs (Juanna → Denise pattern)
3. Document the change in `history.md` of this skill

## Why Avis is currently locked out (root cause)

Avis (`avislyndelle@bebang.ph`) is listed as an Editor on the **receiving sheets** in the `/dr-gr-rfp` skill, but she is **not** on the **AP Master** or **FPM** or any of the archived AP sheets. So when she tries to open links the accounting team is sharing (which point to AP Master / archived SOA / FPM), she gets blocked.

**Fix:**
```python
# Add Avis as Editor to all live AP sheets
from googleapiclient.discovery import build
from google.oauth2 import service_account

creds = service_account.Credentials.from_service_account_file(
    'credentials/task-manager-service.json',
    scopes=['https://www.googleapis.com/auth/drive']
).with_subject('sam@bebang.ph')
drive = build('drive', 'v3', credentials=creds, cache_discovery=False)

SHEETS_TO_ADD = [
    '1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c',  # AP Master
    '1ZHe2VoAFa94ET4I68C1jWM7nMzTdTCvttwZbICaLtB4',  # Archived A1 (still being edited)
    '1jSwZRyIPisU4jiKS-Tn9VFoLukQI8UNoW13Hoov-75Y',  # Archived A2
    '1_5BSZeNL9A_o5QO6WD4L42gGjYY6-yCDfgTp01y0fpo',  # PCM
    '19kSR8HQdveZVleMZORGQetHXVCxaeDy6EMlKfe2G77w',  # Bank Balances
    '1W2GERTwbODqfbHM70XpJJEtFwL-jIPbb2zzwC0Rcfeg',  # Cashflow Tracker
]

for sheet_id in SHEETS_TO_ADD:
    drive.permissions().create(
        fileId=sheet_id,
        body={'type': 'user', 'role': 'writer', 'emailAddress': 'avislyndelle@bebang.ph'},
        sendNotificationEmail=False,
        supportsAllDrives=True,
    ).execute()
```

## Audit trail

Every sheet has a revision history (File → Version history → See version history). The Apps Script entries appear as Sam at every full hour mark (xx:12 PHT). Human edits appear at irregular times with the actual editor's email.

For per-cell audit logs, check the `_sync_log_v3` tab on AP Master.
