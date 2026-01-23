# Employee Clearance & Exit Interview - Deployment Progress

> **Created:** 2026-01-22
> **Status:** RESOLVED - Production Restored 2026-01-23
> **Priority:** HIGH (blocks clearance module go-live)
> **Full Plan:** `C:\Users\Sam\.claude\plans\eager-doodling-treehouse.md`

---

## Executive Summary

Building Employee Separation & Exit Interview system with DOLE compliance. Frontend deployed to Vercel successfully. Backend API deployment to Frappe Docker initially **FAILED** due to docker commit corruption.

**Current State (2026-01-23):** PRODUCTION RESTORED. Site is live at https://hrms.bebang.ph. CI/CD pipeline created for safe future deployments.

---

## RESOLUTION (2026-01-23)

### What Was Done

1. **Created CI/CD Pipeline** (`.github/workflows/build-and-deploy.yml`)
   - Automated Docker image build on push to `production` branch
   - AWS SSM deployment to EC2
   - Migration support via workflow inputs
   - Image: `samkarazi/bebang-erpnext-hrms:v15`

2. **Fixed Server Configuration**
   - Correct path: `/home/ubuntu/frappe_docker` (not `/home/ubuntu/frappe-hrms`)
   - Compose file: `pwd.yml` (production with docker)
   - Created `volumes-override.yml` for external volume mounting
   - Changed frontend port from 8080 to 80 (ADMS uses 8080)

3. **Volume Configuration**
   - Site data preserved in `bebang-hrms_*` volumes
   - New stack uses external volumes to access existing data
   - Sites: hrms.bebang.ph, erp.bebang.ph, hr.bebang.ph, lfg.bebang.ph

### Key Files Created/Modified

| File | Purpose |
|------|---------|
| `.github/workflows/build-and-deploy.yml` | CI/CD workflow |
| `.github/helper/apps.json` | Apps included in Docker build |
| `docker-dev/docker-compose.yml` | Local dev environment |
| `/home/ubuntu/frappe_docker/volumes-override.yml` (server) | External volume config |

### Verification

```bash
# Test API
curl https://hrms.bebang.ph/api/method/frappe.ping
# Returns: {"message":"pong"}

# Login page
curl -s -o /dev/null -w "%{http_code}" https://hrms.bebang.ph/login
# Returns: 200
```

---

## What Was Built (COMPLETE)

### 1. Frappe Backend - DocTypes (5 new, 2 modified)

**New DocTypes Created:**
| DocType | Path | Purpose |
|---------|------|---------|
| BEI DOLE Compliance Item | `hrms/hr/doctype/bei_dole_compliance_item/` | Master list of DOLE requirements |
| BEI Separation Type Item | `hrms/hr/doctype/bei_separation_type_item/` | Child: separation types per compliance item |
| BEI DOLE Compliance Checklist | `hrms/hr/doctype/bei_dole_compliance_checklist/` | Child: checklist entries on separation |
| BEI Exit Interview Question | `hrms/hr/doctype/bei_exit_interview_question/` | Master: 26 questionnaire items |
| BEI Exit Interview Response | `hrms/hr/doctype/bei_exit_interview_response/` | Child: employee responses |

**Modified DocTypes:**
- `Employee Separation` - Added `custom_separation_type`, `custom_dole_compliance` fields
- `Exit Interview` - Added `custom_questionnaire_responses`, `custom_primary_reason` fields

**Seed Data Patch:** `hrms/patches/v15_0/seed_dole_compliance_and_questions.py`
- 12 DOLE compliance items
- 26 exit interview questions (7 categories)

### 2. Frappe Backend - API Endpoints

**File:** `hrms/api/employee_clearance.py` (14KB, 417 lines)

| Function | Purpose |
|----------|---------|
| `get_exit_interview_questions()` | Get all active questions for questionnaire |
| `submit_exit_interview_responses(exit_interview, responses)` | Submit questionnaire answers |
| `get_exit_interview_responses(exit_interview)` | Retrieve saved responses |
| `get_separation_types()` | List all separation type options |
| `create_employee_separation(employee, separation_type, ...)` | Create new separation record |
| `get_employee_separation(name)` | Get single separation with compliance |
| `get_employee_separations(employee)` | List all separations for employee |
| `populate_dole_compliance(employee_separation, separation_type)` | Auto-populate DOLE checklist |
| `update_compliance_status(name, status, ...)` | Update checklist item status |
| `get_dole_compliance_items()` | List all DOLE compliance items |
| `get_clearance_status(employee)` | Get clearance progress summary |
| `generate_coe(employee)` | Generate Certificate of Employment |

**Import Added:** `hrms/api/__init__.py` - Line added to import employee_clearance module

### 3. React Frontend - my.bebang.ph (bei-tasks repo)

**Pages Created:**
| Path | File | Purpose |
|------|------|---------|
| `/clearance` | `app/clearance/page.tsx` | Clearance status dashboard |
| `/clearance/exit-interview` | `app/clearance/exit-interview/page.tsx` | 26-question questionnaire |

