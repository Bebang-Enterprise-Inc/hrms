# ADMS Receiver Service (No ZKBioTime)

This service receives ZKTeco iClock/ADMS push logs (`/iclock/*`), stores them with idempotency, and forwards them into Frappe HRMS as `Employee Checkin` records via the whitelisted method:
- `hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field`

## Runtime model
- `app.py`: FastAPI HTTP receiver
- `worker.py`: background worker that pushes stored logs into Frappe
- Postgres: durable store + idempotency

## Environment variables
- `ADMS_DATABASE_URL` (required)
- `FRAPPE_BASE_URL` (required)
- `FRAPPE_TOKEN` (required) — value can be `key:secret` or `token key:secret`
- `SN_MAPPING_CSV` (required) — path to a CSV containing `device_serial_number` + canonical location fields
  - **Important**: The receiver will reject unknown SNs with **HTTP 403**. In practice, this makes `SN_MAPPING_CSV` the primary allowlist.
  - Pilot vs rollout:
    - Pilot: you may point to a small mapping file (1–2 SNs)
    - Rollout: point to the full mapping (example on AWS host: `/repo/adms_receiver/sn_mapping_all.csv`)
- `SN_ALLOWLIST` (optional) — comma-separated SNs allowed to post (extra safety gate)
- `SKIP_AUTO_ATTENDANCE` (default `1`) — passed to Frappe method
- `MAX_ATTEMPTS` (default `20`) — outbox retry attempts before giving up
-
- `DEVICE_ID_FORMAT` (default `canonical_location_id`) — how we set Frappe `Employee Checkin.device_id`
  - `canonical_location_id`
  - `canonical_location_name`
  - `canonical_location_id_and_name`
  - `full`
-
- `ADMIN_TOKEN` (optional) — if set, enables admin endpoints for queuing device commands
- `CMD_MAX_ATTEMPTS` (default `3`) — reserved for future resend behavior (currently we only send once)

## Local run (optional)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export ADMS_DATABASE_URL='postgresql+psycopg://adms:adms@localhost:5432/adms'
export FRAPPE_BASE_URL='https://lfg.bebang.ph'
export FRAPPE_TOKEN='token <key>:<secret>'
export SN_MAPPING_CSV='../data/04_Project_Management/Import_Log/IT_Device_SN_Mapping_CANONICAL_2026-01-07.csv'

uvicorn app:app --host 0.0.0.0 --port 8008
python worker.py
```

## Simulation
Use `simulate_device_push.py` to emulate a device handshake + ATTLOG POST.

## Logs / troubleshooting (AWS)
- In our deployed nginx container, `/var/log/nginx/access.log` is a symlink to `/dev/stdout` (a pipe).
- Use **docker logs** for connectivity evidence:

```bash
docker logs --since 48h adms_receiver-adms-nginx-1
```

## Device command queue (server → device)
Devices poll `GET /iclock/getrequest?SN=...` to fetch commands.

If `ADMIN_TOKEN` is set (recommended), you can queue commands via:
- `POST /admin/device/{sn}/commands`
  - Header: `X-Admin-Token: <ADMIN_TOKEN>`
  - Body: `{ "command_text": "..." }`

Notes:
- Command wire-format for MB10‑VL is still under evidence collection; the receiver returns `command_text` verbatim.
- `POST /devicecmd` callbacks are stored (best-effort) for debugging when `SN` is provided.
