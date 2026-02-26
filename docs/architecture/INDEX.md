# BEI ERP System Flow Map - Architecture Documentation

**Last Updated:** 2026-02-26  
**Last Scanned:** 2026-02-26 (baseline refresh) | **Deep Architecture Scan Snapshot:** 2026-02-23 (`7b998877f`)
**Previous Scan:** 2026-02-17 | **Previous Commit:** 7e445d778
**Platform:** my.bebang.ph (React/Next.js) + hq.bebang.ph (Frappe HRMS)
**Owner:** Sam Karazi  
**Next Review:** 2026-03-05

---

## Executive Summary

> Note: The department/gap analytics below are from the 2026-02-23 deep scan snapshot.
> For the latest architecture truth, use `SOLUTION_ARCHITECTURE_DOCUMENT.md`,
> `REPOSITORY_INVENTORY.md`, and `INFRASTRUCTURE_INVENTORY.md`.

The BEI ERP system is a Frappe HRMS-based platform serving 765 employees across 12 business departments, integrating a React/Next.js frontend (my.bebang.ph) with a Frappe backend (hq.bebang.ph). The February 23 audit scanned 179+ frontend pages across 50+ Python API files, documenting 96 gaps (down from 127 on Feb 17 as many high-priority items were resolved).

Since the February 17 scan, significant new functionality has shipped: the Commissary module grew from stubs to 48 LIVE endpoints (commissary_quality.py, commissary_bom.py, commissary_requisition.py all now fully built); the Warehouse module gained full Trip Wizard, picking workflow, BEI Pick List DocType, driver scheduling, and route management; and the HR Leave Command Center launched on Sprint 09. The ERP sync stubs (5 of 8 functions in erp_sync.py) remain the most critical unresolved architecture gap — they parse data correctly but write nothing to Frappe DocTypes, blocking ERP go-live data integration.

Health metrics: Store Ops (87% LIVE), HR Self-Service (92%), HR Management (88%), Expenses/PCF (93%), Supervisor Tools (95%), Finance (100%), Procurement (100%), Warehouse (100%), Commissary (100%), Projects (100%), Cross-cutting (85% — erp_sync stubs drag this down). The most critical single gap is GAP-001: BEI Shift Record GPS punches are never written to Frappe Attendance, meaning employees who use only the app appear absent in payroll. The second-most critical is the ERP Sync stub cluster (GAP-006 through GAP-009 and GAP-025): five sync functions log-only with no actual DB writes, leaving AR aging, inventory reconciliation, COA, AP opening, and bank accounts un-synced.

The system has 147 unique directional cross-department connections. Store Ops is the most-connected department (43 total), followed by Finance (39) and Cross-cutting (38 inbound). The most critical integration point is the commissary-to-store supply chain, which now has a fully functional pick-list-based fulfillment path. Procurement has 33 frontend pages and 81 endpoints — the most mature module in the system.

---

## Department Health Scores

| Department | Pages | Endpoints | LIVE % | Gaps | Health | Priority |
|------------|-------|-----------|--------|------|--------|----------|
| Store Ops | 13 | 30 | 87% | 9 | 🟢 | HIGH |
| Inventory | 10 | 19 | 89% | 10 | 🟢 | MEDIUM |
| HR Self-Service | 18 | 52 | 92% | 8 | 🟢 | HIGH |
| HR Management | 16 | 58 | 88% | 10 | 🟢 | HIGH |
| Expenses/PCF | 13 | 28 | 93% | 8 | 🟢 | MEDIUM |
| Supervisor Tools | 12 | 38 | 95% | 11 | 🟢 | HIGH |
| Finance | 13 | 42 | 100% | 10 | 🟢 | HIGH |
| Procurement | 33 | 81 | 100% | 12 | 🟢 | HIGH |
| Warehouse | 20 | 34 | 100% | 10 | 🟢 | HIGH |
| Commissary | 11 | 48 | 100% | 8 | 🟢 | MEDIUM |
| Projects | 10 | 40 | 100% | 7 | 🟢 | MEDIUM |
| Cross-cutting | 15 | 47 | 85% | 13 | 🟡 | HIGH |

