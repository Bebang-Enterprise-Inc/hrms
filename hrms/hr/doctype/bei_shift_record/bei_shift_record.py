# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, getdate, time_diff_in_hours


class BEIShiftRecord(Document):
	def validate(self):
		"""Calculate derived fields and run fraud detection checks"""
		self._calculate_total_hours()
		self._check_overtime()
		self._check_cross_day()
		self._update_status()

		if self.punch_out_time and self.punch_out_latitude and self.punch_out_longitude:
			self._check_velocity()

	def _calculate_total_hours(self):
		if self.punch_in_time and self.punch_out_time:
			punch_in_dt = get_datetime(self.punch_in_time)
			punch_out_dt = get_datetime(self.punch_out_time)

			if punch_out_dt <= punch_in_dt:
				frappe.throw("Punch-out time must be after punch-in time")

			self.total_hours = time_diff_in_hours(punch_out_dt, punch_in_dt)

	def _check_overtime(self):
		if self.total_hours and self.total_hours > 8:
			self.overtime_flag = 1
		elif self.punch_out_time:
			# Only reset if shift is completed (has punch-out)
			self.overtime_flag = 0

	def _check_cross_day(self):
		if self.punch_in_time and self.punch_out_time:
			if getdate(get_datetime(self.punch_in_time)) != getdate(get_datetime(self.punch_out_time)):
				self.cross_day_flag = 1
			else:
				self.cross_day_flag = 0

	def _update_status(self):
		if self.punch_out_time:
			self.status = "Completed"
		else:
			self.status = "In Progress"

	def _check_velocity(self):
		"""Flag if employee moved impossibly fast between consecutive punches

		Compares the punch-in GPS of this record against the punch-out GPS of
		the employee's most recent previous completed shift. If the implied
		travel speed exceeds 200 km/h, the record is flagged for review.
		"""
		# Get last completed shift for this employee
		last_records = frappe.get_all(
			"BEI Shift Record",
			filters={
				"employee": self.employee,
				"name": ["!=", self.name],
				"punch_out_time": ["is", "set"],
				"status": "Completed",
			},
			fields=["punch_out_time", "punch_out_latitude", "punch_out_longitude"],
			order_by="punch_out_time desc",
			limit=1,
		)

		if not last_records:
			return

		last = last_records[0]
		if not last.punch_out_latitude or not last.punch_out_longitude:
			return

		from hrms.utils.geo import calculate_haversine_distance

		distance_km = (
			calculate_haversine_distance(
				last.punch_out_latitude,
				last.punch_out_longitude,
				self.punch_in_latitude,
				self.punch_in_longitude,
			)
			/ 1000
		)

		time_hours = time_diff_in_hours(
			get_datetime(self.punch_in_time),
			get_datetime(last.punch_out_time),
		)

		if time_hours > 0 and distance_km / time_hours > 200:
			self.velocity_flag = 1

	def on_update(self):
		"""Post-save hook: bridge to Attendance when status transitions to Completed."""
		if self.status == "Completed" and self.has_value_changed("status"):
			self.create_attendance_from_shift()

	def create_attendance_from_shift(self):
		"""Bridge: create/update Attendance record from completed shift record."""
		att_date = getdate(self.punch_in_time)
		shift_assignment = frappe.db.get_value(
			"Shift Assignment",
			{
				"employee": self.employee,
				"docstatus": 1,
				"status": "Active",
				"start_date": ("<=", att_date),
				"end_date": [">=", att_date],
			},
			["shift_type"],
			as_dict=True,
		)
		if not shift_assignment:
			shift_assignment = frappe.db.get_value(
				"Shift Assignment",
				{
					"employee": self.employee,
					"docstatus": 1,
					"status": "Active",
					"start_date": ("<=", att_date),
					"end_date": ("is", "not set"),
				},
				["shift_type"],
				as_dict=True,
			)
		shift_type = shift_assignment.get("shift_type") if shift_assignment else None

		# Cap auto-punched-out shifts at 8h to prevent phantom overtime
		if getattr(self, "auto_punched_out", 0):
			working_hours = 8.0
			att_status = "Present"
			needs_review = True
		else:
			working_hours = self.total_hours or 0
			att_status = "Present" if (self.total_hours or 0) >= 4 else "Half Day"
			needs_review = False

		# Guard: don't duplicate — update if exists
		existing = frappe.db.exists("Attendance", {"employee": self.employee, "attendance_date": att_date})

		if existing:
			update_fields = {
				"working_hours": working_hours,
				"status": att_status,
				"shift": shift_type,
				"in_time": self.punch_in_time,
				"out_time": self.punch_out_time,
			}
			frappe.db.set_value("Attendance", existing, update_fields)
			try:
				from hrms.hr.doctype.employee_checkin.employee_checkin import get_overtime_data

				if shift_type and att_status == "Present":
					overtime_data = get_overtime_data(shift_type, working_hours)
					if overtime_data:
						frappe.db.set_value(
							"Attendance",
							existing,
							{
								"overtime_type": frappe.db.get_value(
									"Shift Type", shift_type, "overtime_type"
								),
								"standard_working_hours": overtime_data.get("standard_working_hours"),
								"actual_overtime_duration": overtime_data.get("actual_overtime_duration"),
							},
						)
			except Exception:
				pass
			try:
				from hrms.api.overtime import upsert_overtime_case_from_attendance

				upsert_overtime_case_from_attendance(existing, source_trigger="shift_record_close")
			except Exception:
				frappe.log_error(frappe.get_traceback(), f"Failed OT upsert for Attendance {existing}")
			return

		# Create new Attendance via raw SQL (avoids ORM validation cascade)
		att_name = f"ATT-{self.employee}-{att_date}"
		company = frappe.db.get_value("Employee", self.employee, "company")

		try:
			frappe.db.sql(
				"""
				INSERT INTO `tabAttendance` (
					name, employee, employee_name, attendance_date,
					status, working_hours, docstatus,
					company, creation, modified, modified_by, owner
				) VALUES (
					%(name)s, %(employee)s, %(employee_name)s, %(date)s,
					%(status)s, %(hours)s, 1,
					%(company)s, NOW(), NOW(), %(user)s, %(user)s
				)
			""",
				{
					"name": att_name,
					"employee": self.employee,
					"employee_name": self.employee_name,
					"date": att_date,
					"status": att_status,
					"hours": working_hours,
					"company": company,
					"user": frappe.session.user,
				},
			)
		except Exception:
			# Name collision with non-standard naming — fallback to update
			frappe.db.sql(
				"""
				UPDATE `tabAttendance`
				SET working_hours = %(hours)s, status = %(status)s, shift = %(shift)s,
				    in_time = %(in_time)s, out_time = %(out_time)s, modified = NOW()
				WHERE employee = %(employee)s AND attendance_date = %(date)s
				LIMIT 1
			""",
				{
					"employee": self.employee,
					"date": att_date,
					"status": att_status,
					"hours": working_hours,
					"shift": shift_type,
					"in_time": self.punch_in_time,
					"out_time": self.punch_out_time,
				},
			)

		attendance_name = frappe.db.get_value(
			"Attendance",
			{"employee": self.employee, "attendance_date": att_date, "docstatus": 1},
			"name",
		)
		if attendance_name:
			try:
				from hrms.hr.doctype.employee_checkin.employee_checkin import get_overtime_data

				if shift_type and att_status == "Present":
					overtime_data = get_overtime_data(shift_type, working_hours)
					if overtime_data:
						frappe.db.set_value(
							"Attendance",
							attendance_name,
							{
								"shift": shift_type,
								"in_time": self.punch_in_time,
								"out_time": self.punch_out_time,
								"overtime_type": frappe.db.get_value(
									"Shift Type", shift_type, "overtime_type"
								),
								"standard_working_hours": overtime_data.get("standard_working_hours"),
								"actual_overtime_duration": overtime_data.get("actual_overtime_duration"),
							},
						)
			except Exception:
				pass
			try:
				from hrms.api.overtime import upsert_overtime_case_from_attendance

				upsert_overtime_case_from_attendance(attendance_name, source_trigger="shift_record_close")
			except Exception:
				frappe.log_error(frappe.get_traceback(), f"Failed OT upsert for Attendance {attendance_name}")

		if needs_review:
			frappe.logger().warning(
				f"Auto-punched-out shift {self.name} for {self.employee} capped at 8h. "
				f"Original total_hours was {self.total_hours}. Needs manager review."
			)
