# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Projects API
Handles maintenance request management for the Projects team dashboard at my.bebang.ph
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, getdate, date_diff, flt
import json
import math


# ==============================================================================
# MAINTENANCE QUEUE
# ==============================================================================


@frappe.whitelist()
def get_maintenance_queue(
    status=None,
    priority=None,
    category=None,
    store=None,
    assigned_to=None,
    date_from=None,
    date_to=None,
    search=None,
    sort_by="request_date",
    sort_order="desc",
    page=1,
    page_size=20
):
    """
    Get maintenance requests for Projects dashboard with full filtering and pagination.

    Args:
        status: Filter by status (Open, Assigned, In Progress, Completed, Verified, Cancelled)
        priority: Filter by priority (Urgent, High, Normal)
        category: Filter by issue_category (Electrical, Plumbing, etc.)
        store: Filter by specific store (warehouse name)
        assigned_to: Filter by assignee (User)
        date_from: Filter by request_date >= date_from
        date_to: Filter by request_date <= date_to
        search: Search in description, store_code
        sort_by: Field to sort by (default: request_date)
        sort_order: Sort direction (asc/desc, default: desc)
        page: Page number (default: 1)
        page_size: Items per page (default: 20)

    Returns:
        {
            "requests": [...],
            "total": int,
            "page": int,
            "page_size": int,
            "pages": int
        }
    """
    # Build filters
    filters = []

    if status:
        if isinstance(status, str):
            if "," in status:
                # Support comma-separated values
                filters.append(["status", "in", [s.strip() for s in status.split(",")]])
            else:
                filters.append(["status", "=", status])
        elif isinstance(status, list):
            filters.append(["status", "in", status])

    if priority:
        if isinstance(priority, str):
            if "," in priority:
                filters.append(["priority", "in", [p.strip() for p in priority.split(",")]])
            else:
                filters.append(["priority", "=", priority])
        elif isinstance(priority, list):
            filters.append(["priority", "in", priority])

    if category:
        if isinstance(category, str):
            if "," in category:
                filters.append(["issue_category", "in", [c.strip() for c in category.split(",")]])
            else:
                filters.append(["issue_category", "=", category])
        elif isinstance(category, list):
            filters.append(["issue_category", "in", category])

    if store:
        filters.append(["store", "=", store])

    if assigned_to:
        filters.append(["assigned_to", "=", assigned_to])

    if date_from:
        filters.append(["request_date", ">=", date_from])

    if date_to:
        filters.append(["request_date", "<=", date_to])

    # Convert page params to int
    page = int(page)
    page_size = int(page_size)

    # Validate sort_by to prevent SQL injection
    allowed_sort_fields = [
        "request_date", "priority", "status", "issue_category",
        "store_code", "creation", "modified"
    ]
    if sort_by not in allowed_sort_fields:
        sort_by = "request_date"

    if sort_order.lower() not in ["asc", "desc"]:
        sort_order = "desc"

    # Build search condition
    search_condition = ""
    if search:
        search = f"%{search}%"
        search_condition = f" AND (mr.description LIKE %(search)s OR mr.store_code LIKE %(search)s OR mr.name LIKE %(search)s)"

    # Build filter conditions
    filter_conditions = []
    filter_values = {"search": search} if search else {}

    for i, f in enumerate(filters):
        field, op, value = f
        if op == "=":
            filter_conditions.append(f"mr.{field} = %(filter_{i})s")
            filter_values[f"filter_{i}"] = value
        elif op == "in":
            placeholders = ", ".join([f"%(filter_{i}_{j})s" for j in range(len(value))])
            filter_conditions.append(f"mr.{field} IN ({placeholders})")
            for j, v in enumerate(value):
                filter_values[f"filter_{i}_{j}"] = v
        elif op == ">=":
            filter_conditions.append(f"mr.{field} >= %(filter_{i})s")
            filter_values[f"filter_{i}"] = value
        elif op == "<=":
            filter_conditions.append(f"mr.{field} <= %(filter_{i})s")
            filter_values[f"filter_{i}"] = value

    where_clause = ""
    if filter_conditions:
        where_clause = " AND " + " AND ".join(filter_conditions)

    # Get total count
    count_sql = f"""
        SELECT COUNT(*) as total
        FROM `tabBEI Maintenance Request` mr
        WHERE 1=1 {where_clause} {search_condition}
    """
    total = frappe.db.sql(count_sql, filter_values, as_dict=True)[0].total

    # Calculate pagination
    pages = math.ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    # Get requests with photo count
    requests_sql = f"""
        SELECT
            mr.name,
            mr.store,
            mr.store_code,
            mr.request_date,
            mr.status,
            mr.priority,
            mr.impact_on_operations,
            mr.issue_category,
            mr.equipment_area,
            mr.description,
            mr.assigned_to,
            mr.vendor,
            mr.scheduled_date,
            mr.estimated_cost,
            mr.completion,
            mr.resolved_date,
            mr.reported_by,
            mr.reported_at,
            (SELECT COUNT(*) FROM `tabBEI Maintenance Request Photo` WHERE parent = mr.name) as photo_count,
            DATEDIFF(CURDATE(), mr.request_date) as age_days
        FROM `tabBEI Maintenance Request` mr
        WHERE 1=1 {where_clause} {search_condition}
        ORDER BY mr.{sort_by} {sort_order}
        LIMIT {page_size} OFFSET {offset}
    """

    requests = frappe.db.sql(requests_sql, filter_values, as_dict=True)

    # Get reporter names
    for req in requests:
        if req.reported_by:
            req["reporter_name"] = frappe.db.get_value("User", req.reported_by, "full_name") or req.reported_by
        if req.assigned_to:
            req["assignee_name"] = frappe.db.get_value("User", req.assigned_to, "full_name") or req.assigned_to

    return {
        "requests": requests,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages
    }


