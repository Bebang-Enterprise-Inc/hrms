---
sprint_id: S173
display: Sprint 173
doc_type: debt-ledger
title: "S166 Browser-Proof Re-Test Debt Ledger — canonical catalog of 86 unproven L3 scenarios"
branch: s173-s166-retest-debt-ledger
status: LOCKED
related_sprints: [S166, S170, S172, S174]
source_audit: output/l3/s166/AUDIT_2026-04-08/AUDIT_FINDINGS_FINAL.md
created_date: 2026-04-08
owner: S174 (when executed — burn-down sprint)
sprint_registry_row: "S173 reserved on 2026-04-08 as the LEDGER sprint. Branch: s173-s166-retest-debt-ledger. This sprint creates and locks the debt catalog; S174 burns it down."
---

# S166 Browser-Proof Re-Test Debt Ledger

## Purpose

This document is the **canonical, persistent record** of every S166 L3 scenario that failed the strict 2026-04-08 browser-proof audit and therefore has NO trustworthy pass/fail verdict. It lives in `docs/plans/` because that is the only directory the BEI review workflow actually tracks. `output/` is agent scratch — this file is the audit trail.

**Without this ledger, the 86 unproven scenarios would be invisible after S172 closes out.** The ledger survives across sprints, across agent sessions, and across context compaction. Any agent that opens S172 or S173 MUST read this file.

## Headline Numbers (2026-04-08 audit)

- **Total S166 scenarios executed:** 143
- **Browser-proof compliant (keep as-is):** 22
  - `VERIFIED_BROWSER_PASS`: 16
  - `VERIFIED_BROWSER_DEFECT_PASS`: 6 (passed despite known product defect)
- **Legitimate skips with proof (not debt):** 31
  - `LEGITIMATE_SKIP_WITH_PROOF`: 31 (valid upstream blockers documented, e.g. TERMINATE chain blocked by missing Clearance doctypes pre-S170)
- **Verified browser failures (tracked as product defects, not test-debt):** 4
  - `VERIFIED_BROWSER_FAIL`: 4 (already in `output/l3/s166/DEFECTS.csv`)
- **RE-PROOF DEBT — audit rejected, no trustworthy verdict:** 86
  - `AUDIT_FAILED_NO_BROWSER_PROOF`: 55 (claimed pass but evidence has no screenshot / no Playwright action log)
  - `AUDIT_FAILED_API_ONLY`: 29 (tested via backend API shortcut, never drove the UI)
  - `AUDIT_FAILED_MISSING_SCREENSHOT`: 2 (both EMP-ADMS enrollment scenarios)

**Compliance rate: 22/143 = 15.4% clean.** The remaining 86 scenarios need re-proof before we can trust the L3 pass catalog.

## Debt by Module / Prefix

| Prefix (module) | NO_BROWSER_PROOF | API_ONLY | MISSING_SS | BROWSER_FAIL | Total | S172 Phase 8 touches? |
|---|---:|---:|---:|---:|---:|---|
| EMP-EDIT | 0 | 15 | 0 | 1 | **16** | NO |
| EMP-UX | 11 | 0 | 0 | 0 | **11** | partial (Phase 8 unblock) |
| EMP-SALARY | 1 | 8 | 0 | 1 | **10** | partial (Phase 8 unblock) |
| EMP-CREATE | 7 | 0 | 0 | 0 | **7** | NO |
| EMP-PAYROLL | 6 | 0 | 0 | 0 | **6** | partial (Phase 8 unblock) |
| EMP-STUB | 6 | 0 | 0 | 0 | **6** | NO |
| EMP-RBAC | 5 | 0 | 0 | 0 | **5** | NO |
| EMP-TRANSFER | 4 | 0 | 0 | 1 | **5** | NO |
| EMP-LEAVE | 4 | 0 | 0 | 0 | **4** | NO |
| EMP-ATTENDANCE | 3 | 0 | 0 | 0 | **3** | NO |
| EMP-REGULARIZE | 1 | 2 | 0 | 0 | **3** | NO |
| EMP-ADMS | 0 | 0 | 2 | 0 | **2** | NO |
| EMP-BIOCHANGE | 2 | 0 | 0 | 0 | **2** | NO |
| EMP-PAYSLIP | 2 | 0 | 0 | 0 | **2** | NO |
| EMP-PHOTO | 0 | 2 | 0 | 0 | **2** | NO |
| EMP-retest | 1 | 0 | 0 | 0 | **1** | NO |
| EMP-CLEAN | 1 | 0 | 0 | 0 | **1** | NO |
| EMP-COMPLETION | 0 | 1 | 0 | 0 | **1** | NO |
| EMP-CONFLICT | 0 | 0 | 0 | 1 | **1** | NO |
| EMP-DISCIPLINARY | 0 | 1 | 0 | 0 | **1** | partial (Phase 8 unblock) |
| EMP-OVERTIME | 1 | 0 | 0 | 0 | **1** | partial (Phase 8 unblock) |

