# S175 COA Master Template Restructure — Cleanroom Index

**Sprint:** S175
**Created:** 2026-04-09
**Status:** DECISIONS LOCKED — plan rewrite pending
**Ownership:** Sam Karazi (CEO) — single-owner signoff per BEI governance

This directory is the **single authoritative source of truth** for the S175 COA Master Template work. Every decision, every GL change, every fee routing rule, and every live-state fact lives here — NOT in conversation memory. Per the Write-First Rule, any compaction of this session must not lose any load-bearing data.

---

## Files in this directory

| File | Purpose | Read when |
|------|---------|-----------|
| `00_INDEX.md` | This file — navigation + key facts summary | Always first |
| `01_CANONICAL_COA_TEMPLATE.md` | The full 30-account Sales tree + Fork 1 intercompany additions + Butch's reserved expansion slots | Rewriting the plan / auditing the template |
| `02_LOCKED_DECISIONS.md` | All COA-175-### locked decisions with exact source citations + fee routing matrix | Verifying any decision |
| `03_CURRENT_STATE_SNAPSHOT.md` | Phase A live audit summary (39 companies, 136 BEI 6xxx, 41 delete-targets all 0 GL) + per-account delete/migrate action | Building any execution script |
| `04_INTERCOMPANY_ACCOUNTING.md` | Fork 1 (collection-agent-from-day-1) journal entry patterns for BEI and BFC, VAT flow, cutover sweep JE | Writing Phase 6 scaffolding, coding SIs |
| `05_OPEN_QUESTIONS_FOR_BUTCH.md` | The 3 blocking questions that need Butch's answer before execution | Escalation checkpoint |

---

## Key facts (one-line canonical)

| Fact | Value | Source |
|------|-------|--------|
| BEI Group companies | **39** (verified 2026-04-09) | `output/s175/preflight_audit.md#1` |
| BFC exists in Frappe | **False** (audit false-positive on "Managed Franchise" substring) | `03_CURRENT_STATE_SNAPSHOT.md#bfc-status` |
| BEI 6xxxxxx accounts | **136** (134 Income + 2 Expense) — all 0 GL entries | `output/s175/preflight_audit.md#2` |
| BKI delete-targets | **19 of 20 exist**, all 0 GL entries | `03_CURRENT_STATE_SNAPSHOT.md#bki-delete-targets` |
| BEI delete/migrate-targets | **22 of 22 exist**, all 0 GL entries | `03_CURRENT_STATE_SNAPSHOT.md#bei-delete-targets` |
| Template collisions across 39 companies | **11 total** (5 on `4000000`, 5 on `4000200`, 1 on `4000100`) | `output/s175/preflight_audit.md#10` |
| Parent_account references needing child-first delete | **4 parents, 14 children total** | `03_CURRENT_STATE_SNAPSHOT.md#hb7-link-refs` |
| BEI Settings.bki_sales_income_account (current) | `SALES - BKI TO STORES - BKI` (valid link) | `output/s175/preflight_audit.md#5` |
| Revenue recognition model | **Fork 1** (BFC as principal from day 1 via collection-agent letter) | `02_LOCKED_DECISIONS.md#COA-175-013` |
| Collection-agent letter draft | `data/_CLEANROOM/2026-04-09_franchise_agreements/04_BEI_BFC_Collection_Agent_Letter_DRAFT.md` | Fork 1 enabler |

---

## Evidence traceability

Every load-bearing claim in this directory traces to one of:

| Evidence category | Location |
|---|---|
| Butch's canonical GL Sales table (screenshot) | `data/_CLEANROOM/chat_evidence/2026-04-08_butch_gl_sales/DL97trTZUFA.DL97trTZUFA__Screenshot_2026-04-08_at_10.17.04_AM.png` |
| Butch's discount renumber + BFC bank confirmations + BFC-collects-all reversal | `data/_CLEANROOM/chat_evidence/2026-04-08_butch_gl_sales/transcript.md` + `CLAIM_VERIFICATION.md` |
| BFC corporate facts (TIN, SEC, RDO, capital) | `data/_CLEANROOM/2026-04-08_franchise_corp_extract/00_INDEX.md` + `04_BIR_2303.md` |
| Signed JV Agreement fee routing (all to BEI) | `data/_CLEANROOM/2026-04-09_franchise_agreements/01_JV_Agreement_Grand_Central_Gabaldon.md` |
| Unexecuted Franchise Agreement template (all to BFC) | `data/_CLEANROOM/2026-04-09_franchise_agreements/03_Franchise_Agreement_BFC.md` |
| Unexecuted Franchise Management Agreement (2.5% to BFC) | `data/_CLEANROOM/2026-04-09_franchise_agreements/02_Franchise_Management_Agreement_BFC.md` |
| Live Frappe state (39 companies, all delete-target GL counts) | `output/s175/preflight_audit.json` + `preflight_audit.md` |
| PDF fact-check of cleanroom extracts (20/20 SUPPORTED) | `output/plan-audit/s175-coa-master-template/pdf_fact_check.md` |
| Adversarial audit of S175 plan v1 (11 CRITICAL + 15 WARNING) | `output/plan-audit/s175-coa-master-template/verified_blockers_v2.md` |
| Collection-agent letter draft | `data/_CLEANROOM/2026-04-09_franchise_agreements/04_BEI_BFC_Collection_Agent_Letter_DRAFT.md` |

---

## Decision authorities

| Decision | Author | Date | Source |
|---|---|---|---|
| Canonical GL Sales template structure | Butch Formoso | 2026-04-08 10:18 AM PHT | Butch GL screenshot in chat |
| Discount renumber 4000200 → 4000900 | Butch Formoso | 2026-04-08 21:48 PHT | Chat transcript "Option A under 4000900" |
| BFC exists, no bank account yet | Butch Formoso | 2026-04-09 10:37 AM PHT | Chat transcript |
| BFC collects all franchise fees per contracts | Butch Formoso | 2026-04-09 10:37 AM PHT | Chat transcript (reversal of 2026-04-08 PM) |
| JV fees permanently to BEI | Signed JV Agreement §8.1, §9.1, §2 | 2025-01-03 (execution date) | PDF contract |
| Franchise fees contractually to BFC | Unexecuted Franchise Agreement template | 2025-05-23 | PDF contract |
| Uniform COA across all 40 companies | Sam Karazi | 2026-04-08 | This session |
| Fork 1 (collection-agent from day 1) | Sam Karazi | 2026-04-09 | This session — supersedes Fork 2 (interim BEI revenue) |
| Same-signer authority on collection letter | Sam Karazi | 2026-04-09 | This session |

---

## What this directory does NOT contain

- Execution scripts (those live in `scripts/s175_*.py`)
- Live query results (those live in `output/s175/`)
- The plan itself (that lives in `docs/plans/`)
- Audit findings (those live in `output/plan-audit/s175-coa-master-template/`)
- Signed contracts (JV + Franchise + Mgmt Agreement live in `data/_CLEANROOM/2026-04-09_franchise_agreements/`)
- BFC corporate docs (those live in `data/_CLEANROOM/2026-04-08_franchise_corp_extract/`)

This directory is the **decision layer** — the SSOT for *what* we are building and *why*, separated from the scripts, audits, contracts, and plan that implement those decisions.
