#!/bin/bash
# S172 verification v2 — use git -C + absolute paths, no cd
set +e
HRMS=F:/Dropbox/Projects/BEI-ERP
TASKS=F:/Dropbox/Projects/bei-tasks
PROD=origin/production
MAIN=origin/main
PASS=0
FAIL=0
FAILS=""

check() {
  local desc="$1"
  local cmd="$2"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "[PASS] $desc"
    PASS=$((PASS+1))
  else
    echo "[FAIL] $desc"
    FAIL=$((FAIL+1))
    FAILS="$FAILS\n  - $desc"
  fi
}

echo "=== Phase 1: Defect #6 + #21 (compensation chain) ==="
check "P1a has_ssa in get_employee_compensation_detail" \
  "git -C $HRMS show $PROD:hrms/api/payroll_compensation.py | grep -q 'has_ssa'"
check "P1b set_backend_observability_context in get_employee_compensation_detail" \
  "git -C $HRMS show $PROD:hrms/api/payroll_compensation.py | grep -c 'set_backend_observability_context' | awk '{exit (\$1<5)}'"
check "P1c compensation-detail-panel.tsx has disabled={isLoading}" \
  "git -C $TASKS show $MAIN:components/hr/compensation-detail-panel.tsx | grep -q 'disabled={isLoading}'"
check "P1d compensation-setup/[employee]/page.tsx has disabled={isLoading}" \
  "git -C $TASKS show '$MAIN:app/dashboard/hr/payroll/compensation-setup/[employee]/page.tsx' | grep -q 'disabled={isLoading}'"

echo ""
echo "=== Phase 2: Defect #16 (activation silent fail) ==="
check "P2a helper has fallback or throw (no silent skip)" \
  "git -C $HRMS show $PROD:hrms/api/payroll_compensation.py | awk '/def _activate_compensation_change/,/^def [a-z]/' | grep -qE 'fall back|frappe.throw|has_ssa'"
check "P2b caller throws on activation failure" \
  "git -C $HRMS show $PROD:hrms/api/payroll_compensation.py | grep -A10 'rollback_to_savepoint.*compensation_activation' | grep -q 'frappe.throw'"
check "P2c backfill script exists" \
  "git -C $HRMS show $PROD:scripts/s172_backfill_stranded_bccs.py 2>/dev/null | grep -q '_activate_compensation_change'"

echo ""
echo "=== Phase 3: Defect #19 (overtime RoleGuard) ==="
check "P3a overtime/apply/page.tsx no longer imports RoleGuard" \
  "git -C $TASKS show '$MAIN:app/dashboard/hr/overtime/apply/page.tsx' | grep -v 'RoleGuardProps\|role-guard' | grep -q 'ApplyOvertimeForm' && ! git -C $TASKS show '$MAIN:app/dashboard/hr/overtime/apply/page.tsx' | grep -qE '^import.*\{.*RoleGuard.*\}.*role-guard'"
check "P3b diagnosis doc" \
  "git -C $HRMS show $PROD:output/s172/diagnostics/DEFECT_19_DIAGNOSIS.md | grep -q 'Defect #19'"

echo ""
echo "=== Phase 4: Defect #18 (Warehouse→Branch) ==="
check "P4a DocType store.options == Branch" \
  "git -C $HRMS show $PROD:hrms/hr/doctype/bei_incident_report/bei_incident_report.json | python -c 'import sys,json; d=json.load(sys.stdin); f=[x for x in d[\"fields\"] if x[\"fieldname\"]==\"store\"][0]; sys.exit(0 if f.get(\"options\")==\"Branch\" else 1)'"
check "P4b DECISION.md" \
  "git -C $HRMS show $PROD:output/s172/diagnostics/DEFECT_18_DECISION.md | grep -q 'Defect #18'"
check "P4c create_incident_report has Sentry context" \
  "git -C $HRMS show $PROD:hrms/api/disciplinary.py | awk '/def create_incident_report/,/^def [a-z]/' | grep -q 'set_backend_observability_context'"
