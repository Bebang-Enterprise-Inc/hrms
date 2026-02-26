# Entity Relationship Diagrams
**Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17 | **Commit:** 7b998877f

Six domain ERDs covering all major BEI custom DocTypes and their Frappe standard relationships.

---

## Domain 1: HR & Payroll

```mermaid
erDiagram
    Employee {
        string name PK
        string employee_name
        string branch
        string designation
        string new_attendance_device_id
        string employment_type
        string reports_to
    }
    Leave_Application {
        string name PK
        string employee FK
        string leave_type FK
        string leave_approver FK
        int docstatus
    }
    Attendance {
        string name PK
        string employee FK
        date attendance_date
        string status
    }
    BEI_Shift_Record {
        string name PK
        string employee FK
        string verification_status
        float total_hours
        int overtime_flag
    }
    BEI_Official_Business {
        string name PK
        string employee FK
        string supervisor FK
        string matched_ob_location FK
    }
    BEI_Onboarding_Session {
        string name PK
        string created_by_user FK
        string status
        string token
    }
    BEI_Onboarding_Request {
        string name PK
        string employee FK
        string session_token FK
        string status
    }
    Salary_Slip {
        string name PK
        string employee FK
        string payroll_entry FK
        int docstatus
    }
    BEI_Overtime_Request {
        string name PK
        string employee FK
        string attendance FK
        string reviewed_by FK
    }

    Employee ||--o{ Leave_Application : "applies for"
    Employee ||--o{ Attendance : "has"
    Employee ||--o{ BEI_Shift_Record : "punches"
    Employee ||--o{ BEI_Official_Business : "logs"
    Employee ||--o{ BEI_Onboarding_Request : "created via"
    Employee ||--o{ Salary_Slip : "receives"
    Employee ||--o{ BEI_Overtime_Request : "flagged for"
    BEI_Onboarding_Session ||--o{ BEI_Onboarding_Request : "contains"
    Attendance ||--o{ BEI_Overtime_Request : "generates"
```

**Critical Note:** BEI Shift Record and Frappe Attendance are NOT bridged (GAP-001 — Critical). GPS punches never reach payroll.

---

## Domain 2: Procurement & Finance

```mermaid
erDiagram
    BEI_Supplier {
        string name PK
        string frappe_supplier FK
        string payment_terms FK
    }
    BEI_Purchase_Requisition {
        string name PK
        string requested_by FK
        string department FK
        string delivery_to FK
        string status
    }
    BEI_Purchase_Order {
        string name PK
        string pr_reference FK
        string supplier FK
        string ship_to FK
        string frappe_po FK
        string status
    }
    BEI_Goods_Receipt {
        string name PK
        string purchase_order FK
        string supplier FK
        string warehouse FK
        string inspector FK
        string status
    }
    BEI_Invoice {
        string name PK
        string supplier FK
        string purchase_order FK
        string goods_receipt FK
        string frappe_purchase_invoice FK
    }
    BEI_Payment_Request {
        string name PK
        string supplier FK
        string invoice FK
        string purchase_order FK
        string frappe_payment_entry FK
        string status
    }
    BEI_Match_Exception {
        string name PK
        string purchase_order FK
        string requested_by FK
        string approver FK
    }

    BEI_Supplier ||--o{ BEI_Purchase_Order : "supplies"
    BEI_Purchase_Requisition ||--o| BEI_Purchase_Order : "converts to"
    BEI_Purchase_Order ||--o{ BEI_Goods_Receipt : "receives via"
    BEI_Goods_Receipt ||--o| BEI_Invoice : "verified by"
    BEI_Invoice ||--o| BEI_Payment_Request : "paid via"
    BEI_Purchase_Order ||--o{ BEI_Match_Exception : "exception for"
```

**Critical Notes:** BEI Purchase Order is NOT submittable (GAP-016). BEI GR does NOT create Frappe Purchase Receipt.

---

## Domain 3: Store Operations

```mermaid
erDiagram
    Warehouse {
        string name PK
        string custom_area_supervisor
        string custom_gchat_space
    }
    BEI_Store_Order {
        string name PK
        string store FK
        string submitted_by FK
        string approved_by FK
        string trip FK
        string status
    }
    BEI_Store_Opening_Report {
        string name PK
        string store FK
        string submitted_by FK
    }
    BEI_Store_Closing_Report {
        string name PK
        string store FK
        string submitted_by FK
        string pos_upload FK
    }
    BEI_POS_Upload {
        string name PK
        string store FK
        string uploaded_by FK
        float gross_sales
        float net_sales
    }
    BEI_Store_Receiving {
        string name PK
        string store FK
        string trip FK
        string receiver_1 FK
    }
    BEI_FQI_Report {
        string name PK
        string store FK
        string receiving FK
        string item_code FK
        string reported_by FK
    }

    Warehouse ||--o{ BEI_Store_Order : "orders from"
    Warehouse ||--o{ BEI_Store_Opening_Report : "files"
    Warehouse ||--o{ BEI_Store_Closing_Report : "files"
    BEI_Store_Closing_Report ||--o| BEI_POS_Upload : "links"
    Warehouse ||--o{ BEI_Store_Receiving : "receives at"
    BEI_Store_Receiving ||--o{ BEI_FQI_Report : "generates"
```

**Critical Notes:** BEI POS Upload `gross_sales`/`net_sales` never populated (GAP-022).

---

## Domain 4: Warehouse & Logistics