## Full Scenario List

Grouped by module. Re-proof priority:
- **P0** core lifecycle path, cannot ship go-live without proof (CREATE, SALARY, EDIT/GOVID/BANK, ATTENDANCE, PAYROLL, PAYSLIP, ADMS)
- **P1** compliance / audit / UX path (DISCIPLINARY, TERMINATE, RBAC, UX, OVERTIME, LEAVE, TRANSFER, CLEAN, REGULARIZE)
- **P2** nice-to-have proof (PHOTO, BIOCHANGE, STUB, COMPLETION)

### EMP-ADMS - P0 (2 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-ADMS-001 | AUDIT_FAILED_MISSING_SCREENSHOT | `output/l3/s166/lanes/lane_a/evidence/EMP-ADMS-001.json` |
| EMP-ADMS-002 | AUDIT_FAILED_MISSING_SCREENSHOT | `output/l3/s166/lanes/lane_a/evidence/EMP-ADMS-002.json` |

### EMP-ATTENDANCE - P0 (3 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-ATTENDANCE-001 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_d/evidence/EMP-ATTENDANCE-001.json` |
| EMP-ATTENDANCE-002 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_d/evidence/EMP-ATTENDANCE-002.json` |
| EMP-ATTENDANCE-003 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_d/evidence/EMP-ATTENDANCE-003.json` |

### EMP-BIOCHANGE - P2 (2 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-BIOCHANGE-001 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_b/evidence/EMP-BIOCHANGE-001.json` |
| EMP-BIOCHANGE-002 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_b/evidence/EMP-BIOCHANGE-002.json` |

### EMP-CLEAN - P1 (1 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-CLEAN-001-A5d | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_a/evidence/EMP-CLEAN-001-A5d.json` |

### EMP-COMPLETION - P2 (1 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-COMPLETION-002 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-COMPLETION-002.json` |

### EMP-CONFLICT - P2 (1 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-CONFLICT-001 | VERIFIED_BROWSER_FAIL | `output/l3/s166/lanes/lane_a/evidence/EMP-CONFLICT-001.json` |

### EMP-CREATE - P0 (7 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-CREATE-001 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_a/evidence/EMP-CREATE-001.json` |
| EMP-CREATE-002 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_b/evidence/EMP-CREATE-002.json` |
| EMP-CREATE-004 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_h/evidence/EMP-CREATE-004.json` |
| EMP-CREATE-008 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_e/evidence/EMP-CREATE-008.json` |
| EMP-CREATE-009 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_e/evidence/EMP-CREATE-009.json` |
| EMP-CREATE-009_retry | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_e/evidence/EMP-CREATE-009_retry.json` |
| EMP-CREATE-RETEST | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/retest/r4_emp_retest/evidence/EMP-CREATE-RETEST-retest.json` |

### EMP-DISCIPLINARY - P1 (1 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-DISCIPLINARY-005 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-DISCIPLINARY-005.json` |

