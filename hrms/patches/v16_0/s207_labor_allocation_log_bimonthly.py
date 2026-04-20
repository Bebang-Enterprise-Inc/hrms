# Copyright (c) 2026, Bebang Enterprise Inc. and contributors
# For license information, see LICENSE at repo root.

"""S207 DB migration: switch BEI Labor Allocation Log from (year, month) to
slip-based idempotency.

Runs once during bench migrate. Idempotent — safe to re-run (every ALTER is
guarded with existence checks).

Sequence:
  1. Backfill period_start / period_end from the existing year/month columns
     for any pre-S207 rows. Uses MariaDB LAST_DAY() so Feb / 30-day / 31-day
     months are all correct. STR_TO_DATE('YYYY-MM-01') handles 12 -> 1
     rollover naturally.
  2. Verify backfill completeness — abort if any row still has NULL period.
  3. Drop the old `idx_year_month_employee` unique index if present (S206).
  4. Drop `year` and `month` columns (DM-5 — stored duplicates go stale when
     the linked Slip's dates change).
  5. Create the new `idx_slip_employee` unique index (`slip_name`, `employee`).
  6. Commit.

If the S206 patch already created the old index, this patch drops it. If the
old index was never created (fresh install post-S207), the DROP is a no-op.
"""

from __future__ import annotations

import frappe


def execute() -> None:
	# Step 1: Backfill period fields from year/month columns, if both still exist.
	# Tolerate either/both columns already being absent (idempotent re-run).
	year_exists = _column_exists("tabBEI Labor Allocation Log", "year")
	month_exists = _column_exists("tabBEI Labor Allocation Log", "month")
	if year_exists and month_exists:
		frappe.db.sql(
			"""
			UPDATE `tabBEI Labor Allocation Log`
			SET period_start = STR_TO_DATE(CONCAT(`year`, '-', LPAD(`month`, 2, '0'), '-01'), '%Y-%m-%d'),
			    period_end   = LAST_DAY(STR_TO_DATE(CONCAT(`year`, '-', LPAD(`month`, 2, '0'), '-01'), '%Y-%m-%d'))
			WHERE period_start IS NULL
			   OR period_end IS NULL
			"""
		)  # nosemgrep: frappe-sql-format-injection -- no user input; literal table/columns

		# Step 2: Verify backfill before dropping columns
		orphans = frappe.db.sql(
			"""
			SELECT COUNT(*) AS c FROM `tabBEI Labor Allocation Log`
			WHERE period_start IS NULL OR period_end IS NULL
			""",
			as_dict=True,
		)
		if orphans and orphans[0]["c"] > 0:
			frappe.throw(
				f"S207 backfill incomplete: {orphans[0]['c']} rows have NULL period "
				f"fields. Abort migration. Investigate these rows before re-running."
			)

	# Step 3: Drop the old S206 unique index if present
	old_idx = frappe.db.sql(
		"SHOW INDEX FROM `tabBEI Labor Allocation Log` WHERE Key_name = 'idx_year_month_employee'",
		as_dict=True,
	)
	if old_idx:
		try:
			frappe.db.sql_ddl(
				"ALTER TABLE `tabBEI Labor Allocation Log` DROP INDEX `idx_year_month_employee`"
			)
		except Exception as exc:
			frappe.log_error(
				title="S207 patch: failed to drop idx_year_month_employee",
				message=str(exc),
			)

	# Step 4: Drop year + month columns (only if present)
	for col in ("year", "month"):
		if _column_exists("tabBEI Labor Allocation Log", col):
			try:
				frappe.db.sql_ddl(
					f"ALTER TABLE `tabBEI Labor Allocation Log` DROP COLUMN `{col}`"
				)  # nosemgrep: frappe-sql-format-injection -- col is a literal from the tuple above
			except Exception as exc:
				frappe.log_error(
					title=f"S207 patch: failed to drop column {col}",
					message=str(exc),
				)

	# Step 5: Create the new slip-based unique index
	new_idx = frappe.db.sql(
		"SHOW INDEX FROM `tabBEI Labor Allocation Log` WHERE Key_name = 'idx_slip_employee'",
		as_dict=True,
	)
	if not new_idx and _column_exists("tabBEI Labor Allocation Log", "slip_name"):
		try:
			frappe.db.sql_ddl(
				"""
				CREATE UNIQUE INDEX `idx_slip_employee`
				ON `tabBEI Labor Allocation Log` (`slip_name`, `employee`)
				"""
			)
		except Exception as exc:
			frappe.log_error(
				title="S207 patch: failed to create idx_slip_employee",
				message=str(exc),
			)

	# Step 6: Commit the schema migration. nosemgrep: patches legitimately
	# commit DDL so the next bench step sees the new schema.
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- intentional; see docstring


def _column_exists(table: str, column: str) -> bool:
	row = frappe.db.sql(
		"""
		SELECT COUNT(*) AS c
		FROM information_schema.columns
		WHERE table_schema = DATABASE()
		  AND table_name = %s
		  AND column_name = %s
		""",
		(table, column),
		as_dict=True,
	)
	return bool(row and row[0]["c"] > 0)
