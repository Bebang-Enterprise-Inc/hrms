"""S227 unit tests — Store Partner role behavior.

Covers Phase 1 (resolver + decision helper + DocPerm safety) and Phase 2
(strip helpers). Tests focus on pure-function behavior so they do not
require a live Supabase or Redis connection.
"""

from __future__ import annotations

import copy
import inspect
import re
import unittest

import frappe

from hrms.api import sales_dashboard
from hrms.api.sales_dashboard import (
	ALLOWED_ROLES,
	ROLE_ADMINISTRATOR,
	ROLE_AREA_SUPERVISOR,
	ROLE_HQ_USER,
	ROLE_SALES_STAKEHOLDER,
	ROLE_STORE_PARTNER,
	ROLE_STORE_SUPERVISOR,
	ROLE_SYSTEM_MANAGER,
	_should_strip_fleet_context,
)


# ---------- Phase 1 ----------


class TestStorePartnerStripDecision(unittest.TestCase):
	"""Truth table for _should_strip_fleet_context.

	Strip iff Store Partner present AND no other analytics-granting role.
	"""

	def test_store_partner_alone_strips(self):
		self.assertTrue(_should_strip_fleet_context({ROLE_STORE_PARTNER}))

	def test_no_partner_no_strip(self):
		self.assertFalse(_should_strip_fleet_context({ROLE_AREA_SUPERVISOR}))
		self.assertFalse(_should_strip_fleet_context({ROLE_HQ_USER}))
		self.assertFalse(_should_strip_fleet_context({ROLE_ADMINISTRATOR}))
		self.assertFalse(_should_strip_fleet_context({ROLE_SYSTEM_MANAGER}))
		self.assertFalse(_should_strip_fleet_context(set()))

	def test_partner_plus_admin_no_strip(self):
		"""CEO directive: admin-who-is-partner sees admin view."""
		self.assertFalse(
			_should_strip_fleet_context({ROLE_STORE_PARTNER, ROLE_ADMINISTRATOR})
		)

	def test_partner_plus_hq_user_no_strip(self):
		self.assertFalse(_should_strip_fleet_context({ROLE_STORE_PARTNER, ROLE_HQ_USER}))

	def test_partner_plus_area_supervisor_no_strip(self):
		"""CEO directive 2026-04-27: AS view wins for executives-who-are-partners."""
		self.assertFalse(
			_should_strip_fleet_context({ROLE_STORE_PARTNER, ROLE_AREA_SUPERVISOR})
		)

	def test_partner_plus_store_supervisor_no_strip(self):
		self.assertFalse(
			_should_strip_fleet_context({ROLE_STORE_PARTNER, ROLE_STORE_SUPERVISOR})
		)

	def test_partner_plus_sales_stakeholder_no_strip(self):
		"""B5: Sales Stakeholder also wins precedence over Partner."""
		self.assertFalse(
			_should_strip_fleet_context({ROLE_STORE_PARTNER, ROLE_SALES_STAKEHOLDER})
		)

	def test_partner_plus_unrelated_role_strips(self):
		"""A role not in ALLOWED_ROLES (e.g., 'Employee') doesn't grant fleet view."""
		self.assertTrue(_should_strip_fleet_context({ROLE_STORE_PARTNER, "Employee"}))


