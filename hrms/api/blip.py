"""
Blip AI Assistant - Frappe API Endpoints

These endpoints are called by the Blip service to fetch data
from Frappe with proper permission checking.
"""

import frappe
from frappe import _
from datetime import datetime, date, timedelta


# ==================== User Context ====================

@frappe.whitelist(allow_guest=True)
def get_user_context(email: str = None) -> dict:
    """
    Get user context for permission checking.

    Args:
        email: User's email address

    Returns:
        User context with employee info, roles, store, area
    """
    if not email:
        return {}

    context = {
        "email": email,
        "is_admin": False,
        "roles": [],
        "employee": None,
        "employee_name": None,
        "store": None,
        "area": None
    }

    try:
        # Check if user exists
        if not frappe.db.exists("User", email):
            return context

        # Get user roles
        roles = frappe.get_roles(email)
        context["roles"] = roles
        context["is_admin"] = "System Manager" in roles or "Administrator" in roles

        # Get employee info
        employee = frappe.db.get_value(
            "Employee",
            {"user_id": email, "status": "Active"},
            ["name", "employee_name", "custom_store", "custom_area"],
            as_dict=True
        )

        if employee:
            context["employee"] = employee.name
            context["employee_name"] = employee.employee_name
            context["store"] = employee.custom_store
            context["area"] = employee.custom_area

    except Exception as e:
        frappe.log_error(f"Error getting user context: {e}", "Blip API")

    return context


# ==================== HR Data ====================

