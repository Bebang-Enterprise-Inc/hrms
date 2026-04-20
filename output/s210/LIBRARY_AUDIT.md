# Library Audit - S210

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
