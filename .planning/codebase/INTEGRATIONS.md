# External Integrations & APIs - BEI HRMS

## Google Workspace Integrations

### Google OAuth 2.0 (SSO & Token Management)
**Files:** `hrms/utils/google_oauth.py`, `hrms/api/oauth_tokens.py`, `hrms/api/google_login.py`

#### Implementation Details
- **Flow:** OAuth 2.0 Authorization Code Grant
- **Service Account:** `credentials/task-manager-service.json`
- **Impersonation:** `sam@bebang.ph` (Domain-Wide Delegation)
- **Scopes:** 
  - Google Chat: `chat.bot`, `chat.messages`
  - Google Drive: `drive.readonly`, `drive`

#### Token Management
- **Storage:** Encrypted Long Text fields (DocType: `User OAuth Token`)
- **Migration:** Automatic best-effort migration from legacy Password fields
- **Functions:**
  - `store_user_oauth_token()` - Store encrypted tokens per user
  - `get_user_oauth_token()` - Retrieve and decrypt tokens
  - `_maybe_migrate_password_field_to_text()` - Legacy field migration
  - `_get_token()` / `_set_token()` - Internal encryption helpers

#### Related Endpoints
- `GET /api/method/oauth_tokens.get_oauth_token` - Retrieve token
- `POST /api/method/oauth_tokens.store_oauth_token` - Store token
- `POST /api/method/oauth_login.create_oauth_login` - OAuth callback

---

### Google Chat Integration
**File:** `hrms/api/google_chat.py`

#### Capabilities
- **Send Messages:** Direct to spaces, group chats, DMs
- **Receive Messages:** Webhook endpoint for bot messages
- **Space Management:** List spaces with member resolution
- **Authentication:** Service account with domain-wide delegation

#### Implementation
- **Libraries:** `google-api-python-client`, `requests`
- **Service:** `chat_v1.spaces().messages().create()`
- **Webhook Handler:** Receives incoming messages from Google Chat

#### Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/method/send_chat_message` | POST | Send message to space |
| `/api/method/get_chat_spaces` | GET | List accessible spaces |
| `/api/method/resolve_chat_members` | POST | Get member names/IDs |

#### Data Model: Chat Spaces Registry
- Space IDs: `spaces/AAQA3NVVR6c`, `spaces/AAAAw2DfR0Q`, `spaces/AAQAnNWwb0I`, etc.
- 122 spaces, 47 group chats, 65+ DMs (as of last registry update)
- Member resolution: Converts numeric IDs to email addresses

#### Common Issues & Fixes
- **"Unable to load PEM file"** → Verify `credentials/task-manager-service.json` integrity
- **DMs show as IDs** → Google Chat API limitation; groups without displayName filtered out
- **Permission denied** → Domain-wide delegation not active or scopes insufficient

---

### Google Drive Integration
**File:** `hrms/api/google_drive.py`

#### Capabilities
- **File Search:** Query by name, folder, MIME type
- **File Download:** Fetch file content via API
- **Folder Navigation:** List folder contents
- **Metadata:** Retrieve file timestamps, sizes, permissions

#### Implementation
- **Libraries:** `google-api-python-client`, `requests`
- **Methods:** 
  - `drive_v3.files().list()` - Search & list
  - `drive_v3.files().get_media()` - Download
- **Authentication:** Service account with domain-wide delegation

#### Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/method/search_drive_files` | GET | Search by name/folder |
| `/api/method/get_drive_file_content` | GET | Download file |
| `/api/method/list_drive_folder` | GET | List folder contents |

#### Data Access Patterns
- **Query Syntax:** `name contains 'search term'`, `'<folder_id>' in parents`
- **Folder ID Extraction:** From URLs like `https://drive.google.com/drive/folders/<ID>`
- **Fields:** `files(id, name, mimeType, modifiedTime, size, owners, permissions)`

---

### Google Admin SDK (User Provisioning)
**Scope:** Domain-wide delegation with @bebang.ph domain

#### Capabilities
- **User Directory:** List/search users in domain
- **Email Verification:** Validate @bebang.ph addresses
- **Group Management:** Check group memberships
- **Account Status:** Verify suspended/active status

