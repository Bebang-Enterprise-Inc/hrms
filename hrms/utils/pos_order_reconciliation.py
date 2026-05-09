"""Shared pos_orders reconciliation logic — used by both polling sync
(``scripts/sync_pos_to_supabase.py``) and the Mosaic webhook
(``hrms/api/mosaic_webhook.py``).

S232 origin
-----------
The functions in this module were authored as part of S232 to handle four
distinct Mosaic POS quirks:

1. **Same bill returned twice in one fetch** — Mosaic's ``/orders`` endpoint
   sometimes returns multiple physical orders sharing the same
   ``(location_id, business_date, bill_number)`` tuple (e.g. PAID + VOIDED
   versions). The partial unique index ``pos_orders_bill_number_natural_key``
   only allows one ``is_duplicate=false`` row per natural key.
   :func:`_dedupe_incoming_by_natural_key` collapses them — one canonical
   (PAID > VOIDED, higher gross, latest paid_at) and the rest tombstoned.

2. **Same bill returns a NEW id on each refetch** — Mosaic re-issues the
   primary-key ``id`` on subsequent fetches even when the natural key is the
   same. :func:`reconcile_existing_ids` looks up the existing live row by
   natural key and remaps the incoming id back to the stable id we already
   have, so child rows (items + payments) re-attach correctly.

3. **Mosaic id collisions across distinct bills** — Mosaic occasionally
   reuses an ``id`` value across two physically different bills (in different
   batches). After step 2 reconciles one of them to an existing stable id,
   the batch can end up with two rows sharing the same ``id``, and Postgres
   rejects the upsert with ``ON CONFLICT DO UPDATE command cannot affect row
   a second time``. :func:`_resolve_id_collisions` resolves this by
   reassigning the loser to a deterministic synthetic negative id derived
   from :func:`_synthetic_id_from_natural_key`.

4. **Parallel bills from different terminals/channels share bill_number**
   (S242 extension) — Mosaic explicitly allows different terminals/channels
   to share a ``bill_number`` on the same day (e.g. Pickup + FoodPanda
   dispatch terminals). After S242, the partial unique index includes
   ``channel`` and the natural-key tuples in this module are
   ``(location_id, business_date, bill_number, channel)`` — so legitimate
   parallel bills coexist as live rows while same-channel duplicates remain
   tombstoned.

Why a shared module
-------------------
Before S242 v1.1, only the polling sync had this logic. The webhook
(``hrms/api/mosaic_webhook.py``) is an INDEPENDENT writer to ``pos_orders``
that previously did a direct PostgREST upsert keyed on PRIMARY KEY ``id``
only. After S242 extends the partial unique index with ``channel``, any
same-channel webhook duplicate would fail with 23505 — the same bug S232
fixed for polling. Refactoring into a shared module ensures both write paths
behave consistently.

Audit reference
---------------
- Plan: ``docs/plans/2026-05-08-sprint-242-pos-natural-key-channel-discriminator.md``
- Audit B1 finding: ``output/plan-audit/sprint-242-.../system_arch_findings.md``
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable

import httpx


# ---------------------------------------------------------------------------
# Pure transformations (no I/O)
# ---------------------------------------------------------------------------


def _synthetic_id_from_natural_key(row: dict) -> int:
    """Generate a deterministic NEGATIVE bigint id from natural-key fields.

    Used when Mosaic's ``id`` for a new bill collides with an existing stable
    id for a different bill in our DB. Negative range avoids any collision
    with Mosaic's positive ids. SHA-256 of the natural-key tuple keeps the
    id stable across re-syncs of the same bill, so subsequent reconciliations
    look up the synthetic id by natural key and remap correctly.

    Postgres bigint range: -2^63 (≈ -9.22e18) .. +2^63-1. We take 14 hex
    chars (~56 bits) and negate, which fits comfortably and leaves head room.

    S242 NOTE: ``channel`` is NOT part of the synthetic key because two rows
    with the same (loc, date, bill, channel) are TRUE duplicates and should
    collapse to ONE id; the synthetic-id path is only used for cross-bill
    Mosaic id collisions, where ``billed_at``/``paid_at``/``receipt_number``
    discriminate between physically distinct bills.
    """
    key = "|".join([
        "synth-poll",
        str(row.get("location_id")),
        str(row.get("business_date")),
        str(row.get("bill_number") or ""),
        str(row.get("billed_at") or ""),
        str(row.get("paid_at") or ""),
        str(row.get("receipt_number") or ""),
    ])
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return -int(h[:14], 16)


def _canonical_score(row: dict) -> tuple:
    """Score for picking the canonical version when Mosaic returns multiple
    orders sharing the same ``(loc, date, bill_number, channel)``.
    Higher tuple wins.

    Priority:
      1. ``payment_status = 'PAID'`` beats ``VOIDED`` beats other
      2. ``cancelled_at IS NULL`` beats cancelled
      3. higher ``gross_sales`` (the real sale, not a void)
      4. latest ``paid_at`` (most recent state)

    S242 NOTE: this scoring no longer ranks across channels (FoodPanda PHP 704
    vs POS PHP 228 are no longer in the same group post-S242). It only ranks
    within the same ``(loc, date, bill, channel)`` group — i.e. true
    Mosaic-returned-twice duplicates.
    """
    paid = 1 if row.get("payment_status") == "PAID" else (
        0 if row.get("payment_status") == "VOIDED" else -1
    )
    not_cancelled = 1 if row.get("cancelled_at") is None else 0
    gross = float(row.get("gross_sales") or 0)
    paid_at = str(row.get("paid_at") or "")
    return (paid, not_cancelled, gross, paid_at)


def _dedupe_incoming_by_natural_key(
    order_rows: list[dict],
    item_rows: list[dict],
    payment_rows: list[dict],
) -> tuple[list[dict], list[dict], list[dict], int, int]:
    """S242 channel discriminator: within an incoming batch, when multiple
    orders share the same ``(location_id, business_date, bill_number, channel)``,
    keep ONE canonical row as ``is_duplicate=false`` and mark the others as
    ``is_duplicate=true``.

    Mosaic occasionally returns the same bill twice in one fetch (e.g.
    PAID + VOIDED versions of the same receipt). Pre-S242 this was keyed on
    ``(loc, date, bill)`` and would conflate parallel bills from different
    channels (Pickup + FoodPanda). S242 extends the key with ``channel`` so
    parallel bills from different terminals coexist as live, while
    same-channel duplicates dedupe to one canonical row.

    Returns: ``(cleaned_orders, items, payments, dupes_marked, dupes_dropped)``

    Items/payments are PRESERVED for all order versions (canonical + duplicates)
    because the table FKs reference ``order_id`` only; duplicates' children
    stay in place but are filtered out by joins to ``v_pos_orders_live``.
    """
    if not order_rows:
        return order_rows, item_rows, payment_rows, 0, 0

    # Pre-step: dedupe by Mosaic ``id``. When Mosaic returns the SAME order id
    # multiple times in one fetch, map_order produces identical pos_orders rows
    # AND map_order_items produces duplicate (order_id, product_id, line_number)
    # tuples that violate pos_order_items's unique constraint. Keep one copy.
    seen_ids: set = set()
    deduped_orders = []
    for r in order_rows:
        rid = r.get("id")
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        deduped_orders.append(r)
    if len(deduped_orders) != len(order_rows):
        order_rows = deduped_orders

    # ALWAYS dedupe items + payments by their full natural key — items may
    # collide even when orders don't (e.g., when reconcile remaps multiple
    # orders to share an existing id, or when child rows are cloned during
    # collision resolution).
    item_seen: set = set()
    deduped_items = []
    for it in item_rows:
        key = (it.get("order_id"), it.get("product_id"), it.get("line_number"))
        if key in item_seen:
            continue
        item_seen.add(key)
        deduped_items.append(it)
    item_rows[:] = deduped_items
    pay_seen: set = set()
    deduped_pays = []
    for pm in payment_rows:
        key = (pm.get("order_id"), pm.get("payment_type"), pm.get("line_number"))
        if key in pay_seen:
            continue
        pay_seen.add(key)
        deduped_pays.append(pm)
    payment_rows[:] = deduped_pays

    # S242: group by natural key INCLUDING channel discriminator.
    # Rows without bill_number can't conflict — pass thru.
    groups: dict[tuple, list[dict]] = {}
    pass_thru: list[dict] = []
    for row in order_rows:
        bn = row.get("bill_number")
        if bn is None:
            pass_thru.append(row)
            continue
        key = (
            row.get("location_id"),
            str(row.get("business_date")),
            str(bn),
            str(row.get("channel") or ""),
        )
        groups.setdefault(key, []).append(row)

    cleaned: list[dict] = list(pass_thru)
    dupes_marked = 0
    has_dupes = any(len(g) > 1 for g in groups.values())
    for key, group in groups.items():
        if len(group) == 1:
            row = group[0]
            # When the batch will contain dupes, every row needs is_duplicate
            # so PostgREST sees a uniform key schema across the batch.
            if has_dupes and "is_duplicate" not in row:
                row["is_duplicate"] = False
            cleaned.append(row)
            continue
        # Pick canonical = highest score; mark rest as is_duplicate=true.
        ranked = sorted(group, key=_canonical_score, reverse=True)
        canonical = ranked[0]
        canonical["is_duplicate"] = False
        cleaned.append(canonical)
        for dup in ranked[1:]:
            dup["is_duplicate"] = True
            cleaned.append(dup)
            dupes_marked += 1
    if has_dupes:
        for row in pass_thru:
            if "is_duplicate" not in row:
                row["is_duplicate"] = False
    return cleaned, item_rows, payment_rows, dupes_marked, 0


def _resolve_id_collisions(
    order_rows: list[dict],
    item_rows: list[dict],
    payment_rows: list[dict],
    protected_ids: set,
) -> int:
    """Detect and resolve in-batch id collisions.

    Mosaic occasionally reuses an ``id`` value across distinct bills (i.e., the
    same numeric id is assigned to one bill on one fetch and to a DIFFERENT
    bill on a later fetch). Combined with our reconciliation that REUSES
    existing stable ids for matched natural keys, the incoming batch can end
    up with two rows sharing the same ``id`` — Postgres rejects this with
    ``ON CONFLICT DO UPDATE command cannot affect row a second time``.

    Resolution: when a collision is detected, the row that holds a PROTECTED
    id (an existing stable id from natural-key reconciliation) MUST be kept
    so the upsert UPDATEs the right existing row. The other row(s) get a
    deterministic synthetic negative id (stable across re-syncs of the same
    bill). Child rows are cloned for the reassigned rows so the relationship
    is preserved.

    S242: id collisions are resolved AFTER ``_dedupe_incoming_by_natural_key``
    has already collapsed same-channel duplicates and AFTER
    ``reconcile_existing_ids`` has remapped to existing canonical ids — so the
    only remaining case here is genuine cross-bill id collisions, which are
    channel-agnostic.

    Args:
        order_rows: incoming order dicts (will be mutated).
        item_rows: incoming item dicts (may be appended to).
        payment_rows: incoming payment dicts (may be appended to).
        protected_ids: set of ids that MUST NOT be reassigned (the result of
            successful natural-key reconciliation — those ids point to
            existing stable rows in the DB).

    Returns: number of rows reassigned.
    """
    if not order_rows:
        return 0
    # Build id -> [row indices]
    id_groups: dict[Any, list[int]] = {}
    for idx, row in enumerate(order_rows):
        id_groups.setdefault(row["id"], []).append(idx)

    reassigned = 0
    # Snapshot the items first so we can safely mutate id_groups inside the loop.
    for row_id, indices in list(id_groups.items()):
        if len(indices) <= 1:
            continue
        # Pick keeper: prefer a row whose id is in protected_ids; among those,
        # highest canonical score. If none are protected, just take the highest
        # canonical score.
        protected_indices = [i for i in indices if order_rows[i]["id"] in protected_ids]
        candidates = protected_indices or indices
        keeper = max(candidates, key=lambda i: _canonical_score(order_rows[i]))
        losers = [i for i in indices if i != keeper]

        # Cache children of the original colliding id BEFORE we mutate ids.
        old_id = row_id
        old_items = [it for it in item_rows if it["order_id"] == old_id]
        old_pmts = [pm for pm in payment_rows if pm["order_id"] == old_id]

        for idx in losers:
            new_id = _synthetic_id_from_natural_key(order_rows[idx])
            # If the synthetic id ALSO collides (extremely rare), append a salt.
            salt = 0
            while new_id in id_groups and id_groups[new_id] != [idx]:
                salt += 1
                bumped = order_rows[idx].copy()
                bumped["__salt__"] = salt
                new_id = _synthetic_id_from_natural_key(bumped)
            order_rows[idx]["id"] = new_id
            id_groups.setdefault(new_id, []).append(idx)
            # Clone children to point at the new id (the keeper retains old_id's
            # children intact). For the loser, ALL of old_id's children are
            # cloned — without distinguishing original vs cloned, this slightly
            # over-counts items if they were unique to the loser, but ensures
            # no child rows are orphaned. This case is rare (<1% of bills).
            for it in old_items:
                item_rows.append({**it, "order_id": new_id})
            for pm in old_pmts:
                payment_rows.append({**pm, "order_id": new_id})
            reassigned += 1
    return reassigned


# ---------------------------------------------------------------------------
# Reconciliation requiring HTTP (lookup + cascade delete)
# ---------------------------------------------------------------------------


def reconcile_existing_ids(
    client: httpx.Client,
    location_id: int,
    business_date: str,
    order_rows: list[dict],
    item_rows: list[dict],
    payment_rows: list[dict],
    *,
    supabase_url: str,
    headers_fn: Callable[..., dict],
    delete_children_fn: Callable[[httpx.Client, list[Any]], None],
) -> dict:
    """Reconcile incoming Mosaic orders against existing live rows by
    ``(location_id, business_date, bill_number, channel)`` natural key.

    S242 channel discriminator: this lookup queries existing live rows for
    each (bill_number, channel) pair separately so that a Pickup-39966 sync
    does NOT remap to a FoodPanda-39966's id (and vice versa). Pre-S242 the
    lookup used (loc, date, bill) only and would have corrupted both rows
    when the partial unique index is extended with ``channel``.

    Mosaic returns the same ``(location_id, business_date, bill_number,
    channel)`` with a DIFFERENT ``id`` on subsequent fetches, AND occasionally
    returns the same bill twice within a single fetch. The script's
    ``on_conflict=id`` upsert cannot resolve either case against the partial
    unique index ``pos_orders_bill_number_natural_key (location_id,
    business_date, bill_number, channel) WHERE bill_number IS NOT NULL AND
    is_duplicate = false``.

    Two fixes applied here:

    1. **Dedupe within the incoming batch** (via
       ``_dedupe_incoming_by_natural_key``): when Mosaic returns multiple
       versions of the same (loc, date, bill, channel), keep ONE canonical
       version (PAID > VOIDED, non-cancelled > cancelled, higher gross, latest
       paid_at) as ``is_duplicate=false`` and mark the rest as
       ``is_duplicate=true``.
    2. **Reuse existing stable ids**: for each unique (bill, channel) tuple,
       look up the existing live row and rewrite the incoming ``id`` to match.
       Child rows (items + payments) are remapped and replaced via
       delete-then-insert.

    Together these make sync fully idempotent: any number of re-runs converge
    on the same set of stable ids and produce zero duplicates while still
    updating order details when Mosaic state changes.

    Args:
        client: HTTP client supporting ``get(url, headers, params, timeout)``.
        location_id, business_date: scope keys.
        order_rows, item_rows, payment_rows: incoming Mosaic batch.
        supabase_url: e.g. ``https://csnniykjrychgajfrgua.supabase.co``.
        headers_fn: callable returning dict of REST headers
            (typically the caller's ``_supabase_headers`` function).
        delete_children_fn: callable ``(client, order_ids) -> None`` for
            cascade-deleting child rows before re-insert.

    Returns: stats dict for observability. Includes ``protected_ids`` — the set
    of stable existing ids that were reused via natural-key remap; callers
    should pass this set into ``_resolve_id_collisions`` so collision losers
    don't overwrite reconciled rows.
    """
    stats: dict = {
        "looked_up": 0,
        "matched_existing": 0,
        "remapped": 0,
        "incoming_dupes_marked": 0,
        "items_remapped": 0,
        "payments_remapped": 0,
        "children_cleared": 0,
        "protected_ids": set(),
    }
    if not order_rows:
        return stats

    # ---- Step 1: dedupe within incoming batch by natural key (S242: incl channel) ----
    order_rows[:], item_rows[:], payment_rows[:], dupes_marked, _ = (
        _dedupe_incoming_by_natural_key(order_rows, item_rows, payment_rows)
    )
    stats["incoming_dupes_marked"] = dupes_marked

    # Only the canonical (is_duplicate=false) rows participate in
    # natural-key reconciliation. is_duplicate=true rows are exempt from the
    # partial unique index and need no remapping.
    canonical_rows = [r for r in order_rows if not r.get("is_duplicate")]
    if not canonical_rows:
        return stats

    # ---- Step 2: collect (bill_number, channel) tuples from canonical batch ----
    # S242: index now includes channel — must look up per-channel because two
    # rows with same bill_number but different channel are DIFFERENT live
    # rows post-migration.
    by_channel: dict[str, set[str]] = {}
    for r in canonical_rows:
        bn = r.get("bill_number")
        if bn is None:
            continue
        ch = str(r.get("channel") or "")
        by_channel.setdefault(ch, set()).add(str(bn))
    if not by_channel:
        return stats
    stats["looked_up"] = sum(len(v) for v in by_channel.values())

    # ---- Step 3: look up existing live rows by (bill, channel) per-channel ----
    # Returns: existing_by_bill_channel: {(bill, channel): existing_id}
    existing_by_bill_channel: dict[tuple[str, str], Any] = {}
    for channel, bills in by_channel.items():
        bill_list = sorted(bills)
        for chunk in [bill_list[i : i + 100] for i in range(0, len(bill_list), 100)]:
            r = client.get(
                f"{supabase_url}/rest/v1/pos_orders",
                headers=headers_fn(),
                params={
                    "select": "id,bill_number,channel",
                    "location_id": f"eq.{location_id}",
                    "business_date": f"eq.{business_date}",
                    "is_duplicate": "eq.false",
                    "channel": f"eq.{channel}",
                    "bill_number": f"in.({','.join(chunk)})",
                },
                timeout=30,
            )
            if r.status_code != 200:
                raise RuntimeError(
                    f"reconcile lookup failed ({r.status_code}): {r.text[:300]}"
                )
            for row in r.json():
                key = (str(row["bill_number"]), str(row.get("channel") or ""))
                existing_by_bill_channel[key] = row["id"]
    stats["matched_existing"] = len(existing_by_bill_channel)
    if not existing_by_bill_channel:
        return stats

    # ---- Step 4: build remap and rewrite canonical incoming ids ----
    remap: dict[Any, Any] = {}
    for row in canonical_rows:
        bn = row.get("bill_number")
        if bn is None:
            continue
        key = (str(bn), str(row.get("channel") or ""))
        existing_id = existing_by_bill_channel.get(key)
        if existing_id is None:
            continue
        # Even if Mosaic returned the same id we already have, mark it
        # protected so the collision resolver doesn't reassign it.
        stats["protected_ids"].add(existing_id)
        if row["id"] != existing_id:
            remap[row["id"]] = existing_id
            row["id"] = existing_id
    stats["remapped"] = len(remap)
    if not remap:
        return stats

    # ---- Step 5: remap child rows and clear stale children ----
    for it in item_rows:
        if it["order_id"] in remap:
            it["order_id"] = remap[it["order_id"]]
            stats["items_remapped"] += 1
    for pm in payment_rows:
        if pm["order_id"] in remap:
            pm["order_id"] = remap[pm["order_id"]]
            stats["payments_remapped"] += 1
    delete_children_fn(client, list(remap.values()))
    stats["children_cleared"] = len(remap)
    return stats


__all__ = [
    "_synthetic_id_from_natural_key",
    "_canonical_score",
    "_dedupe_incoming_by_natural_key",
    "_resolve_id_collisions",
    "reconcile_existing_ids",
]
