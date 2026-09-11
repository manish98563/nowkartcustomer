# Now Kart

**Quick-commerce grocery delivery platform** · Headless Shopify + Custom Operations Layer

---

## Status

| Layer | Status |
|---|---|
| Customer App (Expo/React Native) | ✅ Production-ready |
| Delivery Service Backend | ✅ Complete |
| Rider Backend | ✅ Complete (38/38 tests) |
| Vendor Backend | ✅ Complete (31/32 tests) |
| Admin Backend + RBAC | ✅ Complete (46/46 tests) |
| Multi-vendor orchestration | ✅ Complete (Iteration 20) |
| Rider restore endpoint | ✅ Complete (HEAD e5dc7c7) |
| Railway production deployment | ✅ Live — `nowkartcustomer-production.up.railway.app` |
| iOS/Android build config (eas.json) | ✅ Configured |
| Rider App | 🔲 Not started (separate Expo repo, backend ready) |
| Vendor App | 🔲 Not started (separate Expo repo, backend ready) |
| Admin Dashboard (web) | 🔲 Not started (separate React+Vite repo, backend ready) |

---

## Applications

| App | Tech | Backend Endpoints |
|---|---|---|
| **Customer App** (this repo) | Expo SDK 54, React Native | `/api/shopify/*` `/api/auth/*` `/api/tracking/*` `/api/delivery/*` |
| **Rider App** (separate repo) | Expo SDK 54, React Native | `/api/rider/*` |
| **Vendor App** (separate repo) | Expo SDK 54, React Native | `/api/vendor/*` |
| **Admin Dashboard** (separate repo) | React + Vite (web) | `/api/admin/*` |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Customer App | Expo SDK 54 · React Native 0.81.5 · TypeScript · expo-router |
| Backend | FastAPI 0.110.1 · Python 3.11 · Motor (async) · PyJWT · passlib[bcrypt] |
| Database | MongoDB (operations data only — never product data) |
| Commerce | Shopify Storefront API + Customer Account API (OAuth2 + PKCE) |
| Process | Supervisor · NGINX · port 8001 (backend) / 3000 (expo) |
| Production hosting | Railway (Railpack builder) · `nowkartcustomer-production.up.railway.app` |
| Native builds | EAS (Expo Application Services) · `frontend/eas.json` |

---

## Repository Structure

```
/
├── README.md                 ← you are here
├── backend/                  FastAPI backend (all 4 apps share this)
│   ├── server.py             Entry point — mounts 15 routers
│   ├── auth/                 Customer OAuth + sessions
│   ├── shopify_integration/  Catalog, cart, checkout
│   ├── tracking/             Order tracking
│   ├── delivery/             Delivery job lifecycle + multi-vendor orchestration
│   ├── rider/                Rider auth + operations
│   ├── vendor/               Vendor auth + order queue
│   ├── admin/                Admin auth + RBAC + management
│   └── webhooks/             Shopify event ingestion
├── frontend/                 Customer App (Expo)
│   ├── app/                  expo-router screens
│   ├── src/                  features/ · repositories/ · theme/ · utils/
│   └── eas.json              EAS build profiles (dev/simulator/preview/production)
├── Procfile / railway.json / nixpacks.toml  Railway production deployment
├── requirements.txt          Dev dependencies
├── backend/requirements.production.txt  Slim production deps (Railway)
├── docs/                     Project documentation ← start here
└── memory/                   AI session memory (PRD, credentials)
```

---

## Quick Start

```bash
# Backend runs on port 8001 (managed by supervisor)
supervisorctl restart backend

# Frontend served by Expo Metro on port 3000
supervisorctl restart expo

# Default admin credentials (seeded on first startup)
# admin@nowkart.com / Admin2026!

# Backend API base
curl http://localhost:8001/api/shopify/home
```

---

## Documentation

| Document | Purpose |
|---|---|
| [`docs/CONTEXT.md`](docs/CONTEXT.md) | **Start here** — 5-minute AI/developer onboarding |
| [`docs/PROJECT_PLAYBOOK.md`](docs/PROJECT_PLAYBOOK.md) | Vision, business model, tech stack |
| [`docs/SYSTEM_ARCHITECTURE.md`](docs/SYSTEM_ARCHITECTURE.md) | Architecture diagrams, module map, DB schema |
| [`docs/BUSINESS_WORKFLOW.md`](docs/BUSINESS_WORKFLOW.md) | Order lifecycle, delivery state machine |
| [`docs/API_GUIDE.md`](docs/API_GUIDE.md) | All 80+ API endpoints |
| [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) | Colors, typography, components |
| [`docs/PROJECT_HANDOVER.md`](docs/PROJECT_HANDOVER.md) | Current status, limitations, build order |
| [`docs/AI_PLAYBOOK.md`](docs/AI_PLAYBOOK.md) | Rules for AI assistants |
| [`docs/DEVELOPER_RULES.md`](docs/DEVELOPER_RULES.md) | Engineering standards |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Architecture Decision Records |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Completed / planned / future |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | Per-iteration change log |

---

## Roadmap

**Backend complete** (all 8 modules, 170+ tests). **Next:** Build frontend apps that consume the existing APIs.

Recommended order: Vendor App → Rider App → Admin Dashboard → Live GPS → Push Notifications

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full plan.

---

## Notes

- This repository contains the **Customer App + shared FastAPI backend only**
- Rider App, Vendor App, and Admin Dashboard are **separate repositories** — all their backend APIs are built and tested in this repo
- All backend APIs are built and tested — mobile apps consume them via the documented endpoints
- Shopify is the system of record for products, inventory, and payments — never duplicated here
- Production backend: `https://nowkartcustomer-production.up.railway.app`
