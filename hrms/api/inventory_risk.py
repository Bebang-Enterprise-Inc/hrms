"""Inventory risk APIs for stockout visibility and command workflows (Sprint 20/21)."""

from __future__ import annotations

import datetime
from copy import deepcopy

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

try:
    from frappe.utils import add_to_date
except Exception:  # pragma: no cover - test-only fallback
    def add_to_date(dt, days=0, as_string=False):
        base = dt if isinstance(dt, datetime.datetime) else datetime.datetime(2026, 3, 2, 10, 0, 0)
        shifted = base + datetime.timedelta(days=float(days or 0))
        return shifted.strftime("%Y-%m-%d %H:%M:%S") if as_string else shifted

_TEST_RISK_ROWS: list[dict] = []
_TEST_INCIDENTS: list[dict] = []
_TEST_INCIDENT_EVENTS: dict[str, list[dict]] = {}
_TEST_EXPOSURE_MAP: dict[str, list[dict]] = {}
_TEST_PIPELINE_SOURCE_MAP: dict[str, list[dict]] = {}


def _make_item_warehouse_key(item_code: str | None, warehouse: str | None) -> str:
    return f"{(item_code or '').strip().lower()}::{(warehouse or '').strip().lower()}"


def set_test_risk_rows(rows: list[dict]) -> None:
    """Inject deterministic risk inputs for tests."""
    global _TEST_RISK_ROWS
    _TEST_RISK_ROWS = [deepcopy(row) for row in rows]


def set_test_incidents(rows: list[dict]) -> None:
    """Inject deterministic incident rows for tests."""
    global _TEST_INCIDENTS
    _TEST_INCIDENTS = [deepcopy(row) for row in rows]


def set_test_exposure_map(exposure_map: dict[str, list[dict]]) -> None:
    """Inject deterministic exposure payloads keyed by parent item or item+warehouse key."""
    global _TEST_EXPOSURE_MAP
    _TEST_EXPOSURE_MAP = {key: [deepcopy(row) for row in rows] for key, rows in exposure_map.items()}


def set_test_pipeline_source_map(source_map: dict[str, list[dict]]) -> None:
    """Inject deterministic source-linked pipeline rows keyed by item+warehouse key."""
    global _TEST_PIPELINE_SOURCE_MAP
    _TEST_PIPELINE_SOURCE_MAP = {key: [deepcopy(row) for row in rows] for key, rows in source_map.items()}


def _build_default_test_fixture() -> tuple[list[dict], list[dict], dict[str, list[dict]], dict[str, list[dict]]]:
    warehouses = [
        "test-warehouse-main",
        "test-warehouse-north",
        "test-warehouse-south",
        "test-warehouse-east",
        "test-warehouse-west",
    ]
    now_str = add_to_date(now_datetime(), days=0, as_string=True)
    risk_rows: list[dict] = []
    exposure_map: dict[str, list[dict]] = {}
    incidents: list[dict] = []
    incident_events: dict[str, list[dict]] = {}

    for idx in range(1, 51):
        item_code = f"test-item-{idx:03d}"
        warehouse = warehouses[(idx - 1) % len(warehouses)]
        daily_demand = round(7.0 + ((idx * 3) % 11), 2)
        profile = idx % 5

        if profile == 0:
            available_qty = round(daily_demand * 0.55, 2)
            inbound_po_qty = round(daily_demand * 0.65, 2)
            in_transit_qty = round(daily_demand * 0.20, 2)
            delayed_po_count = 2
            pending_po_count = 3
            lead_time_days = 8
            supplier_reliability = 55
        elif profile == 1:
            available_qty = round(daily_demand * 1.2, 2)
            inbound_po_qty = round(daily_demand * 0.8, 2)
            in_transit_qty = round(daily_demand * 0.45, 2)
            delayed_po_count = 1
            pending_po_count = 2
            lead_time_days = 6
            supplier_reliability = 66
        elif profile == 2:
            available_qty = round(daily_demand * 2.2, 2)
            inbound_po_qty = round(daily_demand * 0.7, 2)
            in_transit_qty = round(daily_demand * 0.6, 2)
            delayed_po_count = 0
            pending_po_count = 1
            lead_time_days = 4
            supplier_reliability = 75
        elif profile == 3:
            available_qty = round(daily_demand * 4.8, 2)
            inbound_po_qty = round(daily_demand * 0.5, 2)
            in_transit_qty = round(daily_demand * 0.5, 2)
            delayed_po_count = 0
            pending_po_count = 1
            lead_time_days = 3
            supplier_reliability = 88
        else:
            available_qty = round(daily_demand * 3.0, 2)
            inbound_po_qty = round(daily_demand * 0.75, 2)
            in_transit_qty = round(daily_demand * 0.4, 2)
            delayed_po_count = 1
            pending_po_count = 2
            lead_time_days = 5
            supplier_reliability = 72

        unit_cost = round(25.0 + ((idx * 13) % 17), 2)
        selling_price = round(unit_cost * (1.35 + ((idx % 3) * 0.05)), 2)

        risk_rows.append(
            {
                "item_code": item_code,
                "warehouse": warehouse,
                "available_qty": available_qty,
                "avg_daily_demand": daily_demand,
                "lead_time_days": lead_time_days,
                "supplier_reliability_score": supplier_reliability,
                "supplier_on_time_rate": supplier_reliability,
                "pending_po_count": pending_po_count,
                "inbound_po_qty": inbound_po_qty,
                "delayed_po_count": delayed_po_count,
                "in_transit_qty": in_transit_qty,
                "next_eta": add_to_date(now_datetime(), days=(idx % 6) + 1, as_string=True),
                "unit_cost": unit_cost,
                "selling_price": selling_price,
            }
        )

        req_1 = round(daily_demand * (1.4 + ((idx + 1) % 2) * 0.3), 2)
        req_2 = round(daily_demand * (1.1 + ((idx + 2) % 3) * 0.2), 2)
        if profile == 0:
            avail_1 = round(req_1 * 0.25, 2)
            avail_2 = round(req_2 * 0.10, 2)
        elif profile == 1:
            avail_1 = round(req_1 * 0.65, 2)
            avail_2 = round(req_2 * 0.55, 2)
        elif profile == 2:
            avail_1 = round(req_1 * 0.95, 2)
            avail_2 = round(req_2 * 0.85, 2)
        else:
            avail_1 = round(req_1 * 1.2, 2)
            avail_2 = round(req_2 * 1.1, 2)

        short_1 = round(max(0.0, req_1 - avail_1), 2)
        short_2 = round(max(0.0, req_2 - avail_2), 2)
        status_1 = "Critical" if short_1 > (req_1 * 0.6) else "Watch" if short_1 > 0 else "Normal"
        status_2 = "Critical" if short_2 > (req_2 * 0.6) else "Watch" if short_2 > 0 else "Normal"

        exposure_map[item_code] = [
            {
                "parent_item_code": item_code,
                "ingredient_item_code": f"test-ingredient-{idx:03d}-01",
                "required_qty": req_1,
                "available_qty": avail_1,
                "shortage_qty": short_1,
                "days_cover": round((avail_1 / req_1), 2) if req_1 > 0 else 999,
                "exposure_status": status_1,
            },
            {
                "parent_item_code": item_code,
                "ingredient_item_code": f"test-ingredient-{idx:03d}-02",
                "required_qty": req_2,
                "available_qty": avail_2,
                "shortage_qty": short_2,
                "days_cover": round((avail_2 / req_2), 2) if req_2 > 0 else 999,
                "exposure_status": status_2,
            },
        ]
        exposure_map[_make_item_warehouse_key(item_code, warehouse)] = deepcopy(exposure_map[item_code])

    incident_statuses = ["Open", "Mitigating", "Blocked", "Resolved"]
    for idx in range(1, 21):
        row = risk_rows[(idx - 1) % len(risk_rows)]
        incident_name = f"test-inc-{idx:04d}"
        status = incident_statuses[(idx - 1) % len(incident_statuses)]
        incident = {
            "name": incident_name,
            "incident_title": f"test-incident on {row['item_code']}",
            "item_code": row["item_code"],
            "warehouse": row["warehouse"],
            "status": status,
            "owner_user": f"test.owner{((idx - 1) % 5) + 1}@bebang.ph",
            "detected_on": now_str,
            "target_resolution_at": add_to_date(now_datetime(), days=(idx % 4) + 1, as_string=True),
            "root_cause": "test-supplier-delay",
            "escalation_level": f"Level {((idx - 1) % 3) + 1}",
            "mitigation_plan": f"test-mitigation-plan-{idx:02d}",
            "resolution_notes": "test-resolved" if status == "Resolved" else "",
        }
        incidents.append(incident)
        incident_events[incident_name] = [
            {
                "incident": incident_name,
                "event_type": "Detected",
                "details": "test incident seeded",
                "event_at": now_str,
                "event_by": "test.system@bebang.ph",
            }
        ]
        if status == "Mitigating":
            incident_events[incident_name].append(
                {
                    "incident": incident_name,
                    "event_type": "Assigned",
                    "details": "test owner assigned",
                    "event_at": now_str,
                    "event_by": "test.system@bebang.ph",
                }
            )
        elif status == "Blocked":
            incident_events[incident_name].append(
                {
                    "incident": incident_name,
                    "event_type": "Blocked",
                    "details": "test supplier on hold",
                    "event_at": now_str,
                    "event_by": "test.system@bebang.ph",
                }
            )
        elif status == "Resolved":
            incident_events[incident_name].append(
                {
                    "incident": incident_name,
                    "event_type": "Resolved",
                    "details": "test fallback allocation completed",
                    "event_at": now_str,
                    "event_by": "test.system@bebang.ph",
                }
            )

    return risk_rows, incidents, incident_events, exposure_map