# ==============================================================================
# REQUEST DETAIL
# ==============================================================================


@frappe.whitelist()
def get_maintenance_request_detail(request_id):
    """
    Get full detail of a maintenance request including photos, completion, and history.

    Args:
        request_id: The maintenance request name (e.g., MR-BGC-0058)

    Returns:
        {
            "request": {...},
            "photos": [...],
            "completion": {...} or None,
            "history": [...] (status changes)
        }
    """
    if not request_id:
        frappe.throw(_("Request ID is required"))

    if not frappe.db.exists("BEI Maintenance Request", request_id):
        frappe.throw(_("Maintenance request {0} not found").format(request_id))

    doc = frappe.get_doc("BEI Maintenance Request", request_id)

    # Get request data
    request_data = doc.as_dict()

    # Add computed fields
    request_data["age_days"] = date_diff(nowdate(), doc.request_date) if doc.request_date else 0

    # Get reporter name
    if doc.reported_by:
        request_data["reporter_name"] = frappe.db.get_value("User", doc.reported_by, "full_name") or doc.reported_by

    # Get assignee name
    if doc.assigned_to:
        request_data["assignee_name"] = frappe.db.get_value("User", doc.assigned_to, "full_name") or doc.assigned_to

    # Get store display name
    if doc.store:
        request_data["store_display"] = frappe.db.get_value("Warehouse", doc.store, "warehouse_name") or doc.store

    # Get photos
    photos = []
    for photo in doc.photos:
        photos.append({
            "name": photo.name,
            "photo": photo.photo,
            "caption": photo.caption or ""
        })

    # Get completion record if exists
    completion = None
    if doc.completion:
        comp_doc = frappe.get_doc("BEI Maintenance Completion", doc.completion)
        completion = comp_doc.as_dict()
        if comp_doc.verified_by:
            completion["verifier_name"] = frappe.db.get_value("User", comp_doc.verified_by, "full_name")

    # Get history from Version log
    history = []
    try:
        versions = frappe.get_all(
            "Version",
            filters={
                "docname": request_id,
                "ref_doctype": "BEI Maintenance Request"
            },
            fields=["creation", "owner", "data"],
            order_by="creation asc"
        )

        for version in versions:
            try:
                data = json.loads(version.data)
                changes = data.get("changed", [])

                for change in changes:
                    field, old_val, new_val = change
                    if field == "status":
                        history.append({
                            "timestamp": version.creation.isoformat() if version.creation else None,
                            "action": f"Status changed from {old_val} to {new_val}",
                            "user": version.owner,
                            "user_name": frappe.db.get_value("User", version.owner, "full_name") or version.owner
                        })
            except (json.JSONDecodeError, KeyError):
                continue
    except Exception:
        pass  # Version tracking may not be enabled

    # Add creation event
    history.insert(0, {
        "timestamp": doc.creation.isoformat() if doc.creation else None,
        "action": "Request created",
        "user": doc.reported_by or doc.owner,
        "user_name": request_data.get("reporter_name") or doc.owner
    })

    return {
        "request": request_data,
        "photos": photos,
        "completion": completion,
        "history": history
    }


