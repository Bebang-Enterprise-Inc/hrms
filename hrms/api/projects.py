# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Projects API
Handles maintenance request management for the Projects team dashboard at my.bebang.ph
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, getdate, date_diff, flt, sbool
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

    valid_statuses = ["Open", "Assigned", "In Progress", "Pending Parts", "Completed", "Verified", "Cancelled"]
    if status not in valid_statuses:
        frappe.throw(_("Invalid status: {0}").format(status))

    if not frappe.db.exists("BEI Maintenance Request", request_id):
        frappe.throw(_("Maintenance request {0} not found").format(request_id))

    doc = frappe.get_doc("BEI Maintenance Request", request_id)
    old_status = doc.status

    # Define valid transitions
    valid_transitions = {
        "Open": ["Assigned", "Cancelled"],
        "Assigned": ["In Progress", "Pending Parts", "Open", "Cancelled"],
        "In Progress": ["Completed", "Pending Parts", "Assigned", "Cancelled"],
        "Pending Parts": ["In Progress", "Assigned", "Cancelled"],
        "Completed": ["Verified", "In Progress", "Open"],  # Verified via store, Open for reopen
        "Verified": ["Open"],  # Can reopen verified requests
        "Cancelled": ["Open"]  # Can reopen cancelled requests
    }

    if status not in valid_transitions.get(old_status, []) and status != old_status:
        frappe.throw(_(
            "Cannot change status from {0} to {1}. Valid transitions: {2}"
        ).format(old_status, status, ", ".join(valid_transitions.get(old_status, []))))

    doc.status = status

    # Set resolved date when completing (only if not already set)
    if status == "Completed" and not doc.resolved_date:
        doc.resolved_date = nowdate()
    # Clear resolved date when reopening
    if status in ["Open", "Assigned", "In Progress", "Pending Parts"]:
        doc.resolved_date = None

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

    if getdate(completion_date) > getdate(nowdate()):
        frappe.throw(_("Completion date cannot be in the future"))

    if not technician_name:
        frappe.throw(_("Technician name is required"))

    if not work_description:
        frappe.throw(_("Work description is required"))

    valid_resolution_statuses = ["Fully Resolved", "Partially Resolved", "Not Resolved"]
    if resolution_status not in valid_resolution_statuses:
        frappe.throw(_("Invalid resolution status. Must be one of: {0}").format(
            ", ".join(valid_resolution_statuses)
        ))

    follow_up_needed = sbool(follow_up_needed)
    if follow_up_needed and not (follow_up_notes and follow_up_notes.strip()):
        frappe.throw(_("Follow-up notes are required when follow-up is needed"))

    # TODO: Re-enable photo requirement once frontend has upload capability
    # if not after_photos:
    #     frappe.throw(_("At least one after photo is required as proof of completion"))

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

    # Reload request to get latest modified timestamp (avoids version conflict)
    request_doc.reload()

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
        "by_status": dict(status_map),
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


# ==============================================================================
# CHARGING WORKFLOW
# ==============================================================================


@frappe.whitelist()
def assess_maintenance_request(request_id, concern_type, notes=None):
    """
    Technician assesses the request and sets concern type.

    Args:
        request_id: The maintenance request name
        concern_type: "Wear & Tear", "Supplier Deficiency", "Contractor Deficiency"
        notes: Optional assessment notes

    Returns:
        {"success": True, "message": "...", "request": {...}}
    """
    if not request_id:
        frappe.throw(_("Request ID is required"))

    valid_concern_types = ["Wear & Tear", "Supplier Deficiency", "Contractor Deficiency"]
    if concern_type not in valid_concern_types:
        frappe.throw(_("Invalid concern type. Must be one of: {0}").format(", ".join(valid_concern_types)))

    if not frappe.db.exists("BEI Maintenance Request", request_id):
        frappe.throw(_("Maintenance request {0} not found").format(request_id))

    doc = frappe.get_doc("BEI Maintenance Request", request_id)
    doc.concern_type = concern_type

    if notes:
        doc.add_comment("Comment", f"Assessment: {notes}")

    doc.save()

    return {
        "success": True,
        "message": _("Request {0} assessed as {1}").format(request_id, concern_type),
        "request": doc.as_dict()
    }