**Components:**
- `components/clearance/clearance-status.tsx` - Status card with progress
- `components/clearance/exit-interview-form.tsx` - Multi-step questionnaire form
- Various UI components using Shadcn

**TypeScript Fixes Applied:**
- Fixed `Object.entries()` type issues in `wizard-step-review.tsx`
- Fixed type assertions for form data iteration

**Vercel Deployment:** SUCCESS
- URL: https://bei-tasks.vercel.app/clearance
- Production: https://my.bebang.ph/clearance (via Cloudflare proxy)

---

## What Went Wrong (THE BUG)

### Root Cause: Docker Image Corruption via `docker commit`

**Timeline:**
1. Copied `employee_clearance.py` to running container
2. Attempted to reload gunicorn with SIGUSR2 - didn't pick up new whitelist
3. Restarted container - still didn't work (--preload means code loaded at startup)
4. **MISTAKE:** Used `docker commit` to capture container state as new image
5. Tagged committed image as `bebang/erpnext-hrms:v15` (overwrote original)
6. Restarted all containers with "new" image
7. **RESULT:** ALL API calls fail, including core Frappe functions

### Technical Details

**Why hot-patching doesn't work:**
```dockerfile
# Frappe Docker uses --preload
CMD ["gunicorn", "--preload", "frappe.app:application"]
```
- `--preload` loads application code ONCE at master process startup
- Workers fork from pre-loaded master
- File changes in container are NOT picked up
- Container restart reloads ORIGINAL IMAGE, not patched files

**Why docker commit broke everything:**
- `docker commit` captures filesystem state, not process state
- Something about the commit corrupted the Python environment
- Even `frappe.client.get_count` (core Frappe function) returns "not whitelisted"
- This affects ALL Docker images tried (custom, official frappe/erpnext:v15)

**Error Response:**
```json
{
  "exc_type": "PermissionError",
  "exc": "frappe.handler.is_whitelisted() ... is not whitelisted"
}
```

### What Was Tried (All Failed)

| Attempt | Result |
|---------|--------|
| SIGUSR2 to gunicorn | Reloaded but whitelist not updated |
| Container restart | Reloaded from image, still broken |
| Docker commit to new image | Made everything worse |
| Switch to `bebang-hrms-custom:v1` | Same error |
| Switch to `frappe/erpnext:v15` | Same error |
| Clear Redis cache | No effect |

### Current Server State

**Running Image:** `bebang/erpnext-hrms:v15` (corrupted)
**Sites:** erp.bebang.ph, hr.bebang.ph, hrms.bebang.ph, lfg.bebang.ph
**EC2 Instance:** i-026b7477d27bd46d6
**All API calls:** Return 403 "not whitelisted"

---

## How To Fix (UPDATED 2026-01-23)

### Option A: Use New GitHub Actions Workflow (RECOMMENDED)

We've created a proper CI/CD workflow. Just trigger it:

**Via GitHub UI:**
1. Go to https://github.com/Bebang-Enterprise-Inc/Bebang-ERP-HR/actions
2. Select "Build and Deploy Frappe HRMS"
3. Click "Run workflow"
4. Leave defaults (build enabled, migrate enabled)
5. Wait 15-20 minutes for build + deploy

**Via Git Push:**
```bash
# Any push to production triggers build + deploy
git push origin production
```

**Required GitHub Secrets (set these first if not already):**
| Secret | How to get |
|--------|------------|
| `DOCKERHUB_USERNAME` | Docker Hub account username |
| `DOCKERHUB_TOKEN` | Docker Hub > Account Settings > Security > New Access Token |
| `AWS_ACCESS_KEY_ID` | `doppler secrets get AWS_ACCESS_KEY_ID --project bei-erp --config dev --plain` |
| `AWS_SECRET_ACCESS_KEY` | `doppler secrets get AWS_SECRET_ACCESS_KEY --project bei-erp --config dev --plain` |

### Option B: Manual Build (if GitHub Actions fails)

```bash
# 1. Clone frappe_docker
git clone https://github.com/frappe/frappe_docker.git
cd frappe_docker

# 2. Create apps.json (now includes BEI custom repo)
cat > apps.json << 'EOF'
[
  {"url": "https://github.com/frappe/erpnext", "branch": "version-15"},
  {"url": "https://github.com/frappe/payments", "branch": "version-15"},
  {"url": "https://github.com/frappe/hrms", "branch": "version-15"},
  {"url": "https://github.com/Bebang-Enterprise-Inc/Bebang-ERP-HR", "branch": "production"}
]
EOF

# 3. Build new image
export APPS_JSON_BASE64=$(base64 -w 0 apps.json)
docker build \
  --no-cache \
  --build-arg FRAPPE_BRANCH=version-15 \
  --build-arg PYTHON_VERSION=3.11.6 \
  --build-arg NODE_VERSION=20.19.2 \
  --build-arg APPS_JSON_BASE64=$APPS_JSON_BASE64 \
  --file images/custom/Containerfile \
  --tag bebang/erpnext-hrms:v15-$(date +%Y%m%d) \
  --tag bebang/erpnext-hrms:v15 \
  .

# 4. Push to Docker Hub
docker login
docker push bebang/erpnext-hrms:v15-$(date +%Y%m%d)
docker push bebang/erpnext-hrms:v15

# 5. Deploy to server via AWS SSM
export AWS_ACCESS_KEY_ID=$(doppler secrets get AWS_ACCESS_KEY_ID --project bei-erp --config dev --plain)
export AWS_SECRET_ACCESS_KEY=$(doppler secrets get AWS_SECRET_ACCESS_KEY --project bei-erp --config dev --plain)
export AWS_DEFAULT_REGION=ap-southeast-1

aws ssm send-command \
  --instance-ids "i-026b7477d27bd46d6" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /home/ubuntu/frappe-docker && docker compose pull && docker compose up -d"]' \
  --output json
```

