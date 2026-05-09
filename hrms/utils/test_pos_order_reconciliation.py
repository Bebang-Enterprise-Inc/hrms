"""S242 v1.1 Phase 1.A.4: unit tests for the shared pos_order_reconciliation
module. Verifies three behaviors that are critical post-migration:

1. Channel-distinct natural keys do NOT conflate (Pickup + FoodPanda sharing
   bill 39966 stay as 2 distinct canonical rows).
2. Same-channel duplicates dedupe to ONE canonical row using _canonical_score.
3. Mosaic id collisions across distinct bills resolve via synthetic id.

Run from repo root:
    python hrms/utils/test_pos_order_reconciliation.py

(Direct execution avoids `hrms/utils/__init__.py`'s frappe.utils import which
only resolves inside a Frappe bench. The shared module under test has no
Frappe dependencies.)
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

# Load the shared module directly without triggering hrms/utils/__init__.py
# (which imports frappe.utils — unavailable outside a Frappe bench).
_SPEC = importlib.util.spec_from_file_location(
    "_pos_order_reconciliation",
    Path(__file__).parent / "pos_order_reconciliation.py",
)
_module = importlib.util.module_from_spec(_SPEC)  # type: ignore
sys.modules["_pos_order_reconciliation"] = _module
_SPEC.loader.exec_module(_module)  # type: ignore

_canonical_score = _module._canonical_score
_dedupe_incoming_by_natural_key = _module._dedupe_incoming_by_natural_key
_resolve_id_collisions = _module._resolve_id_collisions
_synthetic_id_from_natural_key = _module._synthetic_id_from_natural_key


class TestChannelDistinctNoConflate(unittest.TestCase):
    """The Paseo bill 39966 case: FoodPanda and POS share bill_number on the
    same store-day. Pre-S242 this would be deduped to ONE row (the higher-
    canonical-score one). Post-S242 the channel discriminator means they
    coexist as 2 distinct canonical rows.
    """

    def test_channel_distinct_no_conflate(self) -> None:
        order_rows = [
            {
                "id": 51234223,
                "location_id": 2177,
                "business_date": "2026-04-21",
                "bill_number": 39966,
                "channel": "FoodPanda",
                "payment_status": "PAID",
                "cancelled_at": None,
                "gross_sales": 704.00,
                "paid_at": "2026-04-21T06:01:39+00:00",
            },
            {
                "id": 51234586,
                "location_id": 2177,
                "business_date": "2026-04-21",
                "bill_number": 39966,
                "channel": "POS",
                "payment_status": "PAID",
                "cancelled_at": None,
                "gross_sales": 228.00,
                "paid_at": "2026-04-21T05:31:30+00:00",
            },
        ]
        item_rows: list[dict] = []
        payment_rows: list[dict] = []

        cleaned, _items, _pmts, dupes_marked, _dropped = (
            _dedupe_incoming_by_natural_key(order_rows, item_rows, payment_rows)
        )

        # Both rows survive as canonical (is_duplicate=false).
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(dupes_marked, 0)
        for row in cleaned:
            self.assertFalse(
                row.get("is_duplicate", False),
                f"Row {row['id']} channel={row['channel']} should be canonical "
                "but was marked is_duplicate=true",
            )
        # Channels are preserved.
        channels = {row["channel"] for row in cleaned}
        self.assertEqual(channels, {"FoodPanda", "POS"})


class TestSameChannelDedupesCanonical(unittest.TestCase):
    """Mosaic occasionally returns the same bill twice in one fetch (e.g. PAID
    + VOIDED versions). When both hits are SAME channel, dedup picks PAID >
    VOIDED, higher gross, latest paid_at — same canonical_score logic as S232.
    """

    def test_same_channel_dedupes_canonical(self) -> None:
        order_rows = [
            {
                "id": 99999001,
                "location_id": 2178,
                "business_date": "2026-05-01",
                "bill_number": 12345,
                "channel": "POS",
                "payment_status": "VOIDED",
                "cancelled_at": "2026-05-01T08:00:00+00:00",
                "gross_sales": 350.00,
                "paid_at": "2026-05-01T07:45:00+00:00",
            },
            {
                "id": 99999002,
                "location_id": 2178,
                "business_date": "2026-05-01",
                "bill_number": 12345,
                "channel": "POS",
                "payment_status": "PAID",
                "cancelled_at": None,
                "gross_sales": 350.00,
                "paid_at": "2026-05-01T07:50:00+00:00",
            },
        ]
        cleaned, _items, _pmts, dupes_marked, _dropped = (
            _dedupe_incoming_by_natural_key(order_rows, [], [])
        )

        # 2 rows in, 2 rows out; one canonical, one tombstone.
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(dupes_marked, 1)

        canonical = [r for r in cleaned if not r.get("is_duplicate")]
        tombstones = [r for r in cleaned if r.get("is_duplicate")]
        self.assertEqual(len(canonical), 1)
        self.assertEqual(len(tombstones), 1)

        # PAID beats VOIDED on canonical_score.
        self.assertEqual(canonical[0]["payment_status"], "PAID")
        self.assertEqual(canonical[0]["id"], 99999002)
        self.assertEqual(tombstones[0]["payment_status"], "VOIDED")
        self.assertEqual(tombstones[0]["id"], 99999001)


class TestMosaicIdCollisionSynthetic(unittest.TestCase):
    """Mosaic occasionally reuses an id across two physically distinct bills
    (different (loc, date, bill, channel) tuples but same numeric id). After
    reconcile_existing_ids has remapped one of them to an existing canonical
    id, the batch can have two rows with the same numeric id. Postgres
    rejects the upsert with `cannot affect row a second time`. The collision
    resolver assigns a synthetic negative bigint to the loser to break the
    tie.
    """

    def test_mosaic_id_collision_synthetic(self) -> None:
        # Two physically distinct bills sharing id=77777 (Mosaic id reuse).
        order_rows = [
            {
                "id": 77777,
                "location_id": 2179,
                "business_date": "2026-05-02",
                "bill_number": 5001,
                "channel": "POS",
                "payment_status": "PAID",
                "cancelled_at": None,
                "gross_sales": 500.00,
                "paid_at": "2026-05-02T03:00:00+00:00",
                "billed_at": "2026-05-02T03:00:00+00:00",
                "receipt_number": "R-5001",
            },
            {
                "id": 77777,  # SAME id, but DIFFERENT bill (Mosaic reuse)
                "location_id": 2179,
                "business_date": "2026-05-02",
                "bill_number": 5002,
                "channel": "POS",
                "payment_status": "PAID",
                "cancelled_at": None,
                "gross_sales": 200.00,
                "paid_at": "2026-05-02T04:00:00+00:00",
                "billed_at": "2026-05-02T04:00:00+00:00",
                "receipt_number": "R-5002",
            },
        ]
        item_rows = [
            {"order_id": 77777, "product_id": 1, "line_number": 0, "name": "item-a"},
        ]
        payment_rows = [
            {"order_id": 77777, "payment_type": "CASH", "line_number": 0, "amount": 500},
        ]

        # Suppose the keeper's id is in protected_ids (came from reconcile)
        protected_ids = {77777}

        reassigned = _resolve_id_collisions(
            order_rows, item_rows, payment_rows, protected_ids,
        )

        # One row reassigned to a synthetic negative id.
        self.assertEqual(reassigned, 1)
        ids = sorted([r["id"] for r in order_rows])
        self.assertEqual(len(ids), 2)
        # One id is the original 77777, the other is a NEGATIVE synthetic id.
        self.assertIn(77777, ids)
        synthetic_ids = [i for i in ids if i != 77777]
        self.assertEqual(len(synthetic_ids), 1)
        self.assertLess(synthetic_ids[0], 0,
                        "Synthetic id must be negative to avoid Mosaic-id collisions")

        # Children are cloned for the reassigned row.
        item_order_ids = {it["order_id"] for it in item_rows}
        self.assertIn(77777, item_order_ids)
        self.assertIn(synthetic_ids[0], item_order_ids)


class TestSyntheticIdDeterminism(unittest.TestCase):
    """The synthetic id must be deterministic across re-syncs of the same
    bill so subsequent reconciliations look up the same id and remap
    correctly.
    """

    def test_synthetic_id_deterministic(self) -> None:
        row = {
            "location_id": 2180,
            "business_date": "2026-05-03",
            "bill_number": 6001,
            "billed_at": "2026-05-03T03:00:00+00:00",
            "paid_at": "2026-05-03T03:05:00+00:00",
            "receipt_number": "R-6001",
        }
        id1 = _synthetic_id_from_natural_key(row)
        id2 = _synthetic_id_from_natural_key(dict(row))  # fresh dict, same data
        self.assertEqual(id1, id2)
        self.assertLess(id1, 0)

    def test_synthetic_id_changes_with_natural_key(self) -> None:
        row1 = {
            "location_id": 2180,
            "business_date": "2026-05-03",
            "bill_number": 6001,
            "billed_at": "2026-05-03T03:00:00+00:00",
            "paid_at": "2026-05-03T03:05:00+00:00",
            "receipt_number": "R-6001",
        }
        row2 = dict(row1, bill_number=6002)
        self.assertNotEqual(
            _synthetic_id_from_natural_key(row1),
            _synthetic_id_from_natural_key(row2),
        )


class TestCanonicalScoreOrdering(unittest.TestCase):
    """The canonical score must order PAID > VOIDED > other, then non-cancelled
    > cancelled, then higher gross, then latest paid_at.
    """

    def test_paid_beats_voided(self) -> None:
        paid = {"payment_status": "PAID", "cancelled_at": None,
                "gross_sales": 100, "paid_at": "2026-05-01T00:00:00"}
        voided = {"payment_status": "VOIDED", "cancelled_at": None,
                  "gross_sales": 9999, "paid_at": "2026-05-01T00:01:00"}
        self.assertGreater(_canonical_score(paid), _canonical_score(voided))

    def test_higher_gross_beats_lower(self) -> None:
        # Both PAID, both not cancelled; gross is the tiebreaker.
        a = {"payment_status": "PAID", "cancelled_at": None,
             "gross_sales": 200, "paid_at": "2026-05-01T00:00:00"}
        b = {"payment_status": "PAID", "cancelled_at": None,
             "gross_sales": 100, "paid_at": "2026-05-01T00:00:00"}
        self.assertGreater(_canonical_score(a), _canonical_score(b))


if __name__ == "__main__":
    unittest.main()