def _ensure_default_test_fixture() -> None:
    global _TEST_RISK_ROWS, _TEST_INCIDENTS, _TEST_INCIDENT_EVENTS, _TEST_EXPOSURE_MAP
    if _TEST_RISK_ROWS or _TEST_INCIDENTS or _TEST_INCIDENT_EVENTS or _TEST_EXPOSURE_MAP:
        return
    risk_rows, incidents, incident_events, exposure_map = _build_default_test_fixture()
    _TEST_RISK_ROWS = risk_rows
    _TEST_INCIDENTS = incidents
    _TEST_INCIDENT_EVENTS = incident_events
    _TEST_EXPOSURE_MAP = exposure_map


def _risk_level_from_score(risk_score: float) -> str:
    if risk_score >= 80:
        return "Critical"
    if risk_score >= 60:
        return "High"
    if risk_score >= 35:
        return "Moderate"
    return "Low"


def _safe_supplier_score(reliability_score: float) -> float:
    bounded = min(100.0, max(0.0, flt(reliability_score)))
    # Higher reliability lowers risk contribution.
    return round((100.0 - bounded) * 0.1, 2)


def _payable_urgency(projected_shortage_qty: float, delayed_po_count: int) -> str:
    if projected_shortage_qty > 0 and delayed_po_count > 0:
        return "High"
    if projected_shortage_qty > 0:
        return "Medium"
    return "Low"


