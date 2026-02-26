---
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17
**Commit:** 7b998877f | **Health Score:** 85% LIVE (erp_sync stubs drag this down)
---

# Department Feature Matrix: Cross-cutting Concerns

## Summary

- Frontend pages: 15
- Backend endpoints: 47 total (40 LIVE, 7 STUB/PARTIAL — all 5 erp_sync.py sync functions + 2 proxy wrappers)
- DocTypes: 10 (BEI Announcement, BEI Announcement Read Receipt, BEI Kudos, BEI CEO Complaint, BEI Support Ticket, BEI Weather Log, BEI Weather Zone, BEI Weather Zone Store, BEI Mall Permit, Employee Separation)
- Health Score: 85% LIVE

**Sprint 06 additions:** BEI Announcement Read Receipt DocType, `acknowledge_announcement`, `create_announcement`, `get_unread_announcements`, `attach_complaint_evidence`, CI gate `.github/workflows/dm-checklist-gate.yml`

## Feature Matrix

| Feature | Frontend Page | FE Status | Backend API | BE Status | Notes |
|---------|--------------|-----------|-------------|-----------|-------|
| Communication Hub | `/dashboard/communication` | LIVE | (nav page) | — | "2 unread" count is hardcoded (GAP-068) |
| Announcements List | `/dashboard/communication/announcements` | LIVE | `communication.get_announcements` | LIVE | |
| Announcement Acknowledgment | `/dashboard/communication/announcements` | LIVE | `communication.acknowledge_announcement` | LIVE | Sprint 06; idempotent |
| Unread Announcements Count | `/dashboard/communication` | PARTIAL | `communication.get_unread_announcements` | LIVE | API exists; FE shows hardcoded "2 unread" |
| Create Announcement | — | NOT BUILT | `communication.create_announcement` | LIVE | **GAP-069: no admin UI page** |
| CEO Complaint | `/dashboard/communication/complaint` | LIVE | `communication.submit_ceo_complaint` | LIVE | |
| Kudos Send/Receive/Leaderboard | `/dashboard/communication/kudos` | LIVE | `communication.send_kudos`, `get_kudos_leaderboard` | LIVE | Leaderboard period param ignored in SQL |
| Create Support Ticket | `/dashboard/communication/support` | LIVE | `communication.create_support_ticket` | LIVE | |
| Support Ticket Admin | — | NOT BUILT | None | GAP | **GAP-070: no admin view for IT support** |
| Store Analytics Dashboard | `/dashboard/analytics/store` | LIVE | `dashboard.get_store_dashboard` | LIVE | |
| Area Analytics Dashboard | `/dashboard/analytics/area` | LIVE | `dashboard.get_area_dashboard` | LIVE | |
| Ops-Level Analytics | `/dashboard/analytics` | LIVE | `dashboard.get_ops_dashboard` | LIVE | |
| Biometric Dashboard | `/dashboard/biometric` | LIVE | `biometric_monitoring.get_dashboard_summary` | LIVE (cache) | Cache-backed; stale flag if >6h old |
| Device Status | `/dashboard/biometric/devices` | LIVE | `biometric_monitoring.get_device_status` | LIVE (cache) | 46 devices |
| Biometric Issues | `/dashboard/biometric/issues` | LIVE | `biometric_monitoring.get_not_punching`, `get_wrong_device`, `get_ghost_punchers` | LIVE (cache) | |
| Manual Cache Refresh | `/dashboard/biometric` | LIVE | `biometric_monitoring.refresh_biometric_cache` | LIVE | System Manager only |
| Employee Clearance Status | `/dashboard/` (clearance) | LIVE | `employee_clearance.get_clearance_status` | LIVE | |
| Create Employee Separation | HR admin | LIVE | `employee_clearance.create_employee_separation` | LIVE | Auto-populates DOLE compliance |
| Exit Interview | Clearance page | LIVE | `employee_clearance.get_exit_interview_questions`, `submit_exit_interview_responses` | LIVE | |
| Disable Bio ID (ADMS) | Clearance checklist | LIVE | `employee_clearance.disable_bio_id` | LIVE | HTTP to ADMS (hardcoded localhost:8080 — GAP-072) |
| COE Generation | Clearance page | LIVE (partial) | `employee_clearance.generate_coe` | LIVE | **GAP-071: no custom COE template; generic Frappe format** |
| Google Chat Spaces | `/dashboard/settings/google-chat` | LIVE | `google_chat.get_user_chat_spaces` | LIVE | |
| Google Drive Search | File pickers | LIVE | `google_drive.search_drive_files` | LIVE | User-delegated OAuth |
| ERP Sync: AR Aging | — | STUB | `erp_sync.sync_ar_aging` | **STUB** | **GAP-006: log-only, no Sales Invoice updates** |
| ERP Sync: Inventory | — | STUB | `erp_sync.sync_inventory` | **STUB** | **GAP-007: log-only, no Stock Reconciliation** |
| ERP Sync: COA | — | STUB | `erp_sync.sync_coa` | **STUB** | **GAP-008: log-only, no Account creation** |
| ERP Sync: Bank Accounts | — | STUB | `erp_sync.sync_bank_accounts` | **STUB** | **GAP-025: log-only** |
| ERP Sync: AP Opening | — | STUB | `erp_sync.sync_ap_opening` | **STUB** | **GAP-009: log-only, no Purchase Invoices** |
| Sheets Receiver Webhook | — | N/A | `erp_sync.webhook` | LIVE | Forwards to sheets-receiver:8765 |
| Blip AI Context | No direct FE | N/A | `blip.get_user_context`, `blip.get_leave_balance` | LIVE | allow_guest=True |
| Biometric Daily Digest | N/A | Scheduled | `utils.biometric_alerts.send_daily_digest` | LIVE | 23:00 UTC daily |
| Separation notifications | N/A | Hooks | `employee_clearance.on_separation_created`, `on_separation_updated` | LIVE | **GAP-073: boarding_status never set to Completed** |

