RT-S172-07: soft-deleted HR-EMP-00058:Success, HR-EMP-00059:Success
RT-S172-08: restored original values on 9000026
RT-S172-08: restored original values on 9000026
RT-S172-08: restored original values on 9000026
RT-S172-08: restored original values on 9001858
RT-S172-08: restored original values on 9001858
RT-S172-02: soft-deleted HR-EMP-00060, cancelled SSA, deleted BCC
RT-S172-02: soft-deleted HR-EMP-00061, cancelled SSA, deleted BCC

## Pass 4 in-session cleanup (2026-04-10T02:08:56.070Z)

### RT-S172-05
- IR created for testing — will be left as-is (no delete endpoint for IRs; it's a legitimate test artifact)

### RT-S172-02
- Test employee soft-deleted via SSM: status=Left, relieving_date=today
- SSA cancelled via SSM: docstatus=2

## Pass 4 v2 in-session (2026-04-10T02:13:10.342Z)
RT-S172-05: IR test artifact left (no delete API)
RT-S172-02: Employee soft-deleted + SSA cancelled via SSM

## P4 final in-session (2026-04-10T02:18:43.106Z)
- RT-05: IR artifact (no delete API)
- RT-02: Employee soft-deleted + SSA cancelled via SSM

## P4 v3 in-session (2026-04-10T02:22:40.508Z)
- RT-05: IR test artifact
- RT-02: Employee mark_employee_left called

## RT-S172-02 FINAL (2026-04-10T02:58:49.923Z)
- Added HR Manager role to test.hr, Accounts Manager to test.finance via sam@bebang.ph admin
- Employee HR-EMP-00065 soft-deleted via mark_employee_left

## RT-S172-02 FINAL (2026-04-10T03:00:07.108Z)
- Added HR Manager role to test.hr, Accounts Manager to test.finance via sam@bebang.ph admin
- Employee HR-EMP-00066 soft-deleted via mark_employee_left

## RT-S172-02 FINAL (2026-04-10T03:04:39.378Z)
- Added HR Manager role to test.hr, Accounts Manager to test.finance via sam@bebang.ph admin
- Employee HR-EMP-00068 soft-deleted via mark_employee_left
