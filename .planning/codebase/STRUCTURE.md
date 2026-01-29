# BEI-ERP Directory Structure

**Last Updated:** 2026-01-29
**Purpose:** Complete mapping of codebase directories, naming conventions, and file locations

---

## Root Directory Layout

```
f:\Dropbox\Projects\BEI-ERP/
├── .claude/                          # Claude Code workspace config
├── .github/                          # GitHub Actions CI/CD
├── .planning/                        # Planning & documentation
│   └── codebase/                     # This mapping
├── .vscode/                          # VS Code settings
├── .git/                             # Git repository
├── adms_receiver/                    # Bio-metric attendance receiver
├── assets/                           # Static assets (images, fonts)
├── aws/                              # AWS infrastructure code
├── data/                             # Data analysis tools & imports
├── docker/                           # Production Docker setup
├── docker-dev/                       # Development Docker compose
├── docs/                             # Project documentation
├── frappe_docker_build/              # Custom Frappe Docker image
├── frontend/                         # Vue 3 + Ionic PWA (legacy)
├── gchat_integration/                # Google Chat bot
├── hrms/                             # Frappe HRMS app (main backend)
├── logs/                             # Runtime logs
├── scripts/                          # Utility scripts
├── scratchpad/                       # Temporary work
├── credentials/                      # API credentials (gitignored)
└── roster/                           # Legacy roster system
```

---

## Core Application Structure

### `hrms/` - Main Frappe App (Backend)

**Purpose:** Customized Frappe HRMS fork with BEI-specific features

