# NowKart — Project Memory

## Source of Truth
Repository: https://github.com/manish98563/nowkart (main branch)

## Iterations Completed

### Iterations 1–6 (see previous entries)
UI, Shopify Storefront, Auth, Checkout, Address Management, Order Management — all code-complete.

### Iteration 7 — Live Order Tracking & Delivery Foundation (2026-07-21)

#### What was built

**Backend (4 new files):**
- `backend/tracking/__init__.py` — new module
- `backend/tracking/schemas.py` — `TrackingStageOut`, `TrackingStatusOut` with architecture prep comments (riderName, riderLocation, riderEta fields commented out, ready to uncomment for Rider App)
- `backend/tracking/service.py` — `get_tracking_status(user, order_id)` derives tracking from Shopify fulfillment data; `_build_stages()` maps financialStatus + fulfillmentStatus + fulfillments → timeline stages
- `backend/tracking/router.py` — `GET /api/tracking/order?id=<encoded_gid>` (query param, NGINX-safe)
- `backend/server.py` modified — mounts `tracking_router` at `/api`

**Frontend (6 new/modified files):**
- `src/types/tracking.ts` — `TrackingStage`, `TrackingStatus` with Rider App extension points commented
- `src/types/index.ts` — exports new types
- `src/repositories/trackingRepository.ts` — `getTrackingStatus(orderId)`
- `src/repositories/index.ts` — exports trackingRepository
- `app/order/track.tsx` *(new)* — dedicated tracking screen:
  - `AppState`-aware auto-refresh every 30s (stops in background, stops when !isActive)
  - `useFocusEffect` cleanup prevents background polling when screen is unfocused
  - Live pulsing dot badge when `tracking.isActive = true`
  - Hero status card with current stage label + ETA message (honest Shopify data only)
  - Countdown timer showing "Refreshing in Xs"
  - Full timeline with timestamps from Shopify fulfillment data
  - Delivery address card
  - Compact items list (from TrackingStatus.items — one API call covers all)
  - Pull-to-refresh
  - Auth guard, loading, error states
- `app/order/detail.tsx` modified — "Track Order" button for active orders (navigates to `/order/track`)
- `app/(tabs)/orders.tsx` modified — "Track Order" pill button on active order cards
- `app/_layout.tsx` modified — `Stack.Screen` for `order/track`

#### Architecture prep for Rider App
The `TrackingStatusOut` model and `TrackingStatus` TypeScript interface have commented-out fields that will be added when the Rider App ships:
- `riderName`, `riderPhone` — Rider identification
- `riderLocation: {lat, lng, updatedAt}` — GPS coordinates
- `riderEta` — Rider's GPS-computed ETA
- `trackingUrl` — External courier tracking
These can be added to `TrackingStatusOut` without breaking existing consumers.
The tracking screen will show a MapView when `riderLocation` becomes available.

#### Stage derivation logic (Shopify data only — no fabrication)
| Stage | Condition |
|---|---|
| placed | Always done (order exists) |
| confirmed | financialStatus in PAID/AUTHORIZED/PARTIALLY_PAID |
| preparing | fulfillments.length > 0 OR fulfillmentStatus = PARTIAL |
| out_for_delivery | has_fulfillment AND NOT fulfilled (future: Rider App status) |
| delivered | fulfillmentStatus = FULFILLED |
| cancelled | cancelledAt is set |

## API Routes (19 total)
NEW: `GET /api/tracking/order?id=<encoded_gid>`

## Project Completion
- Customer shopping app scope: ~98%
- Full vision (Rider, Merchant, Admin, Payments): ~60%

## Next Tasks (P0 → P4)
- P0: Native build → Publish → iOS/Android → verify real Shopify login + payment + orders
- P1: Auto-set default Shopify address as delivery address on login
- P2: Shopify Checkout Sheet Kit (Apple Pay / Google Pay)
- P3: Rider App (uses tracking module extension points)
- P4: Merchant Dashboard, Admin Dashboard, push notifications
