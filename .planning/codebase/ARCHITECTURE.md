# BEI-ERP Codebase Architecture

**Last Updated:** 2026-01-29
**Focus:** Frappe HRMS customization for BEI (Bebang Enterprise Inc.)
**Main Branch:** production
**Deployment:** Docker Swarm (zero-downtime deploys)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  BEI ERP System                         │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────┐  ┌──────────────────────────────┐ │
│  │  Frontend Layer  │  │   Backend API Layer          │ │
│  ├──────────────────┤  ├──────────────────────────────┤ │
│  │ Vue 3 + Ionic    │  │ Frappe Framework (Python)    │ │
│  │ + Tailwind       │  │ + ERPNext + HRMS             │ │
│  │ (legacy PWA)     │  │ Microservices APIs:          │ │
│  │                  │  │  - Google OAuth              │ │
│  │ Vite 5 build     │  │  - Google Chat               │ │
│  │ PWA + Workbox    │  │  - Google Drive              │ │
│  └──────────────────┘  │  - Inventory management      │ │
│                         │  - HR/Payroll workflows     │ │
│  ┌──────────────────┐  │  - Employee clearance       │ │
│  │  React/Next.js   │  │  - Onboarding               │ │
│  │  my.bebang.ph    │  │  - Store operations         │ │
│  │  (separate repo) │  │  - Supervisor dashboards    │ │
│  │  Shadcn + Vercel │  └──────────────────────────────┘ │
│  └──────────────────┘                                    │
│                                                           │
│  ┌──────────────────────────────────────────────────────┤
│  │              Database & Integrations                 │ │
│  ├──────────────────────────────────────────────────────┤
│  │ MariaDB (local Docker)  |  Google Workspace (OAuth)  │ │
│  │ ADMS Receiver           |  Frappe Desk UI            │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## System Layers & Data Flow

### Layer 1: Presentation (Frontend)

#### 1.1 Legacy PWA (Vue 3 + Ionic 7)
- **Location:** `frontend/`
- **Build Tool:** Vite 5 + TypeScript
- **Purpose:** Internal admin interface (legacy)
- **Entry Point:** `frontend/src/App.vue`
- **Key Routes:**
  - `/home` - Dashboard
  - `/dashboard/attendance` - Attendance management
  - `/dashboard/leaves` - Leave requests
  - `/dashboard/expense-claims` - Expense tracking
  - `/dashboard/salary-slips` - Payroll slips
  - `/login` - Authentication
  - `/profile` - User profile

**Technology Stack:**
```
vue@3.5.12 + @ionic/vue@7.4.3
+ @ionic/vue-router@7.4.3
+ vite@5.4.10
+ tailwindcss@3.4.3
+ frappe-ui@0.1.105
+ pwa (vite-plugin-pwa + workbox)
```

**Data Flow:**
```
Vue Components → Frappe API (whitelisted methods)
                 ↓
         Backend Handlers
                 ↓
         Database (MariaDB)
```

#### 1.2 React/Next.js App (my.bebang.ph)
- **Location:** Separate repository (`bei-tasks`)
- **Framework:** React 18 + Next.js 16 + Shadcn UI
- **Hosting:** Vercel (auto-deploy)
- **API Integration:** Frappe REST API
- **Purpose:** Main employee-facing app

---

### Layer 2: API & Business Logic

#### 2.1 REST API Endpoints
**Location:** `hrms/api/`

**Core Modules:**

| Module | File | Purpose |
|--------|------|---------|
| **Core** | `__init__.py` | User info, employee data, HR settings, notifications |
| **Authentication** | `google_login.py` | Google OAuth 2.0 flow, token management |
| **OAuth Tokens** | `oauth_tokens.py` | OAuth token storage, refresh logic |
| **Communication** | `communication.py` | Internal messaging, notifications |
| **Chat Integration** | `google_chat.py` | Google Chat bot, space management |
| **Drive Integration** | `google_drive.py` | Google Drive file search, download |
| **HR Clearance** | `employee_clearance.py` | Exit interview, separation workflows |
| **Onboarding** | `onboarding.py` | New hire setup, document requests |
| **Payroll** | `supervisor.py` | Store payroll, supervisor workflows |
| **Store Operations** | `store.py` | Store-level operations, reports |
| **Inventory** | `inventory.py` | Warehouse stock, opening balances |
| **Coverage** | `coverage.py` | Staff coverage, shift requests |
| **Dashboard** | `dashboard.py` | Analytics, KPIs, reporting |
| **Coverage** | `dispatch.py` | Task dispatch, routing |
| **Coverage** | `enrichment.py` | Data enrichment, transformation |
| **Roster** | `roster.py` | Attendance roster, scheduling |
| **Health Check** | `hello.py` | API liveness probe, build info |