```
hrms/
├── __init__.py                       # Package initialization
├── hooks.py                          # ★ Frappe lifecycle hooks (CRITICAL)
├── setup.py                          # Installation & custom field setup
├── subscription_utils.py             # Subscription management
├── install.py                        # Post-install script
├── uninstall.py                      # Pre-uninstall script
├── modules.txt                       # Module declarations
├── patches.txt                       # Migration patch registry
├── mcp.py                            # MCP tool definitions (empty)
│
├── api/                              # ★ REST API ENDPOINTS (all whitelisted)
│   ├── __init__.py                   # Core user/employee endpoints
│   │   ├── get_current_user_info()
│   │   ├── get_current_employee_info()
│   │   ├── get_all_employees()
│   │   ├── get_hr_settings()
│   │   └── [50+ other methods]
│   │
│   ├── google_login.py               # OAuth 2.0 flow
│   │   ├── google_oauth_login()
│   │   ├── google_oauth_callback()
│   │   └── disconnect_oauth()
│   │
│   ├── oauth_tokens.py               # Token management
│   │   ├── store_oauth_token()
│   │   ├── refresh_oauth_token()
│   │   └── get_oauth_token()
│   │
│   ├── google_chat.py                # Google Chat bot
│   │   ├── send_chat_message()
│   │   ├── create_space()
│   │   └── get_chat_spaces()
│   │
│   ├── google_drive.py               # Google Drive search
│   │   ├── search_drive_files()
│   │   └── download_file()
│   │
│   ├── employee_clearance.py         # Exit interview workflows
│   │   ├── create_exit_interview()
│   │   ├── submit_clearance()
│   │   └── track_handover()
│   │
│   ├── onboarding.py                 # New hire workflows
│   │   ├── create_onboarding_request()
│   │   ├── assign_documents()
│   │   └── complete_onboarding()
│   │
│   ├── supervisor.py                 # Store payroll & operations (47KB - largest)
│   │   ├── get_store_metrics()
│   │   ├── calculate_store_payroll()
│   │   └── approve_supervisor_actions()
│   │
│   ├── store.py                      # Store-level operations
│   │   ├── get_store_data()
│   │   ├── submit_store_report()
│   │   └── track_store_performance()
│   │
│   ├── inventory.py                  # Warehouse & stock management
│   │   ├── get_opening_inventory()
│   │   ├── create_stock_movement()
│   │   └── calculate_variance()
│   │
│   ├── coverage.py                   # Staff coverage requests
│   │   ├── request_coverage()
│   │   ├── approve_coverage()
│   │   └── notify_staff()
│   │
│   ├── dashboard.py                  # Analytics & KPIs
│   │   ├── get_attendance_summary()
│   │   ├── get_payroll_metrics()
│   │   └── get_store_analytics()
│   │
│   ├── dispatch.py                   # Task routing
│   │   ├── dispatch_task()
│   │   ├── route_to_user()
│   │   └── track_dispatch()
│   │
│   ├── enrichment.py                 # Data transformation
│   │   ├── enrich_attendance_data()
│   │   ├── resolve_references()
│   │   └── validate_data_quality()
│   │
│   ├── roster.py                     # Attendance scheduling
│   │   ├── get_roster()
│   │   ├── create_shift_plan()
│   │   └── validate_scheduling()
│   │
│   ├── communication.py              # Internal messaging
│   │   ├── send_notification()
│   │   ├── create_message()
│   │   └── mark_read()
│   │
│   ├── hello.py                      # Health check
│   │   └── hello() → {"build_version": "..."}
│   │
│   └── [other modules]               # [empty stubs, future expansion]
│
├── hr/                               # ★ HR DOCTYPES (domain models)
│   ├── __init__.py
│   ├── utils.py                      # Shared HR utilities
│   │
│   └── doctype/                      # DocType implementations
│       ├── attendance/               # Daily check-in/out
│       │   ├── attendance.py         # Controller
│       │   ├── attendance.json       # Schema
│       │   └── [templates, fixtures]
│       │
│       ├── leave_application/        # PTO requests
│       ├── leave_allocation/         # Annual leave balance
│       ├── shift_assignment/         # Work schedule
│       ├── salary_slip/              # Payroll document
│       ├── employee_advance/         # Loans & advances
│       ├── expense_claim/            # Reimbursements
│       │
│       ├── employee/                 # Employee master (extended)
│       │   ├── employee.py
│       │   └── employee.json
│       │
│       ├── bei_kudos/                # ★ Custom: Recognition program
│       ├── bei_onboarding_request/   # ★ Custom: Hiring workflow
│       ├── bei_coaching_log/         # ★ Custom: Training tracker
│       ├── bei_exit_interview_*/     # ★ Custom: Separation data
│       ├── bei_store_audit_item/     # ★ Custom: Store compliance
│       ├── bei_cycle_count/          # ★ Custom: Inventory audit
│       ├── bei_distribution_trip/    # ★ Custom: Logistics
│       ├── bei_fqi_report/           # ★ Custom: Food quality
│       ├── bei_inventory_variance/   # ★ Custom: Stock variance
│       ├── bei_midshift_checklist/   # ★ Custom: Operational checklists
│       ├── bei_pos_upload/           # ★ Custom: Sales integration
│       ├── bei_staff_coverage_request/ # ★ Custom: Shift swap
│       ├── bei_dole_compliance_*/    # ★ Custom: Labor law tracking
│       └── [40+ more BEI doctypes]
│
├── payroll/                          # Payroll-specific DocTypes
│   ├── __init__.py
│   └── doctype/
│       ├── salary_slip/              # Payroll generation
│       ├── salary_structure/         # Pay bands
│       ├── additional_salary/        # Bonuses, deductions
│       └── [payroll utilities]
│
├── overrides/                        # ★ ERPNext integration layer
│   ├── company.py                    # Company settings customization
│   ├── employee_master.py            # Employee validation overrides
│   ├── employee_payment_entry.py     # Payroll entry customization
│   ├── employee_timesheet.py         # Timesheet workflows
│   ├── employee_project.py           # Project time tracking
│   ├── dashboard_overrides.py        # UI customizations
│   └── [other overrides]
│
├── mixins/                           # ★ Shared behavior
│   ├── base_mixin.py                 # Common validation
│   └── [domain-specific mixins]
│
├── controllers/                      # Event handlers
│   ├── employee_boarding_controller.py   # Onboarding events
│   ├── employee_reminders.py             # Reminder emails
│   └── tests/
│
├── config/                           # Frappe workspaces & modules
│   ├── default.py                    # Default module config
│   ├── hr.py                         # HR module layout
│   ├── payroll.py                    # Payroll module layout
│   └── [module definitions]
│
├── patches/                          # Database migrations
│   ├── v15/                          # Version 15 patches
│   ├── v16/                          # Version 16 patches
│   └── [migration scripts]
│
├── fixtures/                         # Default data
│   ├── employee_group.json           # Employee classification
│   ├── designation.json              # Job titles
│   ├── department.json               # Organizational units
│   └── [default records]
│
├── regional/                         # Country-specific logic
│   └── [Philippines-specific rules]
│
├── utils/                            # Utility functions
│   ├── google_oauth.py               # OAuth token helpers
│   ├── page_renderers.py             # [DELETED - migration in progress]
│   └── [utility modules]
│
├── public/                           # Static assets & build output
│   ├── frontend/                     # Built Vue PWA output
│   │   ├── index.html
│   │   ├── js/                       # Vite build chunks
│   │   └── css/                      # Tailwind output
│   │
│   ├── js/                           # Frappe Desk customizations
│   │   ├── erpnext/
│   │   │   ├── employee.js           # Employee form custom JS
│   │   │   ├── company.js
│   │   │   ├── department.js
│   │   │   └── [doctype JS]
│   │   └── [other JS]
│   │
│   ├── css/                          # Stylesheets
│   │   └── [custom CSS]
│   │
│   └── www/                          # Website pages
│       └── hrms.html                 # PWA entry point
│
├── templates/                        # Email & document templates
│   ├── email/
│   │   ├── offer_letter.html         # Hiring template
│   │   ├── appointment_letter.html   # Onboarding
│   │   └── [email templates]
│   │
│   └── print/                        # Print formats
│       ├── salary_slip.html
│       ├── attendance_certificate.html
│       └── [print templates]
│
├── tests/                            # Unit & integration tests
│   ├── test_employee.py              # Employee model tests
│   ├── test_attendance.py            # Attendance workflow tests
│   ├── test_api.py                   # API endpoint tests
│   └── [test files]
│
├── locale/                           # Translations
│   └── [i18n files]
│
└── hrms/                             # Legacy namespace (unused currently)
    └── [legacy code]
```

