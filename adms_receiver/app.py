from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config import load_settings
from db import make_engine, make_session_factory, wait_for_db
from mapping import load_sn_mapping
from models import (
    AdmsAttlogOutbox,
    AdmsAttlogRaw,
    AdmsDeviceCmd,
    AdmsDeviceCmdCallback,
    Base,
    DeviceCmdStatus,
)
from parser import parse_attlog_line

settings = load_settings()
engine = make_engine(settings.database_url)
SessionLocal = make_session_factory(engine)

mapping = load_sn_mapping(settings.sn_mapping_csv)

app = FastAPI(title="ADMS Receiver")


@app.on_event("startup")
def _startup() -> None:
    # Postgres container may not be ready yet; wait briefly instead of crashing.
    wait_for_db(engine, timeout_seconds=60)
    Base.metadata.create_all(bind=engine)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "time": datetime.utcnow().isoformat()}


def _check_sn_allowed(sn: str) -> None:
    if not sn:
        raise HTTPException(status_code=400, detail="Missing SN")

    if settings.sn_allowlist and sn not in settings.sn_allowlist:
        raise HTTPException(status_code=403, detail="SN not allowed")

    # Always require SN to exist in mapping (simple allowlist)
    if sn not in mapping.sn_to_device_id:
        raise HTTPException(status_code=403, detail="Unknown SN")


def _require_admin(x_admin_token: str | None) -> None:
    # Admin endpoints are disabled unless ADMIN_TOKEN is set.
    if not settings.admin_token:
        raise HTTPException(status_code=403, detail="Admin endpoints disabled")

    if not x_admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")


class QueueCommandIn(BaseModel):
    command_text: str