@frappe.whitelist()
def set_maintenance_charge(request_id, charge_amount, charging_reason):
    """
    Set a charge to store for a maintenance request.

    Args:
        request_id: The maintenance request name
        charge_amount: Amount to charge
        charging_reason: Reason for the charge

    Returns:
        {"success": True, "message": "...", "request": {...}}
    """
    if not request_id:
        frappe.throw(_("Request ID is required"))

    if not charge_amount or flt(charge_amount) <= 0:
        frappe.throw(_("Charge amount must be greater than 0"))

    if not charging_reason:
        frappe.throw(_("Charging reason is required"))

    if not frappe.db.exists("BEI Maintenance Request", request_id):
        frappe.throw(_("Maintenance request {0} not found").format(request_id))

    doc = frappe.get_doc("BEI Maintenance Request", request_id)
    doc.charge_to_store = 1
    doc.charge_amount = flt(charge_amount)
    doc.charging_reason = charging_reason
    doc.status = "Pending Acknowledgement"
    doc.save()

    return {
        "success": True,
        "message": _("Charge of {0} set for {1}. Pending store acknowledgement.").format(
            doc.charge_amount, request_id
        ),
        "request": doc.as_dict()
    }


@frappe.whitelist()
def acknowledge_maintenance_charge(request_id):
    """
    Store supervisor acknowledges charge to store.

    Args:
        request_id: The maintenance request name

    Returns:
        {"success": True, "message": "..."}
    """
    if not request_id:
        frappe.throw(_("Request ID is required"))

    if not frappe.db.exists("BEI Maintenance Request", request_id):
        frappe.throw(_("Maintenance request {0} not found").format(request_id))

    doc = frappe.get_doc("BEI Maintenance Request", request_id)

    if not doc.charge_to_store:
        frappe.throw(_("This request has no charge to acknowledge"))

    if doc.store_acknowledged:
        frappe.throw(_("Charge already acknowledged"))

    doc.store_acknowledged = 1
    doc.acknowledged_by = frappe.session.user
    doc.acknowledgement_date = nowdate()
    doc.status = "Verified"
    doc.save()

    return {
        "success": True,
        "message": _("Charge acknowledged for {0}").format(request_id)
    }


