#!/usr/bin/env bash
set -e
PHASE="$1"  # L, S, or C; ALL runs all three
cd /f/Dropbox/Projects/bei-tasks

if [ "$PHASE" = "L" ] || [ "$PHASE" = "ALL" ]; then
  test -f tests/e2e/pages/PurchaseRequisitionPage.ts || { echo "X PurchaseRequisitionPage missing"; exit 1; }
  test -f tests/e2e/pages/PurchaseOrderPage.ts || { echo "X PurchaseOrderPage missing"; exit 1; }
  test -f tests/e2e/pages/GoodsReceiptPage.ts || { echo "X GoodsReceiptPage missing"; exit 1; }
  test -f tests/e2e/pages/InvoicePage.ts || { echo "X InvoicePage missing"; exit 1; }
  test -f tests/e2e/pages/PaymentRequestPage.ts || { echo "X PaymentRequestPage missing"; exit 1; }
  test -f tests/e2e/pages/MatchExceptionPage.ts || { echo "X MatchExceptionPage missing"; exit 1; }
  test -f tests/e2e/builders/ProcurementChainBuilder.ts || { echo "X ProcurementChainBuilder missing"; exit 1; }
  test -f tests/e2e/assertions/procurementAssertions.ts || { echo "X procurementAssertions missing"; exit 1; }
  test -f tests/e2e/fixtures/procurement.ts || { echo "X procurement fixture missing"; exit 1; }
  grep -q "procurement:" tests/e2e/support/selectors.ts || { echo "X TEST_IDS.procurement missing"; exit 1; }
  grep -q "createBEISupplier" tests/e2e/support/ssmSetup.ts || { echo "X createBEISupplier missing"; exit 1; }
  grep -q "loggedInAsMae" tests/e2e/fixtures/auth.ts || { echo "X loggedInAsMae fixture missing"; exit 1; }
  COUNT=$(grep -rh 'data-testid="procurement-' app/dashboard/procurement | wc -l | tr -d ' ')
  if [ "$COUNT" -lt 30 ]; then
    echo "X procurement data-testid count is $COUNT (need >=30)"
    exit 1
  fi
  echo "OK Phase L file gate passed (procurement testids: $COUNT)"
fi

if [ "$PHASE" = "S" ] || [ "$PHASE" = "ALL" ]; then
  SPEC=tests/e2e/specs/s194-procurement-chain.spec.ts
  test -f "$SPEC" || { echo "X s194 spec missing"; exit 1; }
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31; do
    grep -q "S194-${i}:" "$SPEC" || { echo "X S194-${i} missing"; exit 1; }
  done
  if grep -E 'page\.request|fetch\(|curl ' "$SPEC"; then echo "X Forbidden API call in spec"; exit 1; fi
  if grep -E 'page\.click\("button:has-text|page\.locator\("button' "$SPEC"; then echo "X Inline button selector in spec"; exit 1; fi
  if grep -q 'waitForTimeout' "$SPEC"; then echo "X waitForTimeout used (flakiness mask)"; exit 1; fi
  if grep -E 'page\.route.*fulfill|page\.route\(.*mock' "$SPEC"; then echo "X page.route mocking forbidden (airtight browser rule)"; exit 1; fi
  if grep -E "^import.*(axios|got|node-fetch)" "$SPEC"; then echo "X HTTP client import forbidden -- use browser"; exit 1; fi
  grep -q "cleanupLedger\|procurementLedger" "$SPEC" || { echo "X cleanupLedger not used"; exit 1; }
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31; do
    DIR="../BEI-ERP/output/l3/s194/screenshots/S194-${i}"
    [ -d "$DIR" ] || { echo "X S194-${i} screenshot dir missing -- scenario did not run"; exit 1; }
    COUNT=$(ls "$DIR"/*.png 2>/dev/null | wc -l | tr -d ' ')
    [ "$COUNT" -ge 5 ] || { echo "X S194-${i} has only $COUNT screenshots (need >=5)"; exit 1; }
  done
  echo "OK Phase S spec gate passed"
fi

if [ "$PHASE" = "C" ] || [ "$PHASE" = "ALL" ]; then
  cd /f/Dropbox/Projects/BEI-ERP
  test -f output/l3/s194/form_submissions.json || { echo "X form_submissions.json missing"; exit 1; }
  test -f output/l3/s194/api_mutations.json || { echo "X api_mutations.json missing"; exit 1; }
  test -f output/l3/s194/state_verification.json || { echo "X state_verification.json missing"; exit 1; }
  test -f output/l3/s194/RUN_SUMMARY.md || { echo "X RUN_SUMMARY missing"; exit 1; }
  echo "OK Phase C artifact gate passed"
fi