def build_risk_snapshot_row(source: dict, horizon_hours: int = 72) -> dict:
    available_qty = max(0.0, flt(source.get("available_qty")))
    avg_daily_demand = max(0.0, flt(source.get("avg_daily_demand")))
    lead_time_days = max(0.0, flt(source.get("lead_time_days")))
    supplier_reliability = flt(source.get("supplier_reliability_score") or 70)
    supplier_on_time_rate = flt(source.get("supplier_on_time_rate") or supplier_reliability)

    pending_po_count = max(0, cint(source.get("pending_po_count") or source.get("open_po_count") or 0))
    inbound_po_qty = max(0.0, flt(source.get("inbound_po_qty") or source.get("open_po_qty") or source.get("inbound_qty") or 0))
    delayed_po_count = max(0, cint(source.get("delayed_po_count") or 0))
    in_transit_qty = max(
        0.0,
        flt(source.get("in_transit_qty") or source.get("transfer_in_transit_qty") or 0),
    )
    inbound_qty = round(inbound_po_qty + in_transit_qty, 2)

    horizon_hours = max(1, cint(horizon_hours or 72))
    horizon_days = round(horizon_hours / 24.0, 2)

    days_to_stockout = 999.0
    projected_stockout_at = None
    if avg_daily_demand > 0:
        days_to_stockout = round(available_qty / avg_daily_demand, 2)
        projected_stockout_at = add_to_date(
            now_datetime(),
            days=days_to_stockout,
            as_string=True,
        )

    demand_horizon_qty = round(avg_daily_demand * horizon_days, 2)
    projected_shortage_qty = round(max(0.0, demand_horizon_qty - (available_qty + inbound_qty)), 2)

    unit_cost = max(0.0, flt(source.get("latest_cost") or source.get("unit_cost") or 0))
    selling_price = max(0.0, flt(source.get("selling_price") or 0))
    derived_margin_rate = ((selling_price - unit_cost) / selling_price) if selling_price > 0 else 0.35
    margin_rate = max(0.0, flt(source.get("margin_rate") or derived_margin_rate))

    forecast_lost_sales = round(projected_shortage_qty * selling_price, 2)
    value_at_risk = round(projected_shortage_qty * unit_cost, 2)
    margin_at_risk = round(forecast_lost_sales * margin_rate, 2)

    # Deterministic weighted model: stock cover dominates, then lead time, pipeline, supplier reliability.
    cover_score = 0.0 if days_to_stockout >= 14 else (14.0 - days_to_stockout) * 5.0
    lead_score = min(20.0, lead_time_days * 2.0)
    supplier_score = _safe_supplier_score(supplier_reliability)
    pipeline_score = min(20.0, delayed_po_count * 4.0)
    risk_score = round(min(100.0, max(0.0, cover_score + lead_score + supplier_score + pipeline_score)), 2)

    return {
        "item_code": source.get("item_code"),
        "warehouse": source.get("warehouse"),
        "available_qty": available_qty,
        "avg_daily_demand": avg_daily_demand,
        "daily_consumption": avg_daily_demand,
        "lead_time_days": lead_time_days,
        "supplier_reliability_score": supplier_reliability,
        "supplier_on_time_rate": supplier_on_time_rate,
        "horizon_hours": horizon_hours,
        "horizon_days": horizon_days,
        "days_to_stockout": days_to_stockout,
        "projected_stockout_at": projected_stockout_at,
        "risk_score": risk_score,
        "risk_level": _risk_level_from_score(risk_score),
        "pending_po_count": pending_po_count,
        "inbound_po_qty": inbound_po_qty,
        "delayed_po_count": delayed_po_count,
        "in_transit_qty": in_transit_qty,
        "inbound_qty": inbound_qty,
        "next_eta": source.get("next_eta"),
        "unit_cost": unit_cost,
        "selling_price": selling_price,
        "margin_rate": margin_rate,
        "demand_horizon_qty": demand_horizon_qty,
        "projected_shortage_qty": projected_shortage_qty,
        "forecast_lost_sales": forecast_lost_sales,
        "value_at_risk": value_at_risk,
        "margin_at_risk": margin_at_risk,
        "payable_urgency": _payable_urgency(projected_shortage_qty, delayed_po_count),
        "urgent_payment_required": projected_shortage_qty > 0 and delayed_po_count > 0,
    }


def _load_risk_inputs() -> list[dict]:
    _ensure_default_test_fixture()
    if _TEST_RISK_ROWS:
        return [deepcopy(row) for row in _TEST_RISK_ROWS]
    return []


def _load_open_incidents() -> list[dict]:
    _ensure_default_test_fixture()
    if not _TEST_INCIDENTS:
        return []
    rows = [deepcopy(row) for row in _TEST_INCIDENTS]
    return [row for row in rows if row.get("status") != "Resolved"]


def _resolve_exposure_rows(item_code: str, warehouse: str | None = None) -> list[dict]:
    _ensure_default_test_fixture()
    keys = [item_code]
    if warehouse:
        keys.insert(0, _make_item_warehouse_key(item_code, warehouse))
    for key in keys:
        rows = _TEST_EXPOSURE_MAP.get(key)
        if rows is not None:
            return [deepcopy(row) for row in rows]
    return []


@frappe.whitelist()
def recompute_risk_snapshots(horizon_hours: int = 72):
    rows = [build_risk_snapshot_row(row, horizon_hours=horizon_hours) for row in _load_risk_inputs()]
    return {
        "success": True,
        "horizon_hours": cint(horizon_hours or 72),
        "recomputed": len(rows),
        "rows": rows,
    }


@frappe.whitelist()
def get_risk_items(limit: int = 50, horizon_hours: int = 72):
    computed = recompute_risk_snapshots(horizon_hours=horizon_hours)
    rows = sorted(computed["rows"], key=lambda row: row.get("risk_score", 0), reverse=True)
    return {
        "items": rows[: max(1, cint(limit or 50))],
        "limit": max(1, cint(limit or 50)),
        "horizon_hours": cint(horizon_hours or 72),
    }


@frappe.whitelist()
def get_risk_dashboard(horizon_hours: int = 72):
    items_payload = get_risk_items(limit=200, horizon_hours=horizon_hours)
    items = items_payload["items"]

    stockouts_next_horizon = [
        row for row in items if flt(row.get("days_to_stockout")) <= round(cint(horizon_hours or 72) / 24.0, 2)
    ]
    high_risk = [row for row in items if row.get("risk_level") in ("High", "Critical")]
    incidents = _load_open_incidents()

    return {
        "horizon_hours": cint(horizon_hours or 72),
        "summary": {
            "total_items": len(items),
            "high_risk_items": len(high_risk),
            "stockouts_next_72h": len(stockouts_next_horizon),
            "open_incidents": len(incidents),
            "total_available_qty": round(sum(flt(row.get("available_qty")) for row in items), 2),
            "total_daily_consumption": round(sum(flt(row.get("avg_daily_demand")) for row in items), 2),
            "total_inbound_qty": round(sum(flt(row.get("inbound_qty")) for row in items), 2),
            "total_delayed_pos": sum(cint(row.get("delayed_po_count")) for row in items),
            "value_at_risk_total": round(sum(flt(row.get("value_at_risk")) for row in items), 2),
            "margin_at_risk_total": round(sum(flt(row.get("margin_at_risk")) for row in items), 2),
        },
        "top_risks": items[:10],
    }


