import pytest
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "hrms" / "api" / "g046_alerting.py"
SPEC = importlib.util.spec_from_file_location("g046_alerting", MODULE_PATH)
g046_alerting = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g046_alerting)

build_failure_alert_payload = g046_alerting.build_failure_alert_payload
emit_failure_alert = g046_alerting.emit_failure_alert
get_force_failure_stage = g046_alerting.get_force_failure_stage
maybe_raise_forced_failure = g046_alerting.maybe_raise_forced_failure
serialize_alert_payload = g046_alerting.serialize_alert_payload


def test_build_failure_alert_payload_is_deterministic():
    payload = build_failure_alert_payload(
        stock_entry_name="STE-0001",
        stage="purchase_invoice_create",
        error=RuntimeError("boom"),
        store_info={
            "store_type": "JV",
            "department": "Test Dept",
            "customer": "CUST-001",
            "warehouse_name": "TEST-STORE - BEI",
        },
        sales_invoice_name="ACC-SINV-0001",
        purchase_invoice_name="ACC-PINV-0001",
        forced_failure_stage="purchase_invoice_create",
        target_company="Bebang Enterprise Inc.",
    )

    assert list(payload.keys()) == [
        "schema_version",
        "event",
        "gap_id",
        "flow_id",
        "severity",
        "trace_id",
        "stock_entry_name",
        "stage",
        "forced_failure",
        "forced_failure_stage",
        "documents",
        "store",
        "companies",
        "error",
        "actions",
    ]
    assert payload["trace_id"] == "G046::STE-0001"
    assert payload["forced_failure"] is True
    assert payload["documents"]["sales_invoice"] == "ACC-SINV-0001"
    assert payload["documents"]["purchase_invoice"] == "ACC-PINV-0001"
    assert payload["error"]["type"] == "RuntimeError"
    assert payload["store"]["warehouse_name"] == "TEST-STORE - BEI"


def test_serialize_alert_payload_is_stable():
    payload = build_failure_alert_payload(
        stock_entry_name="STE-0002",
        stage="preflight",
        error=ValueError("x"),
        target_company="Bebang Enterprise Inc.",
    )
    assert serialize_alert_payload(payload) == serialize_alert_payload(payload)


def test_get_force_failure_stage_resolves_supported_keys():
    assert get_force_failure_stage({"force_failure_stage": "preflight"}) == "preflight"
    assert get_force_failure_stage({"_force_failure_stage": "sales_invoice_create"}) == "sales_invoice_create"
    assert (
        get_force_failure_stage({"__force_failure_stage": "purchase_invoice_create"})
        == "purchase_invoice_create"
    )
    assert get_force_failure_stage({}) == ""


def test_maybe_raise_forced_failure_is_stage_sensitive():
    maybe_raise_forced_failure("purchase_invoice_create", "sales_invoice_create")
    with pytest.raises(RuntimeError, match="GAP-046 forced failure at stage=purchase_invoice_create"):
        maybe_raise_forced_failure("purchase_invoice_create", "purchase_invoice_create")


def test_emit_failure_alert_logs_and_sends_message():
    captured = {"log": None, "title": None, "chat": None}
    payload = build_failure_alert_payload(
        stock_entry_name="STE-0003",
        stage="purchase_invoice_create",
        error=RuntimeError("PI mapping missing"),
        target_company="Bebang Enterprise Inc.",
    )

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

    assert captured["title"] == "GAP-046 Failure Alert Payload"
    assert captured["log"] == payload_json
    assert "GAP-046 Inter-company Invoice Failure" in captured["chat"]
    assert "Trace: `G046::STE-0003`" in captured["chat"]
    assert f"Payload JSON: `{payload_json}`" in captured["chat"]