@app.post("/admin/device/{sn}/commands")
def admin_queue_command(
    sn: str,
    payload: QueueCommandIn,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict:
    _require_admin(x_admin_token)

    sn = (sn or "").strip()
    _check_sn_allowed(sn)

    cmd_text = (payload.command_text or "").strip()
    if not cmd_text:
        raise HTTPException(status_code=400, detail="Missing command_text")

    with SessionLocal() as db:
        cmd = AdmsDeviceCmd(sn=sn, command_text=cmd_text)
        db.add(cmd)
        db.commit()
        db.refresh(cmd)
        return {"id": cmd.id, "sn": cmd.sn, "status": cmd.status}


@app.get("/admin/device/{sn}/commands")
def admin_list_commands(
    sn: str,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    limit: int = 50,
) -> dict:
    _require_admin(x_admin_token)

    sn = (sn or "").strip()
    _check_sn_allowed(sn)

    limit = max(1, min(int(limit or 50), 200))

    with SessionLocal() as db:
        q = select(AdmsDeviceCmd).where(AdmsDeviceCmd.sn == sn).order_by(AdmsDeviceCmd.created_at.desc()).limit(limit)
        rows = list(db.execute(q).scalars())

    return {
        "sn": sn,
        "rows": [
            {
                "id": r.id,
                "status": r.status,
                "attempts": r.attempts,
                "created_at": (r.created_at.isoformat() if r.created_at else None),
                "sent_at": (r.sent_at.isoformat() if r.sent_at else None),
                "acked_at": (r.acked_at.isoformat() if r.acked_at else None),
                "last_error": r.last_error,
                "command_text": r.command_text,
            }
            for r in rows
        ],
    }


@app.get("/iclock/cdata", response_class=PlainTextResponse)
def iclock_handshake(
    SN: str | None = None,
    options: str | None = None,
    language: str | None = None,
    pushver: str | None = None,
):
    sn = (SN or "").strip()
    _check_sn_allowed(sn)

    # Minimal response similar to documented protocol.
    now_stamp = int(datetime.utcnow().timestamp())
    body = "\n".join(
        [
            f"GET OPTION FROM: {sn}",
            "STAMP=9999",
            f"ATTLOGSTAMP={now_stamp}",
            f"OPERLOGStamp={now_stamp}",
            "ErrorDelay=30",
            "Delay=10",
            "TransInterval=1",
            "Realtime=1",
            "TimeZone=8",  # PH = UTC+8
            "Encrypt=None",
            "0",
        ]
    )
    return PlainTextResponse(content=body + "\n", status_code=200)


@app.post("/iclock/cdata", response_class=PlainTextResponse)
async def iclock_receive(
    request: Request,
    SN: str | None = None,
    table: str | None = None,
    Stamp: str | None = None,
    OpStamp: str | None = None,
):
    sn = (SN or "").strip()
    _check_sn_allowed(sn)

    t = (table or "").strip().upper()
    raw_body = (await request.body()) or b""

    # For MVP we only process ATTLOG.
    if t != "ATTLOG":
        return PlainTextResponse(content="OK: 0\n", status_code=200)

    try:
        text = raw_body.decode("utf-8", errors="replace")
    except Exception:
        text = str(raw_body)

    lines = [ln for ln in text.splitlines() if ln.strip()]

    inserted = 0
    with SessionLocal() as db:
        for ln in lines:
            row = parse_attlog_line(ln)
            if not row:
                continue

            try:
                # Use a SAVEPOINT per-row so one duplicate does not rollback the whole batch.
                with db.begin_nested():
                    raw = AdmsAttlogRaw(
                        sn=sn,
                        pin=row.pin,
                        event_time=row.event_time,
                        status_code=row.status_code,
                        verify_code=row.verify_code,
                        workcode=row.workcode,
                        raw_line=row.raw_line,
                    )
                    db.add(raw)
                    db.flush()  # assigns raw.id; may raise IntegrityError on duplicate

                    out = AdmsAttlogOutbox(raw_id=raw.id)
                    db.add(out)

                inserted += 1
            except IntegrityError:
                # Duplicate row (idempotency): ignore
                continue

        db.commit()

    return PlainTextResponse(content=f"OK: {inserted}\n", status_code=200)


@app.get("/iclock/getrequest", response_class=PlainTextResponse)
def iclock_getrequest(SN: str | None = None):
    sn = (SN or "").strip()
    _check_sn_allowed(sn)

    # Best-effort: deliver queued commands (format is stored verbatim).
    now = datetime.utcnow()
    cmds: list[AdmsDeviceCmd] = []

    with SessionLocal() as db:
        q = (
            select(AdmsDeviceCmd)
            .where(AdmsDeviceCmd.sn == sn)
            .where(AdmsDeviceCmd.status == DeviceCmdStatus.PENDING)
            .order_by(AdmsDeviceCmd.created_at.asc())
            .limit(10)
        )
        cmds = list(db.execute(q).scalars())

        if not cmds:
            return PlainTextResponse(content="OK\n", status_code=200)

        for c in cmds:
            # Prevent repeated re-sends until we implement full retry behavior.
            c.status = DeviceCmdStatus.SENT
            c.sent_at = now
            c.attempts += 1

        db.commit()

    # Evidence-backed command wire-format (admsjs):
    # Each line is: C:<ID>:<COMMAND>
    # Where <COMMAND> is typically: "DATA UPDATE USERINFO" + tab-separated key=value pairs.
    body = "\n".join(f"C:{c.id}:{c.command_text}" for c in cmds).rstrip() + "\n"
    return PlainTextResponse(content=body, status_code=200)


@app.post("/devicecmd", response_class=PlainTextResponse)
@app.post("/iclock/devicecmd", response_class=PlainTextResponse)
async def devicecmd(request: Request, SN: str | None = None):
    # Device callback for command execution results.
    # Evidence-backed callback format (admsjs):
    #   ID=<id>&Return=<code>&...
    # Possibly multiple lines.

    sn = (SN or "").strip() or None

    raw_body = (await request.body()) or b""
    try:
        text = raw_body.decode("utf-8", errors="replace")
    except Exception:
        text = str(raw_body)

    # avoid huge payload spam
    if len(text) > 8000:
        text = text[:8000] + "…"

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    with SessionLocal() as db:
        # Always store callback payloads (device may not include SN).
        db.add(AdmsDeviceCmdCallback(sn=sn, payload_text=text))

        # Best-effort: mark command ACKED/FAILED when callback includes ID=<id>.
        for line in lines:
            parts: dict[str, str] = {}
            for kv in line.split("&"):
                if "=" not in kv:
                    continue
                k, v = kv.split("=", 1)
                parts[k] = v

            cmd_id_raw = parts.get("ID")
            if not cmd_id_raw:
                continue

            try:
                cmd_id = int(cmd_id_raw)
            except Exception:
                continue

            cmd = db.get(AdmsDeviceCmd, cmd_id)
            if not cmd:
                continue

            ret = parts.get("Return")
            if ret in (None, "0"):
                cmd.status = DeviceCmdStatus.ACKED
                cmd.last_error = None
            else:
                cmd.status = DeviceCmdStatus.FAILED
                cmd.last_error = f"device_return={ret}"

            cmd.acked_at = datetime.utcnow()

        db.commit()

    # Mirror admsjs behavior: OK: <line_count>
    return PlainTextResponse(content=f"OK: {len(lines)}\n", status_code=200)
