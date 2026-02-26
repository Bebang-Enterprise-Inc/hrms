# SAD Ownership and Agent Training Plan

**Date:** 2026-02-25  
**Scope:** Interim ownership of 5 Solution Architecture Document readiness areas for BEI ERP

## 1) Interim Ownership Model

For now, `Codex` acts as the working owner for all five SAD readiness areas:

1. NFRs/SLOs
2. Security architecture
3. Deployment topology + DR
4. ADRs (architecture decisions)
5. Ownership/governance

Human approval remains with BEI leadership for risk, cost, and timeline tradeoffs.

## 2) Project-Aligned Skill Stack (Primary)

Use existing BEI-local skills first:

- `sre-engineer` (NFR/SLO baselines, error budgets, reliability gates)
- `security-auditor` (auth/authz boundaries, secrets, audit posture)
- `deploy-frappe-bei-erp` + `deployment-automation` (release workflow, rollback, DR execution paths)
- `architect-reviewer-bei-erp` (system design review, integration and boundary checks)
- `workflow-bei-erp` (governance gates, branch/PR/deploy discipline)
- `frappe-expert-bei-erp` + `local-frappe-bei-erp` (Frappe-specific implementation and validation)
- `google-oauth-bei-erp` (identity/OAuth architecture details)

## 3) External Skills (Optional Augmentation)

Candidate external skills discovered and verified:

- `jeffallan/claude-skills@devops-engineer`
- `jeffallan/claude-skills@sre-engineer`
- `sickn33/antigravity-awesome-skills@senior-architect`
- `sergio-bershadsky/ai@frappe-doctype`
- `wshobson/agents@architecture-decision-records`

Use external skills as secondary references only. BEI-local skills remain source-of-truth for project-specific workflows.

## 4) Agent Training Tracks by SAD Area

### A. NFRs/SLOs

- Lead skill(s): `sre-engineer`
- Output artifacts:
  - SLI/SLO table per critical flow
  - Availability and latency targets
  - Error budget policy
- Exit criteria:
  - Each critical flow has measurable SLO and alert thresholds

### B. Security Architecture

- Lead skill(s): `security-auditor`, `google-oauth-bei-erp`, `workflow-bei-erp`
- Output artifacts:
  - AuthN/AuthZ boundary map
  - Secret handling policy
  - Audit logging requirements
- Exit criteria:
  - Security section includes identity, authorization, secrets, and evidence path

### C. Deployment Topology + DR

- Lead skill(s): `deploy-frappe-bei-erp`, `deployment-automation`, `local-frappe-bei-erp`
- Output artifacts:
  - Environment topology diagram
  - Rollback runbook links
  - RTO/RPO targets per critical service
- Exit criteria:
  - Recovery steps are reproducible and time-bounded

### D. ADRs

- Lead skill(s): `architect-reviewer-bei-erp`
- Optional add-on: `wshobson/agents@architecture-decision-records`
- Output artifacts:
  - ADR index
  - One ADR per high-impact architecture decision
- Exit criteria:
  - Major decisions are justified, dated, and linked to consequences

### E. Ownership/Governance

- Lead skill(s): `workflow-bei-erp`, `architect-reviewer-bei-erp`
- Output artifacts:
  - Domain ownership matrix
  - Decision and escalation policy
  - Change-control gate for architecture-impacting changes
- Exit criteria:
  - Every critical domain has a named owner and escalation path

## 5) 14-Day Execution Sequence

1. Days 1-3: Draft NFR/SLO and Security sections
2. Days 4-6: Draft Deployment/DR section with RTO/RPO baselines
3. Days 7-9: Backfill ADR set for existing major choices
4. Days 10-12: Finalize ownership/governance matrix
5. Days 13-14: Publish SAD v1 and run review pass

## 6) Definition of Done (SAD v1)

SAD v1 is complete when:

1. All 5 sections exist and are internally consistent
2. Every section links to executable evidence (runbooks, tests, logs, scripts, reports)
3. Open risks and assumptions are explicit
4. Leadership-approved targets are recorded (not implied)

## 7) Immediate Next Action

Create `docs/architecture/SOLUTION_ARCHITECTURE_DOCUMENT.md` and populate it using this plan plus:

- `docs/architecture/INDEX.md`
- `docs/plans/system-flow-gaps-v3.md`
- `docs/plans/system-flow-gaps-v3-full-route-map.md`
- `docs/MY_BEBANG_PH_COMPLETE_REFERENCE.md`