@frappe.whitelist(allow_guest=True)
def get_leave_balance(employee: str = None, email: str = None) -> dict:
    """Get leave balance for an employee."""
    try:
        # Resolve employee
        emp = _resolve_employee(employee, email)
        if not emp:
            return {"error": "Employee not found"}

        # Get leave allocations
        allocations = frappe.get_all(
            "Leave Allocation",
            filters={
                "employee": emp,
                "docstatus": 1,
                "from_date": ["<=", frappe.utils.today()],
                "to_date": [">=", frappe.utils.today()]
            },
            fields=["leave_type", "total_leaves_allocated", "new_leaves_allocated"]
        )

        # Get leave taken
        balances = []
        for alloc in allocations:
            taken = frappe.db.sql("""
                SELECT COALESCE(SUM(total_leave_days), 0) as taken
                FROM `tabLeave Application`
                WHERE employee = %s
                AND leave_type = %s
                AND docstatus = 1
                AND status = 'Approved'
                AND from_date >= (
                    SELECT from_date FROM `tabLeave Allocation`
                    WHERE employee = %s AND leave_type = %s AND docstatus = 1
                    ORDER BY from_date DESC LIMIT 1
                )
            """, (emp, alloc.leave_type, emp, alloc.leave_type), as_dict=True)

            taken_days = taken[0].taken if taken else 0
            balance = alloc.total_leaves_allocated - taken_days

            balances.append({
                "leave_type": alloc.leave_type,
                "allocated": alloc.total_leaves_allocated,
                "taken": taken_days,
                "balance": balance
            })

        employee_name = frappe.db.get_value("Employee", emp, "employee_name")
        return {
            "employee": emp,
            "employee_name": employee_name,
            "balances": balances
        }

    except Exception as e:
        frappe.log_error(f"Error getting leave balance: {e}", "Blip API")
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_leave_applications(
    employee: str = None,
    status: str = None,
    email: str = None
) -> dict:
    """Get leave applications with optional filters."""
    try:
        filters = {"docstatus": ["!=", 2]}

        if employee:
            emp = _resolve_employee(employee, email)
            if emp:
                filters["employee"] = emp

        if status:
            filters["status"] = status

        applications = frappe.get_all(
            "Leave Application",
            filters=filters,
            fields=[
                "name", "employee", "employee_name", "leave_type",
                "from_date", "to_date", "total_leave_days", "status",
                "posting_date"
            ],
            order_by="posting_date desc",
            limit=20
        )

        return {"applications": applications}

    except Exception as e:
        frappe.log_error(f"Error getting leave applications: {e}", "Blip API")
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_employees_on_leave(
    date: str = None,
    store: str = None,
    email: str = None
) -> dict:
    """Get list of employees on leave for a date."""
    try:
        check_date = date or frappe.utils.today()

        # Get approved leave applications for the date
        query = """
            SELECT
                la.employee,
                la.employee_name,
                la.leave_type,
                la.from_date,
                la.to_date,
                la.total_leave_days,
                e.custom_store as store
            FROM `tabLeave Application` la
            JOIN `tabEmployee` e ON e.name = la.employee
            WHERE la.docstatus = 1
            AND la.status = 'Approved'
            AND la.from_date <= %s
            AND la.to_date >= %s
        """
        params = [check_date, check_date]

        if store:
            query += " AND e.custom_store = %s"
            params.append(store)

        query += " ORDER BY la.employee_name"

        employees = frappe.db.sql(query, params, as_dict=True)

        return {
            "date": check_date,
            "count": len(employees),
            "employees": employees
        }

    except Exception as e:
        frappe.log_error(f"Error getting employees on leave: {e}", "Blip API")
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_attendance(
    employee: str = None,
    date: str = None,
    email: str = None
) -> dict:
    """Get attendance record for an employee."""
    try:
        emp = _resolve_employee(employee, email)
        if not emp:
            return {"error": "Employee not found"}

        check_date = date or frappe.utils.today()

        attendance = frappe.db.get_value(
            "Attendance",
            {"employee": emp, "attendance_date": check_date, "docstatus": 1},
            ["name", "status", "in_time", "out_time", "working_hours", "late_entry", "early_exit"],
            as_dict=True
        )

        employee_name = frappe.db.get_value("Employee", emp, "employee_name")

        if attendance:
            return {
                "employee": emp,
                "employee_name": employee_name,
                "date": check_date,
                "found": True,
                **attendance
            }
        else:
            return {
                "employee": emp,
                "employee_name": employee_name,
                "date": check_date,
                "found": False,
                "message": "No attendance record found"
            }

    except Exception as e:
        frappe.log_error(f"Error getting attendance: {e}", "Blip API")
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_team_attendance(
    date: str = None,
    store: str = None,
    email: str = None
) -> dict:
    """Get team attendance for a store/date."""
    try:
        check_date = date or frappe.utils.today()

        # Get store from user context if not provided
        if not store and email:
            store = frappe.db.get_value(
                "Employee",
                {"user_id": email, "status": "Active"},
                "custom_store"
            )

        if not store:
            return {"error": "Store not specified"}

        # Get all active employees in store
        employees = frappe.get_all(
            "Employee",
            filters={"custom_store": store, "status": "Active"},
            fields=["name", "employee_name"]
        )

        # Get attendance for each
        attendance_list = []
        present_count = 0
        absent_count = 0
        leave_count = 0

        for emp in employees:
            att = frappe.db.get_value(
                "Attendance",
                {"employee": emp.name, "attendance_date": check_date, "docstatus": 1},
                ["status", "in_time", "out_time"],
                as_dict=True
            )

            if att:
                status = att.status
                if status == "Present":
                    present_count += 1
                elif status == "On Leave":
                    leave_count += 1
                else:
                    absent_count += 1
            else:
                status = "No Record"
                absent_count += 1

            attendance_list.append({
                "employee": emp.name,
                "employee_name": emp.employee_name,
                "status": status,
                "in_time": att.in_time if att else None,
                "out_time": att.out_time if att else None
            })

        return {
            "store": store,
            "date": check_date,
            "summary": {
                "total": len(employees),
                "present": present_count,
                "absent": absent_count,
                "on_leave": leave_count
            },
            "attendance": attendance_list
        }

    except Exception as e:
        frappe.log_error(f"Error getting team attendance: {e}", "Blip API")
        return {"error": str(e)}


# ==================== Sales Data ====================

@frappe.whitelist(allow_guest=True)
def get_sales_data(
    store: str = None,
    area: str = None,
    period: str = "today",
    email: str = None
) -> dict:
    """
    Get sales data from BEI POS Upload and BEI Store Sales Day.

    Args:
        store: Store name (can be alias like "megamall")
        area: Area name (BGC, Makati, etc.)
        period: today, yesterday, this_week, last_week, this_month
        email: User email for permission checking
    """
    try:
        # Calculate date range based on period
        today = frappe.utils.today()
        start_date, end_date = _get_date_range(period, today)

        # Resolve store name to warehouse
        warehouse = _resolve_store(store) if store else None

        # Try BEI POS Upload first (primary source)
        try:
            sales = _get_pos_upload_sales(warehouse, area, start_date, end_date)
            if sales.get("records"):
                return sales
        except Exception:
            pass

        # Fallback to BEI Store Sales Day
        try:
            sales = _get_store_sales_day(warehouse, start_date, end_date)
            if sales.get("records"):
                return sales
        except Exception:
            pass

        return {
            "period": period,
            "store": store,
            "start_date": start_date,
            "end_date": end_date,
            "message": "No sales data found for this period",
            "empty": True
        }

    except Exception as e:
        frappe.log_error(f"Error getting sales data: {e}", "Blip API")
        return {"error": str(e)}


