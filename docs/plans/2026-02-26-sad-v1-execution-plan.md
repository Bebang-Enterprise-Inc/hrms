# Solution Architecture Document (SAD) V1 Execution Plan

**Date:** 2026-02-26  
**Status:** In progress (hardening started 2026-02-26)  
**Primary owner (accountable):** Sam Karazi  
**Execution owner:** Codex  
**Business approver:** Sam Karazi (CEO)

---

## 1) Purpose

Create a **single, complete, structured Solution Architecture Document** that any technical personnel can use to understand:

1. What the BEI ERP solution is
2. How all major components connect
3. How the system is operated, secured, tested, and deployed
4. What reliability targets and recovery commitments exist
5. Who owns each domain and how decisions are made

---

## 2) Target Output

Primary artifact to produce:

- `docs/architecture/SOLUTION_ARCHITECTURE_DOCUMENT.md`

Supporting artifacts to produce/update:

- `docs/architecture/adr/ADR-INDEX.md`
- `docs/architecture/adr/ADR-0001-*.md` (initial ADR set)
- `docs/architecture/OWNERSHIP_MATRIX.md`
- `docs/architecture/NFR_SLO_BASELINE.md`
- `docs/architecture/SECURITY_ARCHITECTURE.md`
- `docs/architecture/DEPLOYMENT_TOPOLOGY_AND_DR.md`
- `docs/architecture/DOCUMENTATION_TRUTH_PROTOCOL.md`

---

## 3) Existing Inputs (Already Available)

Use these as baseline source material:

- `docs/architecture/INDEX.md`
- `docs/architecture/erd.md`
- `docs/MY_BEBANG_PH_COMPLETE_REFERENCE.md`
- `docs/plans/system-flow-gaps-v3.md`
- `docs/plans/system-flow-gaps-v3-full-route-map.md`
- `docs/testing/ROUTE_REGISTRY.md`
- `docs/testing/scenarios/index.yaml`
- `docs/deployment/ROLLBACK_RUNBOOK.md`
- `docs/infrastructure/README.md`
- `docs/GOOGLE_OAUTH_RUNBOOK.md`
- `docs/00_START_HERE.md`

---

## 4) Skills Strategy

### 4.1 Primary skills (already in BEI environment)

These are source-of-truth for execution in this project:

1. `architect-reviewer-bei-erp`
2. `sre-engineer`
3. `security-auditor`
4. `deploy-frappe-bei-erp`
5. `deployment-automation`
6. `workflow-bei-erp`
7. `frappe-expert-bei-erp`
8. `local-frappe-bei-erp`
9. `google-oauth-bei-erp`
10. `database-schema`

### 4.2 External skills install set (curated allowlist)

Install only these five first:

1. `jeffallan/claude-skills@devops-engineer`
2. `jeffallan/claude-skills@sre-engineer`
3. `sickn33/antigravity-awesome-skills@senior-architect`
4. `sergio-bershadsky/ai@frappe-doctype`
5. `wshobson/agents@architecture-decision-records`

Install commands:

```bash
npx skills add jeffallan/claude-skills@devops-engineer -g -y
npx skills add jeffallan/claude-skills@sre-engineer -g -y
npx skills add sickn33/antigravity-awesome-skills@senior-architect -g -y
npx skills add sergio-bershadsky/ai@frappe-doctype -g -y
npx skills add wshobson/agents@architecture-decision-records -g -y
```

Install verification command:

```bash
npx skills ls -g
```

### 4.3 Installation completion record (2026-02-26)

Completed:

1. `jeffallan/claude-skills@devops-engineer`
2. `jeffallan/claude-skills@sre-engineer`
3. `sickn33/antigravity-awesome-skills@senior-architect`
4. `sergio-bershadsky/ai@frappe-doctype`
5. `wshobson/agents@architecture-decision-records`

### 4.4 Skill usage rule

1. BEI-local skills are primary.
2. External skills are secondary guidance only.
3. Any conflict: BEI-local workflow wins.

### 4.5 Skill safety hardening rules

1. Every SAD section must state which skill(s) were used to draft it.
2. No architecture claim can rely on a skill alone; it must reference a BEI repo source.
3. If an external skill recommendation conflicts with current BEI implementation, log it as an ADR candidate.
4. External skills can propose patterns; final decisions are recorded only via ADRs in this repo.

---

