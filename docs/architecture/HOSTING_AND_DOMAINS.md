# Hosting and Domains Inventory - BEI ERP

**Last Updated:** 2026-02-26  
**Owner:** Sam Karazi  
**Next Review:** 2026-03-05  
**Evidence Window:** 2026-02-26 (live DNS + HTTP checks, repo/workflow audit)

## Purpose

This document records exactly where BEI ERP endpoints are reachable, what infrastructure/workflows back them, and where domain/repo evidence currently conflicts.

## Domain and Hosting Matrix

| Domain | Live Check (2026-02-26) | DNS Evidence (2026-02-26) | Hosting Evidence | Source Files |
|---|---|---|---|---|
| `my.bebang.ph` | `200` | `CNAME cname.vercel-dns.com`, A: `76.76.21.164`, `66.33.60.34` | Vercel-hosted frontend domain | `.github/workflows/uptime-check.yml`, `docs/architecture/INFRASTRUCTURE_INVENTORY.md` |
| `tasks.bebang.ph` | `200` | `CNAME cname.vercel-dns.com`, A: `76.76.21.164`, `66.33.60.34` | Additional Vercel frontend alias | Local DNS/HTTP checks (2026-02-26) |
| `bei-tasks.vercel.app` | `200` | A: `64.29.17.195`, `216.198.79.195` | Vercel project default URL for frontend repo | `C:\Users\Sam\Projects\Claude\bei-tasks\README.md` |
| `hq.bebang.ph` | `200` (`/api/method/frappe.ping`) | Cloudflare A: `104.26.12.188`, `104.26.13.188`, `172.67.72.103` | Backend public edge; deployment driven by AWS + Docker Swarm workflow | `.github/workflows/build-and-deploy.yml`, `docs/architecture/INFRASTRUCTURE_INVENTORY.md` |
| `hrms.bebang.ph` | `200` (`/api/method/frappe.ping`) | Cloudflare A: `104.26.12.188`, `104.26.13.188`, `172.67.72.103` | Backend alias used as `FRAPPE_SITE` in deploy workflow | `.github/workflows/build-and-deploy.yml` |
| `lfg.bebang.ph` | `200` (`/api/method/frappe.ping`) | Cloudflare A: `104.26.12.188`, `104.26.13.188`, `172.67.72.103` | Backend alias used in BEI-Tasks defaults/docs | `C:\Users\Sam\Projects\Claude\bei-tasks\app\api\frappe\[...path]\route.ts`, `README.md` |

## Repository and Deployment Mapping

| Surface | Repo | Branch/Commit Snapshot | Deployment Mechanism | Infra Target |
|---|---|---|---|---|
| Frontend (`my.bebang.ph`) | `Bebang-Enterprise-Inc/BEI-Tasks` | `master` @ `b9e7106e238a6ced88f49a14229102a5c4de9d7b` | Vercel deployment (project metadata present locally) | Vercel org `team_xvK1nhuvsdZp3GNfd4uDJ0DW`, project `prj_Axx7rOKGfuvIDME1uxq6bgxdaJ6F` (`.vercel/project.json`) |
| Backend (`hq/hrms/lfg.bebang.ph`) | `Bebang-Enterprise-Inc/hrms` | `fix/l3-expense-store-resolution-20260223` @ `ffcb5d9f124e6984f4d523d89e5f420fe658e9fe` | GitHub Actions + Docker Hub + AWS SSM rolling updates | EC2 `i-026b7477d27bd46d6`, Docker Swarm services (`frappe_*`) |

See also:
- `docs/architecture/REPOSITORY_INVENTORY.md`
- `docs/architecture/INFRASTRUCTURE_INVENTORY.md`

## Evidence Divergence Register (No Assumptions)

1. Frontend identity conflict in BEI-Tasks sources:
   - Repo README lists production as `https://bei-tasks.vercel.app` and backend as `https://lfg.bebang.ph`.
   - Architecture/monitoring docs use `https://my.bebang.ph` and `https://hq.bebang.ph`.
2. Backend domain conflict in deploy workflow:
   - `FRAPPE_SITE` is set to `hrms.bebang.ph` in `.github/workflows/build-and-deploy.yml`.
   - Verification steps in the same workflow target `https://hq.bebang.ph`.
3. DNS and uptime checks show `hq.bebang.ph`, `hrms.bebang.ph`, and `lfg.bebang.ph` all resolve and return `200`.
   - Inference: these are active aliases on the same Cloudflare edge set.

## Operations Baseline (Used by CI Monitoring)

Current monitoring sources treat these as operationally authoritative:

1. Backend health: `https://hq.bebang.ph/api/method/frappe.ping`.
2. Frontend health: `https://my.bebang.ph`.
3. ADMS health: `https://adms.bebang.ph/health`.

Source: `.github/workflows/uptime-check.yml`

## Refresh Commands

```powershell
# Endpoint checks
Invoke-WebRequest https://hq.bebang.ph/api/method/frappe.ping -UseBasicParsing
Invoke-WebRequest https://my.bebang.ph -UseBasicParsing
Invoke-WebRequest https://lfg.bebang.ph/api/method/frappe.ping -UseBasicParsing
Invoke-WebRequest https://hrms.bebang.ph/api/method/frappe.ping -UseBasicParsing

# DNS checks
Resolve-DnsName hq.bebang.ph
Resolve-DnsName my.bebang.ph
Resolve-DnsName lfg.bebang.ph
Resolve-DnsName hrms.bebang.ph
Resolve-DnsName tasks.bebang.ph

# Repo/deploy evidence
git -C F:\Dropbox\Projects\BEI-ERP rev-parse --abbrev-ref HEAD
git -C F:\Dropbox\Projects\BEI-ERP rev-parse HEAD
git -C C:\Users\Sam\Projects\Claude\bei-tasks rev-parse --abbrev-ref HEAD
git -C C:\Users\Sam\Projects\Claude\bei-tasks rev-parse HEAD
```
