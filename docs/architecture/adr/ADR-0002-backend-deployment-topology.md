# ADR-0002: Backend Deployment Topology - Docker Swarm on EC2 via GitHub Actions + AWS SSM

**Status:** Accepted  
**Date:** 2026-02-26

## Context

1. Production backend deployment is automated through GitHub workflow.
2. Runtime stack definition uses Docker Swarm services (`backend`, `frontend`, `queue`, `scheduler`, `db`, `redis`).
3. Rollback runbook already uses Swarm rollback commands.

## Decision

Keep backend deployment topology as:

1. Docker image build/push in GitHub Actions.
2. AWS SSM remote execution to apply rolling `docker service update`.
3. Swarm-native rollback for core backend services.

## Consequences

1. Deployment and rollback are operationally centralized in workflow + runbook.
2. Service-level rollback remains fast and command-driven.
3. DR commitments (RTO/RPO) are tracked in `DEPLOYMENT_TOPOLOGY_AND_DR.md`.

## Evidence

1. `.github/workflows/build-and-deploy.yml`
2. `frappe_docker_build/stack-swarm.yml`
3. `docs/deployment/ROLLBACK_RUNBOOK.md`
4. `docs/architecture/DEPLOYMENT_TOPOLOGY_AND_DR.md`

