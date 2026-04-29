# S230 Manual Steps for Sam (require deploy-password execution)

**Status as of 2026-04-29 11:55 PHT:**
- ✅ Server allowlist `sn_mapping_all.csv` updated: `UDP3254701502,XENTROMALL_MONTALBAN` appended (file is now 51 rows)
- ✅ Local `hrms/utils/device_mapping.py` updated: 50 entries (added Estancia + Xentro Mall) — pending merge in PR
- ✅ ADMS `adms_device_cmd` queue: 48 PENDING USERINFO rows pushed (12 each on UDP3251200193, UDP3252900048, UDP3235200594, UDP3254701502)
- ✅ Estancia 4 crew already cross-enrolled on C2 (5 devices ACKED, UDP3252900249 PENDING since 2026-03-30 — fires when device heartbeats)

## Steps for Sam to execute (deploy-password gated):

### Step 1 — Restart `adms_receiver_adms-api_1` so the new device CAN heartbeat

Required because the server-side allowlist file is loaded at API startup. The new `UDP3254701502` row won't be honored until the API container restarts.

```bash
aws ssm send-command --instance-ids i-026b7477d27bd46d6 --document-name AWS-RunShellScript \
  --parameters 'commands=["sudo docker restart adms_receiver_adms-api_1"]' \
  --region ap-southeast-1 # 2289454
```

### Step 2 — Verify the API is back up (within 60 seconds)

```bash
aws ssm send-command --instance-ids i-026b7477d27bd46d6 --document-name AWS-RunShellScript \
  --parameters 'commands=["sleep 30; docker logs adms_receiver_adms-api_1 --tail 30 | grep -E \"200|listening\""]' \
  --region ap-southeast-1 # 2289454
```

You should see `200` log lines (devices heartbeating) and/or `listening` (API ready).

### Step 3 (POST-DEPLOY ONLY) — Restart Frappe backend so `device_mapping.py` change picks up

Run this AFTER the PR is merged to `production` AND deploy completes. The Frappe backend container caches the imported `device_mapping.py` module — restart forces re-import.

```bash
aws ssm send-command --instance-ids i-026b7477d27bd46d6 --document-name AWS-RunShellScript \
  --parameters 'commands=["FB=$(docker ps --filter name=frappe_backend --format {{.Names}} | head -1); echo Restarting $FB; sudo docker restart $FB"]' \
  --region ap-southeast-1 # 2289454
```

## What happens next:

1. After Step 1 restart, when the physical Xentro Mall device (UDP3254701502) is powered on at the store and points at `adms.bebang.ph:8443`:
   - Device heartbeats → API responds with the queued USERINFO commands
   - Device pulls the 12 commands → registers all 12 Xentro crew
   - Device responds with `Return=0` ACK callbacks
   - Crew can punch via fingerprint at the device

2. When physical Estancia device (UDP3252900249) is brought online (still offline since 2026-03-30):
   - Same flow — its 4 PRESERVED PENDING commands fire
   - Note: 54 OTHER PRESERVED PENDING commands also exist on that device (roving employees from earlier batch); they will all replay together

3. The 12 Xentro crew, while the new device is being deployed/configured, can continue to punch at the temp host devices (SM Marikina, Sta Lucia East, Brittany Office) since their previous USERINFO ACKs are still active there.

## L3-style verification (will run automatically; no Sam action needed):

After Step 1 restart, the heartbeat-watch in Phase 6 polls `adms_device_cmd_callback` for ACK arrivals. If the Xentro device is online, ACKs should appear within 60-180s.