def _get_pos_upload_sales(warehouse: str, area: str, start_date: str, end_date: str) -> dict:
    """Get sales from BEI POS Upload DocType."""
    filters = {
        "pos_date": ["between", [start_date, end_date]],
        "status": ["in", ["Extracted", "Verified"]]
    }

    if warehouse:
        filters["store"] = warehouse

    sales = frappe.get_all(
        "BEI POS Upload",
        filters=filters,
        fields=[
            "name", "store", "pos_date", "gross_sales", "net_sales",
            "transaction_count", "total_discount", "vat_amount"
        ],
        order_by="pos_date desc"
    )

    if not sales:
        return {"records": []}

    # Calculate totals
    total_gross = sum(s.gross_sales or 0 for s in sales)
    total_net = sum(s.net_sales or 0 for s in sales)
    total_transactions = sum(s.transaction_count or 0 for s in sales)
    total_discount = sum(s.total_discount or 0 for s in sales)

    # Group by store if multiple stores
    by_store = {}
    for s in sales:
        store_name = s.store or "Unknown"
        if store_name not in by_store:
            by_store[store_name] = {
                "gross_sales": 0,
                "net_sales": 0,
                "transactions": 0
            }
        by_store[store_name]["gross_sales"] += s.gross_sales or 0
        by_store[store_name]["net_sales"] += s.net_sales or 0
        by_store[store_name]["transactions"] += s.transaction_count or 0

    return {
        "source": "POS Upload",
        "period": f"{start_date} to {end_date}",
        "start_date": start_date,
        "end_date": end_date,
        "gross_sales": total_gross,
        "net_sales": total_net,
        "total_transactions": total_transactions,
        "total_discount": total_discount,
        "store_count": len(by_store),
        "by_store": by_store if len(by_store) > 1 else None,
        "records": sales[:10]
    }


def _get_store_sales_day(warehouse: str, start_date: str, end_date: str) -> dict:
    """Get sales from BEI Store Sales Day DocType (fallback)."""
    filters = {
        "business_date": ["between", [start_date, end_date]]
    }

    if warehouse:
        filters["store"] = warehouse

    sales = frappe.get_all(
        "BEI Store Sales Day",
        filters=filters,
        fields=[
            "name", "store", "business_date", "gross_sales", "net_sales",
            "cups_sold", "delivery_sales", "source_system"
        ],
        order_by="business_date desc"
    )

    if not sales:
        return {"records": []}

    total_gross = sum(s.gross_sales or 0 for s in sales)
    total_net = sum(s.net_sales or 0 for s in sales)
    total_cups = sum(s.cups_sold or 0 for s in sales)
    total_delivery = sum(s.delivery_sales or 0 for s in sales)

    return {
        "source": "Store Sales Day",
        "period": f"{start_date} to {end_date}",
        "start_date": start_date,
        "end_date": end_date,
        "gross_sales": total_gross,
        "net_sales": total_net,
        "cups_sold": total_cups,
        "delivery_sales": total_delivery,
        "records": sales[:10]
    }


