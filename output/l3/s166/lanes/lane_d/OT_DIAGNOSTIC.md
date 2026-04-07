# OT Filing UI Diagnostic — S166 Lane D Fix Iter 1

**Timestamp:** 2026-04-07T13:29:33+08:00

## Verdict

**UI exists:** NO
**No File OT / New OT / Request OT button found in any role on any tested route.**

## Per-role on /dashboard/hr/overtime

```json
{
  "crew": {
    "url": "https://my.bebang.ph/dashboard/hr/overtime",
    "restricted": true,
    "file_button": null,
    "button_labels_sample": [
      "TC\ntest.crew1@bebang.ph\ntest.crew1@bebang.ph",
      "Toggle Sidebar",
      "Search\nCtrl K"
    ]
  },
  "supervisor": {
    "url": "https://my.bebang.ph/dashboard/hr/overtime",
    "restricted": false,
    "file_button": null,
    "button_labels_sample": [
      "TS\ntest.supervisor@bebang.ph\ntest.supervisor@bebang.ph",
      "Toggle Sidebar",
      "Search\nCtrl K",
      "Refresh",
      "Approve",
      "Reject",
      "Clarify",
      "Escalate",
      "Approve",
      "Reject",
      "Clarify",
      "Escalate",
      "Approve",
      "Reject",
      "Clarify",
      "Escalate",
      "Approve",
      "Reject",
      "Clarify",
      "Escalate",
      "Approve",
      "Reject",
      "Clarify",
      "Escalate",
      "Approve",
      "Reject",
      "Clarify",
      "Escalate",
      "Approve",
      "Reject"
    ]
  },
  "hr": {
    "url": "https://my.bebang.ph/dashboard/hr/overtime",
    "restricted": false,
    "file_button": null,
    "button_labels_sample": [
      "TH\ntest.hr@bebang.ph\ntest.hr@bebang.ph",
      "Toggle Sidebar",
      "Search\nCtrl K",
      "Refresh",
      "Approve",
      "Reject",
      "Clarify",
      "Escalate",
      "Approve",
      "Reject",
      "Clarify",
      "Escalate",
      "Approve",
      "Reject",
      "Clarify",
      "Escalate",
      "Approve",
      "Reject",
      "Clarify",
      "Escalate",
      "Approve",
      "Reject",
      "Clarify",
      "Escalate",
      "Approve",
      "Reject",
      "Clarify",
      "Escalate",
      "Approve",
      "Reject"
    ]
  }
}
```

## Alternate routes (as crew)

```json
{
  "/dashboard/hr/overtime/new": {
    "status": 404,
    "final_url": "https://my.bebang.ph/dashboard/hr/overtime/new",
    "has_ot_button_text": false
  },
  "/dashboard/hr/overtime/apply": {
    "status": 404,
    "final_url": "https://my.bebang.ph/dashboard/hr/overtime/apply",
    "has_ot_button_text": false
  },
  "/dashboard/hr/attendance": {
    "status": 200,
    "final_url": "https://my.bebang.ph/dashboard/hr/attendance",
    "has_ot_button_text": false
  }
}
```

## Conclusion

Self-service OT filing UI does not exist on production. EMP-OVERTIME-001/002/003 cannot be tested via the employee portal. Logged as CRITICAL product gap defect. Marking as SKIP with upgraded reason.
