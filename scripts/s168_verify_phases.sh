#!/bin/bash
# S168 phase verification gate. Run from BEI-ERP working dir.
# Usage: bash scripts/s168_verify_phases.sh <phase_number|all>
#
# Implements MUST_MODIFY/MUST_CONTAIN assertions per phase per the plan
# 2026-04-07-sprint-168-bki-store-sale-billing-on-delivery.md (R1+R2 amendments).
set -e
PHASE="${1:-all}"

err() { echo "FAIL: $1"; exit 1; }
ok() { echo "OK: $1"; }

# ---------------------------------------------------------------------------
# Phase 0 — Pre-flight scripts + audit JSON stubs
# ---------------------------------------------------------------------------
phase0() {
  echo "=== Phase 0: Pre-flight ==="
  for f in \
    scripts/s168_audit_bki_coa.py \
    scripts/s168_audit_missing_customers.py \
    scripts/s168_audit_vat_template.py \
    scripts/s168_audit_receiving_baseline.py \
    scripts/s168_verify_phases.sh; do
    test -f "$f" || err "missing $f"
  done
  grep -q "2102205" scripts/s168_audit_bki_coa.py || err "audit_bki_coa.py missing 2102205 OUTPUT VAT PAYABLE check"
  grep -q "4000100" scripts/s168_audit_bki_coa.py || err "audit_bki_coa.py missing 4000100 wholesale group check"
  grep -q "4000101" scripts/s168_audit_bki_coa.py || err "audit_bki_coa.py missing 4000101 sales-bki-to-stores check"
  grep -q "store_buyer_entity_register" scripts/s168_audit_missing_customers.py || err "audit_missing_customers.py not loading S037 register"
  grep -q "Sales Taxes and Charges Template" scripts/s168_audit_vat_template.py || err "audit_vat_template.py not querying SI tax templates"
  grep -q "BEI Store Receiving" scripts/s168_audit_receiving_baseline.py || err "receiving baseline not querying receiving doctype"
  ok "phase 0"
}

# ---------------------------------------------------------------------------
# Phase 1 — DocType + custom field schema extensions
# ---------------------------------------------------------------------------
phase1() {
  echo "=== Phase 1: Schema extensions ==="
  local SETTINGS=hrms/hr/doctype/bei_settings/bei_settings.json
  local FIXT=hrms/fixtures/custom_field.json
  test -f "$SETTINGS" || err "missing $SETTINGS"
  test -f "$FIXT" || err "missing $FIXT"
  # BEI Settings new fields
  for f in \
    bki_markup_jv_percent \
    bki_markup_managed_franchise_percent \
    bki_markup_full_franchise_percent \
    bki_sales_vat_template \
    bki_sales_income_account \
    bki_default_incoterm; do
    grep -q "\"$f\"" "$SETTINGS" || err "BEI Settings missing field $f"
  done
  grep -q "section_break_bki_billing" "$SETTINGS" || err "BEI Settings missing section_break_bki_billing"
  # Sales Invoice custom fields
  grep -q "Sales Invoice-custom_bei_store_order" "$FIXT" || err "fixture missing Sales Invoice-custom_bei_store_order"
  grep -q "Sales Invoice-custom_bei_receiving" "$FIXT" || err "fixture missing Sales Invoice-custom_bei_receiving"
  grep -q "Sales Invoice-custom_delivery_receipt_no" "$FIXT" || err "fixture missing Sales Invoice-custom_delivery_receipt_no"
  grep -q "Sales Invoice-custom_bei_store_billing" "$FIXT" || err "fixture missing Sales Invoice-custom_bei_store_billing (R2-C5)"
  grep -q "Sales Invoice-custom_stock_entry" "$FIXT" || err "fixture missing Sales Invoice-custom_stock_entry"
  # BEI Store Receiving custom fields
  grep -q "BEI Store Receiving-delivery_receipt_no" "$FIXT" || err "fixture missing BEI Store Receiving-delivery_receipt_no"
  grep -q "BEI Store Receiving-sales_invoice" "$FIXT" || err "fixture missing BEI Store Receiving-sales_invoice"
  grep -q "BEI Store Receiving-acceptance_date" "$FIXT" || err "fixture missing BEI Store Receiving-acceptance_date"
  # BEI Billing Schedule reverse link to SI (R2-C10)
  grep -q "BEI Billing Schedule-sales_invoice" "$FIXT" || err "fixture missing BEI Billing Schedule-sales_invoice (R2-C10)"
  ok "phase 1"
}