def _resolve_store(store_hint: str) -> str:
    """Resolve store alias to warehouse name."""
    if not store_hint:
        return None

    hint_lower = store_hint.lower().strip()

    # Common aliases for BEBANG stores
    STORE_ALIASES = {
        "megamall": "SM Megamall",
        "mega mall": "SM Megamall",
        "sm megamall": "SM Megamall",
        "market market": "Market Market",
        "marketmarket": "Market Market",
        "mm": "Market Market",
        "trinoma": "Trinoma",
        "sm north": "SM North EDSA",
        "north edsa": "SM North EDSA",
        "glorietta": "Glorietta",
        "greenbelt": "Greenbelt",
        "uptown": "Uptown Mall",
        "moa": "SM Mall of Asia",
        "mall of asia": "SM Mall of Asia",
        "fairview": "Fairview Terraces",
        "sm aura": "SM Aura",
        "aura": "SM Aura",
        "eastwood": "Eastwood Mall",
        "gateway": "Gateway Mall",
        "galleria": "Robinsons Galleria",
        "magnolia": "Robinsons Magnolia",
        "festival": "Festival Mall",
        "southmall": "SM Southmall",
        "atc": "Alabang Town Center",
        "alabang": "Alabang Town Center",
    }

    # Check aliases first
    if hint_lower in STORE_ALIASES:
        store_name = STORE_ALIASES[hint_lower]
        # Find matching warehouse
        warehouse = frappe.db.get_value(
            "Warehouse",
            {"warehouse_name": ["like", f"%{store_name}%"]},
            "name"
        )
        if warehouse:
            return warehouse

    # Try direct warehouse lookup
    warehouse = frappe.db.get_value(
        "Warehouse",
        {"warehouse_name": ["like", f"%{store_hint}%"]},
        "name"
    )
    if warehouse:
        return warehouse

    # Return original if no match (let the query fail gracefully)
    return store_hint


# ==================== Food Cost Data ====================

@frappe.whitelist(allow_guest=True)
def get_food_cost(
    store: str = None,
    period: str = "this_month",
    email: str = None
) -> dict:
    """Get food cost analysis."""
    try:
        today = frappe.utils.today()
        start_date, end_date = _get_date_range(period, today)

        filters = {
            "docstatus": 1,
            "date": ["between", [start_date, end_date]]
        }

        if store:
            filters["store"] = store

        # Query food cost data - adjust based on actual DocType
        food_costs = frappe.get_all(
            "BEI Food Cost Report",
            filters=filters,
            fields=[
                "store", "date", "total_sales", "total_cost",
                "food_cost_percentage", "target_percentage"
            ],
            order_by="date desc"
        )

        if not food_costs:
            return {
                "period": period,
                "message": "No food cost data found for this period"
            }

        # Calculate averages
        avg_food_cost = sum(fc.food_cost_percentage or 0 for fc in food_costs) / len(food_costs)
        total_sales = sum(fc.total_sales or 0 for fc in food_costs)
        total_cost = sum(fc.total_cost or 0 for fc in food_costs)

        return {
            "period": period,
            "store": store,
            "start_date": start_date,
            "end_date": end_date,
            "total_sales": total_sales,
            "total_cost": total_cost,
            "average_food_cost_percentage": round(avg_food_cost, 2),
            "target_percentage": food_costs[0].target_percentage if food_costs else 35,
            "record_count": len(food_costs)
        }

    except frappe.DoesNotExistError:
        return {
            "error": "Food cost data not available",
            "message": "BEI Food Cost Report DocType not found"
        }
    except Exception as e:
        frappe.log_error(f"Error getting food cost: {e}", "Blip API")
        return {"error": str(e)}


# ==================== Inventory Data ====================

@frappe.whitelist(allow_guest=True)
def get_inventory(
    store: str = None,
    item: str = None,
    email: str = None
) -> dict:
    """Get inventory levels."""
    try:
        # Get warehouse from store
        warehouse = None
        if store:
            # Map store to warehouse - adjust based on actual mapping
            warehouse = frappe.db.get_value("Warehouse", {"custom_store": store}, "name")

        filters = {}
        if warehouse:
            filters["warehouse"] = warehouse
        if item:
            filters["item_code"] = ["like", f"%{item}%"]

        # Get stock balance
        stock = frappe.get_all(
            "Bin",
            filters=filters,
            fields=["item_code", "warehouse", "actual_qty", "reserved_qty", "projected_qty"],
            order_by="item_code",
            limit=50
        )

        # Get item details
        for s in stock:
            item_doc = frappe.db.get_value(
                "Item",
                s.item_code,
                ["item_name", "stock_uom"],
                as_dict=True
            )
            if item_doc:
                s["item_name"] = item_doc.item_name
                s["uom"] = item_doc.stock_uom

        return {
            "store": store,
            "warehouse": warehouse,
            "item_filter": item,
            "items": stock
        }

    except Exception as e:
        frappe.log_error(f"Error getting inventory: {e}", "Blip API")
        return {"error": str(e)}


