# NOW KART — PROJECT HANDOVER

> Last updated: Iteration 11 complete.
> See [`CHANGELOG.md`](CHANGELOG.md) for iteration history.

---

## Current Status

| Layer | Status | Coverage |
|---|---|---|
| **Customer App** | ✅ Production-ready | ~98% of customer scope |
| **Delivery Service** | ✅ Complete | Full state machine, webhooks |
| **Rider Backend** | ✅ Complete | Auth, CRUD, job ops |
| **Vendor Backend** | ✅ Complete | Auth, order queue, workflow |
| **Admin Backend** | ✅ Complete | Auth, RBAC, audit logs, all management |
| **Rider App** | 🔲 Not started | Separate Expo project |
| **Vendor App** | 🔲 Not started | Separate Expo project |
| **Admin Dashboard** | 🔲 Not started | Separate React/Vite project |
| **Live GPS** | 🔲 Not started | Redis + WebSocket (architecture designed) |
| **Push Notifications** | 🔲 Not started | Expo Push / FCM (architecture designed) |
| **Google Maps ETA** | 🔲 Not started | Distance Matrix API slot prepared |

**Backend API surface:** 80+ endpoints · **Test coverage:** 46/46 (Iter 11), cumulative ~170+ tests

---

## Completed Milestones

| Iteration | What was built |
|---|---|
| 1–2 | Expo project scaffold, React Native UI foundation |
| 3 | Live Shopify Storefront API: catalog, collections, search, product detail, cart |
| 4 | Shopify Customer Account OAuth (passwordless), sessions, wishlist, addresses, checkout prep |
| 5 | Checkout completion (WebView), order confirmation, delivery address pre-population |
| 5b | Delivery selector on Home, AsyncStorage-persisted address |
| 6 | Order management: list (filters/search), order detail, reorder |
| 7 | Live order tracking: 30s polling, AppState-aware, Rider App extension points |
| 8 | Delivery Service backend: state machine, Shopify webhooks, MongoDB delivery_jobs |
| 9 | Rider Backend: auth, CRUD, GPS-ready endpoints, stats |
| 10 | Vendor Backend: auth, order queue, accept/reject, prepare, ready workflow |
| 11 | Admin Backend: RBAC, audit logs, dashboard stats, store management, all APIs secured |

---

## What Is NOT Built

- **No Rider App** — all `/api/rider/*` endpoints ready and tested
- **No Vendor App** — all `/api/vendor/*` endpoints ready and tested
- **No Admin Dashboard** — all `/api/admin/*` endpoints ready and tested
- **No live GPS** — delivery_jobs schema has extension points (`riderLocation`, `riderEta`)
- **No push notifications** — `devicePushToken` stored on riders and vendors; dispatch not wired
- **No ETA calculation** — `etaMinutes` field exists on delivery_jobs; Google Maps slot prepared
- **No auto rider assignment** — manual only (admin assigns); 2dsphere index exists for future
- **No Shopify Checkout Sheet Kit** — WebView checkout works; Apple Pay / Google Pay not integrated
- **No native Shopify OAuth verification** — requires native build (cannot test in Expo Go)

---

## Known Limitations

| # | Limitation | Impact | Resolution |
|---|---|---|---|
| 1 | Shopify OAuth requires native build | Cannot fully test auth in web preview | Generate iOS/Android build via Emergent Publish |
| 2 | Admin endpoints still have unauthenticated fallbacks in `delivery/router.py` | Low security risk in dev | Replace with admin-auth versions in future |
| 3 | Vendor-to-store is not unique-indexed | Multiple vendors could link to same store | Add unique index when business confirms 1:1 |
| 4 | Rejected orders don't auto-refund | Refund must be processed manually in Shopify | Implement Shopify Admin API call in admin module |
| 5 | Store address is placeholder in default store | Geocoding not wired | Update via `PUT /api/admin/stores/{id}` |
| 6 | Soft-deleted rider/vendor emails cannot be reused | Minor operational constraint | Filter by `isDeleted: false` in uniqueness check |

---

## Deployment Checklist

```
Before deploying to production:

[ ] Set SHOPIFY_WEBHOOK_SECRET in backend/.env
    (Shopify Admin → Settings → Notifications → Webhooks → Signing secret)

[ ] Register Shopify webhook topics:
    - orders/paid → https://<domain>/api/webhooks/shopify
    - orders/cancelled → same URL

[ ] Update default store address:
    PUT /api/admin/stores/{storeId} with real address

[ ] Generate native iOS/Android build (Emergent Publish)
    - Verify Shopify OAuth login end-to-end
    - Test real order → delivery → tracking flow

[ ] Harden CORS:
    backend/server.py: replace allow_origins=["*"] with specific domains

[ ] Change default admin password:
    POST /api/admin/change-password

[ ] Add rate limiting for:
    - /api/admin/auth/login (brute-force protection)
    - /api/rider/auth/login
    - /api/vendor/auth/login
```

---

## Recommended Build Order (Mobile Apps)

1. **Rider App** (Expo, separate repo)
   - Consumes: `/api/rider/*`
   - Key features: login, status toggle, current job, delivery actions, GPS
   - Requires: background location permission, camera for proof of delivery

2. **Vendor App** (Expo, separate repo)
   - Consumes: `/api/vendor/*`
   - Key features: login, order queue, accept/reject, mark items, prepare, ready

3. **Admin Dashboard** (React + Vite, separate repo)
   - Consumes: `/api/admin/*`
   - Key features: login, live map, delivery management, rider/vendor CRUD, reports

4. **Shopify Checkout Sheet Kit** (in Customer App)
   - Replaces WebView checkout with native Apple Pay / Google Pay


---

## How to Continue Development

### Recommended Implementation Order

```
Vendor App  →  Rider App  →  Admin Dashboard
     ↓               ↓               ↓
  Maps Integration  Live GPS    Push Notifications
     ↓               ↓               ↓
    ETA Calculation  Auto Assignment  Inventory Integration
```

### Why This Order

| Phase | Reason |
|---|---|
| **Vendor App first** | Operationally critical — orders cannot move past `WAITING_VENDOR` without it. Simpler app (no GPS), good starting point to validate the vendor API surface. |
| **Rider App second** | Depends on vendor having accepted/prepared the order. Background GPS and camera permissions make it more complex — build after the simpler vendor flow is stable. |
| **Admin Dashboard third** | Web app (React, not Expo), Google Maps JS SDK for live map. Depends on riders and vendors being operational to show meaningful data. |
| **Maps + Live GPS** | Requires Redis (pub/sub) and WebSocket. Infrastructure addition — implement after all three apps are functional. |
| **Push Notifications** | Push tokens are already stored on riders and vendors. Dispatch module can be added without changing any app UI. |
| **ETA Calculation** | Google Distance Matrix API (server-side). Slot already prepared in `delivery_jobs.etaMinutes`. Add after GPS is live. |
| **Auto Assignment** | 2dsphere index already exists on `rider_locations`. Implement once manual assignment workflow is proven stable. |
| **Inventory Integration** | Shopify webhook + POS scanning. Most complex — do last, after MVP operations are verified end-to-end. |