# ---------------------------------------------------------------------------
# Phases 2-8 (Session A backend) — stubs to be filled in by other agents
# ---------------------------------------------------------------------------
phase2() {
  echo "=== Phase 2: BKI sale builders + register cache reload ==="
  grep -q "def build_bki_store_sale_invoice" hrms/api/commissary.py || err "build_bki_store_sale_invoice missing"
  grep -q "def clear_buyer_entity_cache" hrms/api/commissary.py 2>/dev/null \
    || grep -q "def clear_buyer_entity_cache" hrms/api/store.py 2>/dev/null \
    || err "clear_buyer_entity_cache endpoint missing (Amendment 10)"
  ok "phase 2"
}

phase3() {
  echo "=== Phase 3: Draft SI on fulfillment ==="
  grep -q "_compute_si_row_qty_from_receiving" hrms/api/commissary.py || err "_compute_si_row_qty_from_receiving missing"
  if grep -q "filters_query=" hrms/api/commissary.py; then
    err "filters_query bug still present in commissary.py (Amendment - Phase 3.2)"
  fi
  ok "phase 3"
}

phase4() {
  echo "=== Phase 4: Submit SI on receiving acceptance ==="
  grep -q "complete_receiving" hrms/api/store.py || err "complete_receiving entry point missing"
  grep -q "custom_bei_receiving" hrms/api/store.py || err "store.py not linking SI to receiving"
  ok "phase 4"
}

phase5() {
  echo "=== Phase 5: Customer + VAT template seed ==="
  test -f scripts/s168_seed_customers.py || err "scripts/s168_seed_customers.py missing"
  grep -q "BKI Store" scripts/s168_seed_customers.py || err "seed missing BKI Store customer group precreate (Amendment 5)"
  grep -q "4000101" scripts/s168_seed_customers.py 2>/dev/null \
    || grep -q "bki_sales_income_account" scripts/s168_seed_customers.py \
    || err "seed not wiring sales income account"
  ok "phase 5"
}

phase6() {
  echo "=== Phase 6: Markup + pricing rules ==="
  grep -q "bki_markup_jv_percent" hrms/api/commissary.py || err "commissary.py not reading markup from BEI Settings"
  ok "phase 6"
}

phase7() {
  echo "=== Phase 7: Stock Entry on_cancel hook ==="
  grep -q "custom_sales_invoice_draft" hrms/api/commissary.py 2>/dev/null \
    || grep -q "custom_sales_invoice_draft" hrms/hooks.py \
    || err "Stock Entry on_cancel hook for orphan SI cleanup missing (Amendment Phase 2.7)"
  ok "phase 7"
}

phase8() {
  echo "=== Phase 8: Session A checkpoint commit ==="
  test -f output/s168/SESSION_A_COMPLETE.flag || err "Session A sentinel flag missing (R2-C6)"
  ok "phase 8"
}

# ---------------------------------------------------------------------------
# Phases 9-16 (Session B frontend + finalization)
# ---------------------------------------------------------------------------
phase9() {
  echo "=== Phase 9: DR input on receiving (bei-tasks) ==="
  local PAGE=../bei-tasks/app/dashboard/receiving/\[tripName\]/page.tsx
  local HOOK=../bei-tasks/hooks/use-receiving.ts
  test -f "$PAGE" || err "missing $PAGE"
  test -f "$HOOK" || err "missing $HOOK"
  grep -q "delivery_receipt_no" "$PAGE" || err "receiving page missing delivery_receipt_no field"
  grep -q "const \[deliveryReceiptNo" "$PAGE" || err "receiving page missing deliveryReceiptNo state"
  grep -q "delivery_receipt_no" "$HOOK" || err "use-receiving hook missing delivery_receipt_no param"
  ok "phase 9"
}

phase10() {
  echo "=== Phase 10: approve_billing fee SI + idempotency ==="
  grep -q "savepoint(\"s168_approve_billing_si\"" hrms/api/billing.py || err "approve_billing missing s168_approve_billing_si savepoint (Amendment 4)"
  grep -q "savepoint(\"s168_billing_rollup\"" hrms/api/billing.py || err "billing rollup savepoint missing"
  grep -q "set_backend_observability_context" hrms/api/billing.py || err "billing.py missing Sentry context (R2-C10)"
  grep -q "Sales Invoice-custom_bei_store_billing" hrms/fixtures/custom_field.json || err "custom_bei_store_billing fixture missing (R2-C5)"
  ok "phase 10"
}

