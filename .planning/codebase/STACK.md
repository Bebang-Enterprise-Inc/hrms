# Technology Stack - BEI HRMS

## Backend Runtime & Framework

### Core Platform
- **Framework:** Frappe Framework v15 (Python-based ERP platform)
- **Python Version:** >= 3.10 (from `pyproject.toml`)
- **Build System:** Flit (PEP 517)

### Backend Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| Frappe | >= 15.0.0 | Core ERP framework |
| ERPNext | >= 15.0.0 | ERP application suite |
| HRMS | Custom | HR/Payroll customization (BEI fork) |

### Additional Backend Services

**ADMS Receiver (Time Attendance)**
- `fastapi` (0.115.6) - Async API framework
- `uvicorn[standard]` (0.34.0) - ASGI web server
- `sqlalchemy` (2.0.36) - ORM
- `psycopg[binary]` (3.2.3) - PostgreSQL driver
- `requests` (2.32.3) - HTTP client
- `python-dateutil` (2.9.0.post0) - Date utilities
- `pytest` (9.0.2) - Testing framework

**Google Chat Integration**
- `google-auth` (>= 2.0.0) - OAuth2 authentication
- `google-api-python-client` (>= 2.0.0) - Google APIs client

**Custom APIs** (`hrms/api/`)
- Google OAuth token management
- Google Chat integration
- Google Drive integration
- Employee clearance workflows
- Task management
- Inventory management

---

## Frontend Runtime & Frameworks

### Primary PWA (Legacy Admin Interface)
**Location:** `frontend/`
- **Runtime:** Node.js (ES modules)
- **Build Tool:** Vite 5.4.10
- **Framework:** Vue 3.5.12
- **UI Framework:** Ionic 7.4.3 (mobile-first)
- **Styling:** TailwindCSS 3.4.3 + PostCSS 8.4.5
- **State/API:** Frappe UI (0.1.105)

**Key Dependencies:**
- `@ionic/vue` (7.4.3) - Ionic Vue components
- `@ionic/vue-router` (7.4.3) - Ionic routing
- `vue-router` (4.3.2) - Client-side routing
- `vite-plugin-pwa` (0.20.5) - PWA configuration
- `workbox-core` & `workbox-precaching` (7.0.0) - Service worker
- `dayjs` (1.11.11) - Date manipulation
- `feather-icons` (4.29.1) - Icon library
- `vue-easy-lightbox` (1.17.0) - Image lightbox
- `firebase` (10.8.0) - Firebase services
- `html2canvas` (1.4.1) - HTML to image conversion

**Build Output:** `hrms/public/frontend/` with manifest for PWA

### Secondary PWA (Roster/Scheduling)
**Location:** `roster/`
- **Runtime:** Node.js (ES modules)
- **Build Tool:** Vite 5.4.10
- **Framework:** Vue 3.5.12
- **Styling:** TailwindCSS 3.4.3
- **API:** Frappe UI (0.1.105)

**Key Dependencies:**
- `@vitejs/plugin-vue` (4.4.0) - Vue 3 Vite plugin
- `vue-router` (4.3.2) - Routing
- `TypeScript` (5.4.5) - Type checking
- Same utility packages as primary PWA

**Build Output:** `hrms/www/roster.html`

### External Employee App (Separate Repository)
**Project:** `bei-tasks` (hosted on Vercel)
- **Framework:** Next.js 16 with React
- **UI Components:** Shadcn UI with Tailwind CSS v4
- **Backend:** Connects to Frappe HRMS via REST API
- **Deployment:** Vercel

---

## Build Configuration & Tooling

### Vite Configuration
**File:** `frontend/vite.config.js`
- **Server Port:** 8080 (dev) with proxy to Frappe (port 8000)
- **Build Target:** ES2015
- **Source Maps:** Enabled in dev
- **Plugins:**
  - Vue 3 support
  - Frappe UI integration
  - PWA plugin (injectManifest strategy)
- **Output:** Organized module chunking (frappe-ui separate chunk)

### Code Quality
**Ruff Configuration** (`pyproject.toml`)
- **Line Length:** 110 characters
- **Target Python:** 3.10+
- **Linters:** F, E, W, I, UP, B, RUF
- **Formatters:** Double quotes, tab indentation
- **Import Sorting:** Custom sections (frappe, erpnext, hrms, first-party)