**Health Legend:**
- 🟢 **Green** (>80% LIVE): Production-ready, minor gaps
- 🟡 **Yellow** (50-80% LIVE): Functional but with significant gaps
- 🔴 **Red** (<50% LIVE): Critical functionality missing

---

## Top 15 Gaps (Sorted by Priority)

| ID | Department | Feature | Blocker Type | Priority |
|----|-----------|---------|-------------|---------|
| GAP-001 | HR Self-Service | BEI Shift Record never bridges to Frappe Attendance — GPS punches invisible to payroll | Integration | URGENT |
| GAP-002 | HR Self-Service | `onboarding.py` IndentationError lines 354-357 — all onboarding returns 500 | Bug | URGENT |
| GAP-003 | Store Ops / Warehouse | `preview_trip_stops` missing — Trip Wizard Step 3 always broken | Bug | URGENT |
| GAP-004 | Inventory | Cycle count dashboard calls deprecated v1 endpoint — `/dashboard/inventory/counts` broken | Bug | URGENT |
| GAP-005 | HR Management | Overtime: 4 live endpoints, zero frontend — OT pile up unmanaged | Frontend | URGENT |
| GAP-006 | Cross-cutting | ERP Sync AR Aging: log-only stub — no Sales Invoice updates | Backend Stub | URGENT |
| GAP-007 | Cross-cutting | ERP Sync Inventory: log-only stub — no Stock Reconciliation | Backend Stub | URGENT |
| GAP-008 | Cross-cutting | ERP Sync COA: log-only stub — no Account creation | Backend Stub | URGENT |
| GAP-009 | Cross-cutting | ERP Sync AP Opening: log-only stub — no Purchase Invoices | Backend Stub | URGENT |
| GAP-010 | Hire-to-Onboard | Recruitment kanban stage name mismatch — pipeline always shows 0 | Bug | URGENT |
| GAP-011 | Hire-to-Onboard | Job Offer → Employee creation gap — no automation bridge | Design | URGENT |
| GAP-012 | Hire-to-Onboard | Employee ORM insert in onboarding — cascading validation traps | Bug | URGENT |
| GAP-013 | Finance | SOA: 3 endpoints, zero frontend — Finance cannot generate SOA from app | Frontend | URGENT |
| GAP-014 | Finance | 3PL Billing: 5+ endpoints, zero frontend — no 3PL billing UI | Frontend | URGENT |
| GAP-015 | Finance | Form 2307 EWT Certificate stored in tabComment — no PDF, not BIR-compliant | Architecture | URGENT |

**Full Gap Register:** [gaps/gap-register.md](gaps/gap-register.md) | [gaps/gap-register.csv](gaps/gap-register.csv)
**Total Gaps:** 96 (URGENT: 18 | HIGH: 31 | MEDIUM: 35 | LOW: 12)

---

## Changes Since Feb 17

The following significant features were built between Feb 17 and Feb 23:

**Commissary (major sprint):**
- `commissary_quality.py` — previously a placeholder stub, now 15 live endpoints covering FQI, QC forms, quality inspections, wastage trends
- `commissary_bom.py` — 4 live endpoints for full Frappe BOM CRUD (create, update, detail, feasibility)
- `commissary_requisition.py` — 10 live endpoints for RM requisitions and work order integration
- `picking.py` — new file: 5 endpoints, BEI Pick List DocType, pick-list-based fulfillment workflow
- `/commissary/wastage-trends` page — new: full chart dashboard with 4 group-by dimensions
- G-046 inter-company invoices — now live: async BKI→BEI Sales Invoice + Purchase Invoice on stock transfer

**Warehouse (major sprint):**
- Full route CRUD (get, create, update, delete, duplicate, reorder stops)
- `create_trip_from_route` — new endpoint linking store orders to trip stops
- Trip Creation Wizard at `/trips/create` with drag-and-drop stop ordering
- `_send_delivery_notification` — "1 stop away" Google Chat now live (previously mock)
- Driver scheduling: `get_available_drivers`, `assign_driver`, `get_driver_schedule` all new
- `_create_delivery_billing` — async BEI Billing Schedule creation on delivery confirm