class TestStorePartnerScopeResolverShape(unittest.TestCase):
	"""Source-level invariants on _resolve_allowed_store_scope.

	The resolver looks up rows in a live `BEI Sales Dashboard Store Access`
	table — integration testing is left to Phase 5 L3 with a real test partner
	user. These tests assert the static structure required by the brainstorm:
	- Partner branch placed AFTER Sales Stakeholder (lowest precedence tier).
	- Partner branch falls through to _filter_sales_warehouses (no early return).
	"""

	def test_partner_branch_placed_after_stakeholder(self):
		src = inspect.getsource(sales_dashboard._resolve_allowed_store_scope)
		stakeholder_pos = src.find("ROLE_SALES_STAKEHOLDER in roles")
		partner_pos = src.find("ROLE_STORE_PARTNER in roles")
		self.assertGreater(stakeholder_pos, 0, "Stakeholder branch missing.")
		self.assertGreater(partner_pos, 0, "Partner branch missing.")
		self.assertGreater(
			partner_pos,
			stakeholder_pos,
			"ROLE_STORE_PARTNER branch must come AFTER ROLE_SALES_STAKEHOLDER.",
		)

	def test_partner_branch_does_not_early_return(self):
		src = inspect.getsource(sales_dashboard._resolve_allowed_store_scope)
		# Capture from the partner elif up to the next `if role_label != ROLE_STORE_SUPERVISOR`
		match = re.search(
			r"elif ROLE_STORE_PARTNER in roles:(.*?)if role_label != ROLE_STORE_SUPERVISOR",
			src,
			re.DOTALL,
		)
		self.assertIsNotNone(match, "Partner branch shape not found in source.")
		# A bare `return` inside the partner block would short-circuit the
		# canonical _filter_sales_warehouses pass — forbidden.
		self.assertNotIn(
			"\treturn ",
			match.group(1).split("elif")[0],
			"Partner branch must NOT early-return; must fall through to filter.",
		)


class TestStorePartnerDocPermSafety(unittest.TestCase):
	"""B15: Partner role must not inherit any Custom DocPerm rows on other DocTypes.

	Defense-in-depth: even if a future migration accidentally seeds DocPerms,
	this assertion will fail loudly during CI.
	"""

	def test_no_custom_docperm_for_store_partner(self):
		if not getattr(frappe.local, "site", None):
			self.skipTest(
				"No Frappe site context — DocPerm assertion only runs in bench test."
			)
		rows = frappe.get_all("Custom DocPerm", filters={"role": ROLE_STORE_PARTNER})
		self.assertEqual(
			rows,
			[],
			f"Custom DocPerm rows must not exist for {ROLE_STORE_PARTNER!r}.",
		)


# ---------- Phase 2 (strip helpers) — defined here to keep the partner test
# surface in one file. The helpers are imported lazily inside each test so
# Phase 1 collection does not break if helpers are not yet implemented.


class TestStripFleetFromOverview(unittest.TestCase):
	def _payload(self):
		return {
			"scope": {"selected_stores": [{"warehouse": "SM AURA - X"}]},
			"date_window": {},
			"mode_state": {},
			"summary": {"gross_sales": 1000.0},
			"freshness": {},
			"comparisons": {"net_delta_pct": 5.0},
			"daily": [],
			"analysis": {
				"effects": {
					"channel_mix_shift_vs_baseline": {
						"pickup_share_delta_pct_points": 1.0,
						"delivery_share_delta_pct_points": -1.0,
					},
					"expected_net_sales_without_vat": 950.0,
					"actual_vs_expected_pct": 5.3,
				}
			},
			"stores": [
				{"warehouse": "SM AURA - X", "fleet_rank": 7, "rank": 7},
				{"warehouse": "BGC - X", "fleet_rank": 3, "rank": 3},
			],
			"ranking_state": {"visible": True},
			"discount_rankings": [{"warehouse": "SM AURA - X", "discount_pct": 12.5}],
			"channels": [],
		}

	def _scope(self):
		return {
			"selected_stores": [{"warehouse": "SM AURA - X"}],
			"stores": [{"warehouse": "SM AURA - X"}],
		}

	def _strip(self, payload, scope):
		from hrms.api.sales_dashboard import _strip_fleet_context_from_overview

		return _strip_fleet_context_from_overview(payload, scope)

	def test_strips_discount_rankings(self):
		out = self._strip(self._payload(), self._scope())
		self.assertEqual(out["discount_rankings"], [])

	def test_filters_stores_to_scope(self):
		out = self._strip(self._payload(), self._scope())
		warehouses = [s["warehouse"] for s in out.get("stores", [])]
		self.assertNotIn("BGC - X", warehouses)
		self.assertIn("SM AURA - X", warehouses)

	def test_strips_analysis_effects_baseline_keys(self):
		out = self._strip(self._payload(), self._scope())
		effects = out.get("analysis", {}).get("effects", {})
		self.assertNotIn("channel_mix_shift_vs_baseline", effects)
		self.assertNotIn("expected_net_sales_without_vat", effects)
		self.assertNotIn("actual_vs_expected_pct", effects)

	def test_ranking_state_visible_false(self):
		out = self._strip(self._payload(), self._scope())
		self.assertFalse(out.get("ranking_state", {}).get("visible", True))