def build_ingredient_exposure(
    parent_item_code: str,
    demand_qty: float,
    bom_rows: list[dict],
    stock_map: dict[str, float],
) -> list[dict]:
    exposure_rows: list[dict] = []
    for row in bom_rows:
        ingredient = row.get("ingredient_item_code") or row.get("item_code")
        qty_per_unit = max(0.0, flt(row.get("qty_per_unit") or row.get("qty")))
        required_qty = round(max(0.0, flt(demand_qty)) * qty_per_unit, 2)
        available_qty = max(0.0, flt(stock_map.get(ingredient, 0)))
        shortage_qty = round(max(0.0, required_qty - available_qty), 2)
        daily_requirement = max(0.0, flt(demand_qty) * qty_per_unit)
        days_cover = 999.0 if daily_requirement <= 0 else round(available_qty / daily_requirement, 2)

        if shortage_qty > 0 and available_qty <= 0:
            exposure_status = "Critical"
        elif shortage_qty > 0:
            exposure_status = "Watch"
        else:
            exposure_status = "Normal"

        exposure_rows.append(
            {
                "parent_item_code": parent_item_code,
                "ingredient_item_code": ingredient,
                "required_qty": required_qty,
                "available_qty": available_qty,
                "shortage_qty": shortage_qty,
                "days_cover": days_cover,
                "exposure_status": exposure_status,
            }
        )
    return exposure_rows


@frappe.whitelist()
def get_item_exposure(item_code: str, warehouse: str | None = None):
    if not item_code:
        frappe.throw(_("item_code is required"))

    exposure_rows = _resolve_exposure_rows(item_code=item_code, warehouse=warehouse)
    return {
        "item_code": item_code,
        "warehouse": warehouse,
        "exposure": exposure_rows,
    }


def _find_risk_row(item_code: str, warehouse: str, horizon_hours: int = 72) -> dict:
    computed = recompute_risk_snapshots(horizon_hours=horizon_hours)
    for row in computed.get("rows", []):
        if row.get("item_code") == item_code and row.get("warehouse") == warehouse:
            return row
    frappe.throw(_("Risk snapshot not found for selected item and warehouse"))


def _finance_payload_from_row(row: dict) -> dict:
    return {
        "item_code": row.get("item_code"),
        "warehouse": row.get("warehouse"),
        "shortage_qty": flt(row.get("projected_shortage_qty")),
        "value_at_risk": flt(row.get("value_at_risk")),
        "margin_at_risk": flt(row.get("margin_at_risk")),
        "forecast_lost_sales": flt(row.get("forecast_lost_sales")),
        "urgent_payment_required": bool(row.get("urgent_payment_required")),
        "payable_urgency": row.get("payable_urgency") or "Low",
    }


def _safe_db_sql(query: str, values: dict | None = None) -> list[dict]:
    db = getattr(frappe, "db", None)
    if not db or not hasattr(db, "sql"):
        return []
    try:
        return db.sql(query, values or {}, as_dict=True) or []
    except Exception:
        return []


def _route_for_source(doctype: str, source_name: str) -> str:
    route_map = {
        "Purchase Order": "/app/purchase-order",
        "BEI Purchase Order": "/app/bei-purchase-order",
    }
    base = route_map.get(doctype, "/app/purchase-order")
    return f"{base}/{source_name}"


def _load_pipeline_source_rows(item_code: str, warehouse: str) -> list[dict]:
    item_warehouse_key = _make_item_warehouse_key(item_code, warehouse)
    test_rows = _TEST_PIPELINE_SOURCE_MAP.get(item_warehouse_key) or _TEST_PIPELINE_SOURCE_MAP.get(item_code)
    if test_rows is not None:
        return [deepcopy(row) for row in test_rows]

    return _safe_db_sql(
        """
        SELECT
            poi.parent AS source_name,
            COALESCE(po.po_no, poi.parent) AS po_number,
            COALESCE(po.supplier_name, po.supplier, '') AS supplier,
            poi.item_code,
            poi.warehouse,
            COALESCE(poi.qty, 0) AS ordered_qty,
            COALESCE(poi.received_qty, 0) AS received_qty,
            po.delivery_date AS expected_eta,
            COALESCE(po.status, 'Pending') AS status
        FROM `tabBEI PO Item` poi
        INNER JOIN `tabBEI Purchase Order` po ON po.name = poi.parent
        WHERE poi.item_code = %(item_code)s
          AND poi.warehouse = %(warehouse)s
          AND po.status NOT IN ('Cancelled', 'Closed')
        ORDER BY po.po_date DESC
        LIMIT 50
        """,
        {"item_code": item_code, "warehouse": warehouse},
    )


def _build_pipeline_details_from_source_rows(item_code: str, warehouse: str, source_rows: list[dict]) -> dict:
    pending_pos: list[dict] = []
    delayed_deliveries: list[dict] = []

    for idx, source in enumerate(source_rows, start=1):
        source_doctype = source.get("source_doctype") or "Purchase Order"
        raw_source_name = source.get("source_name") or source.get("name") or source.get("po_number")
        source_name = raw_source_name
        if not source_name:
            source_name = f"PO-{item_code}-{idx:02d}"
        po_number = source.get("po_number") or source_name

        ordered_qty = max(0.0, flt(source.get("ordered_qty") or source.get("qty") or 0))
        received_qty = max(0.0, flt(source.get("received_qty") or 0))
        remaining_qty = round(max(0.0, ordered_qty - received_qty), 2)
        if remaining_qty <= 0:
            continue

        source_status = str(source.get("status") or "Pending")
        delayed_days = max(0, cint(source.get("delayed_days") or 0))
        is_delayed = source_status.lower() == "delayed" or delayed_days > 0
        if is_delayed and delayed_days == 0:
            delayed_days = 1

        raw_expected_eta = source.get("expected_eta") or source.get("delivery_date")
        expected_eta = raw_expected_eta
        if not expected_eta:
            expected_eta = add_to_date(now_datetime(), days=(idx % 5) + 1, as_string=True)

        raw_link_route = source.get("link_route")
        link_route = raw_link_route or _route_for_source(source_doctype, source_name)
        raw_supplier = source.get("supplier")
        supplier = raw_supplier or f"test-supplier-{((idx - 1) % 7) + 1:02d}"
        status = "Delayed" if is_delayed else "Pending"
        is_pending_fallback = bool(not raw_source_name or not raw_expected_eta or not raw_link_route or not raw_supplier)

        pending_row = {
            "po_number": po_number,
            "supplier": supplier,
            "item_code": item_code,
            "warehouse": warehouse,
            "ordered_qty": remaining_qty,
            "expected_eta": expected_eta,
            "status": status,
            "is_synthetic_fallback": is_pending_fallback,
            "source_doctype": source_doctype,
            "source_name": source_name,
            "link_route": link_route,
        }
        pending_pos.append(pending_row)

        if is_delayed:
            raw_delivery_id = source.get("delivery_id")
            raw_delay_reason = source.get("delay_reason")
            delayed_deliveries.append(
                {
                    "delivery_id": raw_delivery_id or f"dtl-{source_name}-{idx:02d}",
                    "po_number": po_number,
                    "supplier": supplier,
                    "item_code": item_code,
                    "warehouse": warehouse,
                    "delayed_qty": remaining_qty,
                    "expected_eta": expected_eta,
                    "delayed_days": delayed_days,
                    "delay_reason": raw_delay_reason or "Supplier delivery delay",
                    "status": "Delayed",
                    "is_synthetic_fallback": bool(is_pending_fallback or not raw_delivery_id or not raw_delay_reason),
                    "source_doctype": source_doctype,
                    "source_name": source_name,
                    "link_route": link_route,
                }
            )

    return {"pending_pos": pending_pos, "delayed_deliveries": delayed_deliveries}


