# BEI ERP Scaling Guide

**Last Updated:** 2026-03-28

---

## Instance Type Comparison

| Instance | vCPU | RAM | Cost/mo | Gunicorn Workers | Queue-Long Workers | Concurrent Users |
|----------|------|-----|---------|------------------|--------------------|-----------------|
| t3.large (current) | 2 | 8 GB | ~$60 | 2 (8 threads) | 1 | 5-10 |
| **t3.xlarge (recommended)** | **4** | **16 GB** | **~$121** | **4 (16 threads)** | **5** | **25-30** |
| t3.2xlarge | 8 | 32 GB | ~$242 | 8 (32 threads) | 10 | 50+ |

**Cost delta:** t3.large → t3.xlarge = +$61/month.

---

## How to Resize EC2

1. **Schedule maintenance window** (2-3 AM PHT, between cron cycles)
2. Verify no active RQ jobs: `docker exec $(docker ps -qf name=frappe_backend) bench --site hq.bebang.ph execute "frappe.get_all('RQ Job', filters={'status': 'started'})"`
3. Stop instance: AWS Console → EC2 → Stop Instance
4. Change type: Actions → Instance Settings → Change Instance Type → `t3.xlarge`
5. Start instance: Start Instance
6. Verify: SSH in, confirm `free -h` shows 16 GB
7. **Downtime: ~2 minutes.** EBS volume persists — zero data loss.

---

## How to Scale Workers

### Gunicorn (API concurrency)

Edit `.github/docker/Containerfile.fast`, change `--workers=2` to `--workers=4`:

```dockerfile
CMD gunicorn --bind=0.0.0.0:8000 --threads=4 --workers=4 --worker-class=gthread \
  --worker-tmp-dir=/dev/shm --timeout=120 --preload frappe.app:application
```

**RAM impact:** Each Gunicorn worker ≈ 150-200 MB. 4 workers ≈ 600-800 MB total.

Then rebuild and deploy:
```bash
# Triggers automatic rebuild via GitHub Actions
git push origin production
```

### Queue-Long (background job parallelism)

Scale via Docker Swarm:
```bash
docker service scale frappe_queue-long=5
```

**RAM impact:** Each queue-long worker ≈ 200-300 MB. 5 workers ≈ 1-1.5 GB total.

**Pre-check:** Verify no active jobs before scaling:
```bash
docker exec $(docker ps -qf name=frappe_backend) bench --site hq.bebang.ph \
  execute "frappe.get_all('RQ Job', filters={'status': 'started'})"
```

### Queue-Short

Current 1 worker is adequate. Scale if hourly jobs start queuing:
```bash
docker service scale frappe_queue-short=2
```

---

## How to Tune MariaDB

### innodb_buffer_pool_size

Current: 128 MB (default). Recommended: 2 GB on t3.xlarge.

Create custom config:
```bash
# On EC2 host
cat > /etc/mysql/conf.d/bei-tuning.cnf << 'EOF'
[mysqld]
innodb_buffer_pool_size = 2G
max_connections = 200
innodb_log_file_size = 256M
innodb_flush_log_at_trx_commit = 2
EOF
```

Mount in docker-compose:
```yaml
mariadb:
  volumes:
    - /etc/mysql/conf.d/bei-tuning.cnf:/etc/mysql/conf.d/bei-tuning.cnf:ro
```

Restart MariaDB:
```bash
docker service update --force mariadb
```

**Do this during the same maintenance window as EC2 resize.**

---

## RAM Budget (t3.xlarge — 16 GB)

| Service | RAM | Notes |
|---------|-----|-------|
| MariaDB (tuned) | 2.5 GB | innodb_buffer_pool=2G |
| Gunicorn (4 workers) | 800 MB | 4 × 200 MB |
| Queue-long (5 workers) | 1.5 GB | 5 × 300 MB |
| Queue-short (1 worker) | 300 MB | |
| Sheets-receiver | 500 MB | pandas + SQLite |
| Documenso + Postgres | 450 MB | E-signatures |
| Blip | 120 MB | AI assistant |
| ADMS | 135 MB | Biometric |
| Redis (×2) | 100 MB | Cache + queue |
| Scheduler + websocket + frontend | 200 MB | |
| **OS + buffers** | **~2 GB** | Linux kernel + filesystem cache |
| **Total** | **~8.6 GB** | **7.4 GB headroom** |

Safe headroom for 25-30 concurrent users + all syncs running.

---

## Safe Limits by Instance Type

| Instance | Max Gunicorn | Max Queue-Long | Max innodb_buffer_pool | Headroom |
|----------|-------------|----------------|----------------------|----------|
| t3.large (8 GB) | 2 | 1-2 | 512 MB | Tight |
| t3.xlarge (16 GB) | 4-6 | 5-8 | 2 GB | Comfortable |
| t3.2xlarge (32 GB) | 8-12 | 10-15 | 4-8 GB | Generous |

### Formula

```
Available RAM = Total RAM - OS overhead (2 GB)
Gunicorn workers = Available / 200 MB × 0.3  (30% for API)
Queue-long workers = Available / 300 MB × 0.2  (20% for background)
innodb_buffer_pool = Available × 0.3  (30% for DB)
Headroom = 20% minimum
```

---

## Monitoring Commands

```bash
# Current RAM usage by container
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}"

# Active RQ jobs
docker exec $(docker ps -qf name=frappe_backend) bench --site hq.bebang.ph \
  execute "frappe.get_all('RQ Job', filters={'status': 'started'}, fields=['job_name', 'queue'])"

# Gunicorn worker count
docker exec $(docker ps -qf name=frappe_backend) ps aux | grep gunicorn | wc -l

# MariaDB connections
docker exec $(docker ps -qf name=mariadb) mysql -u root -e "SHOW STATUS LIKE 'Threads_connected';"

# Queue-long replicas
docker service ls | grep queue-long
```

---

## Restart Bloated Workers

The queue-long worker can leak memory over time (observed: 1.4 GB for a single worker).

```bash
# Force restart without losing in-progress jobs
# (Docker Swarm will drain and restart)
docker service update --force frappe_queue-long
```

**Do NOT restart during active sync windows (7 AM PHT).**

---

## Adding Memory Limits (Future)

Currently no container has memory limits. To add:

```yaml
# In docker-compose.yml
frappe_queue-long:
  deploy:
    resources:
      limits:
        memory: 512M
      reservations:
        memory: 256M
```

This prevents a single service from OOM-killing others. Implement after t3.xlarge upgrade when there's enough headroom for limits to be meaningful.