**Key File Naming Conventions:**

| Pattern | Meaning | Example |
|---------|---------|---------|
| `<doctype>.py` | DocType controller | `attendance.py` |
| `<doctype>.json` | DocType schema | `attendance.json` |
| `<feature>.py` in `api/` | API endpoint | `employee_clearance.py` |
| `bei_*` prefix | Custom BEI doctype | `bei_kudos/` |
| `test_*.py` | Unit tests | `test_api.py` |
| `override_*.py` | ERPNext override | (named without prefix) |

---

### `frontend/` - Vue 3 + Ionic PWA (Legacy Admin Interface)

**Purpose:** Internal PWA for HR admins; uses Vite build system

```
frontend/
├── package.json                      # Dependencies (Ionic, Vue, Tailwind)
├── vite.config.js                    # ★ Build configuration
├── vite.config.js.timestamp-*        # Vite cache files (gitignored)
├── tailwind.config.js                # Tailwind CSS config
├── postcss.config.js                 # PostCSS config
├── ionic.config.json                 # Ionic framework config
├── jsconfig.json                     # JS compilation options
├── eslintrc.js                       # Linting rules
├── prettier.json                     # Code formatting
├── yarn.lock                         # Dependency lock file
├── index.html                        # ★ Entry point
├── node_modules/                     # Dependencies (gitignored)
│
├── public/                           # Static files copied to dist/
│   ├── favicon.ico
│   └── [assets]
│
└── src/                              # ★ SOURCE CODE
    ├── main.js                       # ★ App entry point
    ├── App.vue                       # ★ Root component
    │
    ├── router/                       # ★ Vue Router setup
    │   ├── index.js                  # Main router (CRITICAL)
    │   ├── attendance.js             # Attendance routes
    │   ├── leaves.js                 # Leave routes
    │   ├── claims.js                 # Expense claim routes
    │   ├── advances.js               # Employee advance routes
    │   └── salary_slips.js           # Salary slip routes
    │
    ├── views/                        # Page components (routed)
    │   ├── Home.vue                  # Dashboard home
    │   ├── Login.vue                 # Authentication
    │   ├── Profile.vue               # User profile
    │   ├── Notifications.vue         # Notification center
    │   ├── AppSettings.vue           # Settings
    │   ├── InvalidEmployee.vue       # Error page
    │   ├── TabbedView.vue            # Tab navigation layout
    │   │
    │   ├── attendance/
    │   │   ├── Dashboard.vue         # Attendance overview
    │   │   ├── AttendanceList.vue    # List view
    │   │   └── AttendanceDetail.vue  # Detail view
    │   │
    │   ├── leave/
    │   │   ├── Dashboard.vue         # Leave overview
    │   │   ├── LeaveList.vue
    │   │   └── LeaveDetail.vue
    │   │
    │   ├── expense_claim/
    │   │   ├── Dashboard.vue
    │   │   └── [claim views]
    │   │
    │   ├── salary_slip/
    │   │   ├── Dashboard.vue
    │   │   └── [payroll views]
    │   │
    │   └── enrichment/
    │       └── Dashboard.vue         # Analytics dashboard
    │
    ├── components/                   # Reusable UI components
    │   ├── BaseLayout.vue            # Main layout wrapper
    │   ├── BottomTabs.vue            # Tab navigation
    │   ├── TabbedView.vue            # Tabbed interface
    │   ├── FormView.vue              # Form rendering
    │   ├── ListView.vue              # List rendering
    │   ├── FormField.vue             # Form field wrapper
    │   ├── FormattedField.vue        # Field display
    │   │
    │   ├── Attendance*.vue           # Attendance-related components
    │   │   ├── AttendanceCalendar.vue
    │   │   ├── AttendanceRequestItem.vue
    │   │   ├── AttendanceCheckInPanel.vue
    │   │   └── [attendance components]
    │   │
    │   ├── Leave*.vue                # Leave-related components
    │   │   ├── LeaveBalance.vue
    │   │   ├── LeaveRequestItem.vue
    │   │   └── [leave components]
    │   │
    │   ├── Expense*.vue              # Expense-related components
    │   │   ├── ExpenseClaimItem.vue
    │   │   ├── ExpenseClaimSummary.vue
    │   │   ├── ExpensesTable.vue
    │   │   └── [expense components]
    │   │
    │   ├── Salary*.vue               # Payroll-related components
    │   │   ├── SalarySlipItem.vue
    │   │   ├── SalaryDetailTable.vue
    │   │   └── [salary components]
    │   │
    │   ├── Employee*.vue
    │   │   ├── EmployeeAdvanceBalance.vue
    │   │   ├── EmployeeAvatar.vue
    │   │   └── [employee components]
    │   │
    │   ├── icons/                    # SVG icon components
    │   │   ├── AttendanceIcon.vue
    │   │   ├── LeaveIcon.vue
    │   │   ├── ExpenseIcon.vue
    │   │   ├── SalaryIcon.vue
    │   │   ├── HomeIcon.vue
    │   │   └── [icon SVGs]
    │   │
    │   ├── QuickLinks.vue            # Quick action buttons
    │   ├── Link.vue                  # Link component
    │   ├── EmptyState.vue            # Empty state UI
    │   ├── FileUploaderView.vue      # File upload
    │   ├── FilePreviewModal.vue      # File preview
    │   ├── ProfileInfoModal.vue      # User profile modal
    │   ├── CustomIonModal.vue        # Ionic modal wrapper
    │   ├── ListFiltersActionSheet.vue # Filter menu
    │   ├── RequestActionSheet.vue    # Request action menu
    │   ├── ListItem.vue              # List item
    │   ├── RequestList.vue           # Request list
    │   ├── RequestPanel.vue          # Request details
    │   ├── Holidays.vue              # Holiday calendar
    │   ├── SemicircleChart.vue       # Chart component
    │   └── InstallPrompt.vue         # PWA install prompt
    │
    ├── stores/                       # Global state (if any)
    │   └── [state management]
    │
    ├── api/                          # API client
    │   └── frappe.js                 # Frappe API wrapper
    │
    ├── utils/                        # Utility functions
    │   ├── formatters.js             # Number/date formatting
    │   ├── validators.js             # Form validation
    │   └── [utility functions]
    │
    ├── styles/                       # Global styles
    │   ├── index.css                 # Tailwind imports
    │   ├── variables.css             # CSS variables
    │   └── [shared styles]
    │
    └── service-worker.js             # PWA offline support
```