@frappe.whitelist()
def get_pending_charges(store=None, page=1, page_size=20):
    """
    Get maintenance requests with pending store charges.

    Args:
        store: Filter by specific store (optional)
        page: Page number (default: 1)
        page_size: Items per page (default: 20)

    Returns:
        {
            "requests": [...],
            "total": int,
            "page": int,
            "page_size": int
        }
    """
    filters = {
        "charge_to_store": 1,
        "store_acknowledged": 0,
        "status": ["in", ["Completed", "Pending Acknowledgement"]]
    }

    if store:
        filters["store"] = store

    page = int(page)
    page_size = int(page_size)

    total = frappe.db.count("BEI Maintenance Request", filters)

    requests = frappe.get_all(
        "BEI Maintenance Request",
        filters=filters,
        fields=[
            "name", "store", "store_code", "request_date", "issue_category",
            "description", "charge_amount", "charging_reason", "concern_type",
            "priority", "status"
        ],
        order_by="request_date desc",
        limit_page_length=page_size,
        limit_start=(page - 1) * page_size
    )

    # Get store names
    for req in requests:
        if req.store:
            req["store_name"] = frappe.db.get_value("Warehouse", req.store, "warehouse_name")

    return {
        "requests": requests,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@frappe.whitelist()
def add_maintenance_materials(request_id, materials):
    """
    Add materials to a maintenance request.

    Args:
        request_id: The maintenance request name
        materials: List of materials [{material, quantity, unit, unit_cost}, ...]

    Returns:
        {"success": True, "message": "...", "request": {...}}
    """
    if not request_id:
        frappe.throw(_("Request ID is required"))

    if not frappe.db.exists("BEI Maintenance Request", request_id):
        frappe.throw(_("Maintenance request {0} not found").format(request_id))

    if isinstance(materials, str):
        try:
            materials = json.loads(materials)
        except (json.JSONDecodeError, ValueError):
            frappe.throw(_("Invalid materials format: must be valid JSON"))

    if not materials or not isinstance(materials, list):
        frappe.throw(_("Materials must be a non-empty list"))

    doc = frappe.get_doc("BEI Maintenance Request", request_id)

    total_materials_cost = 0
    for mat in materials:
        quantity = flt(mat.get("quantity", 1))
        unit_cost = flt(mat.get("unit_cost", 0))

        if quantity <= 0:
            frappe.throw(_("Material quantity must be positive"))
        if unit_cost < 0:
            frappe.throw(_("Material unit cost cannot be negative"))

        total_cost = quantity * unit_cost
        total_materials_cost += total_cost

        doc.append("materials", {
            "material": mat.get("material"),
            "quantity": quantity,
            "unit": mat.get("unit", "pcs"),
            "unit_cost": unit_cost,
            "total_cost": total_cost
        })

    doc.materials_cost = flt(doc.materials_cost or 0) + total_materials_cost
    doc.total_cost = flt(doc.materials_cost) + flt(doc.labor_cost or 0)
    doc.save()

    return {
        "success": True,
        "message": _("{0} materials added to {1}").format(len(materials), request_id),
        "request": doc.as_dict()
    }


@frappe.whitelist()
def update_maintenance_costs(request_id, labor_hours=None, labor_cost=None):
    """
    Update labor costs for a maintenance request.

    Args:
        request_id: The maintenance request name
        labor_hours: Hours of labor
        labor_cost: Cost of labor

    Returns:
        {"success": True, "message": "...", "request": {...}}
    """
    if not request_id:
        frappe.throw(_("Request ID is required"))

    if not frappe.db.exists("BEI Maintenance Request", request_id):
        frappe.throw(_("Maintenance request {0} not found").format(request_id))

    doc = frappe.get_doc("BEI Maintenance Request", request_id)

    if labor_hours is not None:
        doc.labor_hours = flt(labor_hours)

    if labor_cost is not None:
        doc.labor_cost = flt(labor_cost)

    # Recalculate total cost
    doc.total_cost = flt(doc.materials_cost or 0) + flt(doc.labor_cost or 0)
    doc.save()

    return {
        "success": True,
        "message": _("Costs updated for {0}").format(request_id),
        "request": doc.as_dict()
    }


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


# ==============================================================================
# PROJECT MANAGEMENT
# ==============================================================================


@frappe.whitelist()
def get_project_dashboard():
    """
    Get projects grouped by stage for kanban dashboard.

    Returns:
        {
            "pre_design": [...],
            "design": [...],
            ...
            "summary": {"total_active": int, "total_budget": float}
        }
    """
    stages = ["Pre-Design", "Design", "Bidding", "Pre-Construction",
              "Construction", "Post-Construction", "Completed"]

    result = {}
    for stage in stages:
        projects = frappe.get_all(
            "BEI Project",
            filters={"stage": stage, "status": ["!=", "Cancelled"]},
            fields=[
                "name", "project_name", "project_type", "store", "store_code",
                "target_opening_date", "progress_percent", "contract_amount",
                "priority", "project_manager"
            ],
            order_by="priority desc, target_opening_date asc"
        )

        # Get project manager names
        for proj in projects:
            if proj.project_manager:
                proj["project_manager_name"] = frappe.db.get_value(
                    "Employee", proj.project_manager, "employee_name"
                )

        key = stage.lower().replace("-", "_").replace(" ", "_")
        result[key] = projects

    # Summary stats
    total_active = frappe.db.count("BEI Project", {
        "stage": ["not in", ["Completed", "Cancelled", "On Hold"]],
        "status": ["!=", "Cancelled"]
    })

    total_budget = frappe.db.sql("""
        SELECT COALESCE(SUM(contract_amount), 0)
        FROM `tabBEI Project`
        WHERE stage NOT IN ('Completed', 'Cancelled', 'On Hold')
        AND status != 'Cancelled'
    """)[0][0]

    result["summary"] = {
        "total_active": total_active,
        "total_budget": flt(total_budget),
        "stages": stages
    }

    return result


@frappe.whitelist()
def get_project_detail(project):
    """
    Get full project detail with related documents.

    Args:
        project: The project name (e.g., PROJ-2026-0001)

    Returns:
        {
            "project": {...},
            "site_inspections": [...],
            "bids": [...],
            "permits": [...],
            "milestones": [...],
            "open_punchlist": [...],
            "punchlist_count": int
        }
    """
    if not project:
        frappe.throw(_("Project name is required"))

    if not frappe.db.exists("BEI Project", project):
        frappe.throw(_("Project {0} not found").format(project))

    doc = frappe.get_doc("BEI Project", project)
    project_data = doc.as_dict()

    # Get project manager name
    if doc.project_manager:
        project_data["project_manager_name"] = frappe.db.get_value(
            "Employee", doc.project_manager, "employee_name"
        )

    # Get contractor name
    if doc.contractor:
        project_data["contractor_name"] = frappe.db.get_value(
            "BEI Supplier", doc.contractor, "supplier_name"
        )

    # Get site inspections
    site_inspections = frappe.get_all(
        "BEI Site Inspection",
        filters={"project": project},
        fields=["name", "inspection_date", "inspection_type", "status",
                "overall_status", "inspector_name"],
        order_by="inspection_date desc"
    )

    # Get bids
    bids = frappe.get_all(
        "BEI Project Bid",
        filters={"project": project},
        fields=["name", "contractor", "contractor_name", "total_amount",
                "final_amount", "status", "is_awarded", "submission_date"],
        order_by="submission_date desc"
    )

    # Get permits
    permits = frappe.get_all(
        "BEI Project Permit",
        filters={"project": project},
        fields=["name", "permit_type", "status", "permit_number",
                "approval_date", "expiry_date"],
        order_by="permit_type"
    )

    # Get milestones
    milestones = frappe.get_all(
        "BEI Project Milestone",
        filters={"project": project},
        fields=["name", "milestone_name", "milestone_type", "status",
                "target_date", "actual_date", "completion_percentage",
                "billing_amount", "payment_status"],
        order_by="sequence asc"
    )

    # Get open punchlist items
    punchlist = frappe.get_all(
        "BEI Punchlist Item",
        filters={"project": project, "status": ["not in", ["Closed", "Waived"]]},
        fields=["name", "category", "severity", "status", "location",
                "description", "due_date"],
        order_by="severity desc, due_date asc"
    )

    # Count total punchlist items
    total_punchlist = frappe.db.count("BEI Punchlist Item", {"project": project})
    closed_punchlist = frappe.db.count("BEI Punchlist Item", {
        "project": project,
        "status": ["in", ["Closed", "Waived"]]
    })

    return {
        "project": project_data,
        "site_inspections": site_inspections,
        "bids": bids,
        "permits": permits,
        "milestones": milestones,
        "open_punchlist": punchlist,
        "punchlist_count": {
            "total": total_punchlist,
            "open": len(punchlist),
            "closed": closed_punchlist
        }
    }


@frappe.whitelist()
def advance_project_stage(project, new_stage, notes=None):
    """
    Move project to a new stage.

    Args:
        project: The project name
        new_stage: The new stage
        notes: Optional notes for the stage change

    Returns:
        {"success": True, "message": "...", "project": {...}}
    """
    valid_stages = ["Pre-Design", "Design", "Bidding", "Pre-Construction",
                    "Construction", "Post-Construction", "Completed",
                    "On Hold", "Cancelled"]

    if new_stage not in valid_stages:
        frappe.throw(_("Invalid stage: {0}").format(new_stage))

    if not frappe.db.exists("BEI Project", project):
        frappe.throw(_("Project {0} not found").format(project))

    doc = frappe.get_doc("BEI Project", project)
    old_stage = doc.stage
    doc.stage = new_stage
    doc.last_update_date = nowdate()

    if notes:
        doc.notes = notes
        doc.add_comment("Comment", f"Stage changed from {old_stage} to {new_stage}: {notes}")

    # Update status based on stage
    if new_stage == "Completed":
        doc.status = "Completed"
        doc.actual_completion_date = nowdate()
    elif new_stage in ["On Hold", "Cancelled"]:
        doc.status = new_stage
    else:
        doc.status = "Active"

    doc.save()

    return {
        "success": True,
        "message": _("Project {0} moved from {1} to {2}").format(
            project, old_stage, new_stage
        ),
        "project": doc.as_dict()
    }


@frappe.whitelist()
def update_project_progress(project, progress_percent, notes=None):
    """
    Update project progress percentage.

    Args:
        project: The project name
        progress_percent: New progress percentage (0-100)
        notes: Optional progress notes

    Returns:
        {"success": True, "message": "...", "project": {...}}
    """
    if not frappe.db.exists("BEI Project", project):
        frappe.throw(_("Project {0} not found").format(project))

    progress = flt(progress_percent)
    if progress < 0 or progress > 100:
        frappe.throw(_("Progress must be between 0 and 100"))

    doc = frappe.get_doc("BEI Project", project)
    doc.progress_percent = progress
    doc.last_update_date = nowdate()

    if notes:
        doc.notes = notes

    doc.save()

    return {
        "success": True,
        "message": _("Project {0} progress updated to {1}%").format(project, progress),
        "project": doc.as_dict()
    }


# ==============================================================================
# SITE INSPECTIONS
# ==============================================================================


@frappe.whitelist()
def submit_site_inspection(inspection_id):
    """
    Submit a site inspection for approval.

    Args:
        inspection_id: The site inspection name

    Returns:
        {"success": True, "message": "...", "inspection": {...}}
    """
    if not frappe.db.exists("BEI Site Inspection", inspection_id):
        frappe.throw(_("Site inspection {0} not found").format(inspection_id))

    doc = frappe.get_doc("BEI Site Inspection", inspection_id)

    if doc.status != "Draft":
        frappe.throw(_("Only draft inspections can be submitted"))

    doc.status = "Submitted"
    doc.submitted_by = frappe.session.user
    doc.submitted_at = now_datetime()
    doc.save()

    return {
        "success": True,
        "message": _("Site inspection {0} submitted for approval").format(inspection_id),
        "inspection": doc.as_dict()
    }


@frappe.whitelist()
def approve_site_inspection(inspection_id, approval_notes=None):
    """
    Approve a submitted site inspection.

    Args:
        inspection_id: The site inspection name
        approval_notes: Optional approval notes

    Returns:
        {"success": True, "message": "...", "inspection": {...}}
    """
    if not frappe.db.exists("BEI Site Inspection", inspection_id):
        frappe.throw(_("Site inspection {0} not found").format(inspection_id))

    doc = frappe.get_doc("BEI Site Inspection", inspection_id)

    if doc.status != "Submitted":
        frappe.throw(_("Only submitted inspections can be approved"))

    doc.status = "Approved"
    doc.approved_by = frappe.session.user
    doc.approved_date = nowdate()

    if approval_notes:
        doc.add_comment("Comment", f"Approved: {approval_notes}")

    doc.save()

    return {
        "success": True,
        "message": _("Site inspection {0} approved").format(inspection_id),
        "inspection": doc.as_dict()
    }


@frappe.whitelist()
def reject_site_inspection(inspection_id, rejection_reason):
    """
    Reject a submitted site inspection.

    Args:
        inspection_id: The site inspection name
        rejection_reason: Reason for rejection

    Returns:
        {"success": True, "message": "...", "inspection": {...}}
    """
    if not rejection_reason:
        frappe.throw(_("Rejection reason is required"))

    if not frappe.db.exists("BEI Site Inspection", inspection_id):
        frappe.throw(_("Site inspection {0} not found").format(inspection_id))

    doc = frappe.get_doc("BEI Site Inspection", inspection_id)

    if doc.status != "Submitted":
        frappe.throw(_("Only submitted inspections can be rejected"))

    doc.status = "Rejected"
    doc.rejection_reason = rejection_reason
    doc.save()

    return {
        "success": True,
        "message": _("Site inspection {0} rejected").format(inspection_id),
        "inspection": doc.as_dict()
    }


# ==============================================================================
# BID MANAGEMENT
# ==============================================================================


@frappe.whitelist()
def get_bid_comparison(project):
    """
    Get bid comparison for a project.

    Args:
        project: The project name

    Returns:
        {
            "project": {...},
            "bids": [...],
            "lowest_bid": {...} or None,
            "awarded_bid": {...} or None
        }
    """
    if not frappe.db.exists("BEI Project", project):
        frappe.throw(_("Project {0} not found").format(project))

    project_doc = frappe.get_doc("BEI Project", project)

    bids = frappe.get_all(
        "BEI Project Bid",
        filters={"project": project, "status": ["!=", "Withdrawn"]},
        fields=[
            "name", "contractor", "contractor_name", "submission_date",
            "base_amount", "vat_amount", "total_amount", "final_amount",
            "status", "technical_score", "financial_score", "overall_score",
            "is_awarded"
        ],
        order_by="total_amount asc"
    )

    lowest_bid = bids[0] if bids else None
    awarded_bid = next((b for b in bids if b.is_awarded), None)

    return {
        "project": {
            "name": project_doc.name,
            "project_name": project_doc.project_name,
            "approved_budget": project_doc.approved_budget
        },
        "bids": bids,
        "lowest_bid": lowest_bid,
        "awarded_bid": awarded_bid,
        "bid_count": len(bids)
    }


@frappe.whitelist()
def evaluate_bid(bid_id, technical_score, financial_score, evaluation_notes=None):
    """
    Evaluate a project bid.

    Args:
        bid_id: The bid name
        technical_score: Technical evaluation score (0-100)
        financial_score: Financial evaluation score (0-100)
        evaluation_notes: Optional notes

    Returns:
        {"success": True, "message": "...", "bid": {...}}
    """
    if not frappe.db.exists("BEI Project Bid", bid_id):
        frappe.throw(_("Bid {0} not found").format(bid_id))

    tech = flt(technical_score)
    fin = flt(financial_score)

    if tech < 0 or tech > 100 or fin < 0 or fin > 100:
        frappe.throw(_("Scores must be between 0 and 100"))

    doc = frappe.get_doc("BEI Project Bid", bid_id)
    doc.technical_score = tech
    doc.financial_score = fin
    doc.overall_score = (tech * 0.6) + (fin * 0.4)  # 60% technical, 40% financial
    doc.status = "Under Review"

    if evaluation_notes:
        doc.evaluation_notes = evaluation_notes

    doc.save()

    return {
        "success": True,
        "message": _("Bid {0} evaluated with overall score {1}%").format(
            bid_id, round(doc.overall_score, 1)
        ),
        "bid": doc.as_dict()
    }


@frappe.whitelist()
def award_bid(bid_id, final_amount=None, award_notes=None):
    """
    Award a bid to a contractor.

    Args:
        bid_id: The bid name
        final_amount: Negotiated final amount (optional)
        award_notes: Award notes (optional)

    Returns:
        {"success": True, "message": "...", "bid": {...}}
    """
    if not frappe.db.exists("BEI Project Bid", bid_id):
        frappe.throw(_("Bid {0} not found").format(bid_id))

    doc = frappe.get_doc("BEI Project Bid", bid_id)

    # Check no other bid is awarded for this project
    existing_award = frappe.db.exists("BEI Project Bid", {
        "project": doc.project,
        "is_awarded": 1,
        "name": ["!=", bid_id]
    })

    if existing_award:
        frappe.throw(_("Another bid is already awarded for this project"))

    doc.is_awarded = 1
    doc.status = "Awarded"
    doc.award_date = nowdate()
    doc.awarded_by = frappe.session.user

    if final_amount:
        doc.final_amount = flt(final_amount)
    else:
        doc.final_amount = doc.total_amount

    if award_notes:
        doc.award_notes = award_notes

    doc.save()

    # Update project with contractor info
    project = frappe.get_doc("BEI Project", doc.project)
    project.contractor = doc.contractor
    project.contract_amount = doc.final_amount
    project.save()

    # Mark other bids as not awarded
    frappe.db.sql("""
        UPDATE `tabBEI Project Bid`
        SET status = 'Not Awarded'
        WHERE project = %s AND name != %s AND status NOT IN ('Withdrawn', 'Awarded')
    """, (doc.project, bid_id))

    return {
        "success": True,
        "message": _("Bid {0} awarded to {1}").format(bid_id, doc.contractor_name),
        "bid": doc.as_dict()
    }


# ==============================================================================
# MILESTONES
# ==============================================================================


@frappe.whitelist()
def complete_milestone(milestone_id, actual_date=None, notes=None):
    """
    Mark a milestone as completed.

    Args:
        milestone_id: The milestone name
        actual_date: Actual completion date (defaults to today)
        notes: Completion notes

    Returns:
        {"success": True, "message": "...", "milestone": {...}}
    """
    if not frappe.db.exists("BEI Project Milestone", milestone_id):
        frappe.throw(_("Milestone {0} not found").format(milestone_id))

    doc = frappe.get_doc("BEI Project Milestone", milestone_id)
    doc.status = "Completed"
    doc.completion_percentage = 100
    doc.actual_date = actual_date or nowdate()

    # Calculate variance
    if doc.target_date and doc.actual_date:
        doc.days_variance = date_diff(doc.actual_date, doc.target_date)

    doc.save()

    # Update project progress based on completed milestones
    _update_project_progress_from_milestones(doc.project)

    return {
        "success": True,
        "message": _("Milestone {0} completed").format(doc.milestone_name),
        "milestone": doc.as_dict()
    }


@frappe.whitelist()
def verify_milestone(milestone_id, verification_notes=None):
    """
    Verify a completed milestone.

    Args:
        milestone_id: The milestone name
        verification_notes: Verification notes

    Returns:
        {"success": True, "message": "...", "milestone": {...}}
    """
    if not frappe.db.exists("BEI Project Milestone", milestone_id):
        frappe.throw(_("Milestone {0} not found").format(milestone_id))

    doc = frappe.get_doc("BEI Project Milestone", milestone_id)

    if doc.status != "Completed":
        frappe.throw(_("Only completed milestones can be verified"))

    doc.status = "Verified"
    doc.verified = 1
    doc.verified_by = frappe.session.user
    doc.verification_date = nowdate()

    if verification_notes:
        doc.verification_notes = verification_notes

    doc.save()

    return {
        "success": True,
        "message": _("Milestone {0} verified").format(doc.milestone_name),
        "milestone": doc.as_dict()
    }


@frappe.whitelist()
def create_milestone_billing(milestone_id):
    """
    Create a payment request for a verified milestone.

    Args:
        milestone_id: The milestone name

    Returns:
        {"success": True, "message": "...", "milestone": {...}, "payment_request": {...}}
    """
    if not frappe.db.exists("BEI Project Milestone", milestone_id):
        frappe.throw(_("Milestone {0} not found").format(milestone_id))

    doc = frappe.get_doc("BEI Project Milestone", milestone_id)

    if doc.status != "Verified":
        frappe.throw(_("Only verified milestones can be billed"))

    if doc.payment_request:
        frappe.throw(_("Payment request already exists: {0}").format(doc.payment_request))

    if not doc.billing_amount or flt(doc.billing_amount) <= 0:
        frappe.throw(_("Billing amount must be greater than 0"))

    # Get project details
    project = frappe.get_doc("BEI Project", doc.project)

    # Create payment request
    payment_request = frappe.new_doc("BEI Payment Request")
    payment_request.supplier = project.contractor
    payment_request.amount = doc.billing_amount
    payment_request.description = f"Progress billing for {project.project_name} - {doc.milestone_name}"
    payment_request.insert()

    # Link payment request to milestone
    doc.payment_request = payment_request.name
    doc.payment_status = "Billed"
    doc.save()

    return {
        "success": True,
        "message": _("Payment request {0} created for milestone {1}").format(
            payment_request.name, doc.milestone_name
        ),
        "milestone": doc.as_dict(),
        "payment_request": payment_request.as_dict()
    }


def _update_project_progress_from_milestones(project_name):
    """
    Internal: Update project progress based on milestone completion.
    """
    milestones = frappe.get_all(
        "BEI Project Milestone",
        filters={"project": project_name},
        fields=["completion_percentage"]
    )

    if milestones:
        avg_progress = sum(m.completion_percentage or 0 for m in milestones) / len(milestones)
        frappe.db.set_value("BEI Project", project_name, "progress_percent", avg_progress)


# ==============================================================================
# PUNCHLIST
# ==============================================================================


@frappe.whitelist()
def get_punchlist(project, status=None, category=None, severity=None, page=1, page_size=50):
    """
    Get punchlist items for a project.

    Args:
        project: The project name
        status: Filter by status (optional)
        category: Filter by category (optional)
        severity: Filter by severity (optional)
        page: Page number
        page_size: Items per page

    Returns:
        {
            "items": [...],
            "total": int,
            "page": int,
            "summary": {...}
        }
    """
    if not frappe.db.exists("BEI Project", project):
        frappe.throw(_("Project {0} not found").format(project))

    filters = {"project": project}

    if status:
        filters["status"] = status

    if category:
        filters["category"] = category

    if severity:
        filters["severity"] = severity

    page = int(page)
    page_size = int(page_size)

    total = frappe.db.count("BEI Punchlist Item", filters)

    items = frappe.get_all(
        "BEI Punchlist Item",
        filters=filters,
        fields=[
            "name", "category", "severity", "status", "location",
            "description", "due_date", "assigned_to", "contractor",
            "photo", "resolved_date"
        ],
        order_by="severity desc, status asc, due_date asc",
        limit_page_length=page_size,
        limit_start=(page - 1) * page_size
    )

    # Get summary by severity
    summary = {}
    for sev in ["Critical", "Major", "Minor", "Cosmetic"]:
        summary[sev.lower()] = frappe.db.count("BEI Punchlist Item", {
            "project": project,
            "severity": sev,
            "status": ["not in", ["Closed", "Waived"]]
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": summary
    }


@frappe.whitelist()
def add_punchlist_item(
    project,
    category,
    location,
    description,
    severity="Minor",
    photo=None,
    assigned_to=None,
    contractor=None,
    due_date=None
):
    """
    Add a punchlist item to a project.

    Args:
        project: The project name
        category: Issue category
        location: Location in the project
        description: Issue description
        severity: Critical, Major, Minor, Cosmetic (default: Minor)
        photo: Photo attachment (optional)
        assigned_to: Assigned user (optional)
        contractor: Assigned contractor (optional)
        due_date: Due date (optional)

    Returns:
        {"success": True, "message": "...", "item": {...}}
    """
    if not frappe.db.exists("BEI Project", project):
        frappe.throw(_("Project {0} not found").format(project))

    doc = frappe.new_doc("BEI Punchlist Item")
    doc.project = project
    doc.category = category
    doc.location = location
    doc.description = description
    doc.severity = severity
    doc.status = "Open"
    doc.reported_by = frappe.session.user
    doc.reported_at = now_datetime()

    if photo:
        doc.photo = photo

    if assigned_to:
        doc.assigned_to = assigned_to

    if contractor:
        doc.contractor = contractor

    if due_date:
        doc.due_date = due_date

    doc.insert()

    return {
        "success": True,
        "message": _("Punchlist item {0} created").format(doc.name),
        "item": doc.as_dict()
    }


@frappe.whitelist()
def resolve_punchlist_item(item_id, resolution_notes, after_photo=None):
    """
    Mark a punchlist item as resolved.

    Args:
        item_id: The punchlist item name
        resolution_notes: Notes about the resolution
        after_photo: Photo after fix (optional)

    Returns:
        {"success": True, "message": "...", "item": {...}}
    """
    if not resolution_notes:
        frappe.throw(_("Resolution notes are required"))

    if not frappe.db.exists("BEI Punchlist Item", item_id):
        frappe.throw(_("Punchlist item {0} not found").format(item_id))

    doc = frappe.get_doc("BEI Punchlist Item", item_id)

    if doc.status in ["Closed", "Waived"]:
        frappe.throw(_("Item is already closed"))

    doc.status = "Resolved"
    doc.resolution_notes = resolution_notes
    doc.resolved_date = nowdate()
    doc.resolved_by = frappe.session.user

    if after_photo:
        doc.after_photo = after_photo

    doc.save()

    return {
        "success": True,
        "message": _("Punchlist item {0} resolved").format(item_id),
        "item": doc.as_dict()
    }


@frappe.whitelist()
def close_punchlist_item(item_id):
    """
    Close a resolved punchlist item after verification.

    Args:
        item_id: The punchlist item name

    Returns:
        {"success": True, "message": "...", "item": {...}}
    """
    if not frappe.db.exists("BEI Punchlist Item", item_id):
        frappe.throw(_("Punchlist item {0} not found").format(item_id))

    doc = frappe.get_doc("BEI Punchlist Item", item_id)

    if doc.status != "Resolved":
        frappe.throw(_("Only resolved items can be closed"))

    doc.status = "Closed"
    doc.verified = 1
    doc.verified_by = frappe.session.user
    doc.verification_date = nowdate()
    doc.save()

    return {
        "success": True,
        "message": _("Punchlist item {0} closed").format(item_id),
        "item": doc.as_dict()
    }


@frappe.whitelist()
def waive_punchlist_item(item_id, reason):
    """
    Waive a punchlist item (accept as-is).

    Args:
        item_id: The punchlist item name
        reason: Reason for waiving

    Returns:
        {"success": True, "message": "...", "item": {...}}
    """
    if not reason:
        frappe.throw(_("Waiver reason is required"))

    if not frappe.db.exists("BEI Punchlist Item", item_id):
        frappe.throw(_("Punchlist item {0} not found").format(item_id))

    doc = frappe.get_doc("BEI Punchlist Item", item_id)

    if doc.status in ["Closed", "Waived"]:
        frappe.throw(_("Item is already closed"))

    doc.status = "Waived"
    doc.resolution_notes = f"WAIVED: {reason}"
    doc.resolved_date = nowdate()
    doc.resolved_by = frappe.session.user
    doc.save()

    return {
        "success": True,
        "message": _("Punchlist item {0} waived").format(item_id),
        "item": doc.as_dict()
    }


# ==============================================================================
# PERMIT MANAGEMENT
# ==============================================================================


@frappe.whitelist()
def get_permit_checklist(project):
    """
    Get permit status checklist for a project.

    Args:
        project: The project name

    Returns:
        {
            "project": {...},
            "permits": [...],
            "summary": {"total": int, "approved": int, "pending": int}
        }
    """
    if not frappe.db.exists("BEI Project", project):
        frappe.throw(_("Project {0} not found").format(project))

    project_doc = frappe.get_doc("BEI Project", project)

    permits = frappe.get_all(
        "BEI Project Permit",
        filters={"project": project},
        fields=[
            "name", "permit_type", "permit_number", "status",
            "issuing_authority", "application_date", "approval_date",
            "expiry_date", "total_fees"
        ],
        order_by="permit_type"
    )

    # Summary
    total = len(permits)
    approved = len([p for p in permits if p.status == "Approved"])
    pending = len([p for p in permits if p.status in ["Not Started", "In Progress", "Pending Requirements", "Submitted"]])

    return {
        "project": {
            "name": project_doc.name,
            "project_name": project_doc.project_name,
            "store_code": project_doc.store_code
        },
        "permits": permits,
        "summary": {
            "total": total,
            "approved": approved,
            "pending": pending,
            "completion_rate": round((approved / total * 100), 1) if total > 0 else 0
        }
    }


@frappe.whitelist()
def update_permit_status(permit_id, status, permit_number=None, approval_date=None, expiry_date=None, remarks=None):
    """
    Update permit status and details.

    Args:
        permit_id: The permit name
        status: New status
        permit_number: Permit number (if approved)
        approval_date: Approval date (if approved)
        expiry_date: Expiry date (if applicable)
        remarks: Optional remarks

    Returns:
        {"success": True, "message": "...", "permit": {...}}
    """
    valid_statuses = ["Not Started", "In Progress", "Pending Requirements",
                      "Submitted", "Approved", "Rejected", "Expired", "Renewed"]

    if status not in valid_statuses:
        frappe.throw(_("Invalid status: {0}").format(status))

    if not frappe.db.exists("BEI Project Permit", permit_id):
        frappe.throw(_("Permit {0} not found").format(permit_id))

    doc = frappe.get_doc("BEI Project Permit", permit_id)
    old_status = doc.status
    doc.status = status

    if permit_number:
        doc.permit_number = permit_number

    if approval_date:
        doc.approval_date = approval_date

    if expiry_date:
        doc.expiry_date = expiry_date

    if remarks:
        doc.remarks = remarks

    # Calculate total fees
    doc.total_fees = flt(doc.application_fee or 0) + flt(doc.permit_fee or 0)

    doc.save()

    return {
        "success": True,
        "message": _("Permit {0} status updated from {1} to {2}").format(
            doc.permit_type, old_status, status
        ),
        "permit": doc.as_dict()
    }
