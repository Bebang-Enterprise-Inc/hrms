# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Commissary Quality APIs — Part of commissary.py split (P0-11).

Extracted from hrms/api/commissary.py to improve maintainability.
Contains all quality-related functionality:
  - Quality Inspection (creation, history, details)
  - Wastage Tracking (log, history, reasons)
  - FEFO Picking Helper (picking list, expiring batches, batch tracking setup)
  - QC Form Management (submit, list, detail, templates)
"""
import frappe
from frappe import _
import json
from frappe.utils import today, add_days, flt

from hrms.api.commissary import get_commissary_warehouse
from hrms.utils.bei_config import get_company


# ============================================================
# QUALITY INSPECTION
# ============================================================

@frappe.whitelist()
def get_pending_inspections():
    """
    Get production batches awaiting quality inspection.
    Returns Stock Entries (Manufacture) that don't have a linked QI.
    """
    commissary_warehouse = get_commissary_warehouse()

    # Get manufacture entries from last 7 days without QI
    pending = frappe.db.sql("""
        SELECT
            se.name,
            se.posting_date,
            sed.item_code,
            sed.item_name,
            sed.qty,
            sed.uom,
            i.quality_inspection_template
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        JOIN `tabItem` i ON i.name = sed.item_code
        WHERE se.stock_entry_type = 'Manufacture'
        AND se.docstatus = 1
        AND sed.t_warehouse = %s
        AND se.posting_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        AND i.inspection_required_before_delivery = 1
        AND NOT EXISTS (
            SELECT 1 FROM `tabQuality Inspection` qi
            WHERE qi.reference_name = se.name
            AND qi.item_code = sed.item_code
            AND qi.docstatus != 2
        )
        ORDER BY se.posting_date DESC
    """, commissary_warehouse, as_dict=True)

    return {
        "success": True,
        "data": pending,
        "total": len(pending)
    }


@frappe.whitelist()
def create_quality_inspection(stock_entry_name, item_code, inspected_by=None,
                              readings=None, status="Accepted",
                              rejection_disposition=None):
    """
    Create a quality inspection record for a production batch.
    If rejected with disposition "Scrap", auto-creates wastage entry.

    Args:
        stock_entry_name: Reference Stock Entry
        item_code: Item being inspected
        inspected_by: Inspector name (defaults to current user)
        readings: Dict of {specification: reading_value}
        status: "Accepted" or "Rejected"
        rejection_disposition: "Scrap", "Rework", or "Hold" (only used when status=Rejected)
    """
    if isinstance(readings, str):
        readings = json.loads(readings)

    # Get the Stock Entry Detail
    sed = frappe.db.get_value(
        "Stock Entry Detail",
        {"parent": stock_entry_name, "item_code": item_code},
        ["qty", "batch_no"],
        as_dict=True
    )

    if not sed:
        return {"success": False, "error": f"Item {item_code} not found in Stock Entry {stock_entry_name}"}

    # Get the QI template for this item
    template = frappe.db.get_value("Item", item_code, "quality_inspection_template")

    # Create QI
    qi = frappe.new_doc("Quality Inspection")
    qi.inspection_type = "Outgoing"
    qi.reference_type = "Stock Entry"
    qi.reference_name = stock_entry_name
    qi.item_code = item_code
    qi.sample_size = sed.qty
    qi.inspected_by = inspected_by or frappe.session.user
    qi.status = status
    qi.batch_no = sed.batch_no

    # If template exists, populate readings
    if template:
        qi.quality_inspection_template = template
        template_doc = frappe.get_doc("Quality Inspection Template", template)
        for param in template_doc.item_quality_inspection_parameter:
            reading = {
                "specification": param.specification,
                "value": param.value,
                "status": "Accepted"
            }
            # Override with provided readings
            if readings and param.specification in readings:
                reading["reading_1"] = readings[param.specification]
            qi.append("readings", reading)
    elif readings:
        # Create readings from provided data
        for spec, value in readings.items():
            qi.append("readings", {
                "specification": spec,
                "reading_1": value,
                "status": "Accepted"
            })

    frappe.db.savepoint("quality_inspection")
    try:
        qi.insert(ignore_permissions=True)
        qi.submit()

        result = {
            "success": True,
            "message": f"Quality Inspection {qi.name} created",
            "data": {"name": qi.name, "status": qi.status}
        }

        # Auto-scrap on rejection with "Scrap" disposition
        if status == "Rejected" and rejection_disposition == "Scrap":
            wastage_result = log_wastage(
                item_code=item_code,
                qty=sed.qty,
                reason_code="quality_fail",
                batch_no=sed.batch_no,
                remarks=f"Auto-scrapped from QI {qi.name}"
            )
            result["data"]["wastage_entry"] = wastage_result.get("data", {}).get("name")
            result["data"]["rejection_disposition"] = "Scrap"
            result["message"] += f" | Wastage logged: {wastage_result.get('data', {}).get('name')}"
        elif status == "Rejected":
            result["data"]["rejection_disposition"] = rejection_disposition or "Hold"

        frappe.db.release_savepoint("quality_inspection")
    except Exception:
        frappe.db.rollback(save_point="quality_inspection")
        raise

    return result


@frappe.whitelist()
def get_inspection_history(item_code=None, days=30):
    """
    Get quality inspection history.

    Args:
        item_code: Filter by specific item (optional)
        days: Number of days to look back (default 30)
    """
    filters = {
        "docstatus": 1,
        "inspection_type": "Outgoing",
        "creation": [">=", add_days(today(), -int(days))]
    }

    if item_code:
        filters["item_code"] = item_code

    inspections = frappe.get_all(
        "Quality Inspection",
        filters=filters,
        fields=[
            "name", "item_code", "item_name", "status",
            "inspected_by", "sample_size", "batch_no",
            "reference_name", "modified"
        ],
        order_by="modified desc",
        limit=100
    )

    # Get summary stats
    total = len(inspections)
    accepted = len([i for i in inspections if i.status == "Accepted"])
    rejected = len([i for i in inspections if i.status == "Rejected"])

    return {
        "success": True,
        "data": inspections,
        "summary": {
            "total": total,
            "accepted": accepted,
            "rejected": rejected,
            "acceptance_rate": round(accepted / total * 100, 1) if total > 0 else 0
        }
    }


@frappe.whitelist()
def get_inspection_details(inspection_name):
    """Get full details of a quality inspection including readings."""
    qi = frappe.get_doc("Quality Inspection", inspection_name)

    return {
        "success": True,
        "data": {
            "name": qi.name,
            "item_code": qi.item_code,
            "item_name": qi.item_name,
            "status": qi.status,
            "inspected_by": qi.inspected_by,
            "sample_size": qi.sample_size,
            "batch_no": qi.batch_no,
            "reference_name": qi.reference_name,
            "readings": [
                {
                    "specification": r.specification,
                    "value": r.value,
                    "reading_1": r.reading_1,
                    "status": r.status
                }
                for r in qi.readings
            ]
        }
    }


# ============================================================
# WASTAGE TRACKING
# ============================================================

# Wastage reason codes
WASTAGE_REASONS = {
    "expired": "Expired/Past shelf life",
    "damaged": "Damaged during handling",
    "quality_fail": "Failed quality inspection",
    "contaminated": "Contaminated/Spoiled",
    "production_loss": "Production loss/Spillage",
    "sampling": "Quality sampling/Testing",
    "other": "Other (specify in remarks)"
}


@frappe.whitelist()
def log_wastage(item_code, qty, reason_code, batch_no=None, remarks=None):
    """
    Log wastage for a commissary item.
    Creates a Material Issue Stock Entry for inventory reduction.

    Args:
        item_code: Item being wasted
        qty: Quantity wasted
        reason_code: Code from WASTAGE_REASONS
        batch_no: Batch number (optional)
        remarks: Additional notes
    """
    commissary_warehouse = get_commissary_warehouse()

    if reason_code not in WASTAGE_REASONS:
        return {
            "success": False,
            "error": f"Invalid reason code. Valid codes: {', '.join(WASTAGE_REASONS.keys())}"
        }

    # Get item details
    item = frappe.db.get_value(
        "Item", item_code,
        ["item_name", "stock_uom", "valuation_rate"],
        as_dict=True
    )

    if not item:
        return {"success": False, "error": f"Item {item_code} not found"}

    # Create Stock Entry for Material Issue (Wastage)
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Issue"
    se.company = get_company()
    se.purpose = "Material Issue"

    # Build remarks with reason
    full_remarks = f"WASTAGE: {WASTAGE_REASONS[reason_code]}"
    if remarks:
        full_remarks += f" - {remarks}"
    se.remarks = full_remarks

    se.append("items", {
        "item_code": item_code,
        "item_name": item.item_name,
        "s_warehouse": commissary_warehouse,
        "qty": flt(qty),
        "uom": item.stock_uom,
        "stock_uom": item.stock_uom,
        "batch_no": batch_no
    })

    se.insert()
    se.submit()

    # Calculate wastage value
    wastage_value = flt(qty) * flt(item.valuation_rate or 0)

    return {
        "success": True,
        "message": f"Wastage logged: {qty} {item.stock_uom} of {item.item_name}",
        "data": {
            "name": se.name,
            "item_code": item_code,
            "qty": qty,
            "reason": WASTAGE_REASONS[reason_code],
            "wastage_value": wastage_value
        }
    }


@frappe.whitelist()
def get_wastage_history(days=30, item_code=None):
    """
    Get wastage history from commissary.

    Args:
        days: Days to look back (default 30)
        item_code: Filter by specific item (optional)
    """
    commissary_warehouse = get_commissary_warehouse()

    # Build filters
    filters = """
        WHERE se.stock_entry_type = 'Material Issue'
        AND se.docstatus = 1
        AND se.remarks LIKE %(wastage_pattern)s
        AND sed.s_warehouse = %(warehouse)s
        AND se.posting_date >= DATE_SUB(CURDATE(), INTERVAL %(days)s DAY)
    """

    params = {
        "warehouse": commissary_warehouse,
        "days": int(days),
        "wastage_pattern": "WASTAGE:%"
    }

    if item_code:
        filters += " AND sed.item_code = %(item_code)s"
        params["item_code"] = item_code

    wastage = frappe.db.sql("""
        SELECT
            se.name,
            se.posting_date,
            sed.item_code,
            sed.item_name,
            sed.qty,
            sed.uom,
            sed.basic_amount as wastage_value,
            se.remarks,
            se.owner as logged_by
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        """ + filters + """
        ORDER BY se.posting_date DESC
    """, params, as_dict=True)

    # Calculate summary
    total_qty = sum(w.qty for w in wastage)
    total_value = sum(w.wastage_value or 0 for w in wastage)

    # Group by reason
    by_reason = {}
    for w in wastage:
        reason = w.remarks.replace("WASTAGE: ", "").split(" - ")[0] if w.remarks else "Unknown"
        if reason not in by_reason:
            by_reason[reason] = {"count": 0, "qty": 0, "value": 0}
        by_reason[reason]["count"] += 1
        by_reason[reason]["qty"] += w.qty
        by_reason[reason]["value"] += w.wastage_value or 0

    return {
        "success": True,
        "data": wastage,
        "summary": {
            "total_entries": len(wastage),
            "total_qty": total_qty,
            "total_value": total_value,
            "by_reason": by_reason
        }
    }


@frappe.whitelist()
def get_wastage_reasons():
    """Get available wastage reason codes and descriptions."""
    return {
        "success": True,
        "data": [
            {"code": code, "description": desc}
            for code, desc in WASTAGE_REASONS.items()
        ]
    }


# ============================================================
# FEFO PICKING HELPER
# ============================================================

@frappe.whitelist()
def get_fefo_picking_list(item_code=None, warehouse=None):
    """
    Get FEFO (First Expired First Out) picking recommendations.
    Returns batches sorted by expiry date for picking priority.

    Args:
        item_code: Filter by specific item (optional)
        warehouse: Filter by warehouse (defaults to commissary)
    """
    commissary_warehouse = warehouse or get_commissary_warehouse()

    # Get batches with stock ordered by expiry date (FEFO)
    picking_list = frappe.db.sql("""
        SELECT
            sle.item_code,
            i.item_name,
            sle.batch_no,
            b.expiry_date,
            b.manufacturing_date,
            SUM(sle.actual_qty) as available_qty,
            i.stock_uom,
            DATEDIFF(b.expiry_date, CURDATE()) as days_to_expiry,
            CASE
                WHEN b.expiry_date IS NULL THEN 'no_expiry'
                WHEN b.expiry_date <= CURDATE() THEN 'expired'
                WHEN DATEDIFF(b.expiry_date, CURDATE()) <= 3 THEN 'critical'
                WHEN DATEDIFF(b.expiry_date, CURDATE()) <= 7 THEN 'warning'
                ELSE 'ok'
            END as expiry_status
        FROM `tabStock Ledger Entry` sle
        JOIN `tabItem` i ON i.name = sle.item_code
        LEFT JOIN `tabBatch` b ON b.name = sle.batch_no
        WHERE sle.warehouse = %(warehouse)s
        AND sle.is_cancelled = 0
        AND i.item_group = 'Finished Goods'
        GROUP BY sle.item_code, sle.batch_no
        HAVING available_qty > 0
        ORDER BY
            CASE WHEN b.expiry_date IS NULL THEN 1 ELSE 0 END,
            b.expiry_date ASC,
            sle.item_code
    """, {"warehouse": commissary_warehouse}, as_dict=True)

    if item_code:
        picking_list = [p for p in picking_list if p.item_code == item_code]

    # Summary by expiry status
    summary = {
        "expired": 0,
        "critical": 0,
        "warning": 0,
        "ok": 0,
        "no_expiry": 0
    }
    for item in picking_list:
        status = item.expiry_status or "no_expiry"
        summary[status] += 1

    return {
        "success": True,
        "data": picking_list,
        "summary": summary,
        "note": "Items without batch numbers will not appear. Enable batch tracking on items for FEFO."
    }


@frappe.whitelist()
def get_expiring_batches(days=7, item_group=None):
    """
    Get batches expiring within specified days.
    Helps identify items that need to be used or disposed.

    Args:
        days: Days until expiry (default 7)
        item_group: Filter by item group (optional)
    """
    commissary_warehouse = get_commissary_warehouse()

    filters = """
        WHERE b.expiry_date IS NOT NULL
        AND b.expiry_date <= DATE_ADD(CURDATE(), INTERVAL %(days)s DAY)
        AND bin.actual_qty > 0
        AND bin.warehouse = %(warehouse)s
    """

    params = {
        "days": int(days),
        "warehouse": commissary_warehouse
    }

    if item_group:
        filters += " AND i.item_group = %(item_group)s"
        params["item_group"] = item_group

    expiring = frappe.db.sql(f"""
        SELECT
            b.name as batch_no,
            b.item as item_code,
            i.item_name,
            i.item_group,
            b.expiry_date,
            b.manufacturing_date,
            bin.actual_qty as available_qty,
            i.stock_uom,
            DATEDIFF(b.expiry_date, CURDATE()) as days_to_expiry,
            CASE
                WHEN b.expiry_date <= CURDATE() THEN 'expired'
                WHEN DATEDIFF(b.expiry_date, CURDATE()) <= 3 THEN 'critical'
                ELSE 'warning'
            END as urgency
        FROM `tabBatch` b
        JOIN `tabItem` i ON i.name = b.item
        LEFT JOIN `tabBin` bin ON bin.item_code = b.item AND bin.warehouse = %(warehouse)s
        {filters}
        ORDER BY b.expiry_date ASC
    """, params, as_dict=True)

    # Group by urgency
    by_urgency = {"expired": [], "critical": [], "warning": []}
    for batch in expiring:
        urgency = batch.urgency
        by_urgency[urgency].append(batch)

    return {
        "success": True,
        "data": expiring,
        "by_urgency": {
            "expired": len(by_urgency["expired"]),
            "critical": len(by_urgency["critical"]),
            "warning": len(by_urgency["warning"])
        },
        "total": len(expiring)
    }


@frappe.whitelist()
def enable_batch_tracking_for_fg():
    """
    Enable batch and expiry date tracking for all Finished Goods items.
    This is required for FEFO picking to work.

    Note: Run this once to enable batch tracking. New batches will be created
    automatically during production.
    """
    updated = 0

    # Get all FG items without batch tracking
    items = frappe.get_all(
        "Item",
        filters={
            "item_group": "Finished Goods",
            "has_batch_no": 0
        },
        fields=["name"]
    )

    for item in items:
        frappe.db.set_value("Item", item.name, {
            "has_batch_no": 1,
            "create_new_batch": 1,
            "has_expiry_date": 1
        })
        updated += 1

    return {
        "success": True,
        "message": f"Enabled batch tracking for {updated} Finished Goods items",
        "updated": updated
    }


# ============================================================
# QC FORM MANAGEMENT
# ============================================================

# QC form templates with expected parameters per form type
QC_FORM_TEMPLATES = {
    "Area Temperature Verification": [
        {"parameter": "Area Temperature", "unit": "°C", "min_range": None, "max_range": None},
        {"parameter": "Humidity", "unit": "%RH", "min_range": None, "max_range": None},
    ],
    "Storage Temperature Monitoring": [
        {"parameter": "Chiller 1 Temperature", "unit": "°C", "min_range": 0, "max_range": 4},
        {"parameter": "Freezer 1 Temperature", "unit": "°C", "min_range": -22, "max_range": -18},
        {"parameter": "Dry Storage Temperature", "unit": "°C", "min_range": 20, "max_range": 35},
    ],
    "Cooking Verification": [
        {"parameter": "Cooking Temperature", "unit": "°C", "min_range": None, "max_range": None},
        {"parameter": "Cooking Time", "unit": "min", "min_range": None, "max_range": None},
        {"parameter": "Product Temperature (post-cook)", "unit": "°C", "min_range": None, "max_range": None},
    ],
    "Mixing Monitoring": [
        {"parameter": "Mixing Time", "unit": "min", "min_range": None, "max_range": None},
        {"parameter": "Mixing Speed", "unit": "RPM", "min_range": None, "max_range": None},
        {"parameter": "Product Temperature", "unit": "°C", "min_range": None, "max_range": None},
    ],
    "Packaging Monitoring Report": [
        {"parameter": "Seal Integrity", "unit": "", "min_range": None, "max_range": None},
        {"parameter": "Label Accuracy", "unit": "", "min_range": None, "max_range": None},
        {"parameter": "Weight Check", "unit": "g", "min_range": None, "max_range": None},
    ],
    "GMP Checklist": [
        {"parameter": "Personal Hygiene", "unit": "", "min_range": None, "max_range": None},
        {"parameter": "Area Cleanliness", "unit": "", "min_range": None, "max_range": None},
        {"parameter": "Equipment Sanitation", "unit": "", "min_range": None, "max_range": None},
        {"parameter": "Waste Disposal", "unit": "", "min_range": None, "max_range": None},
        {"parameter": "Pest Control", "unit": "", "min_range": None, "max_range": None},
    ],
}


@frappe.whitelist()
def submit_qc_form(form_type, readings=None, shift=None, area=None,
                    remarks=None, photo_evidence=None):
    """
    Submit a QC form with readings.

    Args:
        form_type: One of the 8 QC form types
        readings: JSON array of {parameter, value, unit, min_range, max_range}
        shift: "AM (5:00-14:00)" or "PM (16:00-01:00)" or "Dispatch (04:00)"
        area: Storage/production area
        remarks: Optional notes
        photo_evidence: Optional attached photo URL
    """
    if isinstance(readings, str):
        readings = json.loads(readings)

    qc = frappe.new_doc("BEI QC Form")
    qc.form_type = form_type
    qc.form_date = today()
    qc.shift = shift
    qc.area = area
    qc.checked_by = frappe.session.user
    qc.status = "Submitted"
    qc.remarks = remarks
    qc.photo_evidence = photo_evidence

    if readings:
        for r in readings:
            status = ""
            val = flt(r.get("value")) if r.get("value") else None
            if val is not None and r.get("min_range") is not None and r.get("max_range") is not None:
                if flt(r["min_range"]) <= val <= flt(r["max_range"]):
                    status = "Pass"
                else:
                    status = "Fail"

            qc.append("readings", {
                "parameter": r.get("parameter"),
                "value": str(r.get("value", "")),
                "unit": r.get("unit", ""),
                "min_range": r.get("min_range"),
                "max_range": r.get("max_range"),
                "status": status
            })

    qc.insert(ignore_permissions=True)

    return {
        "success": True,
        "message": f"QC Form {qc.name} submitted",
        "data": {
            "name": qc.name,
            "form_type": qc.form_type,
            "readings_count": len(qc.readings),
            "has_failures": any(r.status == "Fail" for r in qc.readings)
        }
    }


@frappe.whitelist()
def get_qc_forms(form_type=None, date_from=None, date_to=None, limit=50):
    """
    List QC forms with optional filters.

    Args:
        form_type: Filter by form type
        date_from: Start date
        date_to: End date
        limit: Max results (default 50)
    """
    filters = {}
    if form_type:
        filters["form_type"] = form_type
    if date_from and date_to:
        filters["form_date"] = ["between", [date_from, date_to]]
    elif date_from:
        filters["form_date"] = [">=", date_from]
    elif date_to:
        filters["form_date"] = ["<=", date_to]

    forms = frappe.get_all(
        "BEI QC Form",
        filters=filters,
        fields=[
            "name", "form_type", "form_date", "shift", "area",
            "status", "checked_by", "verified_by"
        ],
        order_by="form_date desc, creation desc",
        limit=int(limit)
    )

    return {
        "success": True,
        "data": forms,
        "total": len(forms)
    }


@frappe.whitelist()
def get_qc_form_detail(form_name):
    """Get a single QC form with all readings."""
    qc = frappe.get_doc("BEI QC Form", form_name)

    return {
        "success": True,
        "data": {
            "name": qc.name,
            "form_type": qc.form_type,
            "form_date": str(qc.form_date),
            "shift": qc.shift,
            "area": qc.area,
            "status": qc.status,
            "checked_by": qc.checked_by,
            "verified_by": qc.verified_by,
            "remarks": qc.remarks,
            "photo_evidence": qc.photo_evidence,
            "readings": [
                {
                    "parameter": r.parameter,
                    "value": r.value,
                    "unit": r.unit,
                    "min_range": r.min_range,
                    "max_range": r.max_range,
                    "status": r.status
                }
                for r in qc.readings
            ]
        }
    }


@frappe.whitelist()
def get_qc_form_templates():
    """Return expected readings per form type with ranges."""
    return {
        "success": True,
        "data": QC_FORM_TEMPLATES
    }