**Entry Point Decorator:**
```python
@frappe.whitelist()  # Exposes method as API endpoint
def get_current_user_info() -> dict:
    # CORS: accessible to authenticated users
```

#### 2.2 Frappe Framework Integration
**Location:** `hrms/`

- **Hooks:** `hrms/hooks.py` - App lifecycle, events, permissions
- **Setup:** `hrms/setup.py` - Installation, custom fields, fixtures
- **Config:** `hrms/config/` - Workspace definitions, modules
- **Patches:** `hrms/patches/` - Database migrations
- **Tests:** `hrms/tests/` - Unit & integration tests

---

### Layer 3: Data Model (DocTypes)

#### 3.1 Document Structure
**Location:** `hrms/hr/doctype/`

**Standard HR DocTypes:**
- `Employee` - Employee master
- `Attendance` - Daily check-in/out
- `Leave Application` - PTO requests
- `Leave Allocation` - Annual leave balance
- `Shift Assignment` - Work schedule
- `Salary Slip` - Payroll document
- `Expense Claim` - Reimbursement requests
- `Employee Advance` - Loan/advance requests

**Custom BEI DocTypes (~40+ custom types):**
- `BEI Kudos` - Recognition program
- `BEI Onboarding Request` - Hire workflow
- `BEI Coaching Log` - Training tracker
- `BEI Exit Interview Response` - Separation data
- `BEI Store Audit Item` - Store compliance
- `BEI Cycle Count` - Inventory audit
- `BEI Distribution Trip` - Logistics
- `BEI FQI Report` - Food quality inspection
- `BEI Inventory Variance` - Stock discrepancies
- `BEI Midshift Checklist` - Operational checklists
- `BEI POS Upload` - Sales integration
- `BEI Staff Coverage Request` - Shift swap
- `BEI Dole Compliance Checklist` - Labor law tracking

#### 3.2 Database Schema
**Database:** MariaDB (Docker container, local only)
**ORM:** Frappe ORM (DocType abstraction)

**Key Tables Generated from DocTypes:**
- `tab<DocType>` - Main table (e.g., `tabEmployee`)
- `tabCustom Field` - Dynamic fields
- `tabSeries` - Auto-increment sequences
- `tabUser` - Authentication
- `tabRole` - RBAC

---

### Layer 4: Controllers & Business Rules

#### 4.1 DocType Controllers
**Location:** `hrms/hr/doctype/<type>/<type>.py`

**Pattern:**
```python
from frappe.model.document import Document

class Employee(Document):
    def before_save(self):
        # Validation, calculations

    def on_submit(self):
        # Post-submit workflows

    def on_cancel(self):
        # Reversal logic
```

#### 4.2 Overrides (ERPNext Integration)
**Location:** `hrms/overrides/`

- `employee_master.py` - Custom Employee logic
- `employee_payment_entry.py` - Payroll entry customization
- `company.py` - Company-level settings
- `employee_timesheet.py` - Timesheet workflows
- `dashboard_overrides.py` - UI customizations

#### 4.3 Mixins (Shared Behavior)
**Location:** `hrms/mixins/`

- Reusable validation logic
- Common field definitions
- Workflow templates

---

### Layer 5: External Integrations

#### 5.1 Google Workspace
**Files:**
- `hrms/api/google_login.py` - OAuth flow
- `hrms/api/google_chat.py` - Chat bot
- `hrms/api/google_drive.py` - File search
- `hrms/utils/google_oauth.py` - Token management

**Flow:**
```
User logs in → Google OAuth consent → Token stored → API calls authorized
```

**Scopes:**
- `https://www.googleapis.com/auth/userinfo.email`
- `https://www.googleapis.com/auth/userinfo.profile`
- `https://www.googleapis.com/auth/drive.readonly`
- `https://www.googleapis.com/auth/chat.bot`

#### 5.2 ADMS Receiver (Time Attendance)
**Location:** `adms_receiver/`

**Purpose:** Process bio-metric clock-in/out data
- Receives attendance data from ZKTeco devices
- Reconciles with payroll system
- Validates Bio ID mappings

---

## Architectural Patterns

### Pattern 1: Service-Oriented Architecture
Each API module is a standalone service:
```
hrms/api/
├── google_login.py      (Auth Service)
├── supervisor.py        (Supervisor Service)
├── store.py             (Store Service)
├── inventory.py         (Inventory Service)
└── dashboard.py         (Analytics Service)
```

