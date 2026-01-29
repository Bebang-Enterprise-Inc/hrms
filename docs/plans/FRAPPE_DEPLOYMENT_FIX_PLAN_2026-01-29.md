# Frappe Docker Deployment Fix Plan

**Date:** January 29, 2026
**Status:** Stage 1 COMPLETED ✅ | Stage 2 COMPLETED ✅
**Execution Time:** Stage 1: ~60 minutes | Stage 2: ~45 minutes
**Risk Level:** Low (no data affected)

---

## Objective

Fix the recurring CSS 404 errors and setup wizard redirect loop:

### Stage 1 (Completed ✅)
1. **Immediate:** Delete stale assets volume and redeploy ✅
2. **Permanent:** Update GitHub Actions to use `down` + `up -d` pattern ✅
3. **Bonus Fix:** Resolve setup wizard redirect loop discovered during testing ✅

### Stage 2 (Completed ✅)
4. **Docker Swarm Migration:** Zero-downtime deploys with rolling updates ✅
   - Swarm initialized on EC2 (node k6qylre482nup18qw1dylv85h)
   - 9 services deployed: backend, frontend, websocket, queue-short, queue-long, scheduler, db, redis-cache, redis-queue
   - GitHub Actions updated to use `docker service update` for rolling deploys
   - Backups created at `/home/ubuntu/backups/swarm-migration-20260129/`

---

## Execution Summary

### What Was Done

| Step | Status | Details |
|------|--------|---------|
| Pre-flight checks | ✅ | AWS credentials verified, GitHub CLI authenticated |
| Part 1.1: Verify CSS state | ✅ | Confirmed CSS 404 errors before fix |
| Part 1.2: Redeploy containers | ✅ | `docker compose down` + `up -d` via AWS SSM |
| Part 1.3: Verify CSS fix | ✅ | All CSS/JS files return 200 OK |
| Part 2.1: Update workflow | ✅ | Changed deploy to use `down` before `up -d` |
| Part 2.2: Add health check | ✅ | CSS/JS verification step added |
| Part 2.3: Commit & push | ✅ | Commit `48f1c2f9b` pushed to production |
| **Bonus: Setup wizard fix** | ✅ | Fixed `desktop:home_page` database setting |
| E2E browser test | ✅ | Full Google OAuth login flow verified |

### Issues Found and Fixed

#### Issue 1: CSS 404 Errors (Original Issue)

**Root Cause:** GitHub Actions was using `docker compose up -d --no-deps` which only restarted containers without refreshing assets. Frontend container retained old CSS files while backend generated new hashes during migration.

**Fix Applied:**
1. Changed workflow to use `docker compose down` then `up -d`
2. Added CSS/JS health check step that fails workflow on 404
3. Increased stabilization wait from 15s to 30s

**Commit:** `48f1c2f9b` - fix: Add asset volume reset and CSS health check to deployment

#### Issue 2: Setup Wizard Redirect Loop (Discovered During Testing)

**Symptom:** After Google OAuth login, `/app` caused infinite redirect loop with continuous page refresh. The `setup_wizard.load_languages` API was being called repeatedly.

**Root Cause:** Found in `tabDefaultValue` table:
```sql
defkey='desktop:home_page' defvalue='setup-wizard'
```

This caused Frappe to redirect all `/app` requests to the setup wizard, which then redirected back, creating an infinite loop.

**Database Fixes Applied:**
```sql
-- Fix 1: Mark setup as complete
UPDATE tabDefaultValue SET defvalue='1'
WHERE defkey='setup_complete' AND parent='__default';

-- Fix 2: Mark HRMS app as setup complete
UPDATE `tabInstalled Application` SET is_setup_complete=1
WHERE app_name='hrms';

-- Fix 3: ROOT CAUSE FIX - Change home page from setup-wizard
UPDATE tabDefaultValue SET defvalue='Workspaces'
WHERE defkey='desktop:home_page' AND parent='__default';
```

---

## Pre-Flight Checklist

- [x] AWS credentials ready (`doppler secrets get AWS_ACCESS_KEY_ID --plain`)
- [x] GitHub CLI authenticated (`gh auth status`)
- [x] Backup confirmation: Database is in `bebang-hrms_db-data` (NOT deleted)
- [x] Low-traffic time confirmed (early morning PH time)

---

## Success Criteria - ALL PASSED ✅