phase11() {
  echo "=== Phase 11: Credit note flow ==="
  grep -q "def create_store_sale_credit_note" hrms/api/billing.py || err "create_store_sale_credit_note missing"
  grep -q "savepoint(\"s168_credit_note\"" hrms/api/billing.py || err "credit note savepoint missing (Amendment 3)"
  test -f ../bei-tasks/components/billing/credit-note-modal.tsx || err "credit-note-modal.tsx missing"
  grep -q "createStoreSaleCreditNote" ../bei-tasks/hooks/use-billing.ts || err "use-billing.ts missing createStoreSaleCreditNote"
  ok "phase 11"
}

phase12() {
  echo "=== Phase 12: BIR-aware naming series + posting date ==="
  grep -q "bki_sales_naming_series" hrms/api/commissary.py 2>/dev/null \
    || grep -q "bki_sales_naming_series" hrms/api/billing.py \
    || err "naming series wiring missing"
  ok "phase 12"
}

phase13() {
  echo "=== Phase 13: EWT toggle (defaults OFF) ==="
  grep -q "default_ewt_rate" hrms/api/billing.py 2>/dev/null \
    || grep -q "default_ewt_rate" hrms/api/commissary.py \
    || err "EWT field reuse missing (Amendment 9)"
  ok "phase 13"
}

phase14() {
  echo "=== Phase 14: Billing holds dashboard ==="
  for fn in get_billing_holds release_billing_hold reject_billing_hold reassign_billing_hold_customer; do
    grep -q "def $fn" hrms/api/billing.py || err "billing.py missing $fn (Amendment 2)"
  done
  # Sentry + savepoint per Amendment 2 / R2-C10
  grep -A 8 "def release_billing_hold" hrms/api/billing.py | grep -q "set_backend_observability_context" || err "release_billing_hold missing Sentry"
  grep -A 30 "def release_billing_hold" hrms/api/billing.py | grep -q "s168_release_hold" || err "release_billing_hold missing savepoint"
  grep -A 30 "def reject_billing_hold" hrms/api/billing.py | grep -q "s168_reject_hold" || err "reject_billing_hold missing savepoint"
  grep -A 30 "def reassign_billing_hold_customer" hrms/api/billing.py | grep -q "s168_reassign_hold" || err "reassign_billing_hold_customer missing savepoint"
  test -f ../bei-tasks/app/dashboard/accounting/billing-holds/page.tsx || err "billing holds page missing"
  test -f ../bei-tasks/app/api/billing-holds/route.ts || err "billing holds API proxy missing"
  grep -q "BILLING_HOLDS" ../bei-tasks/lib/roles.ts || err "roles.ts missing BILLING_HOLDS module (R2-C4)"
  grep -q "BILLING_HOLDS" ../bei-tasks/lib/navigation-personas.ts || err "navigation-personas.ts missing BILLING_HOLDS"
  ok "phase 14"
}

phase15() {
  echo "=== Phase 15: Same-company reclassification JE + reversal ==="
  grep -q "def reverse_same_company_reclassification_je" hrms/api/store.py || err "reversal endpoint missing (R2-C10)"
  # DM-6: reclass JE rows must include reference_type/reference_name from Stock Entry
  grep -q "reference_type" hrms/api/store.py || err "reclass JE missing reference_type (DM-6)"
  grep -q "Stock Entry" hrms/api/store.py || err "reclass JE missing Stock Entry reference"
  ok "phase 15"
}

phase16() {
  echo "=== Phase 16: L3 evidence (R2-C8 git-gated) ==="
  test -f output/l3/s168/form_submissions.json || err "L3 form_submissions.json missing (R2-C8)"
  test -f output/l3/s168/api_mutations.json || err "L3 api_mutations.json missing (R2-C8)"
  test -f output/l3/s168/state_verification.json || err "L3 state_verification.json missing (R2-C8)"
  ok "phase 16"
}

case "$PHASE" in
  0) phase0 ;;
  1) phase1 ;;
  2) phase2 ;;
  3) phase3 ;;
  4) phase4 ;;
  5) phase5 ;;
  6) phase6 ;;
  7) phase7 ;;
  8) phase8 ;;
  9) phase9 ;;
  10) phase10 ;;
  11) phase11 ;;
  12) phase12 ;;
  13) phase13 ;;
  14) phase14 ;;
  15) phase15 ;;
  16) phase16 ;;
  all) phase0; phase1; phase2; phase3; phase4; phase5; phase6; phase7; phase8; phase9; phase10; phase11; phase12; phase13; phase14; phase15; phase16 ;;
  *) echo "Unknown phase: $PHASE"; exit 2 ;;
esac
