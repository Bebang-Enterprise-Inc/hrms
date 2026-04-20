# S210 Phase 7 — one-click step required

**Why this isn't fully automated:** the Google Forms REST API does not allow
creating forms with file upload questions. Apps Script's `FormApp` does
support native file upload. Our service account + domain-wide delegation
does not have `https://www.googleapis.com/auth/script.deployments` enabled,
so we cannot `scripts.run` a deployed API Executable from Python. A
publisher-approved deployment would need a Google Workspace admin action.

**Workaround** — 30 seconds of your time:

1. Open the Apps Script editor:
   https://script.google.com/d/1lsvOlv1rGEvXl_1zms4SURlsLUZk7CxRhg2NyBDrDHh4fDjuioFZhi2S/edit

2. In the left file panel, click **s210_phase7_form_rebuild**.

3. In the function dropdown at the top of the editor (next to the Debug
   button), select **s210_rebuildSupplierForm**.

4. Click **Run**.

5. If an OAuth consent prompt appears, approve. Scopes requested:
   - Spreadsheet read/write (audit log)
   - Drive (form creation)
   - External HTTP requests

6. Wait ~5 seconds. Execution log shows the returned JSON.

7. The function ALSO persists the result to Sheet C `09_Audit_Log` under
   trigger=`phase7_form_rebuild`. The Python resume script picks it up
   automatically.

8. Now run:

   ```
   python output/s210/phase7_resume.py
   ```

   This reads the new form ID from audit log, rewrites
   `SUPPLIER_URLS.csv` + `SI_UPLOAD_FORM_ID.json`, and commits the
   canonical form metadata.

---

**What the function does when you click Run:**

- Creates a new Google Form titled "BEI Supplier SI Upload"
- Adds 7 items: Supplier Name, PO Number, SI Number, SI Date, Amount (PHP),
  **SI PDF (native file upload)**, Notes
- Shares the form as editor with all 7 BEI staff emails
- Returns `{formId, responderUri, editUrl, entries}`
- Writes the same JSON to Sheet C audit log

The old form (the one that asked suppliers to paste Drive links — bad UX)
was already deleted by the previous phase7 run.