# ==================== Commissary Data ====================

@frappe.whitelist(allow_guest=True)
def get_commissary_production(
    product: str = None,
    date: str = None,
    email: str = None
) -> dict:
    """Get commissary production data."""
    try:
        check_date = date or frappe.utils.today()

        filters = {
            "docstatus": 1,
            "posting_date": check_date
        }

        if product:
            filters["production_item"] = ["like", f"%{product}%"]

        # Query work orders or production entries
        production = frappe.get_all(
            "Work Order",
            filters=filters,
            fields=[
                "name", "production_item", "item_name",
                "qty", "produced_qty", "status", "posting_date"
            ],
            order_by="posting_date desc",
            limit=30
        )

        total_planned = sum(p.qty or 0 for p in production)
        total_produced = sum(p.produced_qty or 0 for p in production)

        return {
            "date": check_date,
            "product_filter": product,
            "total_planned": total_planned,
            "total_produced": total_produced,
            "completion_rate": round((total_produced / total_planned * 100) if total_planned > 0 else 0, 1),
            "items": production
        }

    except Exception as e:
        frappe.log_error(f"Error getting commissary production: {e}", "Blip API")
        return {"error": str(e)}


# ==================== Helper Functions ====================

def _resolve_employee(employee: str, email: str) -> str:
    """Resolve employee ID from name or email."""
    if employee:
        # Check if it's already an employee ID
        if frappe.db.exists("Employee", employee):
            return employee

        # Try to find by employee name
        emp = frappe.db.get_value(
            "Employee",
            {"employee_name": ["like", f"%{employee}%"], "status": "Active"},
            "name"
        )
        if emp:
            return emp

    if email:
        # Get employee from user email
        emp = frappe.db.get_value(
            "Employee",
            {"user_id": email, "status": "Active"},
            "name"
        )
        if emp:
            return emp

    return None


def _get_date_range(period: str, today: str) -> tuple:
    """Calculate date range based on period string."""
    today_date = frappe.utils.getdate(today)

    if period == "today":
        return today, today
    elif period == "yesterday":
        yesterday = today_date - timedelta(days=1)
        return str(yesterday), str(yesterday)
    elif period == "this_week":
        # Monday to today
        start = today_date - timedelta(days=today_date.weekday())
        return str(start), today
    elif period == "last_week":
        # Previous Monday to Sunday
        this_monday = today_date - timedelta(days=today_date.weekday())
        last_monday = this_monday - timedelta(days=7)
        last_sunday = this_monday - timedelta(days=1)
        return str(last_monday), str(last_sunday)
    elif period == "this_month":
        start = today_date.replace(day=1)
        return str(start), today
    elif period == "last_month":
        first_this_month = today_date.replace(day=1)
        last_day_prev = first_this_month - timedelta(days=1)
        first_prev = last_day_prev.replace(day=1)
        return str(first_prev), str(last_day_prev)
    else:
        # Default to today
        return today, today


# ==================== Employee Directory ====================

