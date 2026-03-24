# S105 Verified Blockers
## Date: 2026-03-24
## Method: 5 parallel agents (docker-researcher, deployment-qa, system-arch, team-orchestration, code-verifier)

## CRITICAL Blockers

### B-01: `bench get-app --depth 1` flag does not exist
**Source:** code-verifier (STALE claim #6)
**Evidence:** bench CLI has no `--depth` flag on `get-app`. Bench uses `shallow_clone` site config internally.
**Impact:** Plan task A3 explicitly says `bench get-app hrms --branch production --depth 1` — this command will fail.
**Fix:** Use `bench config set-common-config -c shallow_clone 1` before `bench get-app`, or use direct `git clone --depth 1` followed by `bench setup requirements`.

### B-02: Upstream Containerfile defaults diverged — will build wrong Python/Node versions
**Source:** code-verifier (NEW GAP #1)
**Evidence:** Upstream now defaults to `PYTHON_VERSION=3.14.2`, `NODE_VERSION=24.13.0`, `FRAPPE_BRANCH=version-16`. BEI pins 3.11.6/20.19.2/version-15.
**Impact:** If Containerfile.base uses `FROM` without pinning ARGs, the base image gets Python 3.14 and Node 24, which are incompatible with version-15 frappe.
**Fix:** Containerfile.base MUST hardcode `ARG PYTHON_VERSION=3.11.6`, `ARG NODE_VERSION=20.19.2`, `ARG FRAPPE_BRANCH=version-15`.

### B-03: Mutable base image tag — no rollback or traceability
**Source:** system-arch-auditor (C1)
**Evidence:** Plan uses `samkarazi/frappe-base:v15` as overwritten tag. Previous base is lost on rebuild.
**Impact:** If a base rebuild introduces a regression, all subsequent builds are broken with no rollback.
**Fix:** Tag immutably (e.g., `frappe-base:v15-20260324`). Keep `v15` as floating alias. Record which base tag was used in each build.

### B-04: No max_turns specified
**Source:** team-orchestration-auditor (C1)
**Impact:** Agent could run indefinitely on a stuck Docker build.
**Fix:** Add `max_turns: 30` to execution contract.

## WARNING Findings

### W-01: Cleanup job may prune base image on low-disk
**Source:** system-arch W5
**Fix:** Add base image protection to cleanup job or label-based exclusion.

### W-02: Cache type mismatch between test (type=gha) and production (type=registry)
**Source:** system-arch W3
**Fix:** Align cache strategy. Use same type in both workflows.

### W-03: L3 evidence files inappropriate for infrastructure sprint
**Source:** team-orchestration W3
**Fix:** Replace form_submissions.json with build_timing.json, image_manifest.json, deployment_verification.json.

### W-04: No automated staleness detection for base image
**Source:** system-arch W1, deployment-qa D-04
**Fix:** Add weekly cron workflow to check upstream HEAD SHAs.

### W-05: `bench build --app hrms` behavior unvalidated
**Source:** system-arch W4
**Fix:** Add validation step in B2 comparing assets.json completeness.

### W-06: No explicit rollback procedure documented
**Source:** deployment-qa D-07
**Fix:** Document: revert build-and-deploy.yml change, re-run workflow.

## Improvements from Docker Research

### I-01: Remove QEMU setup step (saves 15-30s)
Not needed for single-platform linux/amd64 builds.

### I-02: Add `provenance: false` (saves 10-20s)
Skip SLSA attestation for internal builds.

### I-03: Use BuildKit cache mounts for pip/yarn
`RUN --mount=type=cache,target=/root/.cache/pip pip install ...` avoids re-downloading even when layer invalidated.

### I-04: Use `type=registry,mode=max` with dedicated buildcache tag
Better than `type=gha` for large multi-stage builds. No 10 GB limit.
