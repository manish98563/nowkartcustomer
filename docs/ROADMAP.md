# NOW KART — ROADMAP

---

## ✅ Completed (Iterations 1–11)

| Milestone | What |
|---|---|
| **Customer App** | Live Shopify catalog, search, cart, product detail, wishlist |
| **Customer Auth** | Shopify Customer Account OAuth2 + PKCE, sessions, addresses |
| **Checkout** | Order review, Shopify WebView checkout, confirmation screen |
| **Order Management** | Order list, order detail, reorder, live tracking (30s polling) |
| **Delivery Service** | State machine, Shopify webhook ingestion, MongoDB collections |
| **Rider Backend** | Auth (JWT), CRUD, status, job ops, stats |
| **Vendor Backend** | Auth (JWT), order queue, accept/reject/prepare/ready workflow |
| **Admin Backend** | Auth (JWT+RBAC), audit logs, dashboard stats, all ops secured |

---

## 🔲 Current Priority — Mobile Applications

### P0 · Pre-deployment
- Register Shopify webhooks + set `SHOPIFY_WEBHOOK_SECRET`
- Generate native iOS/Android build (Emergent Publish)
- Verify Shopify OAuth login end-to-end on real device
- Update default store address in admin
- Change default admin password

### P1 · Rider App (separate Expo repo)
Backend APIs: fully ready (`/api/rider/*`)
- Login, status toggle (ONLINE/OFFLINE)
- Current job screen
- Navigation deep-link (Google Maps / Apple Maps)
- Delivery actions: at-store → picked-up → arrived → delivered
- Proof of delivery: camera capture
- Failed delivery reporting
- Background GPS (expo-location, expo-task-manager)

### P2 · Vendor App (separate Expo repo)
Backend APIs: fully ready (`/api/vendor/*`)
- Login, status management (OPEN/CLOSED/BUSY)
- Incoming order queue
- Accept / reject with reason
- Mark unavailable items
- Preparing → Ready for pickup flow

### P3 · Admin Dashboard (React + Vite web app)
Backend APIs: fully ready (`/api/admin/*`)
- Login with RBAC
- Live map (Google Maps JS SDK — rider markers)
- Delivery job management
- Rider / vendor CRUD
- Platform statistics

---

## 📋 Planned — Backend Extensions

| Feature | Module | Status |
|---|---|---|
| Google Maps ETA | New `shared/eta_service.py` | Slot prepared in delivery_jobs |
| Redis pub/sub (live GPS) | New Redis dependency | Architecture designed |
| WebSocket (rider → customer) | `shared/websocket_manager.py` | Architecture designed |
| Push notifications | New `notifications/` module | Token storage ready |
| Auto rider assignment | `delivery/assignment.py` | 2dsphere index exists |
| Shopify Admin API (refunds) | `admin/` module | Not yet implemented |
| Shopify Checkout Sheet Kit | Customer App | Replaces WebView checkout |

---

## 🔭 Future (after all apps are live)

- Rider earnings / settlement module
- Customer rating of deliveries
- Multi-store zone routing (GeoJSON delivery zones)
- Merchant dashboard (store performance, own orders)
- Push notification templates management
- Production App Store / Play Store submission
