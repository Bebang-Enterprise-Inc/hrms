# Frontend Architecture Decision

**Date:** 2026-01-22
**Status:** APPROVED
**Decision:** All user-facing apps will be built using React + Shadcn UI, connecting to Frappe via API

---

## Decision Summary

| Aspect | Decision |
|--------|----------|
| **User Apps** | React + Shadcn UI + Next.js |
| **Backend** | Frappe ERP/HRMS (existing AWS Docker) |
| **Connection** | Frappe REST API |
| **Hosting** | Vercel (frontend), AWS Docker (backend) |
| **Primary Domain** | `my.bebang.ph` |

---

## Research Findings

### Frappe Deployment Options Evaluated

#### 1. Frappe Docker (Current Setup)

**Source:** [Frappe Docker FAQ](https://github.com/frappe/frappe_docker/wiki/Frequently-Asked-Questions), [Frappe Deployment Docs](https://frappe.io/framework/deployment)

**How it works:**
- Production images are IMMUTABLE - code packaged at build time
- Assets pre-built during image construction
- Cannot `bench get-app`, `bench build`, or `bench restart` in production containers

**Limitations identified:**
| Limitation | Impact on BEI |
|------------|---------------|
| No hot-reload in production | Every code change requires Docker rebuild (5-15 min cycle) |
| Immutable containers | Cannot modify running apps |
| No supervisor | Must use orchestrator commands for restarts |
| No cron in containers | External scheduling required |

**Best for:** Stable production deployments where code changes are infrequent

**Not ideal for:** Rapidly evolving user interfaces, frequent iteration

#### 2. Frappe Cloud

**Source:** [Frappe Cloud Docs](https://frappecloud.com/docs/introduction), [Frappe Cloud vs Self-Hosting](https://www.dexciss.io/blog/educational-6/choosing-the-right-erpnext-hosting-frappe-cloud-vs-self-hosting-112)

**Pros:**
- Managed hosting, one-click deploys
- Automatic updates and backups
- Seamless scaling
- Enterprise-grade security

**Cons:**
- Less control over environment
- Subscription cost
- Limited regions for data residency
- Still uses Frappe UI (not custom mobile-first UI)

#### 3. Traditional Bench on VM

**Source:** [Frappe Bench GitHub](https://github.com/frappe/bench)

**Pros:**
- Hot-reload during development
- Direct `bench` commands
- Full control

**Cons:**
- Manual maintenance
- Scaling challenges
- Not recommended for production by Frappe team

### Frappe Mobile App History

**Source:** [Frappe Mobile Announcement](https://frappe.io/blog/announcements/introducing-frappe-mobile)

**Key finding:** Frappe built and then DISCONTINUED their Flutter mobile app.

**Reason for discontinuation:**
> "Most of the customizations done in Client Scripts weren't transferrable to the mobile app. The mobile app uses Flutter which is incompatible with Javascript. At its current state, the mobile app did not solve any problem that their web version doesn't."

**Current approach:** PWA (Progressive Web App) via `/hrms` URL

### Frappe UI Assessment

**Source:** [Frappe UI Docs](https://ui.frappe.io/), [Frappe UI GitHub](https://github.com/frappe/frappe-ui)

**Components available:** 30+ (Button, Dialog, Forms, DatePicker, etc.)
**Technology:** Vue 3 + TailwindCSS

**Assessment for non-techy store staff:**
| Concern | Finding |
|---------|---------|
| Mobile optimization | Designed for web/desktop first |
| Big button UI | Not built-in, requires custom development |
| Offline support | Limited in default Frappe PWA |
| Customization | Tied to Frappe release cycle |

### React + Shadcn Alternative

**Source:** [Shadcn UI](https://ui.shadcn.com/), existing tasks.bebang.ph implementation

**Advantages for BEI:**
| Advantage | Benefit |
|-----------|---------|
| Instant deploys | Vercel deploys in seconds, no Docker rebuild |
| Mobile-first possible | Full control over UI/UX |
| Offline-capable | Next.js PWA with service workers |
| Proven pattern | Already working at tasks.bebang.ph |
| Decoupled | Frontend changes don't require backend redeployment |
| Fast iteration | Can push fixes/features multiple times per day |

---

## Why React + Shadcn Over Frappe UI

### 1. Development Speed

| Approach | Deploy Time | Iteration Cycle |
|----------|-------------|-----------------|
| Frappe Docker | 5-15 minutes | Build image → Push → Restart containers |
| React + Vercel | 30-60 seconds | Push → Auto-deploy |

### 2. User Experience Control

| Aspect | Frappe UI | React + Shadcn |
|--------|-----------|----------------|
| Mobile-first design | Limited | Full control |
| Big button interfaces | Must customize | Can build exactly what's needed |
| Offline support | Limited | Full PWA capabilities |
| Role-based UI | Server-side only | Client + server |

### 3. Maintenance Independence

- Frontend bugs can be fixed without touching backend
- UI improvements don't require Frappe expertise
- Can use broader React ecosystem (libraries, components)

### 4. Existing Infrastructure

tasks.bebang.ph already has:
- React + Shadcn setup ✅
- Frappe API authentication ✅
- Employee data integration ✅
- Onboarding workflow (built) ✅
- Data enrichment (built) ✅

Building new features extends existing proven infrastructure.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BEI SYSTEM ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   USERS (Store Staff, HQ, Warehouse)                                │
│              │                                                       │
│              ▼                                                       │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │              my.bebang.ph (React + Shadcn)                  │   │
│   │                      Hosted on Vercel                        │   │
│   │                                                              │   │
│   │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │   │
│   │   │  Store   │ │ Dispatch │ │  Tasks   │ │ Profile  │      │   │
│   │   │ Ordering │ │ Tracker  │ │          │ │Enrichment│      │   │
│   │   └──────────┘ └──────────┘ └──────────┘ └──────────┘      │   │
│   │   ┌──────────┐ ┌──────────┐ ┌──────────┐                   │   │
│   │   │  Store   │ │Attendance│ │  Leave   │                   │   │
│   │   │Receiving │ │  View    │ │  View    │                   │   │
│   │   └──────────┘ └──────────┘ └──────────┘                   │   │
│   │                                                              │   │
│   └─────────────────────────────┬───────────────────────────────┘   │
│                                 │                                    │
│                          Frappe REST API                            │
│                                 │                                    │
│   ┌─────────────────────────────▼───────────────────────────────┐   │
│   │           Frappe ERP + HRMS (AWS Docker)                    │   │
│   │                                                              │   │
│   │   Domains: hq.bebang.ph                                    │   │
│   │            (All point to same instance)                     │   │
│   │                                                              │   │
│   │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │   │
│   │   │ Employee │ │   Stock  │ │ Material │ │  Leave   │      │   │
│   │   │  Master  │ │  Entry   │ │ Request  │ │Application│     │   │
│   │   └──────────┘ └──────────┘ └──────────┘ └──────────┘      │   │
│   │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │   │
│   │   │ Supplier │ │ Purchase │ │ Delivery │ │ Payroll  │      │   │
│   │   │  Master  │ │  Order   │ │   Note   │ │  Entry   │      │   │
│   │   └──────────┘ └──────────┘ └──────────┘ └──────────┘      │   │
│   │                                                              │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Consolidate Portal (Week of Jan 22)
- [ ] Rename tasks.bebang.ph → my.bebang.ph (or chosen name)
- [ ] Set up DNS redirect from old URL
- [ ] Enable role-based module visibility
- [ ] Configure enrichment enforcement

### Phase 2: Store Operations (Week of Jan 27)
- [ ] Build Store Ordering module
- [ ] Build Store Receiving module
- [ ] Connect to Frappe Stock Entry API

### Phase 3: Dispatch (Week of Feb 3)
- [ ] Build Dispatch Tracker module
- [ ] Connect to Frappe Delivery Note API

### Phase 4: Attendance/Leave Views (Future)
- [ ] Add attendance view (read from Frappe)
- [ ] Add leave application (write to Frappe)
- [ ] Add salary slip view (read from Frappe)

---

## API Endpoints Required

| Feature | Frappe DocType | API Endpoint |
|---------|---------------|--------------|
| Store Ordering | Material Request | `POST /api/resource/Material Request` |
| Store Receiving | Stock Entry | `POST /api/resource/Stock Entry` |
| Dispatch | Delivery Note | `POST /api/resource/Delivery Note` |
| Employee Profile | Employee | `GET /api/resource/Employee/{id}` |
| Attendance | Employee Checkin | `GET /api/resource/Employee Checkin` |
| Leave | Leave Application | `POST /api/resource/Leave Application` |

---

## References

- Frappe Deployment Docs: https://frappe.io/framework/deployment
- Frappe Docker FAQ: https://github.com/frappe/frappe_docker/wiki/Frequently-Asked-Questions
- Frappe Mobile Blog: https://frappe.io/blog/announcements/introducing-frappe-mobile
- Frappe UI: https://ui.frappe.io/
- Frappe Cloud: https://frappecloud.com/docs/introduction
- Shadcn UI: https://ui.shadcn.com/
- ERPNext CI/CD: https://medium.com/@anshumanth1997/streamline-erpnext-deployment-with-gitlab-ci-cd-684e82aeae43

---

## Approval

| Role | Name | Date |
|------|------|------|
| CEO/Decision Maker | Sam | 2026-01-22 |