check "P4d disciplinary.py defaults store to employee.branch" \
  "git -C $HRMS show $PROD:hrms/api/disciplinary.py | grep -qE 'store_value.*=.*data.get.*store.*or'"

echo ""
echo "=== Phase 5: Defect #8 (employee_id stale) ==="
check "P5a employee_id.py queries employee column" \
  "git -C $HRMS show $PROD:hrms/utils/employee_id.py | grep -q 'SELECT employee FROM'"
check "P5b employee_create.py returns name key" \
  "git -C $HRMS show $PROD:hrms/api/employee_create.py | grep -q 'name.*employee_doc.name'"

echo ""
echo "=== Phase 6: Defect #13 (emergency_phone) ==="
check "P6a useUpdateEmployeeField routes to enrichment" \
  "git -C $TASKS show $MAIN:lib/queries/hr-employee-detail.ts | grep -q 'update_self_service_field'"
check "P6b SELF_SERVICE_FIELDS contains emergency_phone_number" \
  "git -C $TASKS show $MAIN:lib/queries/hr-employee-detail.ts | grep -q 'emergency_phone_number'"

echo ""
echo "=== Phase 7: final defects + #24 ==="
check "P7a Frappe patch file" \
  "git -C $HRMS show $PROD:hrms/patches/v16_0/s172_ensure_hr_employee_permissions.py | grep -q 'DocPerm'"
check "P7b patch registered" \
  "git -C $HRMS show $PROD:hrms/patches.txt | grep -q 's172_ensure_hr_employee_permissions'"
check "P7c Defect #9 diagnosis" \
  "git -C $HRMS show $PROD:output/s172/diagnostics/DEFECT_9_DIAGNOSIS.md | grep -q 'Defect #9'"
check "P7d Defect #24 backend incident_type alias" \
  "git -C $HRMS show $PROD:hrms/api/disciplinary.py | grep -q 'incident_type'"
check "P7e Defect #24 DocType severity field" \
  "git -C $HRMS show $PROD:hrms/hr/doctype/bei_incident_report/bei_incident_report.json | python -c 'import sys,json; d=json.load(sys.stdin); sys.exit(0 if any(x[\"fieldname\"]==\"severity\" for x in d[\"fields\"]) else 1)'"
check "P7f Defect #5 status doc" \
  "git -C $HRMS show $PROD:output/s172/diagnostics/DEFECT_5_STATUS.md | grep -q 'Defect #5'"
check "P7g Defect #11 mark_employee_left helper" \
  "git -C $HRMS show $PROD:hrms/api/employee_create.py | grep -q 'def mark_employee_left'"
check "P7h Defect #15 submit_sensitive_change_request explicit commit" \
  "git -C $HRMS show $PROD:hrms/api/payroll_compensation.py | awk '/def submit_sensitive_change_request/,/^@frappe.whitelist|^def approve/' | grep -c 'frappe.db.commit' | awk '{exit (\$1<1)}'"
check "P7i Defect #20 overtime error message update" \
  "git -C $HRMS show $PROD:hrms/api/overtime_request.py | grep -qi 'attendance correction'"
check "P7j Defect #14 ReportsToLookupField component" \
  "git -C $TASKS show $MAIN:app/dashboard/hr/employee-master/employee-detail-dialog.tsx | grep -q 'ReportsToLookupField'"
check "P7k CONTEXT.md S172 ops patterns" \
  "git -C $HRMS show $PROD:data/04_Project_Management/Import_Log/CONTEXT.md 2>/dev/null | grep -q 'S172 Defects #11'"

echo ""
echo "=== Plan patch (Defect #24 added to plan) ==="
check "Plan Defect #24 row in Phase 7 table" \
  "git -C $HRMS show $PROD:docs/plans/2026-04-08-sprint-172-s166-followup-defect-fixes.md 2>/dev/null | grep -qE 'Defect #24|\\*\\*#24\\*\\*'"

echo ""
echo "=== SUMMARY ==="
echo "PASSED: $PASS / $((PASS+FAIL))"
echo "FAILED: $FAIL"
if [ $FAIL -gt 0 ]; then
  echo ""
  echo "Failures:"
  echo -e "$FAILS"
fi
exit $FAIL