**Key Vue Components Architecture:**

```
App.vue (Root)
├── Login.vue (if not authenticated)
└── TabbedView.vue (layout)
    ├── BottomTabs.vue (navigation)
    ├── Home.vue (main dashboard)
    ├── [Profile, Settings, Notifications]
    └── [Routed Views]
        ├── AttendanceDashboard.vue
        │   └── AttendanceCalendar + AttendanceRequestItem
        ├── LeaveDashboard.vue
        │   └── LeaveBalance + LeaveRequestItem
        ├── ExpenseClaimsDashboard.vue
        │   └── ExpenseClaimItem + ExpenseClaimSummary
        └── SalarySlipsDashboard.vue
            └── SalarySlipItem + SalaryDetailTable
```

**Build Output:**

```
frontend/dist/
├── index.html                        # Built by Vite
├── js/
│   ├── index-*.js                    # App entry chunk
│   ├── views-*.js                    # View lazy-loaded chunk
│   └── [component chunks]
├── css/
│   ├── index-*.css                   # Main CSS
│   └── [component CSS]
└── manifest.json                     # PWA manifest
```

After build, files are copied to:
```
hrms/public/frontend/                 # ← Served by Frappe Desk
hrms/www/hrms.html                    # ← PWA entry point
```

---

### `data/` - Data Analysis & Import Tools

