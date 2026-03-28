# BEI ERP Server Inventory

**Last Updated:** 2026-03-28
**Instance:** AWS EC2 `i-026b7477d27bd46d6` (ap-southeast-1 / Singapore)
**Instance Type:** t3.large (8 GB RAM, 2 vCPU) — upgrade to t3.xlarge pending
**Public URLs:** `https://hq.bebang.ph` (Frappe ERP), `https://adms.bebang.ph` (ADMS)
**Orchestration:** Docker Swarm (single-node)
**Deployment:** GitHub Actions → AWS SSM → `docker service update`
**Image Registry:** GHCR (`ghcr.io/bebang-enterprise-inc/bebang-erpnext-hrms`)

---

## Docker Swarm Services (9)

| Service | Image | Role | Workers/Threads |
|---------|-------|------|-----------------|
| `frappe_backend` | GHCR hrms | Gunicorn WSGI (API + Desk) | 2 workers × 4 threads = 8 concurrent |
| `frappe_queue-short` | GHCR hrms | RQ worker — fast jobs | 1 worker |
| `frappe_queue-long` | GHCR hrms | RQ worker — slow jobs (sync, attendance) | 1 worker (target: 5) |
| `frappe_scheduler` | GHCR hrms | Frappe beat scheduler | 1 |
| `frappe_frontend` | GHCR hrms | Nginx reverse proxy + static assets | — |
| `frappe_websocket` | GHCR hrms | Socket.IO (real-time Desk notifications) | — |
| `frappe_redis-cache` | redis:alpine | Redis cache (flushed on deploy) | — |
| `frappe_redis-queue` | redis:alpine | Redis queue (flushed on deploy) | — |
| `mariadb` | mariadb:10.8 | Database (persistent volume `mariadb-data`) | — |

### Gunicorn Configuration

Source: `.github/docker/Containerfile.fast`

```
gunicorn --bind=0.0.0.0:8000 --threads=4 --workers=2 --worker-class=gthread \
  --worker-tmp-dir=/dev/shm --timeout=120 --preload frappe.app:application
```

### MariaDB Configuration

- **No custom my.cnf.** All defaults.
- `innodb_buffer_pool_size` = 128 MB (default — should be 1-2 GB for production)
- `max_connections` = 151 (default)
- Volume: `mariadb-data` (Docker named volume)

---

## Standalone Services (3)

### Sheets Receiver

- **Container:** `sheets-receiver`
- **Port:** `127.0.0.1:8765` / `172.17.0.1:8765`
- **Image:** Built from `hrms/services/sheets_receiver/Dockerfile` (python:3.11-slim)
- **Purpose:** Google Sheets → Frappe sync (procurement, inventory, AP, COA, banks) + POS XLSX processing
- **State:** SQLite DB at `/app/data/sheets_receiver.db`
- **Health:** `curl -f http://localhost:8765/health` every 30s

**Internal scheduled jobs:**

| Job | Interval | Purpose |
|-----|----------|---------|
| `scheduled_sync_job` | Every 6 hours | Backup sync of all Google Sheets (checksum-gated) |
| `run_daily_baseline_loop` | Checks every 30s | Force-sync 7 AP/procurement sheets once after 7 AM PHT |
| `process_pending_files_job` | Every 2 minutes | Process up to 50 queued POS XLSX files (10 workers) |
| `retry_failed_files_job` | Every 15 minutes | Retry failed POS files (max 3 attempts) |
| `scan_for_new_files_job` | Every 30 minutes | Scan 45 store Google Drive folders for new files |

### Blip AI Assistant

- **Container:** `blip-assistant`
- **Port:** `172.17.0.1:8766` (Docker bridge only)
- **Image:** Built from `hrms/services/blip/deploy/docker-compose.yml`
- **Purpose:** Google Chat AI assistant (Claude Haiku + Gemini Flash)
- **Proxy:** `frappe_frontend` nginx proxies `/webhook/gchat` → `http://172.17.0.1:8766/webhook/gchat`
- **Health:** `curl -f http://localhost:8766/health` every 30s

### ADMS Receiver

- **URL:** `https://adms.bebang.ph`
- **Purpose:** Biometric punch data from ZKTeco terminals
- **Deployment:** Separate compose, not in main repo

---

## RAM Budget (at idle, 9:30 AM PHT)

| Service | RAM | Notes |
|---------|-----|-------|
| frappe_queue-long | ~1.4 GB (bloated) | Restart reclaims ~1.3 GB |
| sheets-receiver | ~486 MB | pandas + SQLite |
| MariaDB | ~484 MB | innodb_buffer_pool=128MB default |
| frappe_backend | ~307 MB | 2 Gunicorn workers |
| Documenso + Postgres | ~422 MB | E-signatures |
| ADMS (DB + API + nginx) | ~133 MB | Biometric attendance |
| Blip (sentinel + assistant) | ~115 MB | AI chatbot |
| Others (redis ×2, scheduler, websocket, frontend) | ~200 MB | Supporting |
| **Total** | **~3.5 GB** (after queue restart) | |

**No memory limits set on any container.** All services compete freely for host RAM.

---

## Frappe Scheduled Jobs (37 total in hooks.py)

### 7:00 AM PHT (`0 23 * * *` UTC)
- `enqueue_scheduled_store_inventory_shadow_sync` — store inventory sync
- `enqueue_scheduled_store_demand_snapshot_sync` — demand snapshot
- `send_daily_digest` — biometric digest

### Every 10 min (`*/10 * * * *`)
- `watch_store_inventory_shadow_sync_health` — watchdog for stale sync

### 8:15 AM PHT (`15 0 * * *`)
- `scheduled_generate_morning_sync_health_report`

### Hourly (8 jobs)
- PCF auto-submit, SLA checks, transfer processing, auto-punch-out, shift sync

### Hourly Long (3 jobs)
- Auto-attendance, shift creation, checkin sync

### Daily (14 jobs)
- Birthday/anniversary reminders, overdue PO/invoice checks, low stock alerts, supplier expiry, overtime detection

### Daily Long (3 jobs)
- Leave allocation expiry, encashment, earned leave

### Other
- Monthly billing (1st of month), weather (5×/day), biometric status (4×/day), discount audit (3 jobs at midnight)

---

## External Sync Services (non-Frappe)

| Service | Trigger | Location |
|---------|---------|----------|
| Mosaic POS daily sync | GHA cron 12:30 AM PHT | `.github/workflows/mosaic-daily-sync.yml` |
| ADMS checkin sync | GHA cron every 5 min | `.github/workflows/adms-checkin-sync.yml` |
| Uptime checks | GHA cron (currently disabled) | `.github/workflows/uptime-check.yml` |

---

## Ports Map

| Port | Service | Exposed |
|------|---------|---------|
| 8000 | Gunicorn (frappe_backend) | Internal (via nginx) |
| 8765 | Sheets Receiver | 127.0.0.1 + Docker bridge |
| 8766 | Blip Assistant | Docker bridge only |
| 443 | Nginx (frappe_frontend) | Public (hq.bebang.ph) |
| 3306 | MariaDB | Internal |
| 6379 | Redis (×2) | Internal |
| 9000 | Socket.IO | Internal (via nginx) |

---

## Volumes

| Volume | Service | Purpose |
|--------|---------|---------|
| `mariadb-data` | mariadb | Database persistence |
| `sites` | frappe_backend + workers | Frappe sites directory |
| `logs` | frappe_backend | Application logs |
| `./credentials` | sheets-receiver | Google API credentials (read-only) |
| `./data` | sheets-receiver | SQLite DB + sync state |