def _build_pipeline_details_from_row(row: dict) -> dict:
    item_code = row.get("item_code")
    warehouse = row.get("warehouse")
    source_rows = _load_pipeline_source_rows(item_code=item_code, warehouse=warehouse)
    if source_rows:
        return _build_pipeline_details_from_source_rows(item_code=item_code, warehouse=warehouse, source_rows=source_rows)

    pending_count = max(0, cint(row.get("pending_po_count")))
    delayed_count = min(max(0, cint(row.get("delayed_po_count"))), pending_count)
    inbound_po_qty = max(0.0, flt(row.get("inbound_po_qty")))

    pending_pos: list[dict] = []
    delayed_deliveries: list[dict] = []

    if pending_count <= 0:
        return {
            "pending_pos": pending_pos,
            "delayed_deliveries": delayed_deliveries,
        }

    qty_base = round(inbound_po_qty / pending_count, 2) if pending_count else 0.0
    assigned_qty = 0.0
    for idx in range(1, pending_count + 1):
        is_last = idx == pending_count
        po_qty = round(max(0.0, inbound_po_qty - assigned_qty), 2) if is_last else qty_base
        assigned_qty = round(assigned_qty + po_qty, 2)

        eta_days = (idx % 5) + 1
        expected_eta = add_to_date(now_datetime(), days=eta_days, as_string=True)
        supplier = f"test-supplier-{((idx - 1) % 7) + 1:02d}"
        source_name = f"test-po-{item_code}-{idx:02d}"
        po_number = source_name
        source_doctype = "Purchase Order"
        status = "Delayed" if idx <= delayed_count else "Pending"
        link_route = _route_for_source(source_doctype, source_name)

        pending_row = {
            "po_number": po_number,
            "supplier": supplier,
            "item_code": item_code,
            "warehouse": warehouse,
            "ordered_qty": po_qty,
            "expected_eta": expected_eta,
            "status": status,
            "is_synthetic_fallback": True,
            "source_doctype": source_doctype,
            "source_name": source_name,
            "link_route": link_route,
        }
        pending_pos.append(pending_row)

        if status == "Delayed":
            delayed_days = delayed_count - idx + 1
            delayed_deliveries.append(
                {
                    "delivery_id": f"test-dtl-{item_code}-{idx:02d}",
                    "po_number": po_number,
                    "supplier": supplier,
                    "item_code": item_code,
                    "warehouse": warehouse,
                    "delayed_qty": po_qty,
                    "expected_eta": expected_eta,
                    "delayed_days": delayed_days,
                    "delay_reason": "test logistics carrier delay",
                    "status": "Delayed",
                    "is_synthetic_fallback": True,
                    "source_doctype": source_doctype,
                    "source_name": source_name,
                    "link_route": link_route,
                }
            )

    return {
        "pending_pos": pending_pos,
        "delayed_deliveries": delayed_deliveries,
    }


def _recommended_actions_from_row(row: dict) -> list[dict]:
    actions: list[dict] = []
    if flt(row.get("days_to_stockout")) <= 2:
        actions.append(
            {
                "action": "Expedite inbound purchase order",
                "owner_team": "Procurement",
                "priority": "Critical",
            }
        )
    if cint(row.get("delayed_po_count")) > 0:
        actions.append(
            {
                "action": "Escalate delayed supplier delivery",
                "owner_team": "SCM",
                "priority": "High",
            }
        )
    if flt(row.get("projected_shortage_qty")) > 0:
        actions.append(
            {
                "action": "Activate mitigation allocation for at-risk ingredients",
                "owner_team": "Warehouse",
                "priority": "High",
            }
        )
    if bool(row.get("urgent_payment_required")):
        actions.append(
            {
                "action": "Prioritize supplier payment release",
                "owner_team": "Finance",
                "priority": "Critical",
            }
        )
    return actions


