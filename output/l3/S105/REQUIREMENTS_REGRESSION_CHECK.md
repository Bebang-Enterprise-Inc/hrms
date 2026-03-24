# Requirements Regression Check — S105 Docker Build Acceleration
## Date: 2026-03-24

| # | Requirement | Status | Implementation Approach |
|---|------------|--------|------------------------|
| 1 | Production workflow untouched until Phase B | YES | Only creating new files in Phase A |
| 2 | Test workflow is workflow_dispatch only | YES | build-fast.yml has `on: workflow_dispatch` only |
| 3 | Test workflow pushes to v15-fast-test, NOT v15 | YES | Tags hardcoded to v15-fast-test |
| 4 | Base image includes frappe/erpnext/payments version-15 | YES | apps.json hardcoded in Containerfile.base |
| 5 | Base Containerfile pins PYTHON_VERSION=3.11.6, NODE_VERSION=20.19.2, FRAPPE_BRANCH=version-15 | YES | ARGs hardcoded (upstream defaults diverged to 3.14/24/v16) |
| 6 | Fast Containerfile uses `bench build --app hrms` | YES | Not `bench build` |
| 7 | Fast Containerfile includes HRMS_SHA cache-busting | YES | ARG HRMS_SHA before bench get-app |
| 8 | Fast Containerfile installs gcc/build-essential | YES | apt-get install before pip, cleanup after |
| 9 | Fast Containerfile does NOT use `--depth 1` flag | YES | Uses `bench config set-common-config -c shallow_clone 1` instead |
| 10 | Base image tagged immutably (v15-YYYYMMDD) | YES | Dated tag + floating v15 alias |
| 11 | EC2 verification before production swap | YES | Phase B tasks B1-B3 |
| 12 | Phase B preserves all deploy steps | YES | B4 only changes build job |
| 13 | All 6 Swarm services use same image | YES | No change to deploy job |
| 14 | Cleanup job excludes frappe-base from pruning | YES | Added to B4 |

## HARD BLOCKERS Verified

| HARD BLOCKER | Task | Addressed |
|-------------|------|-----------|
| Cache-busting (HRMS_SHA) | A3 | YES — ARG before bench get-app |
| Build tools (gcc) | A3 | YES — apt-get install + cleanup |
| Version pinning (3.11.6/20.19.2/v15) | A1 | YES — hardcoded ARGs |
| Base image completeness | A1 | YES — backend stage with all 3 apps |
| bench get-app --depth doesn't exist | A3 | YES — using shallow_clone config |
| Deploy job zero changes (B4) | B4 | YES — diff verification required |