# ==============================================================================
# ASSIGN REQUEST
# ==============================================================================


@frappe.whitelist()
def assign_maintenance_request(
    request_id,
    assigned_to=None,
    vendor=None,
    scheduled_date=None,
    estimated_cost=None,
    notes=None
):
    """
    Assign a maintenance request to internal staff or external vendor.
    Updates status to 'Assigned'.

    Args:
        request_id: The maintenance request name
        assigned_to: Internal User (optional)
        vendor: External vendor name (optional)
        scheduled_date: When work is scheduled (optional)
        estimated_cost: Estimated cost (optional)
        notes: Assignment notes (optional)

    Returns:
        {
            "success": True,
            "message": "...",
            "request": {...}
        }
    """
    if not request_id:
        frappe.throw(_("Request ID is required"))

    if not assigned_to and not vendor:
        frappe.throw(_("Either internal assignee or vendor must be specified"))

    if not frappe.db.exists("BEI Maintenance Request", request_id):
        frappe.throw(_("Maintenance request {0} not found").format(request_id))

    doc = frappe.get_doc("BEI Maintenance Request", request_id)

    # Check current status allows assignment
    if doc.status not in ["Open", "Assigned"]:
        frappe.throw(_("Cannot assign request with status {0}").format(doc.status))

    # Update assignment fields
    if assigned_to:
        if not frappe.db.exists("User", assigned_to):
            frappe.throw(_("User {0} not found").format(assigned_to))
        doc.assigned_to = assigned_to
        doc.vendor = None  # Clear vendor if assigning to internal

    if vendor:
        doc.vendor = vendor
        doc.assigned_to = None  # Clear internal if assigning to vendor

    if scheduled_date:
        doc.scheduled_date = scheduled_date

    if estimated_cost is not None:
        doc.estimated_cost = flt(estimated_cost)

    # Update status
    doc.status = "Assigned"

    # Add notes as comment if provided
    if notes:
        doc.add_comment("Comment", notes)

    doc.save()

    # Get assignee name for response
    assignee_name = None
    if assigned_to:
        assignee_name = frappe.db.get_value("User", assigned_to, "full_name")

    return {
        "success": True,
        "message": _("Request {0} assigned to {1}").format(
            request_id,
            assignee_name or vendor
        ),
        "request": doc.as_dict()
    }


# ==============================================================================
# UPDATE STATUS
# ==============================================================================


@frappe.whitelist()
def update_maintenance_status(request_id, status, notes=None):
    """
    Update maintenance request status.

    Valid transitions:
    - Open -> Assigned, Cancelled
    - Assigned -> In Progress, Open, Cancelled
    - In Progress -> Completed, Assigned
    - Completed -> Verified (via store verification only)

    Args:
        request_id: The maintenance request name
        status: New status
        notes: Optional status change notes

    Returns:
        {
            "success": True,
            "message": "...",
            "request": {...}
        }
    """
    if not request_id:
        frappe.throw(_("Request ID is required"))

    if not status:
        frappe.throw(_("Status is required"))

    valid_statuses = ["Open", "Assigned", "In Progress", "Completed", "Verified", "Cancelled"]
    if status not in valid_statuses:
        frappe.throw(_("Invalid status: {0}").format(status))

    if not frappe.db.exists("BEI Maintenance Request", request_id):
        frappe.throw(_("Maintenance request {0} not found").format(request_id))

    doc = frappe.get_doc("BEI Maintenance Request", request_id)
    old_status = doc.status

    # Define valid transitions
    valid_transitions = {
        "Open": ["Assigned", "Cancelled"],
        "Assigned": ["In Progress", "Open", "Cancelled"],
        "In Progress": ["Completed", "Assigned", "Cancelled"],
        "Completed": ["Verified", "In Progress"],  # Verified usually via store
        "Verified": [],  # Terminal state
        "Cancelled": ["Open"]  # Can reopen cancelled requests
    }

    if status not in valid_transitions.get(old_status, []) and status != old_status:
        frappe.throw(_(
            "Cannot change status from {0} to {1}. Valid transitions: {2}"
        ).format(old_status, status, ", ".join(valid_transitions.get(old_status, []))))

    doc.status = status

    # Set resolved date when completing
    if status == "Completed" and old_status != "Completed":
        doc.resolved_date = nowdate()

    # Add notes as comment if provided
    if notes:
        doc.add_comment("Comment", f"Status changed to {status}: {notes}")

    doc.save()

    return {
        "success": True,
        "message": _("Request {0} status updated from {1} to {2}").format(
            request_id, old_status, status
        ),
        "request": doc.as_dict()
    }