### EMP-EDIT - P0 (16 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-EDIT-ADDRESS-001 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-ADDRESS-001.json` |
| EMP-EDIT-ADDRESS-002 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-ADDRESS-002.json` |
| EMP-EDIT-CONTACT-001 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-CONTACT-001.json` |
| EMP-EDIT-CONTACT-002 | VERIFIED_BROWSER_FAIL | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-CONTACT-002.json` |
| EMP-EDIT-CONTACT-003 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-CONTACT-003.json` |
| EMP-EDIT-CONTACT-004 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-CONTACT-004.json` |
| EMP-EDIT-EMPLOYMENT-001 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-EMPLOYMENT-001.json` |
| EMP-EDIT-EMPLOYMENT-002 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-EMPLOYMENT-002.json` |
| EMP-EDIT-EMPLOYMENT-004 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-EMPLOYMENT-004.json` |
| EMP-EDIT-EMPLOYMENT-005 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-EMPLOYMENT-005.json` |
| EMP-EDIT-PERSONAL-001 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-PERSONAL-001.json` |
| EMP-EDIT-PERSONAL-002 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-PERSONAL-002.json` |
| EMP-EDIT-PERSONAL-003 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-PERSONAL-003.json` |
| EMP-EDIT-PERSONAL-004 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-PERSONAL-004.json` |
| EMP-EDIT-PERSONAL-005 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-PERSONAL-005.json` |
| EMP-EDIT-PERSONAL-006 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-EDIT-PERSONAL-006.json` |

### EMP-LEAVE - P1 (4 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-LEAVE-001 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_d/evidence/EMP-LEAVE-001.json` |
| EMP-LEAVE-002 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_d/evidence/EMP-LEAVE-002.json` |
| EMP-LEAVE-004 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_d/evidence/EMP-LEAVE-004.json` |
| EMP-LEAVE-005 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_d/evidence/EMP-LEAVE-005.json` |

### EMP-OVERTIME - P1 (1 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-OVERTIME-004 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_d/evidence/EMP-OVERTIME-004.json` |

### EMP-PAYROLL - P0 (6 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-PAYROLL-RUN-001 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_g/evidence/EMP-PAYROLL-RUN-001.json` |
| EMP-PAYROLL-RUN-002 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_g/evidence/EMP-PAYROLL-RUN-002.json` |
| EMP-PAYROLL-RUN-003 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_g/evidence/EMP-PAYROLL-RUN-003.json` |
| EMP-PAYROLL-RUN-004 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_g/evidence/EMP-PAYROLL-RUN-004.json` |
| EMP-PAYROLL-RUN-005 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_g/evidence/EMP-PAYROLL-RUN-005.json` |
| EMP-PAYROLL-RUN-006 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_g/evidence/EMP-PAYROLL-RUN-006.json` |

### EMP-PAYSLIP - P0 (2 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-PAYSLIP-001 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_d/evidence/EMP-PAYSLIP-001.json` |
| EMP-PAYSLIP-002 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_d/evidence/EMP-PAYSLIP-002.json` |

### EMP-PHOTO - P2 (2 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-PHOTO-001 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-PHOTO-001.json` |
| EMP-PHOTO-002 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-PHOTO-002.json` |

### EMP-RBAC - P1 (5 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-RBAC-001 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_e/evidence/EMP-RBAC-001.json` |
| EMP-RBAC-002 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_e/evidence/EMP-RBAC-002.json` |
| EMP-RBAC-003 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_e/evidence/EMP-RBAC-003.json` |
| EMP-RBAC-004 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_e/evidence/EMP-RBAC-004.json` |
| EMP-RBAC-005 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_e/evidence/EMP-RBAC-005.json` |

### EMP-REGULARIZE - P1 (3 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-REGULARIZE-001 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-REGULARIZE-001.json` |
| EMP-REGULARIZE-002 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-REGULARIZE-002.json` |
| EMP-REGULARIZE-003 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_c/evidence/EMP-REGULARIZE-003.json` |

