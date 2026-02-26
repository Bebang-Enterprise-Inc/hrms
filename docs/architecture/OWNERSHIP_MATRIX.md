# Ownership Matrix - BEI ERP Architecture

**Last Updated:** 2026-02-26  
**Owner:** Sam Karazi  
**Next Review:** 2026-03-05  
**Purpose:** Assign explicit ownership for architecture domains, decisions, and escalation.

## Ownership Rule

Per current SAD hardening directive, `Sam Karazi (CEO)` is the accountable owner for all architecture domains until delegates are explicitly named in this file.

## Domain Ownership

| Domain | Scope | Accountable Owner | Delegate | Escalation Path | Evidence |
|---|---|---|---|---|---|
| Platform Architecture | Cross-repo architecture decisions (`BEI-ERP`, `bei-tasks`) | Sam Karazi | Not assigned | ADR + owner decision in architecture docs | `docs/00_START_HERE.md`, `docs/architecture/SOLUTION_ARCHITECTURE_DOCUMENT.md` |
| HR and Payroll | Attendance, leave, payroll, employee lifecycle | Sam Karazi | Not assigned | `Sam -> ADR update -> implementation plan` | `docs/architecture/erd.md`, `hrms/api/*.py` |
| Procurement and Finance | PR/PO/GR/billing/payment/accounting | Sam Karazi | Not assigned | `Sam -> ADR update -> implementation plan` | `docs/architecture/erd.md`, `docs/plans/system-flow-gaps-v3*.md` |
| Store Ops and Maintenance | Store cycle, reports, R&M requests | Sam Karazi | Not assigned | `Sam -> ADR update -> implementation plan` | `docs/architecture/flows/07-daily-store-cycle.md`, `docs/architecture/flows/08-maintenance.md` |
| Warehouse, Dispatch, Commissary | Fulfillment, dispatch trips, receiving, production | Sam Karazi | Not assigned | `Sam -> ADR update -> implementation plan` | `docs/architecture/flows/04-store-order-delivery.md`, `docs/architecture/flows/12-3pl-billing.md` |
| Security and Identity | OAuth, session security, secrets, authz boundaries | Sam Karazi | Not assigned | `Sam -> security architecture update -> deploy gate` | `docs/architecture/SECURITY_ARCHITECTURE.md`, `docs/GOOGLE_OAUTH_RUNBOOK.md` |
| Reliability and SRE | SLO policy, monitoring, incident response | Sam Karazi | Not assigned | `Sam -> NFR/SLO update -> workflow update` | `.github/workflows/uptime-check.yml`, `.github/workflows/synthetic-monitoring.yml`, `docs/architecture/NFR_SLO_BASELINE.md` |
| Deployment and DR | Build/deploy/rollback/recovery commitments | Sam Karazi | Not assigned | `Sam -> DR decision -> runbook/workflow update` | `.github/workflows/build-and-deploy.yml`, `docs/deployment/ROLLBACK_RUNBOOK.md`, `docs/architecture/DEPLOYMENT_TOPOLOGY_AND_DR.md` |
| ADR Governance | Decision recording, status, supersession | Sam Karazi | Not assigned | `Sam approves ADR status changes` | `docs/architecture/adr/ADR-INDEX.md` |

## Decision and Escalation Governance

1. Any architecture-impacting change must be recorded in an ADR before or with code change.
2. Any production incident that threatens data integrity or availability uses rollback procedures first, then ADR/root-cause backfill.
3. If no delegate is assigned for a domain, owner escalation is immediate to `Sam Karazi`.

## Update Protocol

1. Add delegate names only with date and scope.
2. Keep historical ownership changes as append-only entries in the ADR index notes.
3. Re-run SAD audit after any ownership change.
