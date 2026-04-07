# Copyright (c) 2026, Bebang Enterprise Inc. and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BEIClearanceItem(Document):
    """Child table row for `BEI Clearance` — one row per station + item.

    Status transitions: Pending -> Returned | Waived | Missing.
    A clearance cannot be submitted while any item is still Pending.
    """

    pass