#### Endpoints (When Implemented)
- Could implement: `/api/method/verify_bebang_user`
- Could implement: `/api/method/list_domain_groups`

---

## Cloud Infrastructure Integrations

### Amazon Web Services (AWS)
**Region:** ap-southeast-1 (Singapore)

#### Services Used

**1. RDS (Relational Database Service)**
- **Instance:** Managed MariaDB 10.6
- **Endpoint:** `frappe-hrms-db.ctmwomgscn66.ap-southeast-1.rds.amazonaws.com`
- **Port:** 3306
- **Database:** Frappe site database
- **Backup:** AWS automated backups (retained for 7 days)
- **Security:** VPC-isolated, security group restricted

**2. ElastiCache (Redis)**
- **Endpoint:** `frappe-hrms-redis.eeyu0l.0001.apse1.cache.amazonaws.com`
- **Node Type:** Standard (configurable size)
- **Purpose:** Cache layer + background job queue
- **Availability:** Single-AZ or Multi-AZ (if configured)

**3. EC2 (Elastic Compute Cloud)**
- **Instance ID:** `i-026b7477d27bd46d6`
- **Instance Type:** (Standard/General purpose - actual type in AWS console)
- **Region:** ap-southeast-1 (Singapore)
- **AMI:** Ubuntu or Amazon Linux with Docker installed
- **Security Groups:** SSH, HTTP, HTTPS, Docker Swarm ports

**4. Systems Manager**
- **Purpose:** Agent-based deployment automation
- **Integration:** GitHub Actions → AWS Systems Manager → EC2
- **Ports:** SSM agent (port 443 outbound)
- **Commands:** Deploy Docker images, run migrations