## 5) SAD Structure Standard (Must-Have Sections)

The final SAD must contain these sections in this order:

1. Executive summary
2. Business context and system scope
3. Solution overview (context diagram)
4. Architecture building blocks (frontend, backend, data, integrations)
5. Data architecture and ERD summary
6. API and integration architecture
7. Security architecture (authn/authz/secrets/audit)
8. Reliability architecture and NFR/SLO targets
9. Deployment topology and release flow
10. DR strategy (RTO/RPO + fail/restore procedure)
11. Testing strategy and quality gates (L1/L2/L3 + evidence model)
12. Observability and operations model
13. Ownership and governance model
14. ADR index and key decisions
15. Open risks, assumptions, and roadmap
16. Glossary and onboarding quick-start

---

## 6) Execution Roadmap (Starting 2026-02-26)

## Phase 0 - Kickoff and Tooling (2026-02-26)

Goals:

1. Confirm scope and acceptance criteria
2. Install curated external skills
3. Freeze source-doc list

Deliverables:

1. Skill install log
2. Final source-doc inventory

Exit gate:

1. All 5 curated external skills installed
2. No missing primary source document for core sections

Hardening update (2026-02-26):

1. Skill installation gate is complete.
2. Phase 1 starts immediately after this plan update.

## Phase 1 - SAD Skeleton and Traceability (2026-02-26 to 2026-02-27)

Goals:

1. Create SAD skeleton with all mandatory sections
2. Add source traceability for each section

Deliverables:

1. `docs/architecture/SOLUTION_ARCHITECTURE_DOCUMENT.md` (structured draft skeleton)
2. Section-to-source traceability table

Exit gate:

1. 100% required sections present
2. Every section linked to at least one source file

## Phase 2 - NFR/SLO + Security + Deployment/DR (2026-02-27 to 2026-03-01)

Goals:

1. Define baseline SLO targets by critical flow
2. Define auth boundaries, secrets model, and audit requirements
3. Define deployment topology, rollback, and DR commitments

Deliverables:

1. `docs/architecture/NFR_SLO_BASELINE.md`
2. `docs/architecture/SECURITY_ARCHITECTURE.md`
3. `docs/architecture/DEPLOYMENT_TOPOLOGY_AND_DR.md`

Exit gate:

1. Each critical flow has SLI/SLO and alert intent
2. Security section covers authn/authz/secrets/audit
3. DR section includes explicit RTO/RPO values

## Phase 3 - ADR and Governance (2026-03-02 to 2026-03-03)

Goals:

1. Backfill major architecture decisions
2. Define domain ownership and escalation

Deliverables:

1. `docs/architecture/adr/ADR-INDEX.md`
2. Initial ADR set (`ADR-0001` to `ADR-0005` minimum)
3. `docs/architecture/OWNERSHIP_MATRIX.md`

Exit gate:

1. Major decisions recorded with rationale and consequences
2. Every critical domain has a named owner and escalation route

## Phase 4 - Finalization and Review (2026-03-04)

Goals:

1. Consolidate all sections into SAD v1
2. Validate readability for new technical personnel

Deliverables:

1. `docs/architecture/SOLUTION_ARCHITECTURE_DOCUMENT.md` (v1 complete)
2. Final review checklist and sign-off notes

Exit gate:

1. SAD passes completeness and clarity checklist
2. CEO approves risk and target commitments

## Phase 5 - Continuous Documentation Truth Sync (Weekly cadence)

Goals:

1. Keep architecture docs aligned with live code and infra setup.
2. Prevent stale counts, stale hosting statements, and assumption-based updates.

Deliverables:

1. `docs/architecture/DOCUMENTATION_TRUTH_PROTOCOL.md`
2. Weekly drift-check evidence note in architecture docs change log.
3. Refreshed SAD metrics when code footprint changes.

Exit gate:

1. No stale code footprint metrics in SAD.
2. All hosting/deployment statements are file-backed by current workflow/config.
3. Any unknown value is labeled as evidence gap (never guessed).

---

## 7) Quality Gates (Definition of Done)

SAD v1 is done only if all are true:

1. All 16 mandatory sections are present and internally consistent.
2. Claims are evidence-linked to repo docs/runbooks/reports.
3. Security, reliability, and DR targets are explicit (not implied).
4. Ownership matrix and escalation model are complete.
5. ADR index exists and covers high-impact architecture decisions.
6. A new tech lead can explain system boundaries and critical flows after reading SAD.
7. SAD metrics are verified from live code checks (no assumed values).

