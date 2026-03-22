import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from hrms.utils import notification_intelligence as ni


class TestNotificationIntelligenceS38(unittest.TestCase):
	def test_certified_manifest_and_exclusion_counts_are_locked(self):
		self.assertEqual(len(ni.build_certified_family_manifest_rows()), 8)
		self.assertGreaterEqual(len(ni.build_exclusion_rows()), 4)

	def test_build_notification_event_fills_defaults_and_rendered_sections(self):
		event = ni.build_notification_event(
			{
				"family": "morning_readiness_digest",
				"facts": {
					"report_date": "2026-03-13",
					"status": "yellow",
					"areas": [
						{"label": "Store Inventory Shadow Sync", "status": "green"},
						{"label": "AP / Procurement Baselines", "status": "yellow"},
					],
					"sync_target_pht_time": "07:00",
					"ready_deadline_pht_time": "09:00",
					"artifact_markdown_path": "F:/tmp/report.md",
				},
			}
		)

		self.assertEqual(event["delivery_class"], "action_digest")
		self.assertEqual(event["requested_space"], ni.SPACE_NOTIFICATIONS)
		self.assertTrue(event["dedup_key"].startswith("morning_readiness_digest:"))
		rendered = ni.render_notification_text(event)
		self.assertIn("*Summary*", rendered)
		self.assertIn("*Why this matters*", rendered)
		self.assertIn("report.md", rendered)

	def test_discount_digest_renderer_mentions_review_queue(self):
		event = ni.build_notification_event(
			{
				"family": "discount_critical_digest",
				"facts": {
					"business_date": "2026-03-12",
					"rows": [
						{"store_name": "SM North EDSA", "identity_key": "25402", "order_count": 2},
						{"store_name": "SM Megamall", "identity_key": "153", "order_count": 2},
					],
					"review_url": "https://my.bebang.ph/dashboard/accounting/discount-abuse",
				},
			}
		)

		rendered = ni.render_notification_text(event)
		self.assertIn("Discount audit found 2 critical clusters", rendered)
		self.assertIn("discount-abuse", rendered)

	def test_store_order_approved_renderer_covers_fulfillment_signal(self):
		event = ni.build_notification_event(
			{
				"family": "store_order_approved",
				"facts": {
					"order_name": "BEI-ORD-0001",
					"store": "Ayala Evo",
					"approved_by": "test.hr@bebang.ph",
					"material_request": "MAT-REQ-0001",
					"dashboard_url": "https://my.bebang.ph/dashboard/store-ops/order-approvals",
				},
			}
		)

		rendered = ni.render_notification_text(event)
		self.assertIn("dispatch request MAT-REQ-0001 is ready", rendered)
		self.assertIn("Warehouse / Store Ops", rendered)


if __name__ == "__main__":
	unittest.main()