**Purpose:** ETL scripts, data validation, master data preparation

```
data/
├── _tools/                           # ★ Analysis scripts (48+ tools)
│   ├── attendance_validation.py      # Bio ID → Payroll reconciliation
│   ├── supplier_master_validator.py  # PO approval matrix
│   ├── inventory_forensics.py        # Stock variance investigation
│   ├── payroll_reconciler.py         # Multi-source payroll validation
│   ├── employee_import_validator.py  # Employee master QA
│   └── [40+ more analysis tools]
│
├── _templates/                       # Template files
│   ├── employee_import.csv           # Template for employee master
│   ├── supplier_master.csv           # Template for vendors
│   ├── item_master.csv               # Template for SKUs
│   └── [import templates]
│
├── 01_HR_&_Payroll/
│   ├── Employee_Master_2026-01-14.csv # 676 employees imported
│   ├── Payroll_Extracts/
│   │   ├── January_2026_Payroll.csv
│   │   └── [monthly extracts]
│   └── [HR-related data]
│
├── 02_Procurement_&_Supply/
│   ├── SUPPLIER_MASTER_FINAL_2026-01-07.csv
│   ├── SKU_Master.csv                # Item catalog
│   ├── WAREHOUSE_TREE_2025-12-31.csv # Location hierarchy
│   └── [procurement data]
│
├── 04_Project_Management/
│   └── Import_Log/
│       ├── CONTEXT.md                # ★ Project decisions & policies (CRITICAL)
│       ├── PROGRESS_INDEX.md         # ★ Topic routing (CRITICAL)
│       ├── PROGRESS_LEGACY.md        # Historical context (65K tokens)
│       │
│       ├── progress/                 # Topic-specific progress
│       │   ├── _CURRENT.md           # Last 2 days activity
│       │   ├── biometrics-adms.md    # ADMS receiver, Bio ID
│       │   ├── hr-employee-import.md # Employee, payroll
│       │   ├── clearance-deployment.md # Docker, deployment
│       │   ├── erp-migration.md      # Go-live activities
│       │   ├── procurement-suppliers.md # PO, vendors
│       │   ├── finance-apex.md       # GL, COA, accounting
│       │   ├── inventory-opening.md  # Stock, warehouse
│       │   └── query.py              # Progress file search script
│       │
│       └── [other tracking]
│
├── ADMS/                             # Time attendance data
│   ├── Bio_ID_Mapping.csv            # Device → Employee mapping
│   ├── Raw_Attendances.csv           # Unprocessed clock data
│   └── [ADMS exports]
│
├── Finance/                          # Accounting data
│   ├── COA_Master_2026-01-14.csv     # Chart of accounts
│   ├── Opening_Balances_2026-01-01.csv
│   ├── Bank_Reconciliation/
│   │   ├── BPI_January_2026.csv
│   │   └── [bank statements]
│   └── [GL extracts]
│
├── Inventory/
│   ├── OPENING_INVENTORY_SUMMARY_2026-01-14.csv
│   ├── Warehouse_Stock_Levels/
│   │   ├── Main_Warehouse_2026-01-14.csv
│   │   ├── Store_1_2026-01-14.csv
│   │   └── [store inventory]
│   └── [stock data]
│
├── HR_Org_Chart/                     # Organizational structure
│   ├── Department_Tree_2026-01-14.csv
│   └── Reporting_Lines.csv
│
├── HR_Masterlists/                   # Reference data
│   ├── Designations.csv
│   ├── Locations.csv
│   └── [master lists]
│
├── Big_Data_Refinery/                # Data cleansing pipeline
│   ├── deduplication.py              # Remove duplicates
│   ├── standardization.py            # Normalize fields
│   ├── validation.py                 # Quality checks
│   └── [data cleaning]
│
└── Finance_APEX/                     # APEX legacy accounting
    ├── GL_Export_*.csv               # General ledger
    ├── Trial_Balance_*.csv
    └── [APEX data]
```