### JavaScript/Frontend Tooling
- **Package Managers:** Yarn (workspaces for monorepo)
- **Linting:** ESLint 8.39.0
- **ESLint Plugins:** `eslint-plugin-vue` (9.11.0)
- **Formatting:** Prettier 2.8.8

---

## Database

### Primary Database
- **Type:** MariaDB 10.6
- **Deployment:** AWS RDS ElastiCache (Production)
- **Local Dev:** Docker container (`mariadb:10.6`)
- **Port:** 3307 (dev), standard 3306 (prod)
- **Charset:** utf8mb4 (Unicode support)

### Cache Layer
- **Type:** Redis
- **Deployment:** AWS ElastiCache (Production)
- **Local Dev:** Two Redis containers (Alpine)
  - `redis-cache` - Cache operations
  - `redis-queue` - Background jobs
- **Driver:** Standard Redis protocol

---

## Containerization & Orchestration

### Docker Images
| Service | Image | Purpose |
|---------|-------|---------|
| Frappe | `frappe/bench:v5.25.11` | Backend application server |
| MariaDB | `mariadb:10.6` | Database |
| Redis | `redis:alpine` | Cache & queue (2x instances) |

### Docker Compose
- **Location:** `docker-dev/docker-compose.yml`
- **Network:** Bridge (`frappe-dev-network`)
- **Volumes:** Named volumes for persistence (`frappe-bench`, `mariadb-data`)
- **Auto-initialization:** Bench setup on first run (10-15 min)
- **Sync Strategy:** BEI custom API files and DocTypes mounted as read-only, synced on container start

### Production Deployment
- **Strategy:** Docker Swarm (zero-downtime deploys)
- **Registry:** GitHub Container Registry (`ghcr.io`)
- **Orchestration:** AWS EC2 + Docker Swarm
- **Instance:** `i-026b7477d27bd46d6` (ap-southeast-1)

---

## CI/CD Pipeline

### GitHub Actions Workflows
**Location:** `.github/workflows/`

**1. Build Container Image**
- **Trigger:** Release publication, manual dispatch, tags
- **Target Branches:** version-15
- **Build Strategy:** Multi-architecture (amd64, arm64)
- **Builder:** Docker Buildx with QEMU
- **Registry:** GitHub Container Registry (GHCR)
- **Frappe Docker:** Layered Containerfile from frappe/frappe_docker