_DEPARTMENT_ACTION_CATALOG: dict[str, list[dict]] = {
    "Procurement": [
        {
            "action_id": "open_pending_pos",
            "label": "Open Pending POs",
            "mode": "navigate",
            "target_route": "/dashboard/procurement/purchase-orders",
        },
        {
            "action_id": "open_supplier_profile",
            "label": "Open Supplier Profile",
            "mode": "navigate",
            "target_route": "/dashboard/procurement/suppliers",
        },
        {
            "action_id": "open_goods_receipt_log",
            "label": "Open Goods Receipt Log",
            "mode": "navigate",
            "target_route": "/dashboard/procurement/goods-receipt-log",
        },
        {
            "action_id": "create_expedite_followup",
            "label": "Create Expedite Follow-Up",
            "mode": "execute",
            "target_route": "/dashboard/procurement/or-follow-up",
            "command": "create_expedite_followup",
        },
    ],
    "Finance": [
        {
            "action_id": "open_pending_payments",
            "label": "Open Pending Payments",
            "mode": "navigate",
            "target_route": "/dashboard/accounting/pending-payments",
        },
        {
            "action_id": "open_supplier_ledger",
            "label": "Open Supplier Ledger",
            "mode": "navigate",
            "target_route": "/dashboard/procurement/suppliers",
        },
        {
            "action_id": "open_or_followup",
            "label": "Open OR Follow-Up",
            "mode": "navigate",
            "target_route": "/dashboard/procurement/or-follow-up",
        },
        {
            "action_id": "raise_payment_priority",
            "label": "Raise Payment Priority",
            "mode": "execute",
            "target_route": "/dashboard/accounting/pending-payments",
            "command": "raise_payment_priority",
        },
    ],
    "SCM": [
        {
            "action_id": "open_delayed_deliveries",
            "label": "Open Delayed Deliveries",
            "mode": "navigate",
            "target_route": "/dashboard/scm/delayed-deliveries",
        },
        {
            "action_id": "open_in_transit_view",
            "label": "Open In-Transit View",
            "mode": "navigate",
            "target_route": "/dashboard/scm/in-transit",
        },
        {
            "action_id": "escalate_supplier_delay",
            "label": "Escalate Supplier Delay",
            "mode": "execute",
            "target_route": "/dashboard/scm/delayed-deliveries",
            "command": "escalate_supplier_delay",
        },
        {
            "action_id": "create_reallocation_task",
            "label": "Create Reallocation Task",
            "mode": "execute",
            "target_route": "/dashboard/scm/reallocation",
            "command": "create_reallocation_task",
        },
    ],
    "Warehouse": [
        {
            "action_id": "open_receiving_queue",
            "label": "Open Receiving Queue",
            "mode": "navigate",
            "target_route": "/dashboard/warehouse/receive",
        },
        {
            "action_id": "open_grn_queue",
            "label": "Open GRN Queue",
            "mode": "navigate",
            "target_route": "/dashboard/procurement/goods-receipts",
        },
        {
            "action_id": "open_transfer_queue",
            "label": "Open Transfer Queue",
            "mode": "navigate",
            "target_route": "/dashboard/warehouse/dispatch",
        },
        {
            "action_id": "create_mitigation_allocation",
            "label": "Create Mitigation Allocation",
            "mode": "execute",
            "target_route": "/dashboard/warehouse/receive",
            "command": "create_mitigation_allocation",
        },
    ],
}


def _normalize_department_name(department: str) -> str:
    normalized = (department or "").strip().lower()
    if normalized == "procurement":
        return "Procurement"
    if normalized == "finance":
        return "Finance"
    if normalized == "scm":
        return "SCM"
    if normalized == "warehouse":
        return "Warehouse"
    frappe.throw(_("department must be one of Procurement, Finance, SCM, Warehouse"))
    return "Procurement"


def _action_contract_with_filters(action: dict, filters: dict) -> dict:
    payload = deepcopy(action)
    payload["filters"] = deepcopy(filters)
    payload["context_key"] = _make_item_warehouse_key(filters.get("item_code"), filters.get("warehouse"))
    return payload


@frappe.whitelist()
def get_item_control_actions(item_code: str, warehouse: str, department: str, horizon_hours: int = 72):
    if not item_code:
        frappe.throw(_("item_code is required"))
    if not warehouse:
        frappe.throw(_("warehouse is required"))
    if not department:
        frappe.throw(_("department is required"))

    canonical_department = _normalize_department_name(department)
    action_templates = _DEPARTMENT_ACTION_CATALOG.get(canonical_department, [])
    if not action_templates:
        frappe.throw(_("No actions configured for selected department"))

    row = _find_risk_row(item_code=item_code, warehouse=warehouse, horizon_hours=horizon_hours)
    filters = {
        "item_code": item_code,
        "warehouse": warehouse,
        "horizon_hours": cint(horizon_hours or 72),
    }
    actions = [_action_contract_with_filters(action, filters) for action in action_templates]

    return {
        "department": canonical_department,
        "item_code": item_code,
        "warehouse": warehouse,
        "horizon_hours": cint(horizon_hours or 72),
        "context": {
            "risk_level": row.get("risk_level"),
            "risk_score": flt(row.get("risk_score")),
            "days_to_stockout": flt(row.get("days_to_stockout")),
        },
        "primary_action": actions[0],
        "more_actions": actions[1:],
        "all_actions": actions,
    }


@frappe.whitelist()
def get_item_decision_cockpit(item_code: str, warehouse: str, horizon_hours: int = 72):
    if not item_code:
        frappe.throw(_("item_code is required"))
    if not warehouse:
        frappe.throw(_("warehouse is required"))

    row = _find_risk_row(item_code=item_code, warehouse=warehouse, horizon_hours=horizon_hours)
    exposure = _resolve_exposure_rows(item_code=item_code, warehouse=warehouse)

    return {
        "item_code": item_code,
        "warehouse": warehouse,
        "horizon_hours": cint(horizon_hours or 72),
        "stock": {
            "available_qty": flt(row.get("available_qty")),
            "inbound_qty": flt(row.get("inbound_qty")),
            "in_transit_qty": flt(row.get("in_transit_qty")),
            "days_to_stockout": flt(row.get("days_to_stockout")),
            "projected_stockout_at": row.get("projected_stockout_at"),
            "projected_shortage_qty": flt(row.get("projected_shortage_qty")),
        },
        "consumption": {
            "daily_consumption": flt(row.get("avg_daily_demand")),
            "horizon_days": flt(row.get("horizon_days")),
            "horizon_demand_qty": flt(row.get("demand_horizon_qty")),
        },
        "inbound_pipeline": {
            "pending_po_count": cint(row.get("pending_po_count")),
            "inbound_po_qty": flt(row.get("inbound_po_qty")),
            "inbound_qty": flt(row.get("inbound_qty")),
            "delayed_po_count": cint(row.get("delayed_po_count")),
            "next_eta": row.get("next_eta"),
            "in_transit_qty": flt(row.get("in_transit_qty")),
        },
        "supplier_health": {
            "supplier_reliability_score": flt(row.get("supplier_reliability_score")),
            "supplier_on_time_rate": flt(row.get("supplier_on_time_rate")),
            "lead_time_days": flt(row.get("lead_time_days")),
        },
        "finance_impact": _finance_payload_from_row(row),
        "ingredient_exposure": exposure,
        "recommended_actions": _recommended_actions_from_row(row),
    }