**File Naming Convention (data/):**

```
<DOMAIN>_<DESCRIPTION>_<DATE>.csv
Examples:
- SUPPLIER_MASTER_FINAL_2026-01-07.csv
- OPENING_INVENTORY_SUMMARY_2026-01-14.csv
- Employee_Master_2026-01-14.csv
```

---

### `docs/` - Project Documentation

**Purpose:** Architecture, deployment, reference guides

```
docs/
├── 00_START_HERE.md                  # ★ Project overview (read first)
├── MY_BEBANG_PH_COMPLETE_REFERENCE.md # ★ Employee app reference
├── BEI_CREDENTIALS.md                # Service account info
├── BEI_ERP_HRMS_Build_Report.md      # Build artifacts
├── GOOGLE_OAUTH_RUNBOOK.md           # OAuth setup guide
├── FRAPPE_DOCKER_SETUP_AUDIT.md      # Docker configuration
├── FRAPPE_TASKS_FEATURE_MAP.md       # Feature inventory
│
├── plans/                            # Implementation roadmaps
│   ├── ERP_MIGRATION_MASTER_PLAN_2026-01-14.md # ★ Go-live (Feb 1)
│   ├── FRAPPE_UI_APPS_COMPREHENSIVE_PLAN_2026-01-14.md
│   ├── OPS_FORMS_EXTRACTION_REPORT_2026-01-14.md
│   └── DEPARTMENT_INPUTS_REQUIRED_CHECKLIST_*.docx
│
├── architecture/                     # System design
│   ├── system_overview.md
│   ├── data_flow.md
│   └── [architecture docs]
│
├── masterlist/                       # Data import guides
│   ├── employee_master.md
│   ├── supplier_master.md
│   ├── item_master.md
│   └── [import procedures]
│
├── masterlist-import/                # Detailed import steps
│   └── [import workflows]
│
├── data-dictionary/                  # Field definitions
│   ├── employee.md
│   ├── attendance.md
│   └── [doctype references]
│
├── reports/                          # Report definitions
│   ├── payroll_reports.md
│   ├── store_reports.md
│   └── [report specs]
│
├── erp/                              # ERP-specific setup
│   ├── company_setup.md
│   ├── warehouse_configuration.md
│   ├── item_setup.md
│   ├── supplier_setup.md
│   └── [ERP docs]
│
├── infrastructure/                   # Deployment & ops
│   ├── docker_setup.md
│   ├── aws_configuration.md
│   ├── monitoring.md
│   └── [ops docs]
│
├── analytics/                        # Dashboard & KPIs
│   ├── dashboard_setup.md
│   ├── kpi_definitions.md
│   └── [analytics docs]
│
├── audits/                           # Audit logs & compliance
│   ├── data_lineage.md
│   ├── access_logs.md
│   └── [audit docs]
│
├── followups/                        # Action items
│   ├── open_issues.md
│   ├── blockers.md
│   └── [follow-up items]
│
├── blip/                             # Google Chat bot docs
│   └── [bot configuration]
│
└── templates/                        # Document templates
    ├── offer_letter.docx
    ├── appointment_letter.docx
    └── [templates]
```

