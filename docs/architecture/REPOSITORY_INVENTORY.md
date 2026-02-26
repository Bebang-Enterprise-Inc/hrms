# Repository Inventory - BEI ERP

**Last Updated:** 2026-02-26  
**Owner:** Sam Karazi  
**Next Review:** 2026-03-05  
**Evidence Basis:** `git remote -v`, `git rev-parse`, `git ls-remote --symref origin HEAD` run on 2026-02-26.

## Canonical Repositories

| System Area | Repository | Local Path | Current Branch | Current Commit | Origin Remote | Upstream Remote | Remote HEAD |
|---|---|---|---|---|---|---|---|
| Backend (hq.bebang.ph) | `Bebang-Enterprise-Inc/hrms` | `F:\Dropbox\Projects\BEI-ERP` | `fix/l3-expense-store-resolution-20260223` | `ffcb5d9f124e6984f4d523d89e5f420fe658e9fe` | `https://github.com/Bebang-Enterprise-Inc/hrms.git` | `https://github.com/frappe/hrms` | `production` |
| Frontend (my.bebang.ph) | `Bebang-Enterprise-Inc/BEI-Tasks` | `C:\Users\Sam\Projects\Claude\bei-tasks` | `master` | `b9e7106e238a6ced88f49a14229102a5c4de9d7b` | `https://github.com/Bebang-Enterprise-Inc/BEI-Tasks.git` | *(none configured)* | `main` |
| Analytics | `Bebang-Enterprise-Inc/Bebang-Metabase-Stats` | `C:\Users\Sam\.cursor\Projects\bebang-analytics` | `master` | `5cec94348a7daea8a1e24c000c49915768b0645f` | `https://github.com/Bebang-Enterprise-Inc/Bebang-Metabase-Stats.git` | *(none configured)* | `master` |

## Remotes (Full)

### BEI-ERP (`F:\Dropbox\Projects\BEI-ERP`)

- `origin` (fetch/push): `https://github.com/Bebang-Enterprise-Inc/hrms.git`
- `upstream` (fetch/push): `https://github.com/frappe/hrms`

### BEI-Tasks (`C:\Users\Sam\Projects\Claude\bei-tasks`)

- `origin` (fetch/push): `https://github.com/Bebang-Enterprise-Inc/BEI-Tasks.git`

### Bebang Analytics (`C:\Users\Sam\.cursor\Projects\bebang-analytics`)

- `origin` (fetch/push): `https://github.com/Bebang-Enterprise-Inc/Bebang-Metabase-Stats.git`

## Path Validation Notes

- `C:\Users\Sam\Projects\Claude\bebang-analytics` was checked and `.git` was not found at this path.
- This inventory is location-specific; if repos are relocated, rerun repository discovery before editing architecture docs.

## Update Command Set

```powershell
git -C F:\Dropbox\Projects\BEI-ERP remote -v
git -C F:\Dropbox\Projects\BEI-ERP rev-parse --abbrev-ref HEAD
git -C F:\Dropbox\Projects\BEI-ERP rev-parse HEAD
git -C F:\Dropbox\Projects\BEI-ERP ls-remote --symref origin HEAD

git -C C:\Users\Sam\Projects\Claude\bei-tasks remote -v
git -C C:\Users\Sam\Projects\Claude\bei-tasks rev-parse --abbrev-ref HEAD
git -C C:\Users\Sam\Projects\Claude\bei-tasks rev-parse HEAD
git -C C:\Users\Sam\Projects\Claude\bei-tasks ls-remote --symref origin HEAD

git -C C:\Users\Sam\.cursor\Projects\bebang-analytics remote -v
git -C C:\Users\Sam\.cursor\Projects\bebang-analytics rev-parse --abbrev-ref HEAD
git -C C:\Users\Sam\.cursor\Projects\bebang-analytics rev-parse HEAD
git -C C:\Users\Sam\.cursor\Projects\bebang-analytics ls-remote --symref origin HEAD
```