## DocType Relationships

| DocType | Link Fields | Child Tables | Submittable? |
|---------|-------------|-------------|--------------|
| BEI Announcement | target_department→Department, published_by→User | None | No |
| BEI Announcement Read Receipt | announcement→BEI Announcement, employee→Employee | None | No |
| BEI Kudos | from_employee→Employee, to_employee→Employee | None | No |
| BEI CEO Complaint | submitted_by→User, employee→Employee | None | No |
| BEI Support Ticket | submitted_by→User, assigned_to→User | None | No |
| Employee Separation | employee→Employee | custom_dole_compliance (BEI DOLE Compliance Checklist) | No |

## Gaps Found

| ID | Feature | Blocker Type | Severity | Notes |
|----|---------|-------------|----------|-------|
| GAP-006 | ERP Sync AR Aging: log-only | Backend Stub | Critical | AR aging never written to Frappe |
| GAP-007 | ERP Sync Inventory: log-only | Backend Stub | Critical | No Stock Reconciliation |
| GAP-008 | ERP Sync COA: log-only | Backend Stub | Critical | No Account creation |
| GAP-009 | ERP Sync AP Opening: log-only | Backend Stub | Critical | No Purchase Invoices |
| GAP-025 | ERP Sync Bank Accounts: log-only | Backend Stub | High | |
| GAP-046 | G-046 failures silently logged | Bug | High | Inter-company invoices can fail silently |
| GAP-068 | Unread announcement count hardcoded | Frontend | Medium | Users see fake "2 unread" |
| GAP-069 | Announcement admin create UI | Frontend | Medium | HR Manager cannot create announcements from app |
| GAP-070 | Support ticket: no admin view | Backend | Medium | IT support cannot manage tickets from app |
| GAP-071 | COE custom print format missing | Asset | Medium | PDF not professional |
| GAP-072 | ADMS base URL hardcoded localhost:8080 | Config | Medium | |
| GAP-073 | boarding_status never set to Completed | Bug | Medium | Duplicate GChat separation alerts |

## Improvements

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| ERP Sync stubs | 5/8 functions log-only | Implement actual DB writes for all 5 | Critical |
| Unread announcement count | Hardcoded "2 unread" | Wire to get_unread_announcements API | HIGH |
| Support ticket admin | Submitter-only views | Add assign_ticket, update_ticket_status, get_all_tickets + admin UI | MEDIUM |
| ADMS base URL | Hardcoded localhost:8080 | Move to frappe.db.get_single_value("BEI Settings", "adms_base_url") | MEDIUM |
| COE PDF template | Generic Frappe format | Create custom COE print format with BEI letterhead | MEDIUM |
