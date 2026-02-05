# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, time_diff_in_hours
from typing import Tuple, Optional

class BEIOfficialBusiness(Document):
    def validate(self):
        """Validate OB record and calculate fields"""
        # Calculate total hours if both check-in and check-out exist
        if self.checkout_datetime and self.checkin_datetime:
            self.total_hours_out = time_diff_in_hours(
                get_datetime(self.checkin_datetime),
                get_datetime(self.checkout_datetime)
            )

        # Validate velocity if checking in
        if self.checkin_datetime and self.checkin_latitude and self.checkin_longitude:
            self._check_velocity()

    def _check_velocity(self):
        """Flag if employee moved impossibly fast"""
        # Get last check-out/in
        last_record = frappe.db.sql("""
            SELECT checkout_datetime, checkout_latitude, checkout_longitude
            FROM `tabBEI Official Business`
            WHERE employee = %s
              AND name != %s
              AND checkout_datetime IS NOT NULL
              AND (status IN ('Out', 'Returned'))
            ORDER BY checkout_datetime DESC
            LIMIT 1
        """, (self.employee, self.name), as_dict=True)

        if not last_record or not last_record[0].checkout_latitude:
            return

        last = last_record[0]

        # Calculate distance (Haversine)
        distance_km = self._get_distance_between_coordinates(
            last.checkout_latitude,
            last.checkout_longitude,
            self.checkin_latitude,
            self.checkin_longitude
        ) / 1000

        # Calculate time difference in hours
        time_hours = time_diff_in_hours(
            get_datetime(self.checkin_datetime),
            get_datetime(last.checkout_datetime)
        )

        # Flag if speed > 200 km/h (impossible without flying)
        if time_hours > 0 and distance_km / time_hours > 200:
            self.velocity_flag = 1
            self.flag_reason = f"Suspicious: {distance_km:.1f}km in {time_hours*60:.0f}min"

    def _get_distance_between_coordinates(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two coordinates using Haversine formula (meters)"""
        from math import radians, cos, sin, asin, sqrt

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))

        # Earth radius in meters
        r = 6371000
        return c * r