- [x] https://hq.bebang.ph/login loads with proper CSS styling
- [x] https://hq.bebang.ph/api/method/frappe.ping returns `{"message":"pong"}`
- [x] Google OAuth login works (redirects to Google, returns to app)
- [x] No CSS 404 errors in browser DevTools Network tab
- [x] GitHub Actions updated with asset health check
- [x] `/app` no longer causes redirect loop
- [x] Full navbar visible (Search, Notifications, Help, User Menu)
- [x] Logout/re-login cycle works correctly

---

## Browser E2E Test Results (Chrome MCP)

Full end-to-end verification completed:

| Test | Result |
|------|--------|
| Navigate to login page | ✅ CSS loads correctly |
| Click "Sign in with Google" | ✅ OAuth flow completes |
| Landing page after login | ✅ `/app/home` with full UI |
| Navbar elements | ✅ All present (Logo, Search, Notifications, Help, User Menu) |
| Sidebar modules | ✅ All visible (HR, Payroll, Stock, etc.) |
| User Menu dropdown | ✅ Opens with "Log out" option |
| Logout functionality | ✅ Returns to login page |
| Re-login via Google | ✅ Works correctly |
| Navigate to `/app` | ✅ Redirects to `/app/home` (no loop!) |
| Network requests | ✅ No `setup_wizard` API calls |

---

## Stage 2: Docker Swarm Migration (Future Sprint)

**Status:** PLANNED - Ready to Execute
**Priority:** Medium (current fix works, but Swarm is more robust)
**Estimated Effort:** 4-6 hours
**Risk Level:** Low (can rollback to Docker Compose if needed)

---

### Why Docker Swarm?

| Benefit | Current (Docker Compose) | With Swarm |
|---------|--------------------------|------------|
| Asset volume handling | Manual `down` + `up` required | Automatic recreation on deploy |
| Zero-downtime deploys | ❌ ~30-60s downtime | ✅ Rolling updates |
| Health checks | Manual verification | Built-in container health checks |
| Rollback | Manual image tag change | `docker service rollback` |
| Scaling | Manual container count | `docker service scale` |
| Secret management | Environment variables | Docker secrets (encrypted) |

**Industry Standard:** Docker Swarm is the recommended production setup for Frappe Docker per official documentation.

---

### Pre-Migration Checklist

- [x] Current Docker Compose deployment stable (Stage 1 complete ✅)
- [x] Backup all volumes before migration (`/home/ubuntu/backups/swarm-migration-20260129/`)
- [x] Schedule maintenance window (low-traffic time - early morning PH)
- [x] Test Swarm commands on staging/local first
- [x] Prepare rollback procedure (documented below)

---

### Step 1: Initialize Docker Swarm on EC2

```bash
# Via AWS SSM
aws ssm send-command \
  --instance-ids "i-026b7477d27bd46d6" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=[
    "docker swarm init",
    "docker node ls"
  ]' \
  --output text --query "Command.CommandId"
```

**Expected Output:**
```
Swarm initialized: current node (xxx) is now a manager.
```

---

### Step 2: Convert pwd.yml to Swarm Stack Format

Create `stack.yml` based on pwd.yml with Swarm-specific configurations:

