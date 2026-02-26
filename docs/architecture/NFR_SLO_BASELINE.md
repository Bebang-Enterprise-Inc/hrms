# NFR and SLO Baseline - BEI ERP

**Last Updated:** 2026-02-26  
**Owner:** Sam Karazi  
**Next Review:** 2026-03-05  
**Status:** Active baseline for architecture governance (v1)

## Evidence Inputs

1. Latest L1/L2/L3 run artifacts:
   - `output/l1/runs/l1_run_20260225_114617_024421.json`
   - `output/l2/runs/l2_run_20260225_114718_554264.json`
   - `output/l3/runs/l3_v2_run_20260225_121602_104741.json`
2. Monitoring workflow definitions:
   - `.github/workflows/uptime-check.yml`
   - `.github/workflows/synthetic-monitoring.yml`
3. Live endpoint latency sample captured on 2026-02-26:
   - `https://hq.bebang.ph/api/method/frappe.ping` -> 200 (306ms, 170ms, 146ms)
   - `https://my.bebang.ph` -> 200 (916ms, 251ms, 182ms)
   - `https://adms.bebang.ph/health` -> DNS failure from this workstation (`No such host is known`)

## Measured Baseline (2026-02-26 Snapshot)

| Metric | Measured Value | Source |
|---|---|---|
| L1 API smoke results | 54 total, 18 pass, 36 warn, 0 fail | `l1_run_20260225_114617_024421.json` |
| L2 page checks | 57 pass, 0 fail | `l2_run_20260225_114718_554264.json` |
| L3 workflow checks | 10 pass, 0 fail, 0 not-implemented | `l3_v2_run_20260225_121602_104741.json` |
| hq health response latency | avg 207.3ms, p50 170ms, p95 306ms (3 samples) | 2026-02-26 live checks |
| my.bebang response latency | avg 449.7ms, p50 251ms, p95 916ms (3 samples) | 2026-02-26 live checks |

## SLI Definitions

1. `SLI-AVAIL-HQ`: Successful probe rate for `https://hq.bebang.ph/api/method/frappe.ping` (`HTTP 200 / total probes`).
2. `SLI-AVAIL-MYBEBANG`: Successful probe rate for `https://my.bebang.ph` (`HTTP 200 / total probes`).
3. `SLI-LATENCY-HQ`: p95 response time of `frappe.ping` probes in milliseconds.
4. `SLI-LATENCY-MYBEBANG`: p95 response time of `my.bebang.ph` probes in milliseconds.
5. `SLI-SYNTHETIC`: Successful click-path runs / total scheduled synthetic runs.
6. `SLI-RELEASE-GATE`: `L1_FAIL == 0`, `L2_FAIL == 0`, `L3_FAIL == 0`, `L3_NOT_IMPLEMENTED == 0`.

## SLO Targets (v1)

| SLO ID | Target | Type | Measurement Source | Alert Condition |
|---|---|---|---|---|
| SLO-01 | `SLI-AVAIL-HQ >= 99.0%` monthly | Availability | `uptime-check.yml` runs | Any single non-200 probe |
| SLO-02 | `SLI-AVAIL-MYBEBANG >= 99.0%` monthly | Availability | `uptime-check.yml` runs | Any single non-200 probe |
| SLO-03 | `SLI-LATENCY-HQ p95 <= 1000ms` | Latency | Probe timings | p95 exceeds 1000ms for 3 consecutive windows |
| SLO-04 | `SLI-LATENCY-MYBEBANG p95 <= 1500ms` | Latency | Probe timings | p95 exceeds 1500ms for 3 consecutive windows |
| SLO-05 | `SLI-SYNTHETIC >= 95.0%` monthly | User-flow reliability | `synthetic-monitoring.yml` runs | Any failed synthetic run |
| SLO-06 | `SLI-RELEASE-GATE` must pass for production rollout | Release quality | L1/L2/L3 run artifacts | Any non-zero fail or NI count |

## Non-Functional Requirements Baseline

| NFR Area | Requirement | Evidence |
|---|---|---|
| Reliability | Automated uptime checks with alerting enabled | `.github/workflows/uptime-check.yml` |
| User-path verification | Scheduled synthetic click-path monitoring with artifacts | `.github/workflows/synthetic-monitoring.yml` |
| Recoverability | Documented rollback commands for backend/frontend/db | `docs/deployment/ROLLBACK_RUNBOOK.md` |
| Security | OAuth domain enforcement + encrypted token handling | `hrms/api/google_login.py`, `hrms/utils/google_oauth.py` |
| Testability | L1/L2/L3 framework with manifest + report generation | `docs/testing/L3_V2_METHOD.md`, `docs/testing/E2E_RULES.md` |

## Current Gaps (Still Open)

1. ADMS endpoint is not resolvable from this workstation during 2026-02-26 checks; monitor from CI runner as source of truth.
2. Monthly SLO rollup automation dashboard is not yet documented in architecture docs.
3. Route-registry binding is 169/169 in full map; remaining risk is unmapped test-account ownership on some routes.

## Review Cadence

1. Weekly: review SLO compliance and probe failures.
2. Per release: enforce `SLO-06` gate before production rollout.
3. Monthly: update this file with measured compliance and target changes (via ADR if thresholds change).
