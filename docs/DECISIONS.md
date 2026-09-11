# NOW KART — ARCHITECTURE DECISION RECORDS

> Decisions are listed in the order they were made.
> Status: **Accepted** = in production. **Superseded** = replaced by a later ADR.

---

## ADR-001 · Shopify as the Commerce Backend

**Decision:** Use Shopify as the single source of truth for products, inventory, pricing, orders, and payments. Never duplicate this data in MongoDB.

**Reason:** The merchant already runs Shopify. Shopify handles the hard problems (PCI compliance, inventory, pricing rules, order financials). Now Kart provides the operational layer on top — not a replacement.

**Alternatives considered:** Custom product catalog in MongoDB; WooCommerce; custom payments.

**Status:** Accepted

---

## ADR-002 · FastAPI Backend-For-Frontend (BFF) Pattern

**Decision:** All Shopify API communication happens only in the FastAPI backend. No mobile client ever holds a Shopify token or calls Shopify directly.

**Reason:** Shopify Storefront tokens and Customer Account OAuth clients must never be exposed client-side. The backend mediates all Shopify calls and issues its own short-lived session tokens.

**Alternatives considered:** Client-side Shopify SDK; Shopify Hydrogen.

**Status:** Accepted

---

## ADR-003 · MongoDB for Operations Data Only

**Decision:** MongoDB stores user sessions, delivery jobs, riders, vendors, admins, and audit logs. It never stores product data, cart contents, or Shopify order financials.

**Reason:** Operations data (delivery jobs, rider GPS, vendor assignments) has no natural home in Shopify. MongoDB's flexible schema handles the operational complexity without fighting the Shopify data model.

**Alternatives considered:** PostgreSQL; Supabase; DynamoDB.

**Status:** Accepted

---

## ADR-004 · Four Separate Frontend Applications

**Decision:** Customer App, Rider App, Vendor App, and Admin Dashboard are four separate projects. Each is a standalone repo consuming the shared FastAPI backend.

**Reason:** Different release cadences, different permissions (background GPS for riders, camera, etc.), different UX paradigms (admin = web desktop, others = mobile). Coupling them would create a monorepo maintenance burden.

**Alternatives considered:** Single monorepo with role-based routing; shared codebase with conditional screens.

**Status:** Accepted — Customer App built. Rider/Vendor/Admin are next.

---

## ADR-005 · Admin Dashboard as a Web App (not mobile)

**Decision:** Admin Dashboard is a React + Vite web SPA, not an Expo app.

**Reason:** Admins work at desks. Google Maps JavaScript SDK for live rider maps is web-only. Complex data tables, forms, and reports are significantly better on desktop than mobile.

**Alternatives considered:** Expo app with role-based admin tab; React Native Web.

**Status:** Accepted

---

## ADR-006 · Shopify Customer Account API (OAuth2 + PKCE) for Authentication

**Decision:** Use Shopify's Customer Account API (OAuth2 + PKCE, passwordless) — not the deprecated Storefront `customerAccessTokenCreate` mutation.

**Reason:** Customer Account API is Shopify's current recommendation for headless apps. It is passwordless (reducing credential risk), PKCE-based (RFC 8252 compliant), and gives access to order history and addresses via the Customer Account GraphQL API.

**Alternatives considered:** Legacy Storefront customer auth; custom email/password auth for customers.

**Status:** Accepted

---

## ADR-007 · Manual Inventory Management for MVP

**Decision:** Vendors manually mark items as unavailable in the Vendor App. No automated stock synchronisation with Shopify inventory.

**Reason:** Shopify's `quantityAvailable` field is unreliable in the dev store (all variants show 0 with "continue selling" enabled). Building real inventory sync requires POS integration, barcode scanning, and Shopify webhook plumbing — out of scope for MVP.

**Alternatives considered:** Real-time Shopify inventory webhooks; barcode scanning at pickup.