**2. Build and Deploy**
- **Trigger:** Push to `production` branch (hrms/** changes)
- **Manual Inputs:**
  - Skip image build (deploy existing)
  - Run migrations
  - Force no-cache build
- **AWS Integration:** EC2 Instance via Systems Manager
- **Docker Image:** `samkarazi/bebang-erpnext-hrms:v15`
- **Site:** `hrms.bebang.ph`

### Apps Configuration
**File:** `.github/helper/apps.json`
```json
[
  {"url": "https://github.com/frappe/erpnext", "branch": "version-15"},
  {"url": "https://github.com/frappe/payments", "branch": "version-15"},
  {"url": "https://github.com/Bebang-Enterprise-Inc/hrms", "branch": "production"}
]
```

---

## Development Tools & Configuration

### Python Development
- **Linter/Formatter:** Ruff (configured in `pyproject.toml`)
- **Build Backend:** Flit Core 3.4+
- **Testing:** Pytest framework

### Node.js Development
- **Version Management:** `.nvmrc` or system default
- **Package Manager:** Yarn (with workspaces)
- **Workspaces:** Frontend, Roster, Frappe UI

### Code Editor Configuration
- **VSCode Support:** `.vscode/` directory
- **Cursor IDE Support:** `.cursor/` directory

---

## API Architecture

### Frappe REST API
- **Endpoint:** `/api/`
- **Auth:** Token-based (API key + secret)
- **Format:** JSON
- **Methods:** GET, POST, PUT, DELETE (standard REST)

### Custom REST Endpoints (`hrms/api/`)
- **Framework:** Frappe decorators (`@frappe.whitelist()`)
- **Endpoints:**
  - `/api/method/hello` - Health check
  - `/api/method/get_current_user_info` - User profile
  - `/api/method/get_current_employee_info` - Employee details
  - `/api/method/request_coverage` - Staff coverage requests
  - `/api/method/approve_coverage` - Coverage approval
  - `/api/method/get_coverage_requests` - Coverage list
  - Google Chat message handlers
  - Google Drive file operations

### MCP (Model Context Protocol)
- **Implementation:** `hrms/api/mcp.py`
- **Framework:** `frappe_mcp` library
- **Tools:** Employee lookup, task listing
- **Purpose:** AI/LLM integration for enterprise workflows

---

## Service Account & Credentials

### AWS Services
- **Credentials:** Stored in Doppler (`bei-erp` project)
- **Services Used:**
  - RDS (MariaDB database)
  - ElastiCache (Redis)
  - EC2 (instance management)
  - Systems Manager (deployment automation)

### Google Workspace
- **Service Account:** `task-manager-service.json`
- **Scopes:** Domain-wide delegation for OAuth
- **Impersonation:** `sam@bebang.ph`
- **APIs:** Google Chat, Google Drive, Google Sheets
- **Token Storage:** Encrypted Long Text fields (User OAuth Token DocType)

### Container Registry
- **GitHub Container Registry (GHCR)**
- **Docker Hub:** `samkarazi/bebang-erpnext-hrms`

---

## Development Environment

### Local Setup Requirements
- **OS:** Windows/Mac/Linux (Git Bash compatible)
- **Docker:** Docker Engine + Docker Compose
- **Python:** 3.10+
- **Node.js:** 18+ (via workspace .nvmrc or system)
- **Git:** For version control

### Development Commands
```bash
# Backend
docker compose up -d                 # Start Docker services
docker exec -it frappe-dev bench ... # Run bench commands

# Frontend (Legacy PWA)
cd frontend
yarn dev                            # Start Vite dev server (port 8080)
yarn build                          # Build for production

# Roster (Scheduling PWA)
cd roster
yarn dev                            # Start Vite dev server
yarn build                          # Build for production

# Full build
yarn build                          # Build all PWAs
```

---

## Version & Compatibility Matrix

| Component | Version | Notes |
|-----------|---------|-------|
| Frappe | 15.x | LTS version for stability |
| ERPNext | 15.x | Aligned with Frappe |
| Python | 3.10+ | Minimum version enforced |
| Node.js | 18+ | ES modules required (type: module) |
| MariaDB | 10.6 | UTF8MB4 support for multilingual data |
| Redis | 7.x (Alpine) | Lightweight for dev/cache |
| Docker | 20.10+ | For Buildx multi-arch support |

---

## Deployment Topology

```
┌─────────────────────────────────────────┐
│        GitHub (Source Control)          │
│  - production branch triggers CI/CD     │
└─────────────────────────────────────────┘
              ↓ (GitHub Actions)
┌─────────────────────────────────────────┐
│    GitHub Container Registry (GHCR)     │
│    Docker Image: ghcr.io/.../hrms       │
└─────────────────────────────────────────┘
              ↓ (AWS Systems Manager)
┌─────────────────────────────────────────┐
│    AWS EC2 (ap-southeast-1)             │
│    Instance: i-026b7477d27bd46d6        │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  Docker Swarm (Orchestration)   │   │
│  │  ├─ Frappe Container            │   │
│  │  ├─ MariaDB (AWS RDS)           │   │
│  │  └─ Redis (AWS ElastiCache)     │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

---

## Notes & Considerations

1. **Monorepo Structure:** Root `package.json` uses Yarn workspaces to manage frontend and roster as sub-packages
2. **Custom DocTypes:** BEI-specific DocTypes synced from `hrms/hr/doctype/` on container start
3. **PWA Strategy:** Service workers configured with Workbox for offline support
4. **Production Database:** MariaDB on AWS RDS (not Docker container)
5. **Token Management:** OAuth tokens stored encrypted, with fallback migration from legacy Password fields
6. **Async Jobs:** Redis queues for background processing (Frappe RQ)
7. **Local Development:** First startup requires 10-15 minutes for bench initialization

