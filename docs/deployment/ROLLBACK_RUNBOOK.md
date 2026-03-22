# Rollback Runbook

This document outlines the steps to perform a rollback in the event of a critical failure during or immediately following a deployment.

## Backend Rollback (Docker Swarm)
If the backend update introduces breaking changes or severe performance issues, revert the Docker services to their previous stable image.

```bash
# Rollback the main backend service
docker service rollback frappe_backend

# Rollback the schedulers and background workers
docker service rollback scheduler
docker service rollback queue-short
docker service rollback queue-long
```
Verify the rollback was successful:
```bash
docker service ls
# Check that the REPLICAS are up and running with the previous image version
```

## Frontend Rollback (Vercel)
If the frontend (Next.js/React app) deployment fails or contains critical bugs:

1. Log into the **Vercel Dashboard**.
2. Navigate to the specific project.
3. Go to the **Deployments** tab.
4. Find the previous stable production deployment.
5. Click the three dots (options menu) next to that deployment.
6. Select **Promote to Production** (or "Redeploy" if necessary).
7. Confirm the rollback.

Alternatively, via Vercel CLI:
```bash
vercel rollback
```

## Database Rollback (Frappe/MariaDB)
If a database migration corrupted data or a patch caused irreversible schema issues:

1. Ensure no background jobs are running that might write to the database during restore.
2. Locate the most recent automated backup (pre-deployment):
   ```bash
   ls -la sites/hq.bebang.ph/private/backups/
   ```
3. Run the bench restore command, targeting the appropriate backup file:
   ```bash
   bench --site hq.bebang.ph restore <backup-file.sql.gz>
   ```
4. If there are related files to restore:
   ```bash
   bench --site hq.bebang.ph restore <backup-file.sql.gz> --with-public-files <public-files.tar> --with-private-files <private-files.tar>
   ```
5. Run migrations to ensure the schema matches the codebase (if you also rolled back the backend code):
   ```bash
   bench --site hq.bebang.ph migrate
   ```

## Post-Rollback Verification
- Perform sanity checks on core endpoints.
- Check error logs (`frappe.log_error`).
- Verify E2E critical paths (e.g., login, submitting an order).