# ==============================================================================
# RECORD COMPLETION
# ==============================================================================


@frappe.whitelist()
def record_maintenance_completion(
    request_id,
    completion_date,
    technician_name,
    work_description,
    resolution_status,
    actual_cost=None,
    follow_up_needed=False,
    follow_up_notes=None,
    after_photos=None
):
    """
    Record completion of maintenance work.
    Creates BEI Maintenance Completion record and updates request status.

    Args:
        request_id: The maintenance request name
        completion_date: Date work was completed
        technician_name: Name of technician who did the work
        work_description: Description of work performed
        resolution_status: Fully Resolved, Partially Resolved, Not Resolved
        actual_cost: Actual cost incurred (optional)
        follow_up_needed: Whether follow-up is needed
        follow_up_notes: Notes about follow-up (required if follow_up_needed)
        after_photos: Photo URL(s) as proof of completion

    Returns:
        {
            "success": True,
            "message": "...",
            "completion": {...}
        }
    """
    if not request_id:
        frappe.throw(_("Request ID is required"))

    if not frappe.db.exists("BEI Maintenance Request", request_id):
        frappe.throw(_("Maintenance request {0} not found").format(request_id))

    # Validate required fields
    if not completion_date:
        frappe.throw(_("Completion date is required"))

    if not technician_name:
        frappe.throw(_("Technician name is required"))

    if not work_description:
        frappe.throw(_("Work description is required"))

    valid_resolution_statuses = ["Fully Resolved", "Partially Resolved", "Not Resolved"]
    if resolution_status not in valid_resolution_statuses:
        frappe.throw(_("Invalid resolution status. Must be one of: {0}").format(
            ", ".join(valid_resolution_statuses)
        ))

    if follow_up_needed and not follow_up_notes:
        frappe.throw(_("Follow-up notes are required when follow-up is needed"))

    if not after_photos:
        frappe.throw(_("At least one after photo is required as proof of completion"))

    request_doc = frappe.get_doc("BEI Maintenance Request", request_id)

    # Check if completion already exists
    if request_doc.completion:
        frappe.throw(_("Completion record already exists: {0}").format(request_doc.completion))

    # Create completion record
    completion = frappe.new_doc("BEI Maintenance Completion")
    completion.maintenance_request = request_id
    completion.store = request_doc.store
    completion.completion_date = completion_date
    completion.status = "Pending Verification"
    completion.resolution_status = resolution_status
    completion.technician_name = technician_name
    completion.work_description = work_description

    if actual_cost is not None:
        completion.actual_cost = flt(actual_cost)

    completion.follow_up_needed = 1 if follow_up_needed else 0
    if follow_up_notes:
        completion.follow_up_notes = follow_up_notes

    # Handle after photos (single or multiple)
    if isinstance(after_photos, str):
        try:
            after_photos = json.loads(after_photos)
        except json.JSONDecodeError:
            # It's a single URL string
            pass

    if isinstance(after_photos, list):
        # Take first photo for the main field (TODO: add child table for multiple)
        completion.after_photos = after_photos[0] if after_photos else None
    else:
        completion.after_photos = after_photos

    completion.submitted_by = frappe.session.user
    completion.submitted_at = now_datetime()

    completion.insert()

    # Update request with completion link and status
    request_doc.completion = completion.name
    request_doc.status = "Completed"
    request_doc.resolved_date = completion_date
    request_doc.save()

    return {
        "success": True,
        "message": _("Completion recorded for {0}. Pending store verification.").format(request_id),
        "completion": completion.as_dict()
    }


# ==============================================================================
# DASHBOARD STATS
# ==============================================================================


