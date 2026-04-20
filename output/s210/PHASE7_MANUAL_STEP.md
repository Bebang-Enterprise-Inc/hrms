# S210 Phase 7 — two UI steps required

**Why fully automated creation isn't possible:**

Google Forms `File upload` questions can ONLY be added through the Forms UI.
No API supports it:
- Forms REST API: returns "Creation of file_upload question not supported"
- Apps Script FormApp: has NO `addFileUploadItem()` method (only a read-only
  `FileUploadItem` class for inspecting existing items)

Previous "native file upload via FormApp" claim was wrong (my mistake).

The only path: FormApp creates the form with text/date/paragraph items,
then a human adds the one File upload field via the form editor UI.

---

## Step 1: Run the helper (30 seconds)

1. Open: https://script.google.com/d/1lsvOlv1rGEvXl_1zms4SURlsLUZk7CxRhg2NyBDrDHh4fDjuioFZhi2S/edit
2. Left panel: click **s210_phase7_form_rebuild**
3. Function dropdown -> **s210_rebuildSupplierForm** -> **Run**
4. Approve OAuth (FormApp + Drive + Sheets scopes) on first run
5. Execution log prints the form JSON. Function also writes the result to
   Sheet C `09_Audit_Log` under trigger=`phase7_form_rebuild`.

The helper creates a form with 7 items:
- Supplier Name (text, pre-fillable, required)
- PO Number (text, required)
- SI Number (text, required)
- SI Date (date, required)
- Amount (PHP) (text, required)
- `[REPLACE_ME ...]` (text placeholder -- delete in Step 2)
- Notes (paragraph, optional)

## Step 2: Swap placeholder for real File upload (10 seconds in UI)

1. In the execution log, copy the `editUrl` value.
2. Open it -- form editor loads.
3. Find the item titled `[REPLACE_ME -- delete this item and add a File upload item titled "SI PDF"]`.
4. Click the trash icon on that item (top-right of the item card).
5. Click the **+** button in the right-hand item toolbar.
6. Select **File upload** from the item type dropdown.
7. Title it exactly: **SI PDF**.
8. Help text: **Tap to upload a clear PDF or photo of your SI.**
9. Turn on **Required** (toggle, bottom of the item).
10. Optional: expand **Settings on this question** and:
    - Specific file types: check `PDF` + `Image`
    - Maximum number of files: 1
    - Maximum file size: 10 MB
11. Close the editor.

## Step 3: Resume Python automation

```
python F:\Dropbox\Projects\BEI-ERP\output\s210\phase7_resume.py
```

This reads the audit log for the form metadata, regenerates
`SUPPLIER_URLS.csv` (98 rows, pre-filled with supplier names) and
`SI_UPLOAD_FORM_ID.json`, and updates `SHEET_IDS.json.si_upload_form_id`.

**Note:** `handleSiUpload` in the .gs reads form responses by field TITLE
(`e.namedValues["SI PDF"]`), not by entry ID. So adding the File upload
item via UI doesn't require any further .gs changes. As long as the field
is titled exactly `SI PDF`, submissions flow correctly into Sheet C
`03_Supplier_SI_Uploads`.

---

## Why the original plan (file upload via FormApp) was wrong

When I said "FormApp supports native file upload" earlier, that was wrong.
The API reference I was recalling was for `FileUploadItem.getMaxFiles()`
etc. -- READ methods on existing items, not CREATE. The actual Form class
method list does not include any `addFileUploadItem`. Apologies for the
incorrect earlier guidance.
