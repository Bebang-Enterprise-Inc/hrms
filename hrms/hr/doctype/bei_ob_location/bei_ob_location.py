# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BEIOBLocation(Document):
    def validate(self):
        """Validate location data"""
        if self.latitude and self.longitude:
            # Update geolocation field for map display
            self.geolocation = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [self.longitude, self.latitude]
                    }
                }]
            }
