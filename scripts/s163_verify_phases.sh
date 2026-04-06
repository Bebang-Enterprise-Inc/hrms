#!/bin/bash
# S163 phase verification gate. Run from BEI-ERP working dir.
# Usage: bash scripts/s163_verify_phases.sh <phase_number|all>
set -e
PHASE="${1:-all}"

err() { echo "FAIL: $1"; exit 1; }
ok() { echo "OK: $1"; }

phase1() {
  echo "=== Phase 1: DocTypes ==="
  for f in \
    hrms/hr/doctype/bei_store_order_component_recipe/bei_store_order_component_recipe.json \
    hrms/hr/doctype/bei_store_order_component_recipe_item/bei_store_order_component_recipe_item.json \
    hrms/hr/doctype/bei_store_order_product_policy/bei_store_order_product_policy.json \
    hrms/hr/doctype/bei_store_item_group/bei_store_item_group.json \
    hrms/hr/doctype/bei_store_item_group_member/bei_store_item_group_member.json; do
    test -f "$f" || err "missing $f"
  done
  grep -q "item_group_code" hrms/hr/doctype/bei_store_order_item/bei_store_order_item.json || err "item_group_code missing"
  grep -q "group_order_seq" hrms/hr/doctype/bei_store_order_item/bei_store_order_item.json || err "group_order_seq missing"
  grep -q "field:recipe_key" hrms/hr/doctype/bei_store_order_component_recipe/bei_store_order_component_recipe.json || err "autoname recipe missing"
  grep -q "field:group_code" hrms/hr/doctype/bei_store_item_group/bei_store_item_group.json || err "autoname group missing"
  grep -q "field:product_name" hrms/hr/doctype/bei_store_order_product_policy/bei_store_order_product_policy.json || err "autoname policy missing"
  ok "phase 1"
}

phase2() {
  echo "=== Phase 2: Migration ==="
  test -f scripts/s163_migrate_csv_to_doctypes.py || err "migration script missing"
  grep -q "savepoint" scripts/s163_migrate_csv_to_doctypes.py || err "savepoint missing"
  grep -q "BEI Store Order Component Recipe" scripts/s163_migrate_csv_to_doctypes.py || err "recipe doctype name missing"
  grep -q "BEI Store Order Product Policy" scripts/s163_migrate_csv_to_doctypes.py || err "policy doctype name missing"
  ok "phase 2"
}

phase3() {
  echo "=== Phase 3: Pipeline ==="
  grep -q "BEI Store Order Component Recipe" hrms/utils/store_order_demand_snapshot.py || err "doctype read missing"
  if grep -q "open(COMPONENT_RECIPE_PATH" hrms/utils/store_order_demand_snapshot.py; then err "CSV open still present"; fi
  grep -q "RuntimeError" hrms/utils/store_order_demand_snapshot.py || err "RuntimeError fallback missing"
  ok "phase 3"
}

phase4() {
  echo "=== Phase 4: Group aggregation ==="
  grep -q "BEI Store Item Group" hrms/api/store.py || err "group query missing"
  grep -q "is_group_row" hrms/api/store.py || err "is_group_row marker missing"
  ok "phase 4"
}

phase5() {
  echo "=== Phase 5: Submit order ==="
  grep -q "item_group_code" hrms/api/store.py || err "item_group_code field missing"
  grep -q "group_order_seq" hrms/api/store.py || err "group_order_seq field missing"
  grep -q "group_resolution_status" hrms/api/store.py || err "group_resolution_status missing"
  ok "phase 5"
}

phase6() {
  echo "=== Phase 6: SCM resolution ==="
  grep -q "def resolve_group_order_item" hrms/api/store.py || err "resolve endpoint missing"
  grep -q "expected_modified" hrms/api/store.py || err "optimistic locking missing"
  test -f ../bei-tasks/app/dashboard/scm/order-review/_components/GroupResolutionModal.tsx || err "modal missing"
  grep -rq "resolve_group_order_item" ../bei-tasks/app/api/ || err "proxy route missing"
  ok "phase 6"
}

phase7() {
  echo "=== Phase 7: Frontend ordering ==="
  grep -q "is_group_row" ../bei-tasks/hooks/use-ordering.ts || err "is_group_row missing in hook"
  grep -q "is_group_row" ../bei-tasks/app/dashboard/store-ops/ordering/_components/OrderItemTable.tsx || err "OrderItemTable missing marker"
  grep -q "is_group_row" ../bei-tasks/app/dashboard/store-ops/ordering/_components/OrderItemCard.tsx || err "OrderItemCard missing marker"
  ok "phase 7"
}

phase8() {
  echo "=== Phase 8: MR expansion ==="
  grep -q 'savepoint("create_mr_for_store_order"' hrms/api/store.py || err "MR savepoint missing"
  grep -q "custom_source_group_code" hrms/fixtures/custom_field.json || err "custom field missing"
  grep -q "custom_source_group_code" hrms/api/store.py || err "MR audit propagation missing"
  ok "phase 8"
}

phase9() {
  echo "=== Phase 9: Sentry ==="
  grep -A 40 "def resolve_group_order_item" hrms/api/store.py | grep -q "set_backend_observability_context" || err "Sentry missing on resolve"
  ok "phase 9"
}

audit_grpcheck() {
  echo "=== AUDIT-FIX: No GRP-* leaks into pick list ==="
  if grep -q "GRP-" hrms/api/picking.py 2>/dev/null; then err "GRP- leaked into picking.py"; fi
  ok "no GRP- in picking.py"
}

case "$PHASE" in
  1) phase1 ;;
  2) phase2 ;;
  3) phase3 ;;
  4) phase4 ;;
  5) phase5 ;;
  6) phase6 ;;
  7) phase7 ;;
  8) phase8 ;;
  9) phase9 ;;
  audit) audit_grpcheck ;;
  all) phase1; phase2; phase3; phase4; phase5; phase6; phase7; phase8; phase9; audit_grpcheck ;;
  *) echo "Unknown phase: $PHASE"; exit 2 ;;
esac
