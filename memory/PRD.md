# NOW KART — LIVING PRD

## Source of Truth
Repository: https://github.com/manish98563/nowkartcustomer (main branch)

---

## What This Project Is
Now Kart is a React Native + Expo (Expo Router) grocery-delivery customer app backed by a FastAPI BFF and MongoDB, acting as a headless mobile front-end for a real Shopify store (vcq88p-fj.myshopify.com).

---

## Iterations Completed

### Iterations 1–7 — Customer App (see NOWKART_MASTER_HANDOVER.md)
UI, Shopify Storefront, Auth, Checkout, Address Management, Order Management, Live Tracking — all code-complete.

### Iteration 8 — Delivery Service Backend (2026-07-22)

#### What was built

**New backend modules (11 files):**
- `backend/delivery/__init__.py`
- `backend/delivery/db.py` — delivery_jobs + stores collections, indexes
- `backend/delivery/schemas.py` — DeliveryJobStatus enum, all Pydantic models (customer view + full view), StoreOut
- `backend/delivery/service.py` — full state machine, job creation, store seeding, queries, cancel logic
- `backend/delivery/router.py` — /api/delivery/* endpoints
- `backend/webhooks/__init__.py`
- `backend/webhooks/db.py` — webhook_events collection + unique index
- `backend/webhooks/schemas.py` — Shopify REST payload schemas
- `backend/webhooks/verification.py` — HMAC-SHA256 signature verification
- `backend/webhooks/service.py` — webhook routing (orders/paid → create job, orders/cancelled → cancel job)
- `backend/webhooks/router.py` — POST /api/webhooks/shopify

**Modified files:**
- `backend/server.py` — mounts delivery_router + webhooks_router, unified startup_event
- `backend/.env` — adds SHOPIFY_WEBHOOK_SECRET (empty), DELIVERY_DEFAULT_STORE_NAME, DELIVERY_DEFAULT_ETA_MINUTES

#### New MongoDB Collections
| Collection | Purpose |
|---|---|
| delivery_jobs | Central delivery job lifecycle records |
| stores | Store configuration (seeded with default on startup) |
| webhook_events | Shopify webhook audit log + idempotency |

#### State Machine
PENDING_ASSIGNMENT → ASSIGNED → AT_STORE → IN_TRANSIT → ARRIVED → DELIVERED (terminal)
PENDING_ASSIGNMENT/ASSIGNED/AT_STORE → CANCELLED (terminal)
IN_TRANSIT → FAILED_DELIVERY → PENDING_ASSIGNMENT (retry) or CANCELLED
FAILED_DELIVERY → CANCELLED

#### Testing
51/51 backend tests passed (test_delivery_service_iteration16.py)

---

### Iteration 9 — Rider Backend Platform (2026-07-23)

#### What was built

**New backend modules (8 files):**
- `backend/rider/__init__.py`
- `backend/rider/db.py` — riders + rider_refresh_tokens collections, indexes
- `backend/rider/schemas.py` — RiderStatus/VehicleType enums, RiderOut, RiderAdminOut, RiderSessionOut, RiderCreateIn, RiderUpdateIn, DeliveryJobBriefOut, etc.
- `backend/rider/security.py` — bcrypt password hashing, Rider JWT (role="rider"), refresh token helpers
- `backend/rider/service.py` — full rider lifecycle: auth, CRUD, status, session, history, live stats
- `backend/rider/router.py` — /api/rider/* rider-facing endpoints
- `backend/rider/dependencies.py` — get_current_rider_required (rejects customer tokens via role check)
- `backend/admin/__init__.py` — admin module scaffold
- `backend/admin/rider_router.py` — /api/admin/riders/* admin CRUD endpoints

**Modified files:**
- `backend/server.py` — mounts rider_router + admin_router, adds ensure_rider_indexes to startup
- `backend/.env` — adds RIDER_JWT_ACCESS_TOKEN_EXPIRE_MINUTES=240, RIDER_REFRESH_TOKEN_EXPIRE_DAYS=30
- `backend/delivery/schemas.py` — adds DeliveryJobAssignIn schema
- `backend/delivery/service.py` — adds assign_rider_to_job() function
- `backend/delivery/router.py` — adds POST /api/delivery/jobs/{jobId}/assign endpoint

#### New MongoDB Collections
| Collection | Purpose |
|---|---|
| riders | One document per rider. isDeleted for soft delete. bcrypt passwordHash. |
| rider_refresh_tokens | Opaque refresh tokens stored as SHA-256 hash. Same pattern as auth_refresh_tokens. |

#### Auth Architecture (3-actor foundation)
| Actor | Token | Expiry | Role Claim | Collection |
|---|---|---|---|---|
| Customer (existing) | JWT + opaque refresh | 15min / 30d | none | users + auth_refresh_tokens |
| Rider (new) | JWT + opaque refresh | 4h / 30d | role="rider" | riders + rider_refresh_tokens |
| Admin (future) | JWT + opaque refresh | 1h / 8h | role="admin" | admin_users (future) |

#### Testing: 38/38 tests passed (test_rider_backend_iteration17.py)


### Delivery
- `GET /api/delivery/job?orderId=` — customer views their delivery job (customer JWT required)
- `GET /api/delivery/jobs` — list all jobs (no auth — TODO admin JWT)
- `GET /api/delivery/jobs/{jobId}` — full job detail (no auth — TODO admin JWT)
- `PUT /api/delivery/jobs/{jobId}/status` — state machine update (no auth — TODO admin+rider JWT)
- `POST /api/delivery/jobs/{jobId}/cancel` — cancel job (no auth — TODO admin JWT)
- `GET /api/delivery/stores` — list stores (no auth — TODO admin JWT)

### Webhooks
- `POST /api/webhooks/shopify` — receives orders/paid and orders/cancelled (HMAC verified)

---

### Iteration 10 — Vendor Backend Platform (2026-07-24)

#### What was built
- `backend/vendor/` — full vendor module (auth, order queue, workflow)
- JWT auth: `role="vendor"`, 8h access / 30d refresh
- Vendor order workflow: accept → mark unavailable items → preparing → ready for pickup
- Extended delivery state machine: `WAITING_VENDOR`, `VENDOR_ACCEPTED`, `PREPARING`, `READY_FOR_PICKUP`, `REJECTED`
- Orders now start at `WAITING_VENDOR`; rider assignment gated until `READY_FOR_PICKUP`
- New collections: `vendors`, `vendor_refresh_tokens`

#### Testing: 31/32 tests passed (test_vendor_backend_iteration18.py, 1 skipped)

---

### Iteration 11 — Admin Backend Platform & Security (2026-07-24)

#### What was built
- `backend/admin/` — full admin module (auth, RBAC, audit logs, dashboard, store/rider/vendor management)
- RBAC: `super_admin(4) > admin(3) > operations_manager(2) > support(1)` via `require_min_role()`
- JWT auth: 1h access / 8h refresh
- Audit logging for every significant admin action → `audit_logs` collection
- Seeded default super admin: `admin@nowkart.com` / `Admin2026!` on first startup
- New collections: `admin_users`, `admin_refresh_tokens`, `audit_logs`

#### Testing: 46/46 tests passed (test_admin_backend.py)

---

### Iterations 12–16 — (auto-commit series; minor fixes and test infrastructure)

---

### Railway Production Deployment (2026-08 — commits 91f22bc → 9b270c9)

- Added `Procfile`, `railway.json` (Railpack builder), `nixpacks.toml`, `requirements.production.txt`
- Fixed health-check path: `/api/` (unauthenticated)
- Fixed admin auth contract: refresh returns `{accessToken, refreshToken}`; seeded ops admin
- Added `frontend/.env` with `EXPO_PUBLIC_BACKEND_URL=https://nowkartcustomer-production.up.railway.app`
- **Production URL:** `https://nowkartcustomer-production.up.railway.app`

---

### EAS iOS/Android Build Configuration (commit ac225f8)

- Added `frontend/eas.json` with build profiles: `development`, `simulator`, `preview`, `production`
- All profiles point to Railway production backend URL
- `submit.production.ios` stub ready (Apple credentials TBD)

---

### Iteration 20 — Multi-Vendor Order Orchestration (2026-09-05, commit 3ef9237)

#### Architecture
- Shopify `orders/paid` webhook fans out into **one delivery job per vendor group**
- New `parent_orders` MongoDB collection acts as transaction guard (idempotent via unique `shopifyOrderId` index)
- Vendor mapping: Shopify line-item `vendor` field matched against `vendors.businessName` (case-insensitive exact regex)
- Unmatched vendors recorded in `parent_orders.unmappedGroups` — never silently assigned to a default vendor
- **Legacy mode:** orders with no vendor field continue on the existing single-job path (full backward compatibility)

#### New MongoDB Collection
| Collection | Purpose |
|---|---|
| `parent_orders` | Fan-out record per Shopify order; links to multiple delivery jobs; tracks unmapped groups |

#### Testing: `test_multi_vendor_orchestration.py` present; **no `iteration_20.json` test report yet**

---

### Rider Soft-Delete Restore Endpoint — HEAD e5dc7c7 (2026-09-07)

#### What was built
- `PUT /api/admin/riders/{riderId}/restore` — re-activates a soft-deleted rider without recreating
- Fixes the 409 "A rider with this email already exists" error when admins tried to recreate a deleted rider via POST
- Idempotent: safe to call on a rider that was never deleted
- `restore_rider()` added to `rider/service.py`; requires `admin` role (same RBAC level as delete/suspend)

#### Testing: 6/6 tests passed (test_rider_restore_endpoint.py)

---

## Project Completion
- Customer shopping app scope: ~98%
- Delivery Service backend: Complete (Iteration 8)
- Rider Backend: Complete (Iteration 9)
- Vendor Backend: Complete (Iteration 10)
- Admin Backend: Complete (Iteration 11)
- Multi-vendor orchestration: Complete (Iteration 20)
- Full platform vision (frontend apps, App Store): ~65%

---

## Current MongoDB Collections (full list)

| Collection | Owner module |
|---|---|
| `status_checks` | legacy scaffold (unused) |
| `users` | auth (customer) |
| `auth_refresh_tokens` | auth (customer) |
| `delivery_jobs` | delivery |
| `stores` | delivery |
| `webhook_events` | webhooks |
| `riders` | rider |
| `rider_refresh_tokens` | rider |
| `vendors` | vendor |
| `vendor_refresh_tokens` | vendor |
| `admin_users` | admin |
| `admin_refresh_tokens` | admin |
| `audit_logs` | admin |
| `parent_orders` | delivery (multi-vendor) |

---

## Next Tasks (ordered)

### P0 — Pre-deployment Checklist
- [ ] Set `SHOPIFY_WEBHOOK_SECRET` in Railway environment → register `orders/paid` + `orders/cancelled` webhooks pointing to `https://nowkartcustomer-production.up.railway.app/api/webhooks/shopify`
- [ ] Update default store address: `PUT /api/admin/stores/{id}` with real address
- [ ] Change default admin password: `POST /api/admin/change-password` (current: `admin@nowkart.com` / `Admin2026!`)
- [ ] Harden CORS: replace `allow_origins=["*"]` with explicit allowlist in `server.py`
- [ ] Generate native iOS/Android build via `eas.json` → verify Shopify OAuth login end-to-end on real device
- [ ] Run formal `testing_agent` pass for Iteration 20 multi-vendor orchestration (no `iteration_20.json` yet)

### P1 — Vendor App (separate Expo repo)
Backend APIs: fully ready (`/api/vendor/*`)
- Login, status management (OPEN/CLOSED/BUSY)
- Incoming order queue
- Accept / reject with reason
- Mark unavailable items
- Preparing → Ready for pickup flow

### P2 — Rider App (separate Expo repo)
Backend APIs: fully ready (`/api/rider/*`)
- Login, status toggle (ONLINE/OFFLINE)
- Current job screen
- Navigation deep-link (Google Maps / Apple Maps)
- Delivery actions: at-store → picked-up → arrived → delivered
- Proof of delivery: camera capture
- Failed delivery reporting
- Background GPS (expo-location, expo-task-manager)

### P3 — Admin Dashboard (React + Vite web app, separate repo)
Backend APIs: fully ready (`/api/admin/*`)
- Login with RBAC
- Live map (Google Maps JS SDK — rider markers)
- Delivery job management
- Rider / vendor CRUD
- Platform statistics

### P4 — Lock Down Delivery Endpoints
- Add admin JWT to currently-unauthenticated delivery endpoints in `delivery/router.py`

### P5 — Google Maps ETA Module
- `GOOGLE_MAPS_API_KEY` in .env
- Distance Matrix API wrapper + cache
- Populate coordinates on delivery job creation (Geocoding API)

### P6 — Push Notifications
- `devicePushToken` already stored on riders and vendors
- Add `notifications/` dispatch module

### P7 — Redis + WebSocket Live GPS
- Rider location WebSocket publish
- Customer tracking WebSocket subscribe

### P8 — Native Build + App Store
- Verify Shopify OAuth end-to-end (see P0)
- iOS App Store / Google Play submission