**Status:** Accepted for MVP — inventory sync is on the long-term roadmap.

---

## ADR-008 · Shared FastAPI Backend (Modular Monolith)

**Decision:** All four apps share one FastAPI backend, structured as a modular monolith (`shopify_integration/`, `auth/`, `delivery/`, `rider/`, `vendor/`, `admin/`, `webhooks/`).

**Reason:** Microservices add network latency, distributed transactions, and ops overhead that is not justified at this stage. Module boundaries enforce the same separation; a module can be extracted into a separate service when load demands it.

**Alternatives considered:** Separate FastAPI microservices per app; GraphQL gateway.

**Status:** Accepted — revisit at 10K+ orders/day

---

## ADR-009 · React Native + Expo (not Flutter)

**Decision:** Customer App (and future Rider/Vendor apps) are built with Expo SDK 54 + React Native, not Flutter.

**Reason:** Flutter CLI was unavailable in the development environment at the time this decision was made. User explicitly approved React Native. The Emergent platform's build/preview pipeline is optimised for Expo.

**Alternatives considered:** Flutter; React Native CLI (without Expo).

**Status:** Accepted — not revisitable without environment change and explicit user approval.

---

## ADR-010 · Role-Based Access Control for Admin

**Decision:** Admin JWT contains the specific role (`super_admin`, `admin`, `operations_manager`, `support`) with a numeric hierarchy for permission checks.

**Reason:** A flat "admin" role with no differentiation would require code changes every time a new permission scope is needed. The hierarchy (`super_admin=4 > admin=3 > operations_manager=2 > support=1`) allows `require_min_role()` to express any access level in one line.

**Alternatives considered:** Permission flags (boolean per capability); flat admin role.

**Status:** Accepted

---

## ADR-011 · Vendor-First Delivery State Machine

**Decision:** New orders start at `WAITING_VENDOR` (not `PENDING_ASSIGNMENT`). Rider assignment is blocked until `READY_FOR_PICKUP`. Vendors must explicitly accept → prepare → ready before a rider can be assigned.

**Reason:** Without vendor confirmation, a rider could arrive at a store that hasn't acknowledged the order or doesn't have the items ready — wasting time and degrading the experience. The vendor gate is non-negotiable for operational reliability.

**Alternatives considered:** Auto-accept all orders; skip vendor step for known items.

**Status:** Accepted

---

## ADR-012 · Backend-First Development

**Decision:** Build all backend APIs (Iterations 8–11) before building any Rider App, Vendor App, or Admin Dashboard frontend.

**Reason:** Frontend apps depend on stable APIs. Building the backend first allows all three frontends to be built in parallel against a complete, tested API surface — reducing rework and design-time uncertainty.

**Alternatives considered:** Frontend-first; parallel development.

**Status:** Accepted — backend phase complete, frontend phase begins next.

---

## ADR-013 · Local Wishlist (Client-Side Only)

**Decision:** Wishlist is stored in `AsyncStorage` on the device and never synced to the backend. Context design includes a documented forward-compatibility seam for future backend sync.

**Reason:** Guest users should have a wishlist without requiring a sign-in. The implementation is deliberately simple and forward-compatible — adding backend sync is a one-function change in `WishlistContext`.

**Alternatives considered:** Backend-synced wishlist (requires login); Shopify's native save-for-later.

**Status:** Accepted for MVP — backend sync is a planned future feature.

---

## ADR-014 · `src/utils/storage/` Abstraction for Secure Storage

**Decision:** All frontend storage operations (secure and general) must go through `src/utils/storage/` — never call `expo-secure-store` or `AsyncStorage` directly.

**Reason:** `expo-secure-store` has zero web support. Calling it directly crashes the web preview entirely (discovered as Bug 4 in production). The abstraction provides a native/web split (`.ts` vs `.web.ts`) transparent to all callers.