**HR (Sprint 09):**
- Leave Command Center at `/hr-admin/leaves/` — `get_leave_overview`, `get_all_leaves`, `check_leave_conflicts`, `bulk_update_leave_status` all live
- Biometric dashboard: confirmed LIVE (cache-backed, not mock as Feb 17 suspected)

**Procurement (Sprint 09 Phase 2):**
- PO Aging audit page at `/procurement/audit/aging/`
- Price History audit page at `/procurement/audit/price-history/`
- `get_open_po_aging`, `get_price_history`, `check_price_variance` endpoints

**Cross-cutting (Sprint 06):**
- BEI Announcement Read Receipt DocType added
- `acknowledge_announcement`, `create_announcement`, `get_unread_announcements` endpoints
- CI gate `.github/workflows/dm-checklist-gate.yml`

---

## Cross-Department Connection Summary

**Total Connections:** 147 unique directional pairs (Feb 17: 267 counting multi-type)

### Most Connected Departments

| Dept | Outbound | Inbound | Total |
|------|----------|---------|-------|
| Store Ops | 23 | 20 | 43 |
| Finance | 17 | 22 | 39 |
| Cross-cutting | 14 | 24 | 38 |
| Warehouse | 17 | 14 | 31 |
| HR Management | 13 | 12 | 25 |
| Procurement | 14 | 11 | 25 |
| Commissary | 13 | 12 | 25 |

### Key Integration Points

- **Warehouse (most shared DocType)** — Warehouse record is a Link field in nearly every module
- **BEI Store Order** — shared across Store Ops, Supervisor Tools, Warehouse, Commissary, Cross-cutting
- **BEI Distribution Trip** — Store Ops, Warehouse, Commissary, Finance all read/write
- **BEI Approval Queue** — Store Ops, HR Self-Service, Supervisor Tools, Cross-cutting
- **Material Request** — Store Ops, Inventory, Warehouse, Commissary (the supply chain spine)

---

## Navigation

### Department Feature Matrices

- [Store Operations](departments/store-ops.md) — 13 pages, 30 APIs, 16 DocTypes
- [Store Inventory](departments/inventory.md) — 10 pages, 19 APIs, 7 DocTypes
- [HR Self-Service](departments/hr-self-service.md) — 18 pages, 52 APIs, 16 DocTypes
- [HR Management](departments/hr-management.md) — 16 pages, 58 APIs, 14 DocTypes
- [Expenses & PCF](departments/expenses.md) — 13 pages, 28 APIs, 5 DocTypes
- [Supervisor Tools](departments/supervisor.md) — 12 pages, 38 APIs, 6 DocTypes
- [Finance & Accounting](departments/finance.md) — 13 pages, 42 APIs, 9 DocTypes
- [Procurement](departments/procurement.md) — 33 pages, 81 APIs, 12 DocTypes
- [Warehouse & Logistics](departments/warehouse.md) — 20 pages, 34 APIs, 13 DocTypes
- [Commissary](departments/commissary.md) — 11 pages, 48 APIs, 12 DocTypes
- [Projects & Maintenance](departments/projects.md) — 10 pages, 40 APIs, 13 DocTypes
- [Cross-cutting Concerns](departments/cross-cutting.md) — 15 pages, 47 APIs, 10 DocTypes

### Business Flow Diagrams

1. [Hire to Onboard](flows/01-hire-to-onboard.md) — MRF → Applicant → Job Offer → Employee
2. [Clock-In to Payslip](flows/02-clock-in-to-payslip.md) — GPS punch → Attendance → Payroll
3. [Leave Approval](flows/03-leave-approval.md) — Employee leave request workflow
4. [Store Order to Delivery](flows/04-store-order-delivery.md) — Store order → Commissary → Trip → Delivery
5. [PR to Payment](flows/05-pr-to-payment.md) — Procurement 4-level approval workflow
6. [Expense Reimbursement](flows/06-expense-reimbursement.md) — PCF batch submission and accounting
7. [Daily Store Cycle](flows/07-daily-store-cycle.md) — Opening report to bank deposit
8. [Maintenance Request](flows/08-maintenance.md) — Store R&M request to charge acknowledgement
9. [Employee Separation](flows/09-separation.md) — Clearance to DOLE compliance
10. [Store Visit & Coaching](flows/10-store-visit.md) — 100-point supervisor inspection
11. [Cycle Count & Variance](flows/11-cycle-count.md) — Blind count to Stock Reconciliation
12. [3PL Billing](flows/12-3pl-billing.md) — Trip completion to 3PL payment JE