```yaml
# stack.yml - Docker Swarm version
version: "3.8"

services:
  backend:
    image: samkarazi/bebang-erpnext-hrms:v15
    deploy:
      replicas: 1
      update_config:
        parallelism: 1
        delay: 10s
        failure_action: rollback
      rollback_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    environment:
      - FRAPPE_SITE_NAME_HEADER=$$host
    networks:
      - frappe-network

  frontend:
    image: samkarazi/bebang-erpnext-hrms:v15
    command: nginx-entrypoint.sh
    deploy:
      replicas: 1
      update_config:
        parallelism: 1
        delay: 10s
        failure_action: rollback
    ports:
      - "80:8080"
    volumes:
      - sites:/home/frappe/frappe-bench/sites:ro
    environment:
      - FRAPPE_SITE_NAME_HEADER=$$host
      - UPSTREAM_REAL_IP_ADDRESS=127.0.0.1
      - UPSTREAM_REAL_IP_HEADER=X-Forwarded-For
      - UPSTREAM_REAL_IP_RECURSIVE=off
    networks:
      - frappe-network

  websocket:
    image: samkarazi/bebang-erpnext-hrms:v15
    command: node /home/frappe/frappe-bench/apps/frappe/socketio.js
    deploy:
      replicas: 1
    volumes:
      - sites:/home/frappe/frappe-bench/sites:ro
      - logs:/home/frappe/frappe-bench/logs
    networks:
      - frappe-network

  queue-short:
    image: samkarazi/bebang-erpnext-hrms:v15
    command: bench worker --queue short,default
    deploy:
      replicas: 1
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    networks:
      - frappe-network

  queue-long:
    image: samkarazi/bebang-erpnext-hrms:v15
    command: bench worker --queue long
    deploy:
      replicas: 1
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    networks:
      - frappe-network

  scheduler:
    image: samkarazi/bebang-erpnext-hrms:v15
    command: bench schedule
    deploy:
      replicas: 1
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    networks:
      - frappe-network

  db:
    image: mariadb:10.6
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --skip-character-set-client-handshake
      - --skip-innodb-read-only-compressed
    volumes:
      - db-data:/var/lib/mysql
    environment:
      MYSQL_ROOT_PASSWORD_FILE: /run/secrets/db_root_password
    secrets:
      - db_root_password
    networks:
      - frappe-network

  redis-cache:
    image: redis:alpine
    deploy:
      replicas: 1
    networks:
      - frappe-network

  redis-queue:
    image: redis:alpine
    deploy:
      replicas: 1
    volumes:
      - redis-queue-data:/data
    networks:
      - frappe-network

networks:
  frappe-network:
    driver: overlay

volumes:
  sites:
    external: true
    name: bebang-hrms_sites
  db-data:
    external: true
    name: bebang-hrms_db-data
  logs:
    external: true
    name: bebang-hrms_logs
  redis-queue-data:
    external: true
    name: bebang-hrms_redis-queue-data

secrets:
  db_root_password:
    external: true
```

---

### Step 3: Create Docker Secrets

```bash
# Create secret for database password
aws ssm send-command \
  --instance-ids "i-026b7477d27bd46d6" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=[
    "echo \"YOUR_DB_PASSWORD\" | docker secret create db_root_password -",
    "docker secret ls"
  ]' \
  --output text --query "Command.CommandId"
```

---

### Step 4: Deploy the Stack

```bash
# Stop Docker Compose stack first
aws ssm send-command \
  --instance-ids "i-026b7477d27bd46d6" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=[
    "cd /home/ubuntu/frappe_docker",
    "docker compose -f pwd.yml -f volumes-override.yml down",
    "docker stack deploy -c stack.yml frappe",
    "docker stack services frappe",
    "sleep 30",
    "docker service ls"
  ]' \
  --output text --query "Command.CommandId"
```

---

### Step 5: Update GitHub Actions for Swarm

Replace the deploy step in `.github/workflows/build-and-deploy.yml`:

```yaml
      - name: Deploy via Docker Swarm
        run: |
          COMMAND_ID=$(aws ssm send-command \
            --instance-ids "${{ env.EC2_INSTANCE_ID }}" \
            --document-name "AWS-RunShellScript" \
            --parameters 'commands=[
              "cd /home/ubuntu/frappe_docker",
              "docker service update --image ${{ env.DOCKER_IMAGE }}:${{ env.DOCKER_TAG }} frappe_backend",
              "docker service update --image ${{ env.DOCKER_IMAGE }}:${{ env.DOCKER_TAG }} frappe_frontend",
              "docker service update --image ${{ env.DOCKER_IMAGE }}:${{ env.DOCKER_TAG }} frappe_websocket",
              "docker service update --image ${{ env.DOCKER_IMAGE }}:${{ env.DOCKER_TAG }} frappe_queue-short",
              "docker service update --image ${{ env.DOCKER_IMAGE }}:${{ env.DOCKER_TAG }} frappe_queue-long",
              "docker service update --image ${{ env.DOCKER_IMAGE }}:${{ env.DOCKER_TAG }} frappe_scheduler",
              "echo Waiting for rolling update...",
              "sleep 60",
              "docker service ls"
            ]' \
            --output text \
            --query 'Command.CommandId')

          echo "Deploy Command ID: $COMMAND_ID"
```

**Key Difference:** `docker service update` performs rolling updates automatically - no downtime!

---

### Step 6: Verify Swarm Deployment

