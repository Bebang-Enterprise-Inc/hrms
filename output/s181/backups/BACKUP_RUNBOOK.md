# S181 Pre-Migrate Backup Runbook (HB-6 Gate)

**Context:** S181 adds 47 Custom Fields + 2 new child DocTypes to Frappe's
`Company` DocType in a single `bench migrate`. If that migrate fails
partway, the working tree and the DB can end up in a mutually inconsistent
state (fixture updated on disk, half the rows inserted in `tabCustom Field`,
one of the two child DocTypes created but not the other). Without a
pre-migrate snapshot there is no clean rollback path.

**HB-6 gate:** `bench migrate` for this sprint MUST NOT run until all
three backup files in this directory exist with real (non-placeholder)
content. If you are about to deploy and one of them is still `PENDING`,
stop and run the steps below first.

---

## Step 1 — Fixture snapshot (already captured offline)

`custom_field_BEFORE.json` in this directory is a snapshot of
`hrms/fixtures/custom_field.json` as it existed at commit `ad4c030f3`
(the plan renumber commit, which did NOT touch the fixture). It contains:

- 73 total Custom Field rows
- 4 Company-scoped Custom Field rows (the 4 S178 fields)
- Zero S181 fields

This is the rollback target — if `bench migrate` fails, restore with:

```bash
cp output/s181/backups/custom_field_BEFORE.json hrms/fixtures/custom_field.json
```

**Do not overwrite `custom_field_BEFORE.json` at deploy time.** It is
already the pre-S181 snapshot and must be preserved.

---

## Step 2 — DB-level Custom Field snapshot (run at deploy time)

On the production host, just before the S181 `bench migrate`:

```bash
ssh <deploy host>
cd /path/to/hrms-bench

# Dump the Company-scoped Custom Field rows (schema + data)
bench --site hq.bebang.ph mariadb -e "
  SELECT * FROM \`tabCustom Field\`
  WHERE dt='Company'
  ORDER BY idx, name;
" > output/s181/backups/tabCustomField_Company_BEFORE.sql

# Verify row count matches the fixture snapshot (should be 4 rows for S178 only)
wc -l output/s181/backups/tabCustomField_Company_BEFORE.sql
```

The resulting file should show 4 data rows (the S178 additions:
`store_locations`, `partner_names`, `stakeholders_section`, `stakeholders`).
If it shows zero, S178 was not deployed and HB-0 has failed — stop and
investigate.

If it shows more than 4, another sprint has added Company Custom Fields
between S178 and S181 — stop and reconcile.

---

## Step 3 — Timestamp file

On the production host, just before `bench migrate`:

```bash
date -Iseconds > output/s181/backups/BACKUP_TIMESTAMP.txt
```

This overwrites the `PENDING` placeholder with the real backup moment.
The file should look like:

```
2026-04-12T08:30:15+08:00
```

---

## Step 4 — Verify all three backup files exist before migrate

```bash
ls -la output/s181/backups/ | grep -E 'BEFORE|TIMESTAMP'
```

You should see:
- `BACKUP_TIMESTAMP.txt` — real ISO timestamp, not `PENDING`
- `custom_field_BEFORE.json` — the git-captured snapshot
- `tabCustomField_Company_BEFORE.sql` — live DB dump from step 2

Only after all three are present with real content may `bench migrate`
run. This is the HB-6 gate.

---

## Rollback procedure (if `bench migrate` fails)

```bash
# 1. Restore the fixture file
cp output/s181/backups/custom_field_BEFORE.json hrms/fixtures/custom_field.json

# 2. Delete any partial S181 Custom Field rows
bench --site hq.bebang.ph mariadb -e "
  DELETE FROM \`tabCustom Field\`
  WHERE dt='Company'
    AND (
         name LIKE 'Company-bir_legal%'
      OR name LIKE 'Company-branch_tin'
      OR name LIKE 'Company-bir_rdo_code'
      OR name LIKE 'Company-bir_registration_date'
      OR name LIKE 'Company-sec_registration%'
      OR name LIKE 'Company-location%'
      OR name LIKE 'Company-full_address'
      OR name LIKE 'Company-city'
      OR name LIKE 'Company-province'
      OR name LIKE 'Company-region'
      OR name LIKE 'Company-mall_or_building'
      OR name LIKE 'Company-gps_%'
      OR name LIKE 'Company-google_maps_place_id'
      OR name LIKE 'Company-operations%'
      OR name LIKE 'Company-entity_category'
      OR name LIKE 'Company-store_ownership_type'
      OR name LIKE 'Company-operational_status'
      OR name LIKE 'Company-opening_date'
      OR name LIKE 'Company-operating_hours'
      OR name LIKE 'Company-pos_system'
      OR name LIKE 'Company-mosaic_location_id'
      OR name LIKE 'Company-adms_devices%'
      OR name LIKE 'Company-contacts%'
      OR name LIKE 'Company-store_manager%'
      OR name LIKE 'Company-area_supervisor'
      OR name LIKE 'Company-regional_manager'
      OR name LIKE 'Company-compliance_docs%'
      OR name LIKE 'Company-compliance_documents'
      OR name LIKE 'Company-drive_folder_url'
      OR name LIKE 'Company-bd_pipeline%'
      OR name LIKE 'Company-pipeline_status'
      OR name LIKE 'Company-target_opening_date'
      OR name LIKE 'Company-lease_%'
      OR name LIKE 'Company-revenue_share_pct'
      OR name LIKE 'Company-provisioning_state%'
      OR name LIKE 'Company-first_provision_done'
    );
"

# 3. Drop the two new child DocTypes if they were partially created
bench --site hq.bebang.ph mariadb -e "
  DROP TABLE IF EXISTS \`tabBEI Company Document\`;
  DROP TABLE IF EXISTS \`tabBEI Company ADMS Device\`;
  DELETE FROM tabDocType
    WHERE name IN ('BEI Company Document', 'BEI Company ADMS Device');
  DELETE FROM \`tabDocField\`
    WHERE parent IN ('BEI Company Document', 'BEI Company ADMS Device');
"

# 4. Clear cache and rebuild
bench --site hq.bebang.ph clear-cache
bench --site hq.bebang.ph build
```

After rollback, investigate the migrate failure (likely a fixture JSON
error, a circular `insert_after` chain, or a DocType JSON schema mismatch)
and retry.