### Connection Analysis

- [Department Interaction Matrix](connections/department-matrix.md) — 12×12 matrix
- [Critical Path Diagrams](connections/critical-paths.md) — 5 most-used end-to-end flows
- [Per-Department Connections](connections/per-department/) — Visual diagrams per department

### Gap Analysis

- [Gap Register (Markdown)](gaps/gap-register.md) — 96 gaps sorted by priority/severity
- [Gap Register (CSV)](gaps/gap-register.csv) — Machine-readable format
- [Improvements Register](gaps/improvements-register.md) — 30 non-blocking enhancement opportunities

### Data Model

- [Entity Relationship Diagrams](erd.md) — 6 domains (HR/Payroll, Procurement/Finance, Store Ops, Warehouse/Logistics, Commissary, Projects/Maintenance)

### Architecture Governance

- [Solution Architecture Document](SOLUTION_ARCHITECTURE_DOCUMENT.md) — full architecture baseline
- [NFR and SLO Baseline](NFR_SLO_BASELINE.md) — numeric reliability targets and current baseline
- [Security Architecture](SECURITY_ARCHITECTURE.md) — auth/authz/secrets/audit boundaries
- [Deployment Topology and DR](DEPLOYMENT_TOPOLOGY_AND_DR.md) — deployment flow + RTO/RPO commitments
- [Ownership Matrix](OWNERSHIP_MATRIX.md) — accountable owner and escalation model
- [ADR Index](adr/ADR-INDEX.md) — architecture decision log
- [Documentation Truth Protocol](DOCUMENTATION_TRUTH_PROTOCOL.md) — evidence-only update standard
- [Repository Inventory](REPOSITORY_INVENTORY.md) — exact repo paths/remotes/branches/commits
- [Infrastructure Inventory](INFRASTRUCTURE_INVENTORY.md) — AWS/network/DNS/cert/secrets/backups inventory
- [Hosting and Domains](HOSTING_AND_DOMAINS.md) — domain endpoints, hosting targets, and evidence divergences
- [Flow Catalog](FLOW_CATALOG.md) — unified flow index and current L3 flow coverage status
- [Monthly Snapshots](snapshots/2026-02.md) — monthly architecture truth baseline
- [Branch Intent (Rajat Handoff)](BRANCH_INTENT_handoff-rajat-sad-2026-02-26.md) — branch scope and guardrails to prevent mixed work

---

## Key Statistics

| Metric | Feb 23 | Feb 17 | Change |
|--------|--------|--------|--------|
| Frontend pages scanned | 179+ | 179 | stable |
| Backend API files | 50+ | 41 | +9 new files |
| Backend endpoints | 430+ | 492 (est.) | recount in progress |
| DocTypes (all) | 108+ | 108 | +new: Pick List, Announcement Read Receipt, Mall Permit |
| Gaps identified | 96 | 127 | -31 resolved |
| URGENT gaps | 18 | 5 | +13 newly identified |
| Improvements logged | 30 | — | new register |
| Cross-dept connections | 147 | 267 | methodology change |

---

## Scan Metadata

- **Scan Date:** 2026-02-23
- **Git Commit:** 7b998877f ("docs: append post-deployment fixes for HR Leave Command Center")
- **Agents:** dept-scanner-1 through 6, flow-tracer-1, synthesis-alpha, synthesis-bravo
- **Previous Scan:** 2026-02-17 | Commit 7e445d778
- **QA Status:** synthesis-bravo final assembly
