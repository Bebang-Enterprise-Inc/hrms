"""Lightweight verification script for GAP-046 alert emission behavior.

Runs without a live Frappe site.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "hrms" / "api" / "g046_alerting.py"
SPEC = importlib.util.spec_from_file_location("g046_alerting", MODULE_PATH)
g046_alerting = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g046_alerting)

build_failure_alert_payload = g046_alerting.build_failure_alert_payload
emit_failure_alert = g046_alerting.emit_failure_alert
maybe_raise_forced_failure = g046_alerting.maybe_raise_forced_failure
serialize_alert_payload = g046_alerting.serialize_alert_payload


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    payload = build_failure_alert_payload(
        stock_entry_name="STE-VERIFY-0001",
        stage="purchase_invoice_create",
        error=RuntimeError("forced test error"),
        store_info={
            "store_type": "Managed Franchise",
            "department": "Store Ops",
            "customer": "CUST-VERIFY",
            "warehouse_name": "TEST-STORE - BEI",
        },
        sales_invoice_name="ACC-SINV-VERIFY-0001",
        purchase_invoice_name="",
        forced_failure_stage="purchase_invoice_create",
        target_company="Bebang Enterprise Inc.",
    )

    serialized_once = serialize_alert_payload(payload)
    serialized_twice = serialize_alert_payload(payload)
    _assert(serialized_once == serialized_twice, "Payload serialization must be deterministic")
    _assert(payload["forced_failure"] is True, "forced_failure flag must be true in forced scenario")

    try:
        maybe_raise_forced_failure("purchase_invoice_create", "purchase_invoice_create")
        raise AssertionError("Forced failure stage did not raise RuntimeError")
    except RuntimeError as exc:
        _assert("GAP-046 forced failure" in str(exc), "Forced failure message mismatch")

    captured = {"log": None, "title": None, "chat": None}

    def _log_error(message, title):
        captured["log"] = message
        captured["title"] = title

    def _send_chat_message(message):
        captured["chat"] = message

    payload_json = emit_failure_alert(
        payload,
        log_error=_log_error,
        send_chat_message=_send_chat_message,
    )
    _assert(captured["title"] == "GAP-046 Failure Alert Payload", "Unexpected log title")
    _assert(captured["log"] == payload_json, "Logged payload should match serialized payload")
    _assert("GAP-046 Inter-company Invoice Failure" in (captured["chat"] or ""), "Chat title missing")
    _assert("Payload JSON:" in (captured["chat"] or ""), "Chat payload context missing")

    # Wiring check: commissary async flow must call forced-failure + payload builder.
    commissary_source = (REPO_ROOT / "hrms" / "api" / "commissary.py").read_text(encoding="utf-8")
    _assert(
        "force_failure_stage = get_force_failure_stage(store_info)" in commissary_source,
        "Commissary async flow missing force_failure_stage wiring",
    )
    _assert(
        "maybe_raise_forced_failure(force_failure_stage, current_stage)" in commissary_source,
        "Commissary async flow missing stage-based forced failure hook",
    )
    _assert(
        "payload = build_failure_alert_payload(" in commissary_source,
        "Commissary async flow missing deterministic payload builder",
    )
    _assert(
        "_emit_g046_failure_alert(payload)" in commissary_source,
        "Commissary async flow missing alert emission call",
    )

    print("GAP-046 alerting verification passed")
    print(payload_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
