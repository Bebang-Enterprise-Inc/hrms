from __future__ import annotations

import time

from sqlalchemy import select

from config import load_settings
from db import make_engine, make_session_factory, wait_for_db
from frappe import FrappeClient
from mapping import load_sn_mapping
from models import AdmsAttlogOutbox, OutboxStatus, Base


def _is_missing_employee_error(err: Exception) -> bool:
    s = str(err)
    return ("failed: 417" in s) or ("No Employee found for the given employee field value" in s)


def main() -> int:
    settings = load_settings()

    engine = make_engine(settings.database_url)
    SessionLocal = make_session_factory(engine)

    wait_for_db(engine, timeout_seconds=60)
    Base.metadata.create_all(bind=engine)

    mapping = load_sn_mapping(settings.sn_mapping_csv)
    frappe = FrappeClient(base_url=settings.frappe_base_url, auth_header=settings.frappe_token)

    while True:
        processed_any = False
        with SessionLocal() as db:
            q = (
                select(AdmsAttlogOutbox)
                .where(AdmsAttlogOutbox.status.in_([OutboxStatus.PENDING, OutboxStatus.FAILED]))
                .where(AdmsAttlogOutbox.attempts < settings.max_attempts)
                .order_by(AdmsAttlogOutbox.created_at.asc())
                .limit(50)
            )
            outbox_rows = list(db.execute(q).scalars())

            for out in outbox_rows:
                raw = out.raw
                if not raw:
                    out.status = OutboxStatus.FAILED
                    out.last_error = "Missing raw row"
                    out.attempts += 1
                    continue

                sn = raw.sn
                pin = raw.pin
                device_id = mapping.frappe_device_id(sn, device_id_format=settings.device_id_format)
                if not device_id:
                    out.status = OutboxStatus.FAILED
                    out.last_error = f"Unknown SN mapping: {sn}"
                    out.attempts += 1
                    continue

                ts = raw.event_time.strftime("%Y-%m-%d %H:%M:%S")

                try:
                    # Primary path: post using the real attendance_device_id.
                    frappe_doc = frappe.add_checkin_by_attendance_device_id(
                        attendance_device_id=pin,
                        timestamp=ts,
                        device_id=device_id,
                        log_type=None,
                        skip_auto_attendance=settings.skip_auto_attendance,
                    )
                    out.status = OutboxStatus.SENT
                    out.last_error = None
                    processed_any = True
                    continue

                except Exception as e:
                    # Unknown ID catcher: if employee lookup fails, route to the dedicated UNKNOWN employee.
                    if settings.unknown_employee_field_value and _is_missing_employee_error(e):
                        try:
                            fallback_doc = frappe.add_checkin_by_attendance_device_id(
                                attendance_device_id=settings.unknown_employee_field_value,
                                timestamp=ts,
                                device_id=device_id,
                                log_type=None,
                                skip_auto_attendance=settings.skip_auto_attendance,
                            )

                            comment_err = None
                            if settings.unknown_comment_enabled and fallback_doc.get("name"):
                                try:
                                    # Keep the original pin + SN in Frappe for audit/debug.
                                    raw_line = (raw.raw_line or "")
                                    if len(raw_line) > 300:
                                        raw_line = raw_line[:300] + "…"
                                    frappe.add_comment(
                                        reference_doctype="Employee Checkin",
                                        reference_name=fallback_doc["name"],
                                        content=(
                                            f"UNKNOWN_BIO_ID_CATCHER\n"
                                            f"original_attendance_device_id={pin}\n"
                                            f"sn={sn}\n"
                                            f"device_id={device_id}\n"
                                            f"event_time={ts}\n"
                                            f"raw_line={raw_line}"
                                        ),
                                    )
                                except Exception as ce:
                                    comment_err = str(ce)[:200]

                            out.status = OutboxStatus.SENT
                            note = f"ROUTED_TO_UNKNOWN employee_field_value={settings.unknown_employee_field_value} original_pin={pin}"
                            out.last_error = (note + (f"; comment_error={comment_err}" if comment_err else ""))
                            processed_any = True
                            continue
                        except Exception as e2:
                            out.status = OutboxStatus.FAILED
                            out.last_error = f"Unknown catcher failed: {str(e2)[:900]}"
                            out.attempts += 1
                            continue

                    out.status = OutboxStatus.FAILED
                    out.last_error = str(e)[:1000]
                    out.attempts += 1

            db.commit()

        # simple backoff
        time.sleep(1 if processed_any else 5)


if __name__ == "__main__":
    raise SystemExit(main())