---

### `docker-dev/` - Development Docker Setup

**Purpose:** Local development environment with all services

```
docker-dev/
├── docker-compose.yml                # ★ Container orchestration
│   ├── frappe                        # Frappe app container
│   ├── db                            # MariaDB database
│   ├── redis                         # Cache layer
│   └── nginx                         # Reverse proxy
│
├── dev.sh                            # Bash startup script
├── dev.bat                           # Windows startup script
├── test_all_endpoints.py             # API integration tests
├── test_workflows.py                 # Workflow automation tests
├── test_import.py                    # Data import tests
│
└── .frappe-bench/                    # Bench CLI config
    └── [bench state]
```

**Usage:**

```bash
# Start development environment
./dev.sh              # Linux/Mac
dev.bat              # Windows

# Access services
http://localhost:8000  # Frappe app
http://localhost:5173  # Vue PWA (after: cd frontend && yarn dev)
http://localhost:3000  # React app (separate repo)
```

---

### `docker/` - Production Docker Setup

**Purpose:** Minimal production Docker image

```
docker/
├── docker-compose.yml                # Production orchestration
├── init.sh                           # Production initialization
└── [production config]
```

---

### `frappe_docker_build/` - Custom Frappe Image

**Purpose:** Build custom Docker image with HRMS app baked in

```
frappe_docker_build/
├── Dockerfile                        # ★ Custom image definition
│   ├── FROM frappe/bench:latest
│   ├── COPY hrms/ /app/hrms/
│   ├── RUN bench install-app hrms
│   └── [image customizations]
│
└── [build config]
```

**Build Command:**

```bash
docker build -t bei-erp:latest -f frappe_docker_build/Dockerfile .
```

---

### `.github/workflows/` - CI/CD Pipeline

**Purpose:** GitHub Actions automation

```
.github/workflows/
├── deploy.yml                        # Deploy to production
│   ├── Lint (Black for Python)
│   ├── Test (pytest)
│   ├── Build Docker image
│   └── Deploy via AWS SSM / Docker Swarm
│
├── test.yml                          # Run tests on PR
└── [other workflows]
```

---

### `.claude/` - Claude Code Workspace

**Purpose:** AI agent tools & configurations

