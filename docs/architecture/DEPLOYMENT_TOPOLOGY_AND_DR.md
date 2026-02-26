# Deployment Topology and Disaster Recovery - BEI ERP

**Last Updated:** 2026-02-26  
**Owner:** Sam Karazi  
**Next Review:** 2026-03-05  
**Status:** Active reference (v1)

## Deployment Topology (Current)

## 1) Runtime Components

From `frappe_docker_build/stack-swarm.yml`, current Swarm stack includes:

1. `backend`
2. `frontend`
3. `websocket`
4. `queue-short`
5. `queue-long`
6. `scheduler`
7. `db` (MariaDB 10.6)
8. `redis-cache`
9. `redis-queue`

## 2) Deployment Pipeline

From `.github/workflows/build-and-deploy.yml`:

1. Build image: `samkarazi/bebang-erpnext-hrms:v15`.
2. Push image tags (stable + dated + short SHA).
3. Deploy via AWS SSM on EC2 instance `i-026b7477d27bd46d6`.
4. Update services with rolling `docker service update`.
5. Optional migrate + asset sync.
6. Verify `frappe.ping` + CSS/JS asset health.

## 3) Frontend Deployment Policy

From `.claude/rules/deployment.md`:

1. `bei-tasks` deploys to Vercel production after push.
2. Cache-bust marker update and live verification are required.

## DR Strategy

## 4) Recovery Paths

From `docs/deployment/ROLLBACK_RUNBOOK.md`:

1. Backend rollback:
   - `docker service rollback frappe_backend`
   - `docker service rollback scheduler`
   - `docker service rollback queue-short`
   - `docker service rollback queue-long`
2. Frontend rollback:
   - Promote previous Vercel deployment, or run `vercel rollback`.
3. Database restore:
   - `bench --site hq.bebang.ph restore <backup-file.sql.gz>`
   - Optional file restores with `--with-public-files` and `--with-private-files`.

## 5) RTO and RPO Commitments (v1)

| Service Tier | Components | RTO | RPO | Rationale |
|---|---|---|---|---|
| Tier 1 (Customer-facing core) | `hq.bebang.ph`, `my.bebang.ph` | 120 minutes | 24 hours | Rollback runbook exists; backup frequency/retention policy not yet formalized in architecture docs |
| Tier 2 (Operational integrations) | ADMS receiver, Sheets Receiver, Blip integrations | 240 minutes | 24 hours | Integrations are important but non-blocking for immediate frontend/API availability |

## 6) Failover and Rollback Decision Rules

1. If deploy verification fails (`frappe.ping` or static assets), execute service rollback before further changes.
2. If data integrity is suspected, stop write traffic and restore from last known valid backup.
3. After rollback/restore, run L1/L2 smoke and at least one L3 critical flow before reopening full operations.

## 7) Known DR Gaps

1. Backup schedule and retention are not codified in architecture docs.
2. No explicit multi-region failover design is documented.
3. No periodic DR drill cadence is documented in current runbooks.

## 8) Required Follow-ups

1. Document actual backup job schedule and retention source-of-truth.
2. Add DR drill calendar and evidence log path.
3. Define restoration verification checklist for core DocTypes and financial postings.