@frappe.whitelist()
def get_maintenance_dashboard_stats(date_from=None, date_to=None, store=None):
    """
    Get aggregated stats for Projects dashboard.

    Args:
        date_from: Filter by request_date >= date_from
        date_to: Filter by request_date <= date_to
        store: Filter by specific store

    Returns:
        {
            "total_open": int,
            "total_assigned": int,
            "total_in_progress": int,
            "total_completed_pending_verification": int,
            "urgent_count": int,
            "by_category": {"Electrical": 5, "Plumbing": 3, ...},
            "by_store": {"BGC": 10, "Makati": 8, ...},
            "avg_resolution_days": float,
            "total_cost_mtd": float
        }
    """
    # Build filter conditions
    conditions = []
    values = {}

    if date_from:
        conditions.append("mr.request_date >= %(date_from)s")
        values["date_from"] = date_from

    if date_to:
        conditions.append("mr.request_date <= %(date_to)s")
        values["date_to"] = date_to

    if store:
        conditions.append("mr.store = %(store)s")
        values["store"] = store

    where_clause = " AND " + " AND ".join(conditions) if conditions else ""

    # Get status counts
    status_counts = frappe.db.sql(f"""
        SELECT
            status,
            COUNT(*) as count
        FROM `tabBEI Maintenance Request` mr
        WHERE 1=1 {where_clause}
        GROUP BY status
    """, values, as_dict=True)

    status_map = {row.status: row.count for row in status_counts}

    # Count completed with pending verification
    completed_pending_sql = f"""
        SELECT COUNT(*) as count
        FROM `tabBEI Maintenance Request` mr
        JOIN `tabBEI Maintenance Completion` mc ON mc.maintenance_request = mr.name
        WHERE mr.status = 'Completed'
        AND mc.status = 'Pending Verification'
        {where_clause}
    """
    completed_pending = frappe.db.sql(completed_pending_sql, values, as_dict=True)[0].count

    # Get urgent count (across all non-closed statuses)
    urgent_sql = f"""
        SELECT COUNT(*) as count
        FROM `tabBEI Maintenance Request` mr
        WHERE mr.priority = 'Urgent'
        AND mr.status NOT IN ('Verified', 'Cancelled')
        {where_clause}
    """
    urgent_count = frappe.db.sql(urgent_sql, values, as_dict=True)[0].count

    # Get counts by category
    category_sql = f"""
        SELECT
            issue_category,
            COUNT(*) as count
        FROM `tabBEI Maintenance Request` mr
        WHERE mr.status NOT IN ('Verified', 'Cancelled')
        {where_clause}
        GROUP BY issue_category
    """
    category_counts = frappe.db.sql(category_sql, values, as_dict=True)
    by_category = {row.issue_category: row.count for row in category_counts}

    # Get counts by store
    store_sql = f"""
        SELECT
            store_code,
            COUNT(*) as count
        FROM `tabBEI Maintenance Request` mr
        WHERE mr.status NOT IN ('Verified', 'Cancelled')
        {where_clause}
        GROUP BY store_code
    """
    store_counts = frappe.db.sql(store_sql, values, as_dict=True)
    by_store = {row.store_code: row.count for row in store_counts}

    # Calculate average resolution time (for completed/verified requests)
    resolution_sql = f"""
        SELECT
            AVG(DATEDIFF(mr.resolved_date, mr.request_date)) as avg_days
        FROM `tabBEI Maintenance Request` mr
        WHERE mr.status IN ('Completed', 'Verified')
        AND mr.resolved_date IS NOT NULL
        {where_clause}
    """
    resolution_result = frappe.db.sql(resolution_sql, values, as_dict=True)
    avg_resolution_days = flt(resolution_result[0].avg_days) if resolution_result[0].avg_days else 0

    # Get total cost MTD (from completion records)
    today = nowdate()
    mtd_start = today[:8] + "01"  # First day of current month

    cost_sql = """
        SELECT COALESCE(SUM(mc.actual_cost), 0) as total_cost
        FROM `tabBEI Maintenance Completion` mc
        WHERE mc.completion_date >= %(mtd_start)s
        AND mc.completion_date <= %(today)s
    """
    cost_values = {"mtd_start": mtd_start, "today": today}
    if store:
        cost_sql += " AND mc.store = %(store)s"
        cost_values["store"] = store

    cost_result = frappe.db.sql(cost_sql, cost_values, as_dict=True)
    total_cost_mtd = flt(cost_result[0].total_cost) if cost_result else 0

    return {
        "total_open": status_map.get("Open", 0),
        "total_assigned": status_map.get("Assigned", 0),
        "total_in_progress": status_map.get("In Progress", 0),
        "total_completed_pending_verification": completed_pending,
        "total_verified": status_map.get("Verified", 0),
        "total_cancelled": status_map.get("Cancelled", 0),
        "urgent_count": urgent_count,
        "by_category": by_category,
        "by_store": by_store,
        "avg_resolution_days": round(avg_resolution_days, 1),
        "total_cost_mtd": total_cost_mtd
    }