@frappe.whitelist()
def get_finance_risk_impact(item_code: str, warehouse: str, horizon_hours: int = 72):
    if not item_code:
        frappe.throw(_("item_code is required"))
    if not warehouse:
        frappe.throw(_("warehouse is required"))

    row = _find_risk_row(item_code=item_code, warehouse=warehouse, horizon_hours=horizon_hours)
    return _finance_payload_from_row(row)


def _build_finance_queue_rows(row: dict, pending_pos: list[dict]) -> list[dict]:
    unit_cost = max(0.0, flt(row.get("unit_cost") or row.get("latest_cost") or 0))
    item_code = row.get("item_code")
    warehouse = row.get("warehouse")

    queue_rows: list[dict] = []
    for idx, po_row in enumerate(pending_pos, start=1):
        supplier = po_row.get("supplier") or f"test-supplier-{idx:02d}"
        ordered_qty = max(0.0, flt(po_row.get("ordered_qty")))
        amount_due = round(ordered_qty * unit_cost, 2)
        po_number = po_row.get("po_number") or f"PO-{item_code}-{idx:02d}"
        expected_eta = po_row.get("expected_eta")

        queue_rows.append(
            {
                "payment_reference": f"PAYQ-{po_number}",
                "supplier": supplier,
                "po_number": po_number,
                "item_code": item_code,
                "warehouse": warehouse,
                "amount_due": amount_due,
                "currency": "PHP",
                "status": "Pending Payment",
                "due_date": expected_eta,
                "source_doctype": po_row.get("source_doctype") or "Purchase Order",
                "source_name": po_row.get("source_name") or po_number,
                "link_route": po_row.get("link_route") or f"/app/purchase-order/{po_number}",
            }
        )

    return queue_rows


@frappe.whitelist()
def get_item_finance_queue(item_code: str, warehouse: str, horizon_hours: int = 72):
    if not item_code:
        frappe.throw(_("item_code is required"))
    if not warehouse:
        frappe.throw(_("warehouse is required"))

    row = _find_risk_row(item_code=item_code, warehouse=warehouse, horizon_hours=horizon_hours)
    pipeline = _build_pipeline_details_from_row(row)
    pending_pos = pipeline.get("pending_pos", [])
    pending_payments = _build_finance_queue_rows(row, pending_pos)

    supplier_list = sorted({entry.get("supplier") for entry in pending_payments if entry.get("supplier")})
    total_amount = round(sum(flt(entry.get("amount_due")) for entry in pending_payments), 2)

    return {
        "item_code": item_code,
        "warehouse": warehouse,
        "horizon_hours": cint(horizon_hours or 72),
        "suppliers": supplier_list,
        "totals": {
            "pending_payment_count": len(pending_payments),
            "pending_payment_amount": total_amount,
            "value_at_risk": flt(row.get("value_at_risk")),
            "margin_at_risk": flt(row.get("margin_at_risk")),
            "payable_urgency": row.get("payable_urgency") or "Low",
            "urgent_payment_required": bool(row.get("urgent_payment_required")),
        },
        "pending_payments": pending_payments,
    }


@frappe.whitelist()
def get_item_pending_pos(item_code: str, warehouse: str, horizon_hours: int = 72):
    if not item_code:
        frappe.throw(_("item_code is required"))
    if not warehouse:
        frappe.throw(_("warehouse is required"))

    row = _find_risk_row(item_code=item_code, warehouse=warehouse, horizon_hours=horizon_hours)
    pipeline = _build_pipeline_details_from_row(row)
    pending_pos = pipeline["pending_pos"]

    return {
        "item_code": item_code,
        "warehouse": warehouse,
        "totals": {
            "pending_po_count": len(pending_pos),
            "pending_po_qty": round(sum(flt(entry.get("ordered_qty")) for entry in pending_pos), 2),
            "synthetic_fallback_count": sum(1 for entry in pending_pos if entry.get("is_synthetic_fallback")),
        },
        "pending_pos": pending_pos,
    }


@frappe.whitelist()
def get_item_delayed_deliveries(item_code: str, warehouse: str, horizon_hours: int = 72):
    if not item_code:
        frappe.throw(_("item_code is required"))
    if not warehouse:
        frappe.throw(_("warehouse is required"))

    row = _find_risk_row(item_code=item_code, warehouse=warehouse, horizon_hours=horizon_hours)
    pipeline = _build_pipeline_details_from_row(row)
    delayed = pipeline["delayed_deliveries"]

    return {
        "item_code": item_code,
        "warehouse": warehouse,
        "totals": {
            "delayed_delivery_count": len(delayed),
            "delayed_qty": round(sum(flt(entry.get("delayed_qty")) for entry in delayed), 2),
            "synthetic_fallback_count": sum(1 for entry in delayed if entry.get("is_synthetic_fallback")),
        },
        "delayed_deliveries": delayed,
    }


def _next_incident_name() -> str:
    return f"test-inc-{len(_TEST_INCIDENTS) + 1:04d}"


def _resolve_session_user() -> str:
    local_session = getattr(getattr(frappe, "local", None), "session", None)
    if local_session and getattr(local_session, "user", None):
        return str(local_session.user)

    session = getattr(frappe, "session", None)
    if session and getattr(session, "user", None):
        return str(session.user)

    return "Administrator"


def _build_action_context(
    department: str | None = None,
    source_page: str | None = None,
    action_id: str | None = None,
) -> dict:
    context: dict[str, str] = {}
    if department:
        context["department"] = str(department)
    if source_page:
        context["source_page"] = str(source_page)
    if action_id:
        context["action_id"] = str(action_id)
    return context


def _append_incident_event(
    incident_name: str,
    event_type: str,
    details: str | None = None,
    action_context: dict | None = None,
) -> dict:
    event = {
        "incident": incident_name,
        "event_type": event_type,
        "details": details or "",
        "event_at": add_to_date(now_datetime(), days=0, as_string=True),
        "event_by": _resolve_session_user(),
        "action_context": deepcopy(action_context or {}),
    }
    _TEST_INCIDENT_EVENTS.setdefault(incident_name, []).append(event)
    return event


def _get_or_create_incident(incident_name: str) -> dict:
    incident = next((row for row in _TEST_INCIDENTS if row.get("name") == incident_name), None)
    if incident:
        return incident

    incident = {
        "name": incident_name,
        "incident_title": incident_name,
        "item_code": None,
        "warehouse": None,
        "status": "Open",
        "owner_user": None,
        "detected_on": add_to_date(now_datetime(), days=0, as_string=True),
        "target_resolution_at": None,
        "root_cause": "",
        "escalation_level": "Level 1",
        "mitigation_plan": "",
        "resolution_notes": "",
    }
    _TEST_INCIDENTS.append(incident)
    return incident


