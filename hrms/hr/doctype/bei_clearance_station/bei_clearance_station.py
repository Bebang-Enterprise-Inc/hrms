# Copyright (c) 2026, Bebang Enterprise Inc. and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BEIClearanceStation(Document):
    """Master record for a clearance station (e.g., IT, POS, Uniform, Keys).

    Each enabled station becomes a row in a clearance checklist when an
    employee is processed for separation. See `BEI Clearance` and
    `BEI Clearance Item`.
    """

    pass
