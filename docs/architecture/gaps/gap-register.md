# Gap Register
**Scanned:** 2026-02-23 | **Commit:** 7b998877f | **Previous Scan:** 2026-02-17
**Total Gaps: 96** | Urgent: 18 | High: 31 | Medium: 35 | Low: 12

---

## Code-Verification Overrides (2026-02-25)

Reference: `output/plan-audit/p0-plus-10-p1-2026-02-25/code_verification.md`

The following entries in this register have stale wording and must not be treated as net-new missing builds without reproduce evidence:
- `GAP-001, GAP-002, GAP-003, GAP-004, GAP-005, GAP-013, GAP-014, GAP-020, GAP-021, GAP-022`

The following entries are partial and should be treated as consolidation/policy hardening:
- `GAP-011, GAP-015, GAP-018, GAP-041, GAP-092`

Execution planning should use the gate values in:
- `docs/plans/2026-02-25-p0-p1-business-evidence-lock.md`

---

## URGENT Gaps (18)

| ID | Department | Feature | Blocker Type | Notes |
|----|-----------|---------|-------------|-------|
| GAP-001 | HR Self-Service | BEI Shift Record → Frappe Attendance bridge missing — GPS punches invisible to payroll | Integration | Employees using only the app appear absent in payroll. Entire GPS punch system disconnected from pay |
| GAP-002 | HR Self-Service | onboarding.py IndentationError lines 354-357 — all onboarding endpoints return 500 | Bug | New hire creation via onboarding approval crashes at runtime |
| GAP-003 | Store Ops / Warehouse | preview_trip_stops missing from dispatch.py — Trip Wizard Step 3 always broken | Bug | All stores show "No order" in wizard; auto-selection fails |
| GAP-004 | Inventory | Cycle count v1 endpoint called from dashboard/counts — throws deprecation error immediately | Bug | /dashboard/inventory/counts completely broken; stores cannot submit counts |
| GAP-005 | HR Management | Overtime: 4 live endpoints, zero frontend | Frontend | OT requests pile up; payroll may silently misprocess |
| GAP-006 | Cross-cutting | ERP Sync AR Aging: log-only stub — no Sales Invoice updates | Backend Stub | AR aging data fed by Sheets Receiver but Frappe side does nothing |
| GAP-007 | Cross-cutting | ERP Sync Inventory: log-only stub — no Stock Reconciliation | Backend Stub | Critical for ERP go-live; inventory never reconciled via sync |
| GAP-008 | Cross-cutting | ERP Sync COA: log-only stub — no Account creation | Backend Stub | COA accounts never created via sync |
| GAP-009 | Cross-cutting | ERP Sync AP Opening: log-only stub — no Purchase Invoices | Backend Stub | AP opening balances never written to ERP |
| GAP-010 | Hire-to-Onboard | Recruitment kanban stage name mismatch — pipeline always shows 0 | Bug | FE: Applied/Screening/Interview/Offer/Hired vs BE: Open/Replied/Hold/Accepted/Rejected |
| GAP-011 | Hire-to-Onboard | Job Offer → Employee creation gap — no automation bridge | Design | HR must manually trigger onboarding after offer |
| GAP-012 | Hire-to-Onboard | Employee ORM insert in onboarding — 5 cascading validation traps (MEMORY Lesson #6) | Bug | New hire creation may fail with cryptic validation errors |
| GAP-013 | Finance | SOA: 3 endpoints, zero frontend | Frontend | Finance cannot generate Statement of Account from app |
| GAP-014 | Finance | 3PL Billing: 5+ endpoints, zero frontend | Frontend | Finance cannot process 3PL billing from app |
| GAP-015 | Finance | Form 2307 EWT Certificate: tabComment storage — no PDF, not BIR-compliant | Architecture | Not searchable; fragile string parsing |
| GAP-016 | Procurement | BEI Purchase Order not submittable — approved POs editable post-approval | Architecture | Fraud risk; no docstatus audit trail |
| GAP-017 | Procurement | Single Source Supplier report: no frontend — ₱23.6M audit finding unmonitored | Frontend | Internal Audit Jan 30 finding (RIGHT GOODS) |
| GAP-018 | Procurement | Form 2307: no DocType (procurement context duplicate of GAP-015) | Architecture | generate_form_2307_entry uses tabComment |

---

## HIGH Gaps (31)

| ID | Department | Feature | Blocker Type | Notes |
|----|-----------|---------|-------------|-------|
| GAP-019 | HR Management | Leave rejection uses db_set not doc.cancel — balance not released on rejection | Bug | |
| GAP-020 | Store Ops | Approval Queue not created if resolve_warehouse fails — order sits in limbo | Bug | |
| GAP-021 | Finance | Monthly billing queries docstatus=1 on non-submittable DocType — returns zero records | Bug | |
| GAP-022 | Store Ops | POS Upload: gross_sales/net_sales never populated from uploaded file | Bug | Dashboard analytics inaccurate |
| GAP-023 | HR Management | DOLE Compliance: DocType exists, zero API/frontend in HR | Feature Gap | Compliance tracking unimplemented |
| GAP-024 | HR Management | Exit Interview: DocType exists, zero API/frontend in HR mgmt | Feature Gap | |
| GAP-025 | Cross-cutting | ERP Sync Bank Accounts: log-only | Backend Stub | Bank accounts never created via sync |
| GAP-026 | Hire-to-Onboard | MRF → Hiring Manager: no notification | Integration | MRFs sit unnoticed |
| GAP-027 | Hire-to-Onboard | MRF Hiring Manager → HR Manager: no notification | Integration | HR Managers unaware |
| GAP-028 | Clock-In to Pay | Overtime approve/reject frontend (confirmed in flow analysis) | Frontend | Duplicate of GAP-005 |
| GAP-029 | Warehouse | get_vehicles response format mismatch — vehicle dropdown always falls back to free-text | Bug | |
| GAP-030 | Projects | Preventive Maintenance: no implementation (no DocType, no API, no frontend) | Feature Gap | Sprint 04 backlog item |
| GAP-031 | Projects / Warehouse | Mall Permits: 5 live endpoints, zero frontend | Frontend | Permit management requires Frappe Desk |
| GAP-032 | Store Ops / Projects | Maintenance Request: no notification to Projects on creation | Bug | Urgent requests unnoticed for hours |
| GAP-033 | Projects | Maintenance charge: no notification to Store Supervisor | Bug | Charges go unacknowledged; billing delayed |
| GAP-034 | Expenses/PCF | ML model absent on EC2 | Deployment | Review queue floods if Gemini+OpenAI also absent |
| GAP-035 | Expenses/PCF | PCF admin panel: no frontend | Frontend | PCF setup requires Frappe Desk |
| GAP-036 | Expenses/PCF | PCF replenishment lifecycle — flag only, no GL entry or cheque tracking | Design | No trackable lifecycle |
| GAP-037 | Supervisor Tools | Coverage request approve: not wired in queue FE | Frontend | Coverage requests cannot be approved from unified queue |
| GAP-038 | Supervisor Tools | Supervisor landing page missing — no /dashboard/supervisor/page.tsx | Frontend | Area supervisors land on Visits for dashboard |
| GAP-039 | HR Self-Service | Leave rejection balance correction — reject_correction uses db_set | Bug | Rejected leave does not release balance |
| GAP-040 | Hire-to-Onboard | CEO MRF approval uses System Manager role — governance bypass | Bug | Any System Manager can approve senior hires |
| GAP-041 | Procurement | EWT JV: wrong AP account (2101001 vs 2101101); party on both rows violates DM-1 | Bug | Incorrect GL; reconciliation errors |
| GAP-042 | Procurement | G-046 not visible in Procurement module | Integration | Procurement cannot audit inter-company transactions |
| GAP-043 | Procurement | Advance subsidiary ledger supplier name/ID mismatch | Bug | Supplier drill-down returns wrong data |
| GAP-044 | Commissary | QC Form tab not wired in quality frontend | Frontend | QC forms submitted only via API |
| GAP-045 | Commissary | Requisition approval UI for SCM manager | Frontend | SCM cannot approve from app |
| GAP-046 | Cross-cutting | G-046 failures silently logged — no GChat on failure | Bug | Inter-company invoices can go uncreated silently |
| GAP-056 | Supervisor Tools | Biometric punch review: not wired into supervisor tools | Feature Gap | Biometric monitoring exists but not wired |
| GAP-060 | Inventory | Variance resolution endpoint unconfirmed | Verify | FE has modal but API wiring unclear |
| GAP-092 | Warehouse | Delivery billing policy hardening: default auto-create on `confirm_delivery`; pre-delivery billing exception requires dual approval (Daymae/CPO + Butch/CFO) | Design | Support valid advance-billing business cases (e.g., construction projects) without weakening standard delivery-first billing control |

---

## MEDIUM Gaps (35)

| ID | Department | Feature | Blocker Type |
|----|-----------|---------|-------------|
| GAP-047 | Finance | AP Aging: no dedicated page — buried in widget only | Frontend |
| GAP-048 | Finance | OR Follow-up: no actual notification sent | Bug |
| GAP-049 | HR Management | Payroll comparison is a stub — returns Frappe data labeled as APEX | Backend Stub |
| GAP-050 | HR Self-Service | OB Cancel: no self-service UI | Frontend |
| GAP-051 | HR Self-Service | Coverage Request approve flow: no frontend | Frontend |
| GAP-052 | HR Self-Service | Training compliance: frontend uses hardcoded mock data | Frontend-Backend mismatch |
| GAP-053 | Supervisor Tools | Queue approve_item ref-doc update swallows errors silently | Bug |
| GAP-054 | Supervisor Tools | Queue escalate: no notification to new approver | Integration |
| GAP-055 | Supervisor Tools | Action plan overdue: no auto-status update | Feature Gap |
| GAP-057 | Inventory | Shelf life extension approval: no frontend | Frontend |
| GAP-058 | Inventory | COS RECON export: no frontend | Frontend |
| GAP-059 | Inventory | Cycle count reconciliation: no frontend | Frontend |
| GAP-061 | Store Ops | Trip creation and departure: no frontend | Frontend |
| GAP-062 | Store Ops | Store returns from receiving: no FE entry point | Frontend |
| GAP-063 | Store Ops | FQI severity field mismatch — data silently dropped | Data Loss |
| GAP-064 | Warehouse | Driver selector in Trip Wizard: free-text only | Integration |
| GAP-065 | Warehouse | Billing pages: unknown backend — may be placeholders | Unclear |
| GAP-066 | Commissary | BOM management: no dedicated UI | Frontend |
| GAP-067 | Commissary | get_vehicles vehicle dropdown always text input | Bug |
| GAP-068 | Cross-cutting | Unread announcement count hardcoded | Frontend |
| GAP-069 | Cross-cutting | Announcement admin create UI | Frontend |
| GAP-070 | Cross-cutting | Support ticket: no admin view | Backend |
| GAP-071 | Cross-cutting | COE custom print format missing | Asset |
| GAP-072 | Cross-cutting | ADMS base URL hardcoded localhost:8080 | Config |
| GAP-073 | Cross-cutting | boarding_status never set to Completed — duplicate GChat alerts | Bug |
| GAP-074 | Projects | Incident Report: DocType exists, zero API/frontend | Feature Gap |
| GAP-075 | Projects | Coaching Log → Performance Review link missing | Design |
| GAP-076 | HR Management | Enrichment reminder via GChat: dead code | Bug |
| GAP-077 | Procurement | Supplier duplicates/data quality: no dedicated page | Frontend |
| GAP-078 | Finance | doc_events not wired to BEI billing | Automation |
| GAP-079 | Finance | Finance reports frontend missing | Frontend |
| GAP-080 | Warehouse | _build_trip_doc does not copy estimated_minutes | Bug |
| GAP-081 | Store Ops | Opening/closing checklists hardcoded | Design |
| GAP-082 | Inventory | Inventory hub stats hardcoded | Bug |
| GAP-083 | HR Self-Service | Roster/Shift Calendar: not on Next.js | Frontend |
| GAP-084 | HR Self-Service / Store Ops | BEI Approval Queue not created when approval routing fails | Bug |
| GAP-085 | HR Management | bulk_import_gov_ids only via script | Frontend |
| GAP-086 | Projects | Maintenance multi-photo completion truncated | Bug |
| GAP-087 | Projects | Maintenance status bypass: allows skipping Completed | Bug |
| GAP-088 | Projects | Internal store charges never billed | Bug |
| GAP-089 | Finance | 3PL JE idempotency: duplicate JE possible | Bug |
| GAP-090 | Finance | Monthly billing: no manual trigger UI | Frontend |
| GAP-091 | Store Ops / Inventory | inventory.ordering page uses simplified API | Verify |

---

## LOW Gaps (12)

| ID | Department | Feature | Blocker Type |
|----|-----------|---------|-------------|
| GAP-093 | Store Ops | ordering.py deprecated proxies still in use | Tech Debt |
| GAP-094 | Inventory | Returns: Material Issue vs Material Transfer inconsistency | Logic |
| GAP-095 | Expenses/PCF | validate_pcf_batch hook is no-op | Code Quality |
| GAP-096 | Expenses/PCF | on_batch_update hook is no-op | Code Quality |
