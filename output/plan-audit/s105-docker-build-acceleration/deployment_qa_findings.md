# Deployment & QA Audit Findings
## Plan: S105 Docker Build Acceleration
## Date: 2026-03-24

### Deployment Findings

#### D-01: Production workflow isolation is correctly specified
The plan explicitly states the test workflow (build-fast.yml) uses `workflow_dispatch` only and pushes to `v15-fast-test`, not `v15`. The production workflow (`build-and-deploy.yml`) remains untouched until Phase B4. The Requirements Regression Checklist covers this. **No issue.**

#### D-02: CACHE_BUST / no-cache preservation is correctly enforced
The plan explicitly prohibits removing `CACHE_BUST` or `no-cache` from the existing workflow. The "Agent Boot Sequence" final line reinforces this. The audit amendment explains the 2026-01-29 production incident. **No issue.**

#### D-03: Docker build type is specified — full build with no-cache for production
Current workflow (line 138): `no-cache: ${{ github.event_name == 'push' || ... }}`. The plan preserves this for production. The fast Containerfile introduces `HRMS_SHA` cache-busting for the hrms layer only. **No issue.**

#### D-04: Base image staleness risk lacks a concrete refresh policy
The plan separates frappe/erpnext/payments into a pre-built base image (`frappe-base:v15`) that is only rebuilt via manual `workflow_dispatch`. **Risk:** If upstream frappe/erpnext pushes a security fix to `version-15`, the base image will serve stale code until someone manually triggers `build-base.yml`. The plan mentions "base staleness" as a stop condition but does not specify:
- How often to rebuild the base (weekly? monthly?)
- Whether a scheduled trigger should be added to `build-base.yml`
- Who is responsible for monitoring upstream changes

**Severity: MEDIUM.** This is not a blocker for Phase A/B but becomes a maintenance risk post-swap.

#### D-05: Build tools (gcc/build-essential) correctly identified
The plan correctly identifies that the upstream `backend` stage (which `Containerfile.fast` would extend) does NOT include gcc/build-essential — those are only in the `builder` stage. The plan's task A3 explicitly calls out installing gcc/build-essential. Verified against the upstream Containerfile (lines 79-108 have build deps; lines 136-161 `backend` stage does not). **No issue.**

#### D-06: Deploy job preservation (Phase B4) needs explicit diff verification
The plan says "Keep ALL deploy steps identical" but does not specify a verification method. The deploy job in `build-and-deploy.yml` is 483 lines (lines 156-639) with 12 SSM command steps including Sentry DSN, Supabase env, nginx fix, Blip proxy, migrations, asset sync, Redis flush, and verification. B4 should include a `git diff` verification that ONLY the build job's `file:` and `context:` lines changed.

**Severity: LOW.** The plan's intent is clear; adding a diff-check step would formalize it.

#### D-07: Rollback plan is implicit but not documented
If the fast build produces a broken image in Phase B4 (after swap), rollback requires reverting the `build-and-deploy.yml` change and re-running. The plan does not explicitly document this rollback path. However, since production images are tagged with date and SHA (lines 126-129), the previous working image is always available via `docker service update --image <old-tag>`.

**Severity: LOW.** Rollback is mechanically straightforward but should be documented for operational clarity.

#### D-08: EC2 disk space consideration
The plan adds a second image tag (`v15-fast-test`) to the EC2 instance during testing. The current workflow already keeps 4 builds and prunes. Having both `v15` and `v15-fast-test` images on EC2 simultaneously is fine — the cleanup job handles this. **No issue.**

#### D-09: Multi-stage copy path must match upstream exactly
The fast Containerfile extends `backend` stage (which has `/home/frappe/frappe-bench` with frappe+erpnext+payments). Task A3 must `bench get-app hrms` into this exact path. If the base image's virtualenv or bench directory structure differs, pip install will fail silently. The plan should include a verification step that `bench doctor` passes after base image build (covered in B3).

**Severity: LOW.** Covered by B3 verification but worth noting.

### Test Coverage Analysis

| Category | Existing | Missing | Recommended |
|----------|----------|---------|-------------|
| L3 Workflow Scenarios | 6 scenarios defined | None critical | Adequate |
| Base image build verification (B1) | 1 scenario | Base image content verification (are all 3 apps installed?) | Add `bench --site test version --format json` check |
| Fast image build time (B2) | 1 scenario + cache hit | Build time regression detection | Add GHA step annotation with build duration |
| EC2 functional verification (B3) | 1 scenario | Specific checks: bench doctor, API endpoint, asset hash | Plan mentions "DocTypes, API endpoints, assets" which is adequate |
| Production swap (B4) | 1 scenario | Post-swap smoke test on hq.bebang.ph | Existing workflow already has `frappe.ping` + asset verification |
| Negative/failure scenarios | 0 | What happens if base image is missing when fast build runs? | Add pre-check in build-fast.yml |
| Rollback scenario | 0 | Manual rollback procedure test | Add as L3 scenario |

**Coverage estimate: ~75% at L3 level.** The 6 L3 scenarios cover the happy path well. Missing: 1 negative scenario (base image unavailable), 1 rollback scenario.

### GO/NO-GO Verdict

**Verdict: GO**

**Blocking items:** None. All critical risks are addressed in the plan.

**Conditional items (should be addressed during execution, not blocking):**
1. D-04: Add base image refresh policy (scheduled or documented cadence)
2. D-07: Document explicit rollback procedure
3. Add 1 negative L3 scenario (base image missing)

### CRITICAL Findings

No critical findings. The plan is well-audited (self-amended based on actual GHA logs), correctly preserves the `CACHE_BUST`/`no-cache` safety mechanism, properly identifies the build-tools gap, and uses a safe parallel-test-lane approach before swapping production.

### Summary

The S105 plan is a well-structured, low-risk optimization that correctly learned from the 2026-01-29 stale-code production incident. Key strengths:

1. **Phase A deleted the dangerous caching approach** — the plan author already caught and removed the Docker layer cache re-enablement that caused the original incident.
2. **Structural separation** (pre-built base vs. hrms-only layer) is the correct architectural pattern for this problem.
3. **Test lane approach** (v15-fast-test) ensures zero production risk during validation.
4. **Build tools gap** (gcc/build-essential) was correctly identified — the upstream `backend` stage lacks these.
5. **HRMS_SHA cache-busting** prevents the exact stale-code problem that CACHE_BUST was created to solve.

Three minor gaps: base image refresh cadence, explicit rollback documentation, and one missing negative test scenario. None are blockers.

### Checklist

- [x] Pre-deployment dependencies identified (Docker Hub creds, base image, gcc/build-essential)
- [x] Docker build type specified (full no-cache for production; layer cache for base; HRMS_SHA bust for fast)
- [x] Test coverage >= 70% at L3+L4 level (75% — 6 L3 scenarios, missing 2 edge cases)
- [ ] Rollback plan documented (implicit but not explicit — D-07)
- [x] Evidence-derived counts use a reproducible method (build times from GHA logs, Containerfile line references verified)
- [x] Build-integrity artifacts required (form_submissions.json, api_mutations.json, state_verification.json listed)