### Option C: Quick Deploy (if image already exists on Docker Hub)

If you just need to restart with existing image:

```bash
export AWS_ACCESS_KEY_ID=$(doppler secrets get AWS_ACCESS_KEY_ID --project bei-erp --config dev --plain)
export AWS_SECRET_ACCESS_KEY=$(doppler secrets get AWS_SECRET_ACCESS_KEY --project bei-erp --config dev --plain)
export AWS_DEFAULT_REGION=ap-southeast-1

aws ssm send-command \
  --instance-ids "i-026b7477d27bd46d6" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /home/ubuntu/frappe-docker && docker compose pull && docker compose up -d"]' \
  --output json
```

### Verify Recovery

```bash
# Test API endpoint
curl https://hrms.bebang.ph/api/method/frappe.client.get_count?doctype=User

# Expected: {"message": 123}  (some number)
# If still "not whitelisted", the image is still corrupted
```

---

## Pending Tasks (Updated 2026-01-23)

| Task | Status | Notes |
|------|--------|-------|
| Fix Docker image | ✅ DONE | Production restored with CI/CD |
| Run `bench migrate` | PENDING | Create new DocTypes in DB |
| Run seed data patch | PENDING | Populate DOLE items + questions |
| Test clearance status page | PENDING | https://my.bebang.ph/clearance |
| Test exit interview form | PENDING | https://my.bebang.ph/clearance/exit-interview |
| Verify API endpoints | PENDING | All 12 functions in employee_clearance.py |
| Include BEI custom code in image | PENDING | Currently using standard frappe/hrms |

---

## Files Reference

### Local (BEI-ERP repo)
```
hrms/api/employee_clearance.py          # API endpoints (committed)
hrms/api/__init__.py                    # Import added (committed)
hrms/hr/doctype/bei_*/                  # 5 new DocTypes (committed)
hrms/patches/v15_0/seed_dole_*.py       # Seed data patch (committed)
```

### Local (bei-tasks repo)
```
app/clearance/page.tsx                  # Clearance status page
app/clearance/exit-interview/page.tsx   # Exit interview form
components/clearance/                   # Clearance components
```

### Server (UPDATED 2026-01-23)
```
/home/ubuntu/frappe_docker/             # Docker compose location (with underscore!)
/home/ubuntu/frappe_docker/pwd.yml      # Production compose file
/home/ubuntu/frappe_docker/volumes-override.yml  # External volumes config
/home/frappe/frappe-bench/apps/hrms/    # HRMS app in container
/home/frappe/frappe-bench/sites/hrms.bebang.ph/  # Site directory
```

### Docker Configuration
```
Image: samkarazi/bebang-erpnext-hrms:v15
Volumes: bebang-hrms_sites, bebang-hrms_db-data, bebang-hrms_logs
Port: 80 (frontend nginx) -> 8080 (internal)
```

---

## Plan Reference

Full implementation plan: `C:\Users\Sam\.claude\plans\eager-doodling-treehouse.md`

### Week 1 Status: DocTypes COMPLETE ✅
- [x] BEI DOLE Compliance Item
- [x] BEI Separation Type Item
- [x] BEI DOLE Compliance Checklist
- [x] BEI Exit Interview Question
- [x] BEI Exit Interview Response
- [x] Employee Separation custom fields
- [x] Exit Interview custom fields
- [x] Seed data patch

### Week 2 Status: Backend Logic - IN PROGRESS
- [x] employee_clearance.py API created
- [ ] Deploy to production (BLOCKED)
- [ ] Test API endpoints
- [ ] COE generation template

### Week 3 Status: Frontend - PARTIAL
- [x] Clearance status page
- [x] Exit interview questionnaire
- [ ] HR separations dashboard (not started)
- [ ] DOLE compliance tracker (not started)

---

## Lessons Learned

1. **NEVER use `docker commit` for Frappe** - It corrupts the Python/gunicorn environment
2. **Hot-patching doesn't work with --preload** - Must rebuild image for Python changes
3. **Always tag images with dates** - Keep rollback options (e.g., v15-20260122)
4. **Set up CI/CD early** - Manual Docker builds are error-prone
5. **Test API locally first** - Use `bench execute` before deploying

---

## Contact / Credentials Needed

- **Docker Hub:** Need login credentials (check with IT or bebang account)
- **AWS SSM:** Working via Doppler (bei-erp config)
- **GitHub:** PAT in Doppler as GITHUB_PAT