#### Credentials
- **Storage:** Doppler (`bei-erp` project, config: `dev`)
- **Secrets:**
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_REGION` (ap-southeast-1)

---

## Continuous Integration / Deployment

### GitHub Actions CI/CD
**Workflows:** `.github/workflows/`

#### Build Container Image Workflow
- **Trigger:** Release published, manual dispatch, git tags
- **Builds:** Multi-arch (amd64, arm64) via QEMU
- **Registry:** GitHub Container Registry (GHCR)
- **Dockerfile:** Frappe Docker layered Containerfile
- **Authentication:** GitHub Token (GITHUB_TOKEN)

#### Build and Deploy Workflow
- **Trigger:** Push to `production` branch (changes in `hrms/**`)
- **Steps:**
  1. Build Docker image → GHCR
  2. Authenticate to AWS Systems Manager
  3. Execute deploy command on EC2 instance
  4. Optional: Run `bench migrate` after deployment
- **Environment Variables:**
  - `AWS_REGION: ap-southeast-1`
  - `EC2_INSTANCE_ID: i-026b7477d27bd46d6`
  - `DOCKER_IMAGE: samkarazi/bebang-erpnext-hrms`
  - `DOCKER_TAG: v15`
  - `FRAPPE_SITE: hrms.bebang.ph`

---

## Repository & Version Control

### GitHub Repository
- **Owner:** Bebang-Enterprise-Inc
- **URL:** `https://github.com/Bebang-Enterprise-Inc/hrms.git`
- **Branch Structure:**
  - `production` - Live deployed code (main branch for CI/CD)
  - `version-15` - Development branch (Frappe v15)
  - Feature branches: `fix/`, `feature/`, etc.
- **Upstream:** `https://github.com/frappe/hrms` (Frappe official HRMS)

### Image Registries
| Registry | Image | Purpose |
|----------|-------|---------|
| GitHub Container Registry | `ghcr.io/Bebang-Enterprise-Inc/hrms` | Official CI/CD output |
| Docker Hub | `samkarazi/bebang-erpnext-hrms:v15` | Secondary mirror |

---

## Time Attendance Integration

### ADMS Receiver (Custom Service)
**Location:** `adms_receiver/`

#### Purpose
- Receive time attendance data from Bio ID/ADMS devices
- Parse and store attendance records
- Provide attendance data to payroll workflows

#### Technology
- **Framework:** FastAPI (async Python web framework)
- **Server:** Uvicorn ASGI server
- **Database:** PostgreSQL (via SQLAlchemy ORM)
- **Docker:** Containerized service

#### Endpoints
- Defined by Bio ID device integration patterns
- Likely: `POST /attendance` - Record punch-in/punch-out events

#### Data Model
- **Tables:** Attendance records with employee ID, timestamp, location
- **Sync:** Periodic pull or real-time push from ADMS

---

## Task Management & Notifications

### Frappe Native Integration
- **DocType:** Task
- **Workflow:** Assignee → Status → Comments
- **Notifications:** Email triggers via Frappe framework
- **API:** RESTful endpoints for task CRUD

### Custom Task APIs (`hrms/api/`)
| Endpoint | Purpose |
|----------|---------|
| `/api/method/list_recent_tasks` | Fetch tasks via MCP |
| `/api/method/create_task` | Create new task |
| `/api/method/update_task` | Modify task status/assignee |

---

## Employee Data Management

### Employee Clearance Workflow
**File:** `hrms/api/employee_clearance.py`

#### Endpoints
- `POST /api/method/request_clearance` - Initiate separation
- `GET /api/method/get_clearance_status` - Check progress
- `POST /api/method/approve_clearance_item` - Department sign-off

#### Integration Points
- **HR Module:** Linked to employee status
- **Finance:** Loan/advance recovery
- **Operations:** Equipment handover
- **IT:** Account deactivation (via employee clearance approval)

---

### Staff Coverage Management
**File:** `hrms/api/coverage.py`

#### Endpoints
- `POST /api/method/request_coverage` - Request relief staff
- `POST /api/method/approve_coverage` - Assign replacement
- `GET /api/method/get_coverage_requests` - List requests by store/date

#### Data Model
- **DocType:** BEI Staff Coverage Request
- **Fields:** store, coverage_date, shift, reason, assigned_employee, status

---

## Store & Inventory Management

### Store Data API
**File:** `hrms/api/store.py`

#### Endpoints (Likely)
- `GET /api/method/get_store_info` - Store details
- `GET /api/method/list_store_items` - Inventory
- `POST /api/method/record_store_transfer` - Stock movement

### Inventory Management
**File:** `hrms/api/inventory.py`

#### Capabilities
- **Opening Inventory:** Load master data from CSV
- **Stock Movements:** Record IN/OUT transactions
- **Warehouse Management:** Transfer between locations
- **Reporting:** Inventory valuation & aging

#### Integration
- Links to `Item` DocType (SKU master)
- Links to `Warehouse` DocType (locations)
- Integration with `Stock Entry` for movements

---

## Third-Party Services & Libraries

### Firebase
**Package:** `firebase` (10.8.0)

#### Likely Uses
- Push notifications (Cloud Messaging)
- Analytics tracking
- User authentication (potential fallback)
- Real-time database (if used)

#### Configuration
- Likely in `.env` or Frappe site config
- API key stored in Doppler

---

### Stripe (Payment Processing)
**Status:** Not currently integrated
- **Available:** `pyproject.toml` supports dependency inclusion
- **Use Case:** Could be added for: Employee loan repayment, payslip advance payment, leave encashment settlements

---

### Supabase (Data Lake)
**Status:** Integrated for analytics
- **Credentials:** Stored in Doppler (`bei-erp` project)
- **Secrets:**
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
- **Purpose:** BEI Analytics dashboards, ETL reporting

---

## Deployment Integrations

### Vercel (Employee App)
**Project:** `bei-tasks` (separate repository)

#### Integration Points
- **Frontend Framework:** React/Next.js
- **API Calls:** To Frappe HRMS backend via REST
- **Auth:** OAuth tokens from HRMS
- **Auto-Deploy:** On `bei-tasks` repo push

#### Environment Variables
- Stored in Vercel project settings
- Synced from Doppler: `FRAPPE_API_KEY`, `FRAPPE_API_SECRET`

---

## Authentication & Authorization

### Frappe Native Auth
- **Default:** Session-based (cookie)
- **API:** Token-based (API key + secret)
- **Roles:** Frappe role-based access control (RBAC)

### OAuth Integration
- **Provider:** Google Workspace
- **Flow:** User logs in via Google → OAuth token stored → API calls authenticated with token
- **User Creation:** Auto-provisioned on first OAuth login (enforce @bebang.ph domain)

### Permission Model
- **Workspace Roles:**
  - Area Supervisor
  - Store Supervisor
  - Store Staff
  - HR User
  - Admin
- **Resource Permissions:** Document-level via Frappe role rules

---

## Webhooks & Event Handlers

### Incoming Webhooks
- **Google Chat:** Bot receives messages (incoming webhooks)
- **Bio ID/ADMS:** Attendance data pushed to receiver

### Outgoing Webhooks
- **Employee Clearance:** Notifications to approvers
- **Task Updates:** Email notifications
- **Leave Approvals:** Email to supervisors

---

## Configuration Management

### Doppler Secrets (Primary)
**Project:** `bei-erp`
**Config:** `dev`, `prd` (as needed)

#### Secret Categories
| Category | Secrets | Source |
|----------|---------|--------|
| AWS | ACCESS_KEY, SECRET_KEY, REGION | AWS IAM |
| Frappe | API_KEY, API_SECRET, ADMIN_PASSWORD | HRMS instance |
| Google | SERVICE_ACCOUNT_JSON, OAUTH_CREDENTIALS | Google Cloud |
| Vercel | VERCEL_TOKEN, VERCEL_TEAM_ID | Vercel dashboard |
| Supabase | URL, SERVICE_ROLE_KEY | Supabase dashboard |

### Environment Files
- `.env` - Local development (git-ignored)
- `aws/bebang-hrms/.env` - Production environment variables
- `docker-dev/.env` - (If used) Docker dev environment

---

## Monitoring & Observability

### Application Logs
- **Frappe Error Log:** Built-in error tracking
- **Background Jobs:** Frappe RQ job logs (Redis)
- **Docker Logs:** Via `docker compose logs frappe`

### AWS CloudWatch
- **EC2 Instance Metrics:** CPU, memory, network
- **RDS Monitoring:** Database performance, connections
- **ElastiCache Metrics:** Redis memory, evictions

### Frappe Native Monitoring
- **Site Activity:** User login history
- **API Logs:** Request/response tracking
- **DocType Audit Trail:** Change logs for sensitive documents

---

## Data Privacy & Compliance

### Encryption
- **OAuth Tokens:** Encrypted in database (Frappe encryption)
- **Passwords:** Hashed via Frappe's password manager
- **Transit:** HTTPS/TLS for all connections

### Data Retention
- **AWS Backups:** 7-day retention on RDS
- **Audit Logs:** Frappe native audit trail (configurable)
- **DOLE Compliance:** Payroll records retained per Philippine law

### Access Control
- **Service Accounts:** Limited scopes per service
- **API Keys:** Stored securely, rotated periodically
- **SSH Keys:** EC2 access restricted to authorized users

---

## Integration Roadmap

### Planned/Potential Integrations
1. **Supabase Analytics** - In progress (BEI Analytics dashboards)
2. **AWS S3** - Document storage (if volumes grow)
3. **Cloudflare** - CDN for assets, DNS management
4. **Stripe** - Loan/advance payment processing
5. **Twilio** - SMS notifications for leave approvals
6. **ZKTeco SDK** - Bio ID device integration (alternative to ADMS receiver)

### Legacy Integrations
- **Google Sheets** - Data import (currently manual)
- **CSV Upload** - Batch imports (via Frappe Data Importer)

---

## Notes

1. **Service Account Security:** The `task-manager-service.json` file contains sensitive credentials; never commit to version control
2. **Token Refresh:** OAuth tokens auto-refresh via Frappe background jobs (check Job Queue)
3. **Rate Limiting:** Google APIs enforce rate limits; implement caching and backoff strategies
4. **Multi-tenancy:** Single Frappe instance; multiple sites possible but currently one (`hrms.bebang.ph`)
5. **API Versioning:** Frappe v15 API is stable; breaking changes unlikely
6. **Webhook Security:** Verify webhook signatures from third-party services (if implemented)