**Alternatives considered:** Platform.OS checks inline; separate storage utils per platform.

**Status:** Accepted — violation causes white screen on web.

---

## ADR-015 · Multi-Vendor Order Orchestration via Fan-Out

**Decision:** When a Shopify `orders/paid` webhook fires, create one delivery job per distinct vendor group found in the order's line items, linked to a single `parent_orders` record. Unmatched vendors are recorded in `parent_orders.unmappedGroups` and never silently assigned to a default vendor.

**Reason:** A single Shopify order can contain items from multiple vendor stores. Assigning the whole order to one delivery job would require a single rider to service multiple stores — operationally wrong. Fan-out gives each vendor their own independent state machine and rider assignment.

**Alternatives considered:** Single delivery job with multiple vendor stops; split orders client-side before checkout.

**Backward compatibility:** Orders with no `vendor` field in any line item continue on the existing single-job path (legacy mode, fully regression-tested).

**Implementation:** `backend/delivery/service.py::orchestrate_multi_vendor_order()` + `parent_orders` MongoDB collection with unique index on `shopifyOrderId` for idempotency.

**Status:** Accepted — Iteration 20 (commit 3ef9237).

---

## ADR-016 · Railway as Production Deployment Platform

**Decision:** Deploy the FastAPI backend to Railway using the Railpack builder. Production URL: `https://nowkartcustomer-production.up.railway.app`. A separate `backend/requirements.production.txt` contains only the slim set of dependencies needed for production (not the full Emergent dev environment freeze).

**Reason:** Railway provides a straightforward Git-push deployment with Nixpacks/Railpack auto-detection, built-in health-check routing, and environment variable management — suitable for a FastAPI + Python 3.11 service without additional infrastructure configuration.

**Alternatives considered:** Emergent built-in hosting; Render; Fly.io; Heroku.

**Key files:** `Procfile`, `railway.json`, `nixpacks.toml`, `requirements.production.txt`, `runtime.txt` (Python 3.11).

**Health-check:** `GET /api/` (unauthenticated root route).

**Status:** Accepted — deployed (commits 91f22bc through 9b270c9).

---

## ADR-017 · EAS (Expo Application Services) for Native iOS/Android Builds

**Decision:** Use EAS Build (via `frontend/eas.json`) for generating native iOS and Android builds. All EAS build profiles point to the Railway production backend URL. The `eas.json` approach supplements the Emergent platform's Publish button — developers may use either path.

**Reason:** `eas.json` configuration is required for EAS CLI-based builds (used by CI/CD or direct developer workflows) and provides explicit control over build profiles and environment variable injection. The production backend URL is baked into the build via `env.EXPO_PUBLIC_BACKEND_URL` in each profile.

**Alternatives considered:** Emergent Publish button only; custom Fastlane pipeline.

**iOS submit stub:** `eas.json` includes a `submit.production.ios` section with placeholder Apple credentials (`REPLACE_WITH_*`) — fill in before first App Store submission.

**Status:** Accepted — commit ac225f8.

---

## ADR-018 · Rider Soft-Delete Restore Endpoint

**Decision:** Add `PUT /api/admin/riders/{riderId}/restore` rather than requiring admins to delete and recreate a rider. The restore endpoint sets `isDeleted=False`, `isActive=True`, `deletedAt=None` while preserving all other fields (including `passwordHash`).

**Reason:** The existing soft-delete pattern (`isDeleted: true`) combined with a unique email index caused a 409 "email already exists" error when an admin tried to recreate a deleted rider. A restore endpoint is the idiomatic fix — it is also idempotent (safe to call on a rider that was never deleted) and preserves the rider's historical data.

**Alternatives considered:** Hard-delete (destroys history); remove unique email constraint; allow duplicate emails for deleted riders.

**RBAC:** Requires `admin` role (same level as `delete_rider` and `suspend_rider`).

**Status:** Accepted — HEAD e5dc7c7.
