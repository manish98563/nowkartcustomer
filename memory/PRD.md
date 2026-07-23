# NOW KART — LIVING PRD

## Source of Truth
Repository: https://github.com/manish98563/nowkarthandover (main branch)

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

## Project Completion
- Customer shopping app scope: ~98%
- Delivery Service backend: Complete (Iteration 8)
- Full platform vision (Rider App, Admin Dashboard, Payments, App Store): ~65%

---

## Next Tasks (ordered)

### P0 — Rider App (Iteration 9) — Separate Repository
- POST /api/rider/auth/login (email + password → rider JWT)
- POST /api/rider/auth/refresh, /logout
- GET /api/rider/job/current
- POST /api/rider/location (GPS batch)
- POST /api/rider/job/{id}/at-store, /picked-up, /arrived, /delivered, /failed
- PUT /api/rider/status (online/offline toggle)

### P1 — Admin Dashboard API (Iteration 10) — Separate Repository
- POST /api/admin/auth/login (admin JWT with RBAC)
- GET /api/admin/jobs, /api/admin/riders
- POST /api/admin/jobs/{id}/assign, /reassign
- POST /api/admin/riders (create rider account)
- All existing delivery endpoints locked down to admin JWT

### P2 — Lock Down Delivery Endpoints
- Add admin JWT to currently-unauthenticated delivery endpoints
- Add store-scoped RBAC

### P3 — Google Maps ETA Module
- GOOGLE_MAPS_API_KEY in .env
- shared/eta_service.py — Distance Matrix API wrapper + cache
- populate coordinates on delivery job creation (Geocoding API)
- ETA refresh every 2 min during IN_TRANSIT

### P4 — Push Notifications
- notifications/ module
- Expo Push / FCM integration

### P5 — Redis + WebSocket Live GPS
- rider/location WebSocket publish
- customer/tracking WebSocket subscribe

### P6 — Native Build + App Store
- Emergent Publish → iOS + Android builds
- Verify Shopify OAuth end-to-end
