# NOW KART — CONTEXT

> **AI/Developer onboarding in under 5 minutes.**
> Read this first. Follow the reading order at the bottom for deeper context.

---

## Project Summary

Now Kart is a **headless Shopify quick-commerce platform** consisting of:
- A **Customer App** (Expo/React Native, this repo) — live and production-ready
- A **FastAPI backend** (this repo) — fully built, serving all 4 future apps
- 3 frontend apps **not yet built** (Rider App, Vendor App, Admin Dashboard — separate repos)

Shopify handles: catalog, inventory, pricing, orders, payments, customer identity.
Now Kart handles: delivery operations, vendor coordination, rider dispatch, admin management.

---

## Project Snapshot

| Module | Status | Endpoints |
|---|---|---|
| Customer App UI | ✅ Complete | — |
| `shopify_integration` | ✅ Complete | `/api/shopify/*` (12 endpoints) |
| `auth` (customer) | ✅ Complete | `/api/auth/*` (10 endpoints) |
| `tracking` | ✅ Complete | `/api/tracking/*` (1 endpoint) |
| `delivery` | ✅ Complete | `/api/delivery/*` + webhooks |
| `webhooks` | ✅ Complete | `/api/webhooks/shopify` |
| `rider` | ✅ Complete | `/api/rider/*` (9 endpoints) |
| `vendor` | ✅ Complete | `/api/vendor/*` (15 endpoints) |
| `admin` | ✅ Complete | `/api/admin/*` (27+ endpoints) |
| Rider App | 🔲 Not built | (separate Expo repo) |
| Vendor App | 🔲 Not built | (separate Expo repo) |
| Admin Dashboard | 🔲 Not built | (separate React/Vite repo) |

---

## Architecture Overview

```
Customer App ──┐
Rider App ─────┤  HTTPS  →  NGINX  →  FastAPI :8001  →  MongoDB
Vendor App ────┤                               ↕
Admin Dashboard┘                          Shopify APIs
                                    (Storefront + Customer Account)
                                         ↑
                                   Shopify Webhooks
```

All apps share one FastAPI backend. Role-based JWT isolates each actor.
→ Full diagrams: [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md)

---

## Authentication Overview

| Actor | How they log in | JWT role claim | Token duration |
|---|---|---|---|
| Customer | Shopify OAuth2 + PKCE (passwordless) | *(none)* | 15min / 30d |
| Rider | email + password (bcrypt) | `role="rider"` | 4h / 30d |
| Vendor | email + password (bcrypt) | `role="vendor"` | 8h / 30d |
| Admin | email + password (bcrypt) | `role="super_admin"` etc. | 1h / 8h |

All actors share one `JWT_SECRET_KEY`. Role claim enforces isolation.
Admin RBAC: `super_admin(4) > admin(3) > operations_manager(2) > support(1)`

---

## Current Development Phase

**Phase 2 — Logistics Platform** (Iterations 8–11 complete)

Backend is fully built and tested. The immediate next objective is building the three frontend apps that consume the existing APIs, starting with the **Vendor App**.

Recommended order: Vendor App → Rider App → Admin Dashboard → GPS/Tracking → Push Notifications

---

## Repository Rules (non-negotiable)

| Rule | Why |
|---|---|
| All backend routes must start with `/api` | Kubernetes NGINX routing |
| Shopify GIDs in URLs → `?id=encodeURIComponent(gid)` | NGINX double-decodes `%2F` in path segments |
| Never call `expo-secure-store` directly in frontend | Zero web support — use `src/utils/storage/` |
| Never store product data in MongoDB | Shopify is the catalog source of truth |
| Never return Shopify tokens to the client | BFF pattern — client holds only Now Kart JWT |
| `yarn expo install` for JS packages, `pip install` + `pip freeze` for Python | Maintain SDK compatibility |

---

## Things That Must Never Change

- `frontend/metro.config.js` — NGINX proxy config
- `frontend/.env` `EXPO_PACKAGER_*` vars — preview URL generation
- `backend/.env` `MONGO_URL` — pre-configured MongoDB connection
- Customer auth module (`auth/`) — leave unchanged; extend only
- Product card design (square images, 2-line titles) — locked design decision
- Delivery state machine constants — all in `delivery/service.py`, all four dicts must stay consistent

---

## Reading Order

For quick context (5 min):
1. **This file** — done ✓

For architecture understanding (15 min):
2. [`PROJECT_PLAYBOOK.md`](PROJECT_PLAYBOOK.md) — vision and business model
3. [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) — diagrams and module map
4. [`API_GUIDE.md`](API_GUIDE.md) — endpoint reference

For contributing:
5. [`AI_PLAYBOOK.md`](AI_PLAYBOOK.md) — rules for AI assistants
6. [`DEVELOPER_RULES.md`](DEVELOPER_RULES.md) — engineering standards

For project status:
7. [`PROJECT_HANDOVER.md`](PROJECT_HANDOVER.md) — what's built, what's not, limitations
8. [`BUSINESS_WORKFLOW.md`](BUSINESS_WORKFLOW.md) — delivery state machine