## 7.1 Section Quality Rubric (Hardening Gate)

Each SAD section is scored 0-5 on:

1. Clarity (readable by a new technical hire)
2. Accuracy (matches current BEI implementation)
3. Traceability (contains source links/paths)
4. Operability (contains actionable runbook guidance where relevant)
5. Risk clarity (assumptions and failure modes stated)

Minimum pass condition:

1. Every section must score at least 4/5.
2. Any section below 4/5 blocks SAD v1 release.

---

## 8) Risks and Controls

1. **Risk:** Over-reliance on generic external skills  
   **Control:** BEI-local skill precedence rule

2. **Risk:** Ambiguous targets (SLO/RTO/RPO)  
   **Control:** Mandatory explicit numeric targets in SAD

3. **Risk:** Outdated architecture statements  
   **Control:** Source traceability + review date in each section

4. **Risk:** Documentation too deep for onboarding  
   **Control:** Add concise "Onboarding Quick-Start" section and glossary

5. **Risk:** Assumption-based documentation drift  
   **Control:** Enforce `docs/architecture/DOCUMENTATION_TRUTH_PROTOCOL.md` checks before each SAD update

---

## 9) Working Cadence

Daily cadence while executing:

1. 15-minute kickoff: section goals for the day
2. Build/update artifacts
3. End-of-day checkpoint: blockers, decisions, next actions
4. Update progress in this plan (status table below)

---

## 10) Tracker

| Workstream | Owner | Start | Target | Status | Evidence |
|---|---|---|---|---|---|
| Skill install wave | Codex | 2026-02-26 | 2026-02-26 | COMPLETE | `npx skills ls -g` output on 2026-02-26 |
| SAD skeleton + traceability | Codex | 2026-02-26 | 2026-02-27 | COMPLETE | `docs/architecture/SOLUTION_ARCHITECTURE_DOCUMENT.md` |
| NFR/SLO baseline | Codex | 2026-02-27 | 2026-03-01 | COMPLETE | `docs/architecture/NFR_SLO_BASELINE.md` |
| Security architecture | Codex | 2026-02-27 | 2026-03-01 | COMPLETE | `docs/architecture/SECURITY_ARCHITECTURE.md` |
| Deployment + DR | Codex | 2026-02-27 | 2026-03-01 | COMPLETE | `docs/architecture/DEPLOYMENT_TOPOLOGY_AND_DR.md` |
| ADR set v1 | Codex | 2026-03-02 | 2026-03-03 | COMPLETE | `docs/architecture/adr/ADR-INDEX.md` + ADR-0001..0005 |
| Ownership matrix | Codex | 2026-03-02 | 2026-03-03 | COMPLETE | `docs/architecture/OWNERSHIP_MATRIX.md` |
| Documentation truth protocol | Codex | 2026-02-26 | 2026-02-26 | COMPLETE | `docs/architecture/DOCUMENTATION_TRUTH_PROTOCOL.md` |
| SAD v1 final review | Codex + CEO | 2026-03-04 | 2026-03-04 | TODO | pending |

---

## 11) Immediate Next Actions (Today, 2026-02-26)

1. Run post-hardening plan audit against `docs/architecture/SOLUTION_ARCHITECTURE_DOCUMENT.md`.
2. Close remaining risks: backup retention documentation, credential-example redaction/rotation, and monthly SLO rollup artifact.
3. Keep route registry at 169/169 alignment with full route map as new routes are added.
4. Refresh SAD metrics from live code checks (`hrms/api`, `hrms/hr/doctype/bei_*`, `../bei-tasks/app`).
5. Capture final CEO sign-off note for SAD v1.

## 12) Execution Runbook (Hardened Start Sequence)

Run this sequence at the start of each SAD work session:

1. Resolve session context:
   - `pwsh -File ".agents/skills/codex-session/scripts/get_codex_session.ps1" -Json`
2. Verify required skills still available:
   - `npx skills ls -g`
3. Check plan progress state:
   - open this file and update tracker statuses before new edits
4. Execute section work in order:
   - SAD skeleton -> traceability -> NFR/SLO -> Security -> DR -> ADR -> ownership
5. End-of-session closeout:
   - update tracker row evidence paths
   - append unresolved blockers under Risks/Controls