@frappe.whitelist(allow_guest=True)
def search_employees(
    query: str = None,
    store: str = None,
    department: str = None,
    position: str = None,
    email: str = None
) -> dict:
    """
    Search for employees by name, position, or store.

    Args:
        query: Search query (name, position, etc.)
        store: Filter by store
        department: Filter by department
        position: Filter by position/designation
        email: Requesting user's email
    """
    try:
        if not query and not store and not department and not position:
            return {"error": "Please provide a search query or filter"}

        filters = {"status": "Active"}

        if store:
            filters["custom_store"] = store
        if department:
            filters["department"] = department
        if position:
            filters["designation"] = position

        # Build OR conditions for query search
        or_filters = []
        if query:
            or_filters = [
                ["employee_name", "like", f"%{query}%"],
                ["designation", "like", f"%{query}%"],
                ["department", "like", f"%{query}%"],
                ["custom_store", "like", f"%{query}%"]
            ]

        employees = frappe.get_all(
            "Employee",
            filters=filters,
            or_filters=or_filters if or_filters else None,
            fields=[
                "name", "employee_name", "designation", "department",
                "custom_store", "custom_area", "cell_number", "company_email"
            ],
            order_by="employee_name",
            limit=20
        )

        return {
            "query": query,
            "filters": {
                "store": store,
                "department": department,
                "position": position
            },
            "count": len(employees),
            "employees": employees
        }

    except Exception as e:
        frappe.log_error(f"Error searching employees: {e}", "Blip API")
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_store_info(
    store: str = None,
    email: str = None
) -> dict:
    """
    Get information about a store.

    Args:
        store: Store name or alias
        email: Requesting user's email
    """
    try:
        if not store:
            return {"error": "Store name required"}

        # First try to find the warehouse directly
        warehouse = _resolve_store(store)

        if not warehouse:
            return {"error": f"Store '{store}' not found"}

        # Get warehouse details
        wh_doc = frappe.get_doc("Warehouse", warehouse)

        # Get employees at this store
        employee_count = frappe.db.count(
            "Employee",
            {"custom_store": store, "status": "Active"}
        )

        # Get manager (if set)
        manager = frappe.db.get_value(
            "Employee",
            {"custom_store": store, "designation": ["like", "%Manager%"], "status": "Active"},
            ["employee_name", "cell_number", "company_email"],
            as_dict=True
        )

        return {
            "store": store,
            "warehouse": warehouse,
            "warehouse_name": wh_doc.warehouse_name,
            "company": wh_doc.company,
            "is_group": wh_doc.is_group,
            "parent_warehouse": wh_doc.parent_warehouse,
            "address": wh_doc.address_line_1 if hasattr(wh_doc, 'address_line_1') else None,
            "employee_count": employee_count,
            "manager": manager
        }

    except frappe.DoesNotExistError:
        return {"error": f"Store '{store}' not found"}
    except Exception as e:
        frappe.log_error(f"Error getting store info: {e}", "Blip API")
        return {"error": str(e)}


# ==================== Leave Actions ====================

@frappe.whitelist(allow_guest=True)
def submit_leave_request(
    employee: str = None,
    leave_type: str = None,
    from_date: str = None,
    to_date: str = None,
    reason: str = "",
    email: str = None
) -> dict:
    """
    Submit a leave request for an employee.

    Args:
        employee: Employee ID or name
        leave_type: Type of leave (Vacation, Sick, Emergency)
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        reason: Reason for leave
        email: Requesting user's email (for validation)
    """
    try:
        # Validate required fields
        if not employee or not leave_type or not from_date or not to_date:
            return {"error": "Missing required fields: employee, leave_type, from_date, to_date"}

        # Resolve employee
        emp = _resolve_employee(employee, email)
        if not emp:
            return {"error": f"Employee '{employee}' not found"}

        # Validate that the requesting user can submit for this employee
        if email:
            requester_emp = _resolve_employee(None, email)
            # Allow if submitting for self, or if user has HR permissions
            if requester_emp != emp:
                user_roles = frappe.get_roles(email)
                if "HR Manager" not in user_roles and "HR User" not in user_roles:
                    return {"error": "You can only submit leave requests for yourself"}

        # Validate leave type exists
        if not frappe.db.exists("Leave Type", leave_type):
            return {"error": f"Leave type '{leave_type}' not found"}

        # Check leave balance
        from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on

        balance = get_leave_balance_on(
            emp,
            leave_type,
            frappe.utils.getdate(from_date)
        )

        days_requested = frappe.utils.date_diff(to_date, from_date) + 1

        if balance < days_requested:
            return {
                "error": f"Insufficient leave balance. Available: {balance} days, Requested: {days_requested} days"
            }

        # Create the leave application
        leave_app = frappe.get_doc({
            "doctype": "Leave Application",
            "employee": emp,
            "leave_type": leave_type,
            "from_date": from_date,
            "to_date": to_date,
            "description": reason or f"Submitted via Blip assistant",
            "status": "Open"
        })

        leave_app.insert(ignore_permissions=True)

        employee_name = frappe.db.get_value("Employee", emp, "employee_name")

        return {
            "success": True,
            "leave_application": leave_app.name,
            "employee": emp,
            "employee_name": employee_name,
            "leave_type": leave_type,
            "from_date": from_date,
            "to_date": to_date,
            "days": days_requested,
            "status": "Open",
            "message": f"Leave request submitted successfully! Application: {leave_app.name}"
        }

    except frappe.ValidationError as e:
        return {"error": f"Validation error: {str(e)}"}
    except Exception as e:
        frappe.log_error(f"Error submitting leave request: {e}", "Blip API")
        return {"error": str(e)}