Each service:
1. Has single responsibility
2. Exposes @frappe.whitelist() methods
3. Calls database via Frappe ORM
4. Returns JSON-serializable data

### Pattern 2: Layered Whitelist Pattern
```
Frontend (Vue) → API (@frappe.whitelist())
                 ↓
         Business Logic
                 ↓
         Frappe ORM
                 ↓
         MariaDB
```

### Pattern 3: Hook-Based Lifecycle
Frappe provides hooks for:
- `before_save()` - Validation
- `on_submit()` - Approval workflows
- `before_update_after_submit()` - Changes to submitted docs
- `on_trash()` - Deletion logic

### Pattern 4: Permission System (RBAC)
- Role-based access control via Frappe
- Field-level permissions
- Document-level permissions
- Workflow state permissions

---

## Data Flow Examples

### Example 1: Leave Request Submission
```
1. Frontend (Vue)
   ├─ Form.vue collects fields
   └─ POST /api/leave-request (frappe.call)

2. Backend API Handler
   ├─ hrms/api/__init__.py (whitelisted method)
   └─ Creates LeaveApplication document

3. DocType Controller
   ├─ hrms/hr/doctype/leave_application/
   ├─ Validates dates, checks balance
   └─ Triggers workflow

4. Workflow Engine
   ├─ Sends notification to approver
   └─ Writes to audit log

5. Database
   └─ tabLeaveApplication (MariaDB)
```

### Example 2: Store Attendance Sync
```
1. ADMS Receiver (adms_receiver/)
   ├─ Polls ZKTeco device
   ├─ Downloads clock-in/out data
   └─ Matches Bio ID → Employee

2. Transform & Validate
   ├─ hrms/api/enrichment.py
   ├─ Resolves store location
   └─ Checks shift assignment

3. Create Attendance Document
   ├─ Auto-creates tabAttendance
   ├─ Validates against leaves
   └─ Updates working hours

4. Dashboard Updates
   ├─ hrms/api/dashboard.py
   ├─ Aggregates daily metrics
   └─ Returns to Frontend via API

5. Frontend Display
   ├─ frontend/src/views/AttendanceDashboard.vue
   ├─ Polls /api/attendance-data
   └─ Updates charts in real-time
```

---

## Entry Points & Startup Sequence

### Backend Entry Points
1. **Frappe Development Server**
   ```bash
   bench start  # Starts WSGI app on port 8000
   ```
   - Loads `hrms/hooks.py`
   - Registers all @frappe.whitelist() methods
   - Initializes database connection

2. **Docker Production**
   ```bash
   docker-compose -f docker-dev/docker-compose.yml up
   ```
   - Builds custom Frappe image
   - Mounts code volumes
   - Starts gunicorn worker pool

### Frontend Entry Points

1. **Vue PWA (Legacy)**
   ```bash
   cd frontend && yarn dev  # Vite dev server on port 5173
   ```
   - Loads `frontend/src/main.js`
   - Creates Vue app instance
   - Mounts router

2. **Build Output**
   ```bash
   cd frontend && yarn build
   ```
   - Builds to `frontend/dist/`
   - Copies to `hrms/public/frontend/`
   - PWA manifest + service worker

### Deployment Entry Point
- **GitHub Actions** - CI/CD pipeline
- **Docker Swarm** - Orchestration
- **AWS** - Infrastructure (EC2, RDS alternative)

---

## Abstraction Layers & Boundaries

### Boundary 1: Frontend ↔ Backend
- **Protocol:** HTTP/REST via Frappe API
- **Authentication:** Session cookie + JWT (oauth_tokens)
- **Serialization:** JSON
- **Rate Limiting:** None (internal only)

### Boundary 2: Backend ↔ Database
- **ORM:** Frappe Document model
- **Query Builder:** `frappe.query_builder`
- **Transactions:** Database-level ACID
- **Migrations:** `frappe migrate` command

### Boundary 3: Backend ↔ External APIs
- **Google OAuth:** Token-based (Google service account for domain delegation)
- **Error Handling:** Try-catch + logging to Frappe Error Log
- **Retry Logic:** Exponential backoff (custom per integration)

---

## Build & Deployment Pipeline