# ==============================================================================
# EXPORT REQUESTS
# ==============================================================================


@frappe.whitelist()
def export_maintenance_requests(
    status=None,
    date_from=None,
    date_to=None,
    store=None,
    format="xlsx"
):
    """
    Export maintenance requests to Excel file.

    Args:
        status: Filter by status (can be comma-separated)
        date_from: Filter by request_date >= date_from
        date_to: Filter by request_date <= date_to
        store: Filter by specific store
        format: Export format (xlsx or csv)

    Returns:
        {"file_url": "..."} - URL to download the file
    """
    # Get filtered requests
    result = get_maintenance_queue(
        status=status,
        date_from=date_from,
        date_to=date_to,
        store=store,
        page=1,
        page_size=10000  # Get all matching records
    )

    requests = result.get("requests", [])

    if not requests:
        frappe.throw(_("No requests found matching the filters"))

    # Prepare data for export
    export_data = []
    headers = [
        "Request ID", "Store", "Store Code", "Request Date", "Status", "Priority",
        "Category", "Equipment/Area", "Description", "Assigned To", "Vendor",
        "Scheduled Date", "Estimated Cost", "Resolved Date", "Age (Days)",
        "Reported By", "Reported At"
    ]

    for req in requests:
        export_data.append([
            req.get("name", ""),
            req.get("store", ""),
            req.get("store_code", ""),
            str(req.get("request_date", "")),
            req.get("status", ""),
            req.get("priority", ""),
            req.get("issue_category", ""),
            req.get("equipment_area", ""),
            (req.get("description", "") or "")[:500],  # Truncate long descriptions
            req.get("assignee_name", "") or req.get("assigned_to", ""),
            req.get("vendor", ""),
            str(req.get("scheduled_date", "") or ""),
            flt(req.get("estimated_cost", 0)),
            str(req.get("resolved_date", "") or ""),
            req.get("age_days", 0),
            req.get("reporter_name", "") or req.get("reported_by", ""),
            str(req.get("reported_at", "") or "")
        ])

    # Generate file
    from frappe.utils.xlsxutils import make_xlsx

    xlsx_data = [headers] + export_data

    filename = f"maintenance_requests_{nowdate()}.xlsx"
    xlsx_file = make_xlsx(xlsx_data, filename)

    # Save file
    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "content": xlsx_file.getvalue(),
        "is_private": 1
    })
    file_doc.insert()

    return {
        "file_url": file_doc.file_url,
        "file_name": filename,
        "record_count": len(requests)
    }


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


@frappe.whitelist()
def get_projects_team_users():
    """
    Get list of users with Projects User role for assignment dropdown.

    Returns:
        {"users": [{"name": "user@email.com", "full_name": "User Name"}, ...]}
    """
    users = frappe.db.sql("""
        SELECT DISTINCT u.name, u.full_name
        FROM `tabUser` u
        JOIN `tabHas Role` hr ON hr.parent = u.name
        WHERE hr.role = 'Projects User'
        AND u.enabled = 1
        ORDER BY u.full_name
    """, as_dict=True)

    return {"users": users}


@frappe.whitelist()
def get_stores_list():
    """
    Get list of stores/warehouses for filter dropdown.

    Returns:
        {"stores": [{"name": "WH-BGC - BEI", "store_code": "BGC"}, ...]}
    """
    stores = frappe.get_all(
        "Warehouse",
        filters={"is_group": 0, "disabled": 0},
        fields=["name", "warehouse_name as store_code"],
        order_by="warehouse_name"
    )

    return {"stores": stores}


@frappe.whitelist()
def get_maintenance_categories():
    """
    Get list of maintenance categories for filter dropdown.

    Returns:
        {"categories": ["Electrical", "Plumbing", ...]}
    """
    # Get categories from DocType options
    meta = frappe.get_meta("BEI Maintenance Request")
    field = meta.get_field("issue_category")

    if field and field.options:
        categories = [opt.strip() for opt in field.options.split("\n") if opt.strip()]
    else:
        categories = ["Electrical", "Plumbing", "Mechanical", "Pest", "Security", "Network", "Architectural", "Other"]

    return {"categories": categories}