### EMP-SALARY - P0 (10 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-SALARY-CHANGE-001 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-SALARY-CHANGE-001.json` |
| EMP-SALARY-CHANGE-002 | VERIFIED_BROWSER_FAIL | `output/l3/s166/lanes/lane_a/evidence/EMP-SALARY-CHANGE-002.json` |
| EMP-SALARY-CHANGE-003 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-SALARY-CHANGE-003.json` |
| EMP-SALARY-CHANGE-004 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-SALARY-CHANGE-004.json` |
| EMP-SALARY-CHANGE-005 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-SALARY-CHANGE-005.json` |
| EMP-SALARY-CHANGE-006 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-SALARY-CHANGE-006.json` |
| EMP-SALARY-SETUP-001 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-SALARY-SETUP-001.json` |
| EMP-SALARY-SETUP-002 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-SALARY-SETUP-002.json` |
| EMP-SALARY-SETUP-003 | AUDIT_FAILED_API_ONLY | `output/l3/s166/lanes/lane_a/evidence/EMP-SALARY-SETUP-003.json` |
| EMP-SALARY-SETUP-003_arch_note-retest | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/retest/r4_emp_retest/evidence/EMP-SALARY-SETUP-003_arch_note-retest.json` |

### EMP-STUB - P2 (6 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-STUB-001 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-STUB-001.json` |
| EMP-STUB-001-retest | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/retest/r3_ux_reobserve/evidence/EMP-STUB-001-retest.json` |
| EMP-STUB-002 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-STUB-002.json` |
| EMP-STUB-003 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-STUB-003.json` |
| EMP-STUB-004 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-STUB-004.json` |
| EMP-STUB-005 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-STUB-005.json` |

### EMP-TRANSFER - P1 (5 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-TRANSFER-001 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_c/evidence/EMP-TRANSFER-001.json` |
| EMP-TRANSFER-002 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_c/evidence/EMP-TRANSFER-002.json` |
| EMP-TRANSFER-003 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_c/evidence/EMP-TRANSFER-003.json` |
| EMP-TRANSFER-004 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_c/evidence/EMP-TRANSFER-004.json` |
| EMP-TRANSFER-005 | VERIFIED_BROWSER_FAIL | `output/l3/s166/lanes/lane_c/evidence/EMP-TRANSFER-005.json` |

### EMP-UX - P1 (11 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| EMP-UX-001 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-UX-001.json` |
| EMP-UX-002 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-UX-002.json` |
| EMP-UX-003 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-UX-003.json` |
| EMP-UX-004 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-UX-004.json` |
| EMP-UX-004-retest | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/retest/r3_ux_reobserve/evidence/EMP-UX-004-retest.json` |
| EMP-UX-005 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-UX-005.json` |
| EMP-UX-006 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-UX-006.json` |
| EMP-UX-007 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-UX-007.json` |
| EMP-UX-008 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-UX-008.json` |
| EMP-UX-009 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-UX-009.json` |
| EMP-UX-010 | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/lane_f/evidence/EMP-UX-010.json` |

### EMP-retest - P2 (1 debt rows)

| Scenario | Verdict | Original evidence file |
|---|---|---|
| COMP_PAGE_PROBE-retest | AUDIT_FAILED_NO_BROWSER_PROOF | `output/l3/s166/lanes/retest/r4_emp_retest/evidence/COMP_PAGE_PROBE-retest.json` |

## Remediation Path

Every row in this ledger is closed ONLY by:

1. An S174 (burn-down) agent running the scenario via real browser with Playwright headless.
2. Writing evidence to `output/l3/s174/reproof/<prefix>/<sid>.json` containing:
   - `actions[]` (Playwright UI interaction log)
   - `screenshots[]` (pre + post, non-zero bytes)
   - `network[]` (API calls observed during the interaction, NOT as the primary proof)
3. An INDEPENDENT audit agent (separate session, per post-#497 `/l3-v2-bei-erp` rule) inspecting the evidence and writing a verdict.
4. Only the audit gate flips a ledger row from PENDING to CLOSED.

**An agent CANNOT close a ledger row just because S172 fixed the underlying defect.** The scenario must still be browser-re-proven.

## Cross-References

- **Source audit:** `output/l3/s166/AUDIT_2026-04-08/AUDIT_FINDINGS_FINAL.md`
- **Per-scenario audit JSON:** `output/l3/s166/AUDIT_2026-04-08/audit_per_scenario.json`
- **Audit amendment PR:** #496 (merged)
- **Skill rule PR:** #497 (merged, binding audit gate rule)
- **S172 defect-fix sprint:** `docs/plans/2026-04-08-sprint-172-s166-followup-defect-fixes.md` (fixes 9 product defects; does NOT burn down this ledger)
- **S173 burn-down sprint:** `docs/plans/2026-04-08-sprint-174-s166-browser-reproof-burndown.md`
- **Canonical defect register:** `output/l3/s166/DEFECTS.csv`

## Ledger Maintenance Rule

This file is updated by EVERY subsequent sprint that touches S166 scenarios:
- S172 Phase 8 retests ~25 scenarios. Those rows get their status updated here in this ledger (not only in `output/`) at S172 closeout.
- S174 burns down the remaining ~60 rows.
- Any new test-debt discovered in future audits is appended with a dated section.

**If this ledger says PENDING after a sprint closes, the sprint did NOT close the debt, regardless of what its own closeout doc claims.**