### Build Stages
```
Source Code (GitHub)
    ↓
[GitHub Actions Workflow]
    ├─ Lint (ESLint, Black)
    ├─ Test (pytest, Vitest)
    ├─ Build Docker Image
    └─ Push to registry
    ↓
[Docker Swarm]
    ├─ Pull image
    ├─ Start containers (zero-downtime)
    └─ Health check (GET /api/hello)
    ↓
[Production]
    └─ Load balancer routes traffic
```

### Critical Files for Deployment
- `.github/workflows/` - CI/CD definition
- `docker-dev/docker-compose.yml` - Container orchestration
- `frappe_docker_build/Dockerfile` - Custom Frappe image
- `frontend/vite.config.js` - Frontend build config

---

## Technology Stack Summary

| Layer | Technology | Version | Location |
|-------|-----------|---------|----------|
| **Web Framework** | Frappe | 15+ | N/A |
| **ERP** | ERPNext | 15+ | N/A |
| **HRMS** | Custom Fork | 0.0.0 | `hrms/` |
| **Language (Backend)** | Python | 3.10+ | `hrms/` |
| **Language (Frontend)** | TypeScript/Vue | 3.5.12 | `frontend/` |
| **Database** | MariaDB | 10.4+ | Docker |
| **UI Framework** | Ionic Vue | 7.4.3 | `frontend/` |
| **CSS** | Tailwind | 3.4.3 | `frontend/` |
| **Build (Frontend)** | Vite | 5.4.10 | `frontend/` |
| **Build (Docker)** | Docker Compose | 3.8+ | `docker-dev/` |
| **Deployment** | Docker Swarm | Native | AWS |
| **Authentication** | Google OAuth 2.0 | 2.0 | `hrms/api/` |
| **Chat API** | Google Chat | v1 | `hrms/api/` |

---

## Code Organization Principles

### Single Responsibility
- Each API file handles one domain (e.g., `inventory.py` only handles inventory)
- Each DocType controller manages one document type
- Each Vue component renders one feature

### Dependency Injection
- Frappe ORM injected via `frappe.db`, `frappe.get_doc()`
- No global state (uses Frappe singleton pattern)

### Error Handling
- Backend: Raise `frappe.ValidationError` for validation failures
- Frontend: Catch and display via toast notifications
- Logging: All errors logged to `Frappe Error Log` DocType

### Testing Strategy
- Unit tests in `hrms/tests/`
- Integration tests via browser automation (E2E tests)
- Deployment validation: `/api/hello` health check

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Monolithic Frappe** | All-in-one ERP provides rapid development, built-in RBAC, audit trails |
| **Vue PWA (Legacy)** | Internal admin tool; React/Next.js is for external employees (my.bebang.ph) |
| **Docker Swarm** | Simpler than Kubernetes; good for small-team DevOps |
| **Separate Repos** | Frontend (React) and Backend (Frappe) can deploy independently |
| **Google OAuth** | Aligns with Bebang Google Workspace tenant (@bebang.ph domain) |
| **Custom DocTypes** | 40+ BEI-specific types to support QSR operations (stores, inventory, audits) |
| **MariaDB (Local)** | Docker-based database; not AWS RDS to keep infrastructure simple |

---

## Performance & Scalability Notes

### Optimizations
- **Frontend:** PWA with Workbox offline capability
- **Backend:** Frappe query caching, database indexing on key fields
- **API Responses:** Paginated lists (limit=999999 for now, migrate to pagination)

### Bottlenecks
- **ADMS Polling:** ZKTeco device polling may lag during high attendance
- **Dashboard Queries:** Large aggregations need query optimization
- **Storage:** Google Drive file search limited by API quota (500 requests/min)

### Scalability Path
1. Migrate to paginated API responses
2. Implement Redis caching layer
3. Separate read replicas for analytics queries
4. Vertical pod autoscaling in Swarm

---

## Maintenance & Debugging

### Logs
- **Backend:** `~/.bench/logs/` (docker-dev setup)
- **Frontend:** Browser console (F12)
- **Database:** MariaDB error log in container

### Health Checks
```bash
# API liveness
curl http://localhost:8000/api/hello

# Frontend PWA
curl http://localhost:5173/

# Database
mysql -u frappe -ppassword frappe_erp
```

### Common Issues & Fixes
| Issue | Cause | Fix |
|-------|-------|-----|
| 401 Unauthorized | Session expired | Logout & re-login via Google OAuth |
| 404 API Not Found | Whitelist decorator missing | Add `@frappe.whitelist()` to function |
| CORS Error | Frontend requests backend | Add to `frappe.conf.json` allowed origins |
| Docker container exits | Database connection failed | Check `docker-compose.yml` env vars |

---

**End of Architecture Document**