class TestStripFleetFromProductMix(unittest.TestCase):
	def _payload(self):
		return {
			"products": [
				{
					"product_name": "Halo Halo Special",
					"total_quantity": 100,
					"total_gross_sales": 5000.0,
					"velocity": 3.3,
					"contribution_pct": 25.0,
					"trend_label": "strong",
					"fleet_rank": 7,
					"fleet_total_stores": 44,
					"per_store_breakdown": [{"location_id": 1, "rank": 7}],
					"wow_delta_pct": 12.5,
					"store_coverage": "1/44",
				}
			],
			"meta": {
				"is_single_store": True,
				"assortment_gap_count": 12,
				"assortment_gap_products": [{"product_name": "Coke Float"}],
				"total_products": 1,
			},
		}

	def _scope(self):
		return {"selected_stores": [{"warehouse": "SM AURA - X", "location_id": 1}]}

	def _strip(self, payload, scope):
		from hrms.api.sales_dashboard import _strip_fleet_context_from_product_mix

		return _strip_fleet_context_from_product_mix(payload, scope)

	def test_strips_fleet_rank(self):
		out = self._strip(self._payload(), self._scope())
		self.assertNotIn("fleet_rank", out["products"][0])

	def test_strips_fleet_total_stores(self):
		out = self._strip(self._payload(), self._scope())
		self.assertNotIn("fleet_total_stores", out["products"][0])

	def test_strips_per_store_breakdown(self):
		out = self._strip(self._payload(), self._scope())
		self.assertNotIn("per_store_breakdown", out["products"][0])

	def test_strips_assortment_gap_count_and_products(self):
		out = self._strip(self._payload(), self._scope())
		self.assertNotIn("assortment_gap_count", out["meta"])
		self.assertNotIn("assortment_gap_products", out["meta"])

	def test_rewrites_store_coverage_to_X_over_X(self):
		"""B13: literal '44' fleet count never appears for partners."""
		out = self._strip(self._payload(), self._scope())
		# scope has 1 selected store -> store_coverage should be "1/1"
		self.assertEqual(out["products"][0]["store_coverage"], "1/1")


class TestCachePoisoningPrevention(unittest.TestCase):
	"""V1/B1: deepcopy-before-strip protects cached objects from cross-role contamination."""

	def test_strip_does_not_mutate_via_deepcopy_pattern(self):
		from hrms.api.sales_dashboard import _strip_fleet_context_from_overview

		original = {
			"scope": {},
			"summary": {},
			"discount_rankings": [{"warehouse": "X"}],
			"stores": [{"warehouse": "BGC - X"}],
			"ranking_state": {"visible": True},
			"analysis": {"effects": {"expected_net_sales_without_vat": 100}},
		}
		clone = copy.deepcopy(original)
		_strip_fleet_context_from_overview(
			clone, {"stores": [{"warehouse": "SM AURA - X"}]}
		)
		self.assertEqual(original["discount_rankings"], [{"warehouse": "X"}])
		self.assertEqual(original["stores"], [{"warehouse": "BGC - X"}])
		self.assertTrue(original["ranking_state"]["visible"])
		self.assertEqual(
			original["analysis"]["effects"]["expected_net_sales_without_vat"], 100
		)


if __name__ == "__main__":
	unittest.main()