```mermaid
erDiagram
    BEI_Route {
        string name PK
        string source_warehouse FK
        string default_vehicle FK
        string default_driver FK
    }
    BEI_Route_Stop {
        string name PK
        string parent FK
        string store FK
        int estimated_minutes
    }
    BEI_Vehicle {
        string name PK
        string vehicle_plate
        string vehicle_type
    }
    BEI_Distribution_Trip {
        string name PK
        string route_name FK
        string driver FK
        string vehicle FK
        string status
    }
    BEI_Trip_Stop {
        string name PK
        string parent FK
        string store FK
        string store_order FK
        string status
    }
    BEI_Pick_List {
        string name PK
        string trip FK
        string warehouse FK
        string picked_by FK
        string status
    }
    BEI_Store_Order {
        string name PK
        string trip FK
        string store FK
    }
    BEI_Billing_Schedule {
        string name PK
        string store FK
        string trip_reference FK
        string billing_type
    }

    BEI_Route ||--o{ BEI_Route_Stop : "has stops"
    BEI_Route ||--o{ BEI_Distribution_Trip : "generates"
    BEI_Vehicle ||--o{ BEI_Distribution_Trip : "used in"
    BEI_Distribution_Trip ||--o{ BEI_Trip_Stop : "visits"
    BEI_Distribution_Trip ||--o| BEI_Pick_List : "picked via"
    BEI_Distribution_Trip ||--o{ BEI_Billing_Schedule : "billed via"
    BEI_Trip_Stop }o--o| BEI_Store_Order : "fulfills"
```

**Critical Notes:** `preview_trip_stops` missing (GAP-003). `get_vehicles` response mismatch (GAP-029). `estimated_minutes` not propagated from route to trip stop (GAP-080).

---

## Domain 5: Commissary

```mermaid
erDiagram
    Item {
        string name PK
        string item_group
        int has_batch_no
    }
    BOM {
        string name PK
        string item FK
        string company FK
        int is_active
        int docstatus
    }
    Work_Order {
        string name PK
        string production_item FK
        string bom_no FK
        string fg_warehouse FK
        int docstatus
    }
    Stock_Entry {
        string name PK
        string from_warehouse FK
        string to_warehouse FK
        string bom_no FK
        string work_order FK
        int docstatus
    }
    Material_Request {
        string name PK
        string company FK
        string set_warehouse FK
        int docstatus
    }
    BEI_FQI_Report {
        string name PK
        string store FK
        string item_code FK
    }
    BEI_QC_Form {
        string name PK
        string checked_by FK
        string verified_by FK
    }
    BEI_Pick_List {
        string name PK
        string trip FK
        string warehouse FK
    }

    Item ||--o{ BOM : "has BOM"
    BOM ||--o{ Work_Order : "drives"
    Work_Order ||--o{ Stock_Entry : "creates"
    Material_Request ||--o{ Stock_Entry : "fulfilled by"
    Item ||--o{ BEI_FQI_Report : "reported in"
    BEI_Pick_List }o--|| BEI_Distribution_Trip : "for trip"
```

**Critical Notes:** QC Form tab not wired in /quality frontend (GAP-044). G-046 async fires on `fulfill_store_order` Stock Entry submit.

---

## Domain 6: Projects & Maintenance

```mermaid
erDiagram
    BEI_Maintenance_Request {
        string name PK
        string store FK
        string assigned_to FK
        string completion FK
        string reported_by FK
        string status
        int charge_to_store
        float charge_amount
        string billing_status
    }
    BEI_Maintenance_Completion {
        string name PK
        string maintenance_request FK
        string store FK
        string verified_by FK
    }
    BEI_Project {
        string name PK
        string store FK
        string project_manager FK
        string contractor FK
    }
    BEI_Project_Bid {
        string name PK
        string project FK
        string contractor FK
        string awarded_by FK
    }
    BEI_Project_Milestone {
        string name PK
        string project FK
        string payment_request FK
        string verified_by FK
    }
    BEI_Mall_Permit {
        string name PK
        string store FK
        date expiry_date
        string status
    }
    BEI_Payment_Request {
        string name PK
        string supplier FK
        string invoice FK
    }
    BEI_Billing_Schedule {
        string name PK
        string billing_type
    }

    BEI_Maintenance_Request ||--o| BEI_Maintenance_Completion : "completed by"
    BEI_Maintenance_Request }o--|| BEI_Billing_Schedule : "rolled into"
    BEI_Project ||--o{ BEI_Project_Bid : "receives bids"
    BEI_Project ||--o{ BEI_Project_Milestone : "has milestones"
    BEI_Project_Milestone ||--o| BEI_Payment_Request : "billed via"
    BEI_Project_Bid }o--|| BEI_Supplier : "from contractor"
    BEI_Mall_Permit }o--|| Warehouse : "for store"
```

**Critical Notes:** Permits: 5 endpoints LIVE; 4 have no frontend (GAP-031). Preventive Maintenance: no implementation (GAP-030). Coaching Log → Appraisal link missing (GAP-075).

---

## DocType Count by Domain

| Domain | Custom DocTypes | Frappe Standard | Total |
|--------|----------------|-----------------|-------|
| HR & Payroll | 6 | 4 | 10 |
| Procurement & Finance | 7 | 0 | 7 |
| Store Operations | 9 | 1 | 10 |
| Warehouse & Logistics | 8 | 0 | 8 |
| Commissary | 4 | 5 | 9 |
| Projects & Maintenance | 6 | 0 | 6 |
| **Total** | **40** | **10** | **50** |

**New since Feb 17:** BEI Pick List, BEI Announcement Read Receipt, BEI Mall Permit (formalized in ERD)