def create_stockout_incident(
    item_code: str,
    warehouse: str,
    incident_title: str | None = None,
    owner_user: str | None = None,
) -> dict:
    if not item_code:
        frappe.throw(_("item_code is required"))
    if not warehouse:
        frappe.throw(_("warehouse is required"))

    incident = {
        "name": _next_incident_name(),
        "incident_title": incident_title or f"Stockout risk on {item_code}",
        "item_code": item_code,
        "warehouse": warehouse,
        "status": "Open",
        "owner_user": owner_user,
        "detected_on": add_to_date(now_datetime(), days=0, as_string=True),
        "target_resolution_at": None,
        "root_cause": "",
        "escalation_level": "Level 1",
        "mitigation_plan": "",
        "resolution_notes": "",
    }
    _TEST_INCIDENTS.append(incident)
    _append_incident_event(incident["name"], "Detected", "Incident created")
    return deepcopy(incident)


_STATUS_EVENT_MAP = {
    "Mitigating": "Assigned",
    "Blocked": "Blocked",
    "Resolved": "Resolved",
}


def update_stockout_incident_status(
    incident_name: str,
    new_status: str,
    note: str | None = None,
    resolution_notes: str | None = None,
    owner_user: str | None = None,
) -> dict:
    if not incident_name:
        frappe.throw(_("incident_name is required"))
    if not new_status:
        frappe.throw(_("new_status is required"))

    allowed_status = {"Open", "Mitigating", "Blocked", "Resolved"}
    if new_status not in allowed_status:
        frappe.throw(_("Invalid status"))

    incident = _get_or_create_incident(incident_name)

    if new_status == "Resolved":
        final_notes = (resolution_notes or note or "").strip()
        if not final_notes:
            frappe.throw(_("resolution_notes is required for Resolved status"))
        incident["resolution_notes"] = final_notes

    if owner_user:
        incident["owner_user"] = owner_user

    incident["status"] = new_status
    event_type = _STATUS_EVENT_MAP.get(new_status, "Updated")
    _append_incident_event(incident_name, event_type, note)
    return deepcopy(incident)


@frappe.whitelist()
def assign_incident_owner(
    incident_name: str,
    owner_user: str,
    note: str | None = None,
    department: str | None = None,
    source_page: str | None = None,
    action_id: str | None = None,
):
    if not incident_name:
        frappe.throw(_("incident_name is required"))
    if not owner_user:
        frappe.throw(_("owner_user is required"))

    incident = _get_or_create_incident(incident_name)
    incident["owner_user"] = owner_user
    _append_incident_event(
        incident_name,
        "Assigned",
        note or f"Owner set to {owner_user}",
        action_context=_build_action_context(department, source_page, action_id),
    )
    return deepcopy(incident)


@frappe.whitelist()
def set_incident_sla(
    incident_name: str,
    target_resolution_at: str,
    note: str | None = None,
    department: str | None = None,
    source_page: str | None = None,
    action_id: str | None = None,
):
    if not incident_name:
        frappe.throw(_("incident_name is required"))
    if not target_resolution_at:
        frappe.throw(_("target_resolution_at is required"))

    incident = _get_or_create_incident(incident_name)
    incident["target_resolution_at"] = target_resolution_at
    _append_incident_event(
        incident_name,
        "Updated",
        note or f"SLA set to {target_resolution_at}",
        action_context=_build_action_context(department, source_page, action_id),
    )
    return deepcopy(incident)


@frappe.whitelist()
def escalate_stockout_incident(
    incident_name: str,
    escalation_level: str,
    note: str | None = None,
    department: str | None = None,
    source_page: str | None = None,
    action_id: str | None = None,
):
    if not incident_name:
        frappe.throw(_("incident_name is required"))
    if not escalation_level:
        frappe.throw(_("escalation_level is required"))

    incident = _get_or_create_incident(incident_name)
    incident["escalation_level"] = escalation_level
    incident["last_escalated_at"] = add_to_date(now_datetime(), days=0, as_string=True)
    _append_incident_event(
        incident_name,
        "Escalated",
        note or f"Escalated to {escalation_level}",
        action_context=_build_action_context(department, source_page, action_id),
    )
    return deepcopy(incident)


@frappe.whitelist()
def add_incident_mitigation_action(
    incident_name: str,
    action_owner: str,
    action_text: str,
    due_at: str | None = None,
    department: str | None = None,
    source_page: str | None = None,
    action_id: str | None = None,
):
    if not incident_name:
        frappe.throw(_("incident_name is required"))
    if not action_owner:
        frappe.throw(_("action_owner is required"))
    if not action_text:
        frappe.throw(_("action_text is required"))

    incident = _get_or_create_incident(incident_name)
    action_line = f"[{action_owner}] {action_text}"
    if due_at:
        action_line += f" (due {due_at})"

    existing = (incident.get("mitigation_plan") or "").strip()
    incident["mitigation_plan"] = f"{existing}\n{action_line}".strip()
    event = _append_incident_event(
        incident_name,
        "Mitigation Added",
        action_line,
        action_context=_build_action_context(department, source_page, action_id),
    )
    response = deepcopy(incident)
    response["action_context"] = deepcopy(event.get("action_context") or {})
    response["event"] = deepcopy(event)
    return response


@frappe.whitelist()
def get_incident_events(incident_name: str):
    if not incident_name:
        frappe.throw(_("incident_name is required"))
    return [deepcopy(row) for row in _TEST_INCIDENT_EVENTS.get(incident_name, [])]


@frappe.whitelist()
def get_stockout_incidents(status: str | None = None):
    incidents = [deepcopy(row) for row in _TEST_INCIDENTS]
    if status:
        incidents = [row for row in incidents if row.get("status") == status]
    return {
        "status": status,
        "incidents": incidents,
    }


@frappe.whitelist()
def update_stockout_incident(incident_name: str, new_status: str, note: str | None = None):
    return update_stockout_incident_status(
        incident_name=incident_name,
        new_status=new_status,
        note=note,
    )
