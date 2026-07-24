# NOW KART — PROJECT PLAYBOOK

> **Quick-commerce grocery delivery platform** · Headless Shopify + Custom Operations Layer

---

## Vision

Deliver a fast, native-feeling grocery shopping experience for merchants already running Shopify, while providing a fully custom operations layer for vendors, riders, and administrators — without replacing Shopify as the financial and catalog system of record.

---

## Business Model

| Layer | Owner | Responsibility |
|---|---|---|
| **Catalog, Inventory, Pricing** | Shopify | Single source of truth — never duplicated |
| **Orders & Payments** | Shopify | All financial transactions |
| **Customer Identity** | Shopify Customer Account API | OAuth2 + PKCE, passwordless |
| **Delivery Operations** | Now Kart FastAPI Backend | Job lifecycle, vendor/rider coordination |
| **Customer Experience** | Now Kart Customer App | React Native, branded UI |

---

## Four Applications

| App | Status | Tech | Consumes |
|---|---|---|---|
| **Customer App** | ✅ Production-ready (Iter 1–7) | Expo SDK 54, React Native | `/api/shopify/*` `/api/auth/*` `/api/tracking/*` `/api/delivery/*` |
| **Rider App** | 🔲 Not built | Expo (separate repo) | `/api/rider/*` |
| **Vendor App** | 🔲 Not built | Expo (separate repo) | `/api/vendor/*` |
| **Admin Dashboard** | 🔲 Not built | React + Vite (web) | `/api/admin/*` |

---

## Technology Stack

### Frontend (Customer App — this repo)
- Expo SDK 54 · React Native 0.81.5 · React 19.1.0
- TypeScript · expo-router 6 (file-based routing)
- react-native-reanimated 4 · expo-secure-store · AsyncStorage
- StyleSheet.create only — no CSS, no NativeWind

### Backend (this repo)
- FastAPI 0.110.1 · Python 3.11 · Motor (async MongoDB)
- PyJWT (HS256) · passlib[bcrypt] · cryptography (Fernet)
- Supervisor-managed, port 8001

### Data
- MongoDB — user/session/operations data only (never product data)
- Shopify — catalog, inventory, cart, orders, customer identity

---

## Documentation Map

| File | Purpose |
|---|---|
| [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) | System diagrams, module map, database schema |
| [`BUSINESS_WORKFLOW.md`](BUSINESS_WORKFLOW.md) | Order lifecycle, delivery state machine |
| [`API_GUIDE.md`](API_GUIDE.md) | All endpoints grouped by module |
| [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) | Colors, typography, spacing tokens |
| [`PROJECT_HANDOVER.md`](PROJECT_HANDOVER.md) | Current status, what's built, what's next |
| [`AI_PLAYBOOK.md`](AI_PLAYBOOK.md) | Rules for AI assistants continuing this project |
| [`DEVELOPER_RULES.md`](DEVELOPER_RULES.md) | Engineering standards and conventions |
| [`ROADMAP.md`](ROADMAP.md) | Completed / planned / future milestones |
| [`CHANGELOG.md`](CHANGELOG.md) | Per-iteration change summaries |
