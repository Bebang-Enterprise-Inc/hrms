"""
Centralized RBAC role sets for SCM (Supply Chain Management) modules.

P0-10: All SCM role definitions live here. Import from this module instead of
defining inline in each API file. This prevents role drift across modules.

Usage:
    from hrms.utils.scm_roles import SCM_DISPATCH_ROLES, check_scm_permission
"""

import frappe
from frappe import _


# ============================================================
# SCM Role Sets
# ============================================================

# Dispatch / trip management (dispatch.py)
SCM_ADMIN_ROLES = {"HR Manager", "Warehouse Manager", "System Manager"}
SCM_DISPATCH_ROLES = {"HR Manager", "Warehouse Manager", "Logistics Coordinator", "System Manager"}
SCM_STORE_ROLES = {"Store Staff", "Store Supervisor", "Area Supervisor", "Warehouse User", "System Manager"}

# Picking / loading (picking.py)
SCM_PICKING_ROLES = {"Warehouse Manager", "Warehouse Staff", "Logistics Coordinator", "System Manager"}

# Ordering (ordering.py)
ORDERING_STORE_ROLES = {"Store Staff", "Store Supervisor", "Store OIC", "System Manager"}
ORDERING_WAREHOUSE_ROLES = {
	"Area Supervisor",
	"Regional Manager",
	"HR Manager",
	"Warehouse Manager",
	"System Manager",
}
ORDERING_APPROVAL_ROLES = {
	"Area Supervisor",
	"Regional Manager",
	"HR Manager",
	"Warehouse Manager",
	"System Manager",
}

# Billing (billing.py)
RATE_MANAGEMENT_ROLES = {"Accounts Manager", "Supply Chain Manager", "System Manager"}
SCM_BILLING_ROLES = {"Warehouse Manager", "Logistics Coordinator", "HR Manager", "System Manager"}

# Inventory (inventory.py)
SCM_INVENTORY_ROLES = {"Warehouse Manager", "Warehouse Staff", "Logistics Coordinator", "System Manager"}
SCM_STOCK_UPDATE_ROLES = {"Warehouse Manager", "Warehouse Staff", "System Manager"}

# Permits (permits.py)
SCM_PERMIT_ROLES = {"Warehouse Manager", "Logistics Coordinator", "HR Manager", "System Manager"}

# Requisition approval (commissary_requisition.py)
SCM_APPROVAL_ROLES = {"Warehouse Manager", "Supply Chain Manager", "HR Manager", "System Manager"}


# ============================================================
# Shared Permission Check
# ============================================================

def check_scm_permission(allowed_roles, action="access this resource"):
    """Check if current user has any of the allowed roles.

    Args:
        allowed_roles: Set of role names that grant access
        action: Description of the action for the error message

    Raises:
        frappe.PermissionError: If user has none of the allowed roles
    """
    user_roles = set(frappe.get_roles(frappe.session.user))
    if not user_roles.intersection(allowed_roles):
        frappe.throw(
            _("You do not have permission to {0}").format(action),
            frappe.PermissionError
        )