```
.claude/
├── CLAUDE.md                         # Project instructions (critical)
├── rules/                            # Custom rules
│   ├── core-governance.md            # Evidence-based policy
│   ├── progress-access.md            # Progress file routing
│   ├── troubleshooting.md            # Common issues & fixes
│   └── [other rules]
│
├── skills/                           # Custom AI skills (50+)
│   ├── frappe-doctype/               # DocType development
│   ├── frappe-ui/                    # Frappe UI components
│   ├── google-oauth/                 # OAuth integration
│   ├── erp-blueprint-tools/          # Data analysis
│   ├── forensic-auditing/            # Data validation
│   └── [50+ domain-specific skills]
│
├── agents/                           # Custom agent definitions
│   ├── data-validator/               # Data QA
│   ├── etl-transformer/              # Data ETL
│   ├── extraction-auditor/           # Data audit
│   └── [agent specs]
│
├── credentials/                      # Service account credentials
│   ├── doppler.md                    # Doppler secrets management
│   └── services/                     # Credential references
│
├── scripts/                          # Utility scripts
│   ├── aws_mcp_wrapper.py            # AWS MCP fix
│   └── [helper scripts]
│
├── e2e_screenshots/                  # QA test evidence
│   ├── browser_tests_2026-01-25/
│   ├── qa_testing_2026-01-25/
│   └── [screenshot galleries]
│
├── rlm_state/                        # Recursive LLM state
│   ├── results/                      # Analysis results
│   ├── chunks/                       # Context chunks
│   └── [RLM artifacts]
│
└── hooks/                            # Claude hook scripts
    ├── classify-prompt.py            # Model routing
    └── memory-manager.py             # Persistent memory
```

---

## Naming Conventions

### Python Modules

```
# Function names (snake_case)
get_current_employee_info()
create_exit_interview()

# Class names (PascalCase)
class EmployeeClearance(Document):

# API endpoints (underscores)
/api/method/hrms.api.get_current_user_info

# File names (snake_case)
employee_clearance.py
google_oauth.py
```

### Vue Components

```
# Component files (PascalCase)
AttendanceCalendar.vue
ExpenseClaimItem.vue

# Route names (PascalCase)
route: "/home" → name: "Home"

# Props (camelCase)
:employee-id="123"

# Event names (kebab-case)
@update:item="handleUpdate"
```

### DocTypes

```
# Standard types (no prefix)
Employee, Attendance, Leave Application

# Custom BEI types (bei_ prefix)
BEI Kudos → bei_kudos
BEI Onboarding Request → bei_onboarding_request

# Database table (tab prefix)
tabBEI_Kudos (from DocType "BEI Kudos")
```

### Data Files

```
# Master data (UPPERCASE)
SUPPLIER_MASTER_FINAL_2026-01-07.csv
OPENING_INVENTORY_SUMMARY_2026-01-14.csv

# Extracts (PascalCase)
Payroll_Extract_January_2026.csv
GL_Export_2026_01_01.csv
```

---

## Key File Locations (Quick Reference)

| What | Where |
|------|-------|
| **Backend API** | `hrms/api/__init__.py` (core) + individual modules |
| **Router** | `frontend/src/router/index.js` |
| **Views** | `frontend/src/views/` |
| **Components** | `frontend/src/components/` |
| **Employee DocType** | `hrms/hr/doctype/employee/` |
| **Attendance DocType** | `hrms/hr/doctype/attendance/` |
| **Docker Setup** | `docker-dev/docker-compose.yml` |
| **Hooks** | `hrms/hooks.py` |
| **Setup** | `hrms/setup.py` |
| **Custom Fields** | `hrms/setup.py` (get_custom_fields function) |
| **Patches/Migrations** | `hrms/patches/` |
| **Project Docs** | `docs/` |
| **Progress Tracking** | `data/04_Project_Management/Import_Log/` |
| **ERP Master Data** | `data/02_Procurement_&_Supply/` |
| **Data Tools** | `data/_tools/` |

---

## Entry Points Summary

| Type | Location | Command |
|------|----------|---------|
| **Backend** | `hrms/hooks.py` | `bench start` |
| **Frontend (Vue)** | `frontend/src/main.js` | `yarn dev` |
| **Docker Dev** | `docker-dev/docker-compose.yml` | `docker-compose up` |
| **Production Build** | `.github/workflows/deploy.yml` | Push to production branch |
| **API** | `hrms/api/` | GET/POST `/api/method/hrms.api.*` |

---

**End of Structure Document**
