# NOW KART — CHANGELOG

> One section per completed iteration. Brief summaries only.
> Full details in commit history and test reports.

---

## Iteration 11 — Admin Backend Platform & Security
**Date:** 2026-07-24

- Implemented complete Admin module (`admin/`) with JWT auth (1h access, 8h refresh)
- RBAC: `super_admin > admin > operations_manager > support` via role hierarchy
- Secured all `/api/admin/riders/*` and `/api/admin/vendors/*` endpoints with admin JWT + audit logging
- New endpoints: auth, admin CRUD, dashboard stats, health check, store management, delivery overrides
- Audit logging: every significant admin action written to `audit_logs` collection
- Seeded default super admin: `admin@nowkart.com` on first startup
- New collections: `admin_users`, `admin_refresh_tokens`, `audit_logs`
- **Tests:** 46/46 pass

---

## Iteration 10 — Vendor Backend Platform
**Date:** 2026-07-24

- Implemented complete Vendor module (`vendor/`) with JWT auth (8h access, 30d refresh, `role="vendor"`)
- Vendor order workflow: accept → mark unavailable items → preparing → ready for pickup
- Extended delivery state machine: added `WAITING_VENDOR`, `VENDOR_ACCEPTED`, `PREPARING`, `READY_FOR_PICKUP`, `REJECTED`
- Orders now start at `WAITING_VENDOR` (previously `PENDING_ASSIGNMENT`)
- Rider assignment gated: only allowed from `READY_FOR_PICKUP` or `PENDING_ASSIGNMENT`
- Vendor auto-linked to delivery job at creation via store lookup
- New collections: `vendors`, `vendor_refresh_tokens`
- **Tests:** 31/32 pass (1 skipped — no Shopify customer credentials)

---

## Iteration 9 — Rider Backend Platform
**Date:** 2026-07-23

- Implemented complete Rider module (`rider/`) with JWT auth (4h access, 30d refresh, `role="rider"`)
- Rider CRUD: create, activate, suspend, soft delete
- Token isolation: rider tokens rejected on customer/vendor/admin endpoints (role check)
- Suspension immediately revokes all rider refresh tokens
- Live stats computed from `delivery_jobs` via MongoDB aggregation
- New collections: `riders`, `rider_refresh_tokens`
- Added `assign_rider_to_job()` to delivery service (transitions `PENDING_ASSIGNMENT` → `ASSIGNED`)
- **Tests:** 38/38 pass

---

## Iteration 8 — Delivery Service Backend
**Date:** 2026-07-22

- Implemented delivery state machine: `PENDING_ASSIGNMENT → ASSIGNED → AT_STORE → IN_TRANSIT → ARRIVED → DELIVERED`
- Shopify webhook ingestion: `orders/paid` creates delivery job, `orders/cancelled` cancels it
- Idempotency: `X-Shopify-Webhook-Id` unique index prevents duplicate processing
- `IN_TRANSIT` cancellation blocked: adds alert event, requires admin intervention
- Default store auto-seeded on startup
- New collections: `delivery_jobs`, `stores`, `webhook_events`
- **Tests:** 51/51 pass

---

## Iteration 7 — Live Order Tracking
**Date:** 2026-07-21

- New `backend/tracking/` module: derives tracking stages from Shopify fulfillment data
- `GET /api/tracking/order?id=` (query param, NGINX-safe)
- Customer App: `app/order/track.tsx` — 30s AppState-aware auto-refresh, pulsing live dot
- Rider App extension points documented (`riderName`, `riderLocation`, `riderEta`)
- **Tests:** 12/12 pass (backend only)

---

## Iteration 6 — Order Management
**Date:** 2026-07-21

- `app/(tabs)/orders.tsx`: order list with All/Active/Completed/Cancelled filters, search, thumbnails
- `app/order/detail.tsx`: timeline, line items, price breakdown, reorder per-item and all
- Backend: `GET /api/auth/orders?id=` endpoint + `ORDER_DETAIL_QUERY`
- Reorder: Storefront product search to re-add items to cart

---

## Iteration 5 — Checkout Completion
**Date:** 2026-07-21

- `app/checkout/address.tsx`: order review, address selection, delivery instructions, grand total
- `app/checkout/webview.tsx`: Shopify hosted checkout via react-native-webview
- `app/checkout/confirmation.tsx`: order confirmed, ETA, items, CTAs
- Delivery address pre-populated via `deliveryAddressPreferences` in `cartBuyerIdentityUpdate`
- `app/(tabs)/index.tsx`: `DeliverySelector` wired to AsyncStorage + `/addresses?select=1` picker

---

## Iteration 4 — Customer Auth & Checkout Foundation
**Date:** 2026-07-21

- Shopify Customer Account API OAuth2 + PKCE (passwordless)
- Backend: `backend/auth/` module — authorize-url, token-exchange, refresh, logout, me, addresses
- Session: Now Kart JWT (15min) + rotating opaque refresh token (30d)
- Shopify tokens encrypted at rest with Fernet
- Wishlist (local, AsyncStorage), address CRUD, checkout prep foundation
- `countryCode` → `territoryCode` fix (Shopify API 2026-07 breaking change)

---

## Iterations 1–3 — Customer App Foundation
**Date:** 2026-07-21

- Expo SDK 54 + React Native + expo-router project setup
- Live Shopify Storefront API: catalog, collections (CATEGORY_GROUPS config), search, product detail
- Guest cart backed by Shopify Cart API (persisted Cart ID in AsyncStorage)
- Full design system: dark theme, violet accent, product cards, category groups
- Square product images, 2-line card titles (locked design decisions)
- `AnimatedPressable`, skeleton shimmer, `useAsyncData` hook, `src/utils/storage/` abstraction