```bash
# Check service status
docker service ls

# Check service logs
docker service logs frappe_backend --tail 50

# Check replicas
docker service ps frappe_frontend

# Test API
curl https://hq.bebang.ph/api/method/frappe.ping
```

---

### Rollback Procedure (If Needed)

**Option A: Rollback individual service:**
```bash
docker service rollback frappe_backend
docker service rollback frappe_frontend
```

**Option B: Return to Docker Compose:**
```bash
# Remove Swarm stack
docker stack rm frappe

# Wait for cleanup
sleep 30

# Restart with Docker Compose
cd /home/ubuntu/frappe_docker
docker compose -f pwd.yml -f volumes-override.yml up -d
```

---

### Swarm vs Compose Command Reference

| Action | Docker Compose | Docker Swarm |
|--------|----------------|--------------|
| Start | `docker compose up -d` | `docker stack deploy -c stack.yml frappe` |
| Stop | `docker compose down` | `docker stack rm frappe` |
| Update image | `docker compose pull && down && up` | `docker service update --image` |
| View logs | `docker compose logs` | `docker service logs` |
| Scale | `docker compose up --scale` | `docker service scale` |
| Status | `docker compose ps` | `docker service ls` |

---

### Post-Migration Verification

- [x] All services running (`docker service ls`) - 9/9 services at 1/1 replicas
- [x] API responding (`curl .../frappe.ping`) - Returns `{"message":"pong"}`
- [x] CSS/JS loading correctly (browser test)
- [x] Google OAuth login works
- [x] No setup wizard redirect loop
- [x] WebSocket connection working
- [x] Background jobs processing (check queue)

**Reference:** `docs/reports/FRAPPE_DOCKER_DEPLOYMENT_RESEARCH_2026-01-28.md`

---

## Rollback Plan (Not Needed - Fix Successful)

### If containers won't start:
```bash
aws ssm send-command \
  --instance-ids "i-026b7477d27bd46d6" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /home/ubuntu/frappe_docker && docker compose -f pwd.yml -f volumes-override.yml logs --tail=100"]'
```

### If database issues (unlikely):
Database is in `bebang-hrms_db-data` volume - NOT affected by this fix.

### If need to restore previous image:
```bash
aws ssm send-command \
  --instance-ids "i-026b7477d27bd46d6" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /home/ubuntu/frappe_docker && docker compose -f pwd.yml -f volumes-override.yml pull samkarazi/bebang-erpnext-hrms:v15-PREVIOUS_TAG && docker compose -f pwd.yml -f volumes-override.yml up -d"]'
```

---

## Post-Fix Documentation

- [x] Update `data/04_Project_Management/Import_Log/progress/_CURRENT.md` with today's fix
- [ ] Send summary to Tech Team Google Chat space
- [x] Mark this plan as COMPLETED

---

## Permanence Assessment

### What is NOW Permanent:

| Fix | Permanent? | Notes |
|-----|------------|-------|
| CSS 404 prevention | ✅ YES | GitHub Actions workflow updated - every future deploy uses `down` + `up -d` |
| CSS health check | ✅ YES | Workflow fails if CSS returns 404 - catches regressions |
| Setup wizard fix | ✅ YES | Database value changed - persists across restarts |

### What Could Regress:

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Manual `docker compose up --no-deps` | Low | Documented in skills - always use `down` first |
| Database reset/restore | Low | Setup wizard fix would need re-application |
| Major Frappe upgrade | Medium | May require re-running setup wizard legitimately |

### Recommendations for Future:

1. **Docker Swarm Migration** (Stage 2 above) - Would eliminate CSS issues entirely with rolling updates and proper volume handling. Ready to execute when needed.
2. **Database backup includes DefaultValue** - Ensure backups capture the `desktop:home_page` setting
3. **Post-deploy validation script** - Consider adding to CI/CD for comprehensive health checks

---

## References

| Document | Purpose |
|----------|---------|
| `docs/reports/FRAPPE_DOCKER_DEPLOYMENT_RESEARCH_2026-01-28.md` | Full research findings |
| `.claude/skills/deploy-frappe/skill.md` | Updated deployment guide |
| `.claude/skills/local-frappe/skill.md` | Local vs production differences |
| [GitHub Issue #790](https://github.com/frappe/frappe_docker/issues/790) | Official bug report |
| [Frappe Docker FAQ](https://github.com/frappe/frappe_docker/wiki/Frequently-Asked-Questions) | Official guidance |
