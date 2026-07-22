# NOW KART — MASTER PROJECT HANDOVER

**Document type:** Complete, zero-knowledge-transfer engineering handover.
**Audience:** A brand-new AI engineer or human developer with NO prior access to this project's conversation history.
**Last updated:** Iteration 7 (Live Order Tracking & Delivery Foundation) code is complete and verified. Iterations 5–7 added: checkout completion (Shopify hosted checkout via WebView), order management (full order history + detail), delivery address pre-population, and a tracking module with architecture prep for the future Rider App. **Real end-to-end Shopify Customer Account OAuth login on a native iOS/Android build has NOT been performed or verified** — this boundary applies to all auth-gated features.
**Companion documents:** `PROJECT_MEMORY.md` (long-term memory/philosophy), `DEVELOPER_PLAYBOOK.md` (practical day-to-day guide). All three documents are cross-consistent as of this update; re-verify against the live codebase before trusting any specific claim if substantial time has passed since this line was written.

> Wherever this document states something that was not explicitly confirmed by the user/testing evidence, it is explicitly marked **[ASSUMPTION]**.
> Wherever this document distinguishes implementation maturity, it uses exactly these four labels: **Implemented** (code complete, exercised by at least automated/browser tests), **Implemented — untested boundary** (code complete, but cannot be exercised in this preview environment for platform/protocol reasons, e.g. native OAuth), **Partially implemented**, or **Planned / Future roadmap** (no code exists yet).

---

## 1. EXECUTIVE SUMMARY

### What is Now Kart?
Now Kart is a **quick-commerce (q-commerce) grocery delivery mobile application** — a React Native + Expo customer-facing app modeled visually and functionally on a real, live Shopify storefront (`vcq88p-fj.myshopify.com`). It lets a shopper browse grocery categories/collections, search products, view product detail with variants/pricing/inventory, manage a cart, maintain a wishlist, sign in with a passwordless Shopify Customer Account, manage delivery addresses, and prepare (but not yet complete) checkout. The product design language ("Delivered in minutes", dark violet/purple theme, lightning-bolt branding) matches quick-commerce apps like Blinkit/Zepto/Instacart in spirit.

### Business Model **[ASSUMPTION]**
Now Kart is architected as a **headless Shopify storefront** — i.e., Shopify remains the merchant's system of record for catalog, inventory, pricing, customer accounts, and (eventually) orders/payments, while Now Kart is a bespoke, branded mobile front-end + a thin FastAPI backend that mediates all Shopify communication. This is the standard "headless commerce" business model: the merchant keeps using Shopify's admin/back-office tooling, but end customers get a fully custom, native mobile experience instead of the default Shopify web storefront or a generic Shopify mobile app. Revenue model would be standard e-commerce margin on grocery items sold through the existing Shopify store; Now Kart itself does not currently process payments (see Section 17, Next Development Roadmap).

### Target Market **[ASSUMPTION]**
Urban/semi-urban grocery shoppers who want fast ("minutes", per the header tagline), mobile-first grocery ordering — the same market segment as Blinkit, Zepto, Instacart, Gopuff. The live product catalog (`diamonds-frozen-paratha`, `shan-original-paratha`, spices/masalas, Asian foods, ready-to-eat items) suggests a South Asian / Asian grocery specialty focus, but this is inferred from catalog data only, not an explicit business statement — flagged as **[ASSUMPTION]**.

### Long-Term Vision
Based on all iterations planned and discussed to date, the intended end-state product includes:
1. Full customer-facing shopping app (catalog, search, cart, wishlist) — **DONE**.
2. Passwordless customer authentication + address management + checkout preparation — **DONE**.
3. Native checkout completion via Shopify hosted checkout (WebView) + payments — **Implemented (WebView checkout complete; Shopify Checkout Sheet Kit / Apple Pay / Google Pay not yet integrated)**.
4. Order placement, order history, live order tracking — **Implemented (order history, order detail, order tracking screen with auto-refresh all complete; Implemented — untested boundary for real order data, requires native build)**.
5. A separate **Rider App** for delivery personnel — **NOT STARTED**. Architecture prep exists in `backend/tracking/` (extension points documented).
6. A separate **Merchant Dashboard** for the grocery store/merchant — **NOT STARTED, NOT DESIGNED**.
7. A separate **Admin Dashboard** for platform-level operations — **NOT STARTED, NOT DESIGNED**.
8. Production deployment to the Apple App Store and Google Play Store — **NOT STARTED**.

### Overall Architecture (one paragraph)
Now Kart is a three-tier system: **(1) Expo/React Native frontend** (file-based routing via `expo-router`) that never talks to Shopify directly; **(2) a FastAPI backend** acting as a Backend-For-Frontend (BFF) that is the *only* component allowed to hold Shopify credentials and talk to Shopify's Storefront GraphQL API (catalog/cart) and Customer Account API (OAuth/auth/profile/addresses); **(3) MongoDB** for Now Kart's own user/session records (never for product data — that always comes live from Shopify). The frontend authenticates against Now Kart's *own* backend-issued session (JWT + rotating refresh token), never holding a real Shopify token on-device.

### Current Completion Percentage **[ASSUMPTION — no official %, this is an engineering estimate]**
Estimated **~60%** of the full long-term vision (all 8 items above). Within the "customer shopping app" scope (items 1–4), completion is **~98%** — the remaining 2% is native OAuth verification and Shopify Checkout Sheet Kit / Apple Pay integration.

### Current Development Phase
**Iteration 7 complete**: Checkout completion (Shopify hosted checkout via WebView), order management (order list with filters/search, order detail with timeline and reorder), delivery address pre-population in Shopify checkout, live order tracking screen with 30s auto-refresh, and tracking architecture prep for the future Rider App. All verified by testing agent.

### Immediate Next Milestone
**Production native build** — generate iOS/Android build via Emergent Publish to validate: real Shopify OAuth login, real payment through Shopify hosted checkout, real order history display, and live tracking updates from Shopify fulfillment data. Then: Shopify Checkout Sheet Kit (Apple Pay/Google Pay) and Rider App (architecture already prepared in `backend/tracking/`).

---

## 2. PRODUCT REQUIREMENTS DOCUMENT (FINAL, AS OF THIS HANDOVER)

### Business Goals
- Provide a fast, native-feeling, branded mobile shopping experience for a grocery merchant already running Shopify.
- Keep Shopify as the single source of truth for products, inventory, pricing, and (eventually) orders/payments/customer records — Now Kart must never fork or duplicate this data into its own database.
- Support both guest and authenticated shopping — never force login to browse or add to cart.
- Lay a secure, scalable authentication + checkout foundation that a future payments iteration can build on without rearchitecting.

### Customer Journey (as implemented today)
1. **Guest lands on Home** → sees category groups + product rails (Best Sellers, New Arrivals) pulled live from Shopify.
2. **Browses Categories tab** → sees all category groups; taps a category → Collection screen (products in that Shopify collection).
3. **Searches** → debounced live Shopify product search.
4. **Opens a Product** → sees images, variants (size/flavor/etc.), price, compare-at price, stock, description; can add to cart; can toggle wishlist (heart icon).
5. **Views Cart** → guest cart persisted locally (AsyncStorage-stored Shopify Cart ID); increment/decrement/remove lines; sees subtotal/total.
6. **Optionally taps Account icon** → if guest, routed to `/profile`, which shows a sign-in gate; if authenticated, shows real profile (name/email), addresses, order-history placeholder, logout.
7. **Signs Up or Logs In** → both buttons trigger the *same* Shopify Customer Account passwordless OAuth flow (system browser) — Shopify sends the shopper an email verification code/magic link; on success, the app receives its own session and the user is now "authenticated".
8. **Proceeds to Checkout (foundation only)** → from Cart, taps "Proceed to Checkout" → `/checkout/address`: cart is validated against live Shopify stock, signed-in buyer identity is attached to the Shopify cart, a delivery address can be selected (or the guest is told they'll enter one at checkout) — a disabled "Continue to Payment" button clearly signals payments are coming in a future update.
9. **Wishlist** → heart icon anywhere adds/removes a product from a locally persisted wishlist; Header badge and `/wishlist` screen always stay in sync.

### Features (Implemented)
- Live Shopify-backed Home, Categories, Collection, Search, Product Detail, Cart.
- Shopify Customer Account passwordless Sign Up / Log In / Logout with backend-mediated OAuth2+PKCE.
- Session persistence + silent restoration on app relaunch; guest mode always available.
- Local (device-only) wishlist with cross-screen badge sync.
- Address management (Customer Account API-backed create/update/delete/list).
- **Delivery address selector** on Home screen (`DeliverySelector`) — persists selected address in AsyncStorage, navigates to `/addresses?select=1` picker mode; clears on sign-out.
- **Checkout completion**: full order review screen (items, price breakdown, delivery instructions), Shopify hosted checkout via `react-native-webview`, order confirmation screen with items + total + ETA.
- **Delivery address pre-population in Shopify checkout**: selected address is sent as `deliveryAddressPreferences` in `cartBuyerIdentityUpdate` so Shopify Checkout opens with shipping pre-filled.
- **Order management**: order list (filter by All/Active/Completed/Cancelled, search by order number, pull-to-refresh, status badges, thumbnails), order detail (timeline, line items, price breakdown, delivery address, reorder per-item + all), reorder via Storefront product search.
- **Live order tracking**: dedicated tracking screen (`/order/track`) with 30s auto-refresh (AppState-aware, stops for delivered/cancelled), dynamic timeline from Shopify fulfillment data, delivery address, items, last-updated timestamp.

### Customer Journey (as implemented today — UPDATED)
1. **Guest lands on Home** → taps "Set delivery address" → picks from saved addresses (authenticated) or navigates to Profile (guest).
2. **Browses, searches, adds to cart** — same as before.
3. **Proceeds to Checkout** → full order review (items, breakdown, address selection, delivery instructions, grand total) → "Continue to Payment" → Shopify hosted checkout WebView → order confirmation screen.
4. **Views Orders** → order list with filters/search → order detail with timeline → track button for active orders → tracking screen with auto-refresh.

### Features (Explicitly Out of Scope — do NOT implement without new instructions)
- Shopify Checkout Sheet Kit / Apple Pay / Google Pay (WebView checkout works; native payment sheet is next).
- Rider App (architecture prep exists in `backend/tracking/`; do not build until explicitly requested).
- Merchant dashboard, Admin dashboard, push notifications, live GPS tracking.

### Future Roadmap (see Section 17 for the full milestone-by-milestone detail)
Checkout Sheet Kit / hosted checkout → payments → order creation/history → live tracking → Rider App → Merchant Dashboard → Admin Dashboard → production app-store/play-store deployment.

### Completed Milestones (chronological)
1. Initial Now Kart UI (React Native + Expo, Flutter unavailable, user approved pivot).
2. Live Shopify Storefront API integration (Iteration 3): catalog, collections, search, product detail, guest cart.
3. UI polish (Iteration 3.5): square product images, 2-line card titles.
4. Customer Authentication + Checkout Foundation (Iteration 4): OAuth2+PKCE, sessions, wishlist, addresses, checkout-prep.
5. **Auth fix**: `countryCode` → `territoryCode` (Shopify Customer Account API 2026-07 renamed this field; old name caused HTTP 400 in token-exchange).
6. **Checkout completion (Iteration 5)**: full checkout review screen, Shopify hosted checkout (WebView), order confirmation, delivery address pre-population via `deliveryAddressPreferences` in `cartBuyerIdentityUpdate`.
7. **Address selector on Home (Iteration 5b)**: DeliverySelector wired to AsyncStorage-persisted delivery address; `/addresses?select=1` picker mode.
8. **Order Management (Iteration 6)**: order list (filters/search/thumbnails), order detail (timeline/line items/reorder), `GET /api/auth/orders?id=`, ORDER_DETAIL_QUERY.
9. **Live Order Tracking (Iteration 7)**: `backend/tracking/` module, `GET /api/tracking/order?id=`, tracking screen with 30s AppState-aware polling, Rider App extension points documented.

### Pending Milestones (remaining roadmap)
- **P0**: Generate native iOS/Android build → verify OAuth login + payment + order tracking end-to-end.
- **P1**: Shopify Checkout Sheet Kit (Apple Pay / Google Pay native payment sheet).
- **P2**: Rider App — plug into `backend/tracking/` extension points (`riderLocation`, `riderEta`, `riderName`).
- **P3**: Merchant Dashboard, Admin Dashboard.
- **P4**: Push Notifications (order status webhooks → device push).
- **P5**: Production App Store / Play Store submission.

### Known Constraints
- Real Shopify OAuth completion (email verification + native custom-scheme redirect) **cannot be tested in Expo Go or the web preview** — it requires a native development/production build. This is a platform/protocol limitation, not a bug.
- No web Shopify Customer Account OAuth client is registered — the backend intentionally rejects `platform="web"` authorize requests with HTTP 400.
- The current Shopify dev store's product variants mostly have `quantityAvailable = 0` with "continue selling when out of stock" enabled — this is real store data, not a bug (see Section 14).
- Missing product/collection images on some Shopify items are a Shopify **data** gap (the merchant hasn't uploaded images for those items), not a Now Kart code bug — the existing fallback chain (collection image → first product image → branded placeholder) must never be changed to "fix" this.

### Technical Decisions (see Section 3 for full architecture rationale)
- React Native + Expo (not Flutter) — environment constraint + user approval.
- Expo Router (file-based routing) — mandated by platform convention.
- FastAPI BFF pattern — Shopify credentials must never reach the client.
- MongoDB only for Now Kart's own user/session records, never product data.
- Shopify Customer Account API (2026, OAuth2+PKCE) for auth — NOT the deprecated legacy Storefront `customerAccessTokenCreate` flow.
- `expo-secure-store` (via a project-owned `src/utils/storage` abstraction) for session tokens on native; AsyncStorage fallback on web (there is no OS Keychain on web).

### Design Philosophy
Dark, premium, "quick-commerce" aesthetic: near-black background (`#0B0710`), violet/purple primary accent (`#8B5CF6`), white product-card backgrounds for contrast, generous rounded corners, subtle shadows, `react-native-reanimated`-driven micro-animations (press scale, fade-in, zoom-in) rather than blunt page transitions. See Section 12 for full UI/UX decision log.

### Brand Guidelines
- Wordmark: "NOW" in white + "KART" in violet (`colors.primary.main`), with a small amber lightning-bolt icon (`#FBBF24`) — see `Header.tsx`.
- Tagline: "Delivered in minutes" (eyebrow-style small caps, secondary text color).
- Colors, typography, spacing are centralized in `frontend/src/theme/` and must be extended (not replaced) if new values are needed — see the explicit comment in `colors.ts`: "DO NOT invent new colors here. Extend only if a new literal color is found on the storefront."

### User Experience Principles (mandated, see system-level UI/UX framework too)
- Guest browsing is always available; auth is never forced.
- Thumb-friendly, gesture-driven, glanceable — bottom tab nav for the 3 primary areas (Home/Categories/Orders), stack navigation with back buttons for everything else.
- Every async operation has explicit loading/empty/error states (skeleton components exist for product/category cards).
- Every permission-gated or auth-gated action degrades gracefully rather than dead-ending the user (e.g., guest tapping checkout still sees a usable, if guest-scoped, flow).

---

## 3. SYSTEM ARCHITECTURE

### High-Level Diagram (textual)
```
[Expo/React Native App]  --HTTPS-->  [FastAPI backend, /api/*]  --HTTPS-->  [Shopify Storefront GraphQL API]
        |                                    |                  --HTTPS-->  [Shopify Customer Account API (OAuth+GraphQL)]
        |                                    |
        |                                    +--> [MongoDB: users, auth_refresh_tokens, status_checks]
        |
        +--> [expo-secure-store / AsyncStorage: Now Kart's OWN session tokens only]
        +--> [AsyncStorage: guest Shopify Cart ID, local Wishlist]
```

### Frontend
- **Framework:** Expo (SDK 54) + React Native 0.81.5 + React 19.1.0, TypeScript.
- **Routing:** `expo-router` 6.0.24, file-based, under `/app`. Root layout (`app/_layout.tsx`) wraps everything in `SafeAreaProvider > AuthProvider > WishlistProvider > CartProvider > Stack`.
- **Navigation model:** Bottom tab navigator (`app/(tabs)/_layout.tsx`, custom `CustomTabBar` component) for Home / Categories / Orders. A root `Stack` (in `app/_layout.tsx`) hosts everything else as pushed screens with slide/fade animations: `cart`, `search`, `product/[handle]`, `collection/[handle]`, `profile`, `wishlist`, `addresses`, `checkout/address`, `auth/callback`.
- **State management:** React Context (no Redux/Zustand) — three global providers: `AuthContext`, `WishlistContext`, `CartContext`. Screen-local state uses `useState`/`useCallback`; data-fetching uses a shared `useAsyncData` hook.
- **Styling:** `StyleSheet.create()` everywhere, centralized design tokens in `src/theme/` (colors, typography, spacing, radius, shadows). No CSS, no NativeWind, no styled-components.
- **Animation:** `react-native-reanimated` 4.1.1 (+ `react-native-worklets`) for press-scale (`AnimatedPressable`), fade/zoom-in on error/empty states, skeleton shimmer.

### Backend
- **Framework:** FastAPI 0.110.1 (Python), running via `uvicorn` with `watchfiles` auto-reload in dev, bound to `0.0.0.0:8001` (managed by supervisor, never change this binding).
- **Structure:** `server.py` is the FastAPI app entrypoint — it loads `.env`, connects to MongoDB, mounts four routers: a legacy generic `/api` status-check router, `shopify_router` (`/api/shopify/*`), `auth_router` (`/api/auth/*`), and `tracking_router` (`/api/tracking/*`). CORS is currently wide open — known P3 hardening item.
- **Three clean bounded modules:**
  - `backend/shopify_integration/` — Shopify Storefront GraphQL API (catalog, collections, search, cart, checkout-prep with delivery address pre-population).
  - `backend/auth/` — Shopify Customer Account API (OAuth2+PKCE, sessions, profile, addresses, order detail).
  - `backend/tracking/` — Order tracking derived from Shopify fulfillment data; architecture prep for Rider App (`riderLocation`, `riderEta` extension points commented in `schemas.py`).
- These modules have a one-directional import: `shopify_integration.router` imports `auth.service`/`auth.dependencies`; `tracking.service` imports `auth.service`; `auth` never imports from `shopify_integration` or `tracking`.

### Shopify Integration (see Section 7 for full detail)
- **Storefront API** (public catalog/cart) — accessed with a **private Storefront API token** (server-side only) via a thin async GraphQL client (`shopify_integration/client.py`).
- **Customer Account API** (OAuth2+PKCE, customer profile/addresses/orders) — accessed via OIDC discovery + a dedicated async client (`auth/customer_account_client.py`).

### Authentication (see Section 8 for full detail)
Backend-mediated (BFF) OAuth2 Authorization Code + PKCE against Shopify's Customer Account API. The device generates the PKCE verifier/challenge in memory, gets an authorization code via the system browser + a registered native custom-scheme redirect, and forwards `{code, code_verifier}` to the backend once. The backend performs the actual token exchange, encrypts and holds the real Shopify tokens server-side, and issues Now Kart's own JWT access token (15 min) + rotating opaque refresh token (30 days) to the client. The client never sees a real Shopify token.

### Wishlist
Purely client-side today: a `WishlistContext` persists full `Product` snapshots (not just IDs) to AsyncStorage under key `nowkart_wishlist_v1`, so the Wishlist screen renders instantly with zero refetch. Every consumer (Header badge, Product Detail heart icon, Search/Collection cards, Wishlist screen) reads from this single context — they can never drift out of sync with each other. The context's own doc comment explicitly designs for future backend sync (e.g., once `isAuthenticated` is true, swap the load/persist functions to also hit a backend endpoint) without any consuming screen needing to change.

### Cart
Guest-first: `CartContext` persists only the Shopify **Cart ID** (a GID) in AsyncStorage under key `nowkart_cart_id`; the actual cart contents always come live from Shopify via the backend on every mutation. No login is required to have a cart. If a user signs in, `POST /api/shopify/cart` and `POST /api/shopify/checkout/prepare` both transparently attach the signed-in buyer's Shopify Customer Account access token to the cart via `cartBuyerIdentityUpdate`.

### Search
Debounced live query against `/api/shopify/search?q=...`, using a Storefront query of `title:*<q>* OR tag:*<q>*`.

### Collections
`/api/shopify/collections/{handle}/products` — a static `collection_groups.py` config maps human-friendly section titles ("Snacks & Drinks", "Grocery & Kitchen", etc.) to an ordered list of candidate Shopify collection handles; any handle that doesn't exist yet on the live store is skipped gracefully (no broken UI even if the merchant hasn't created every collection).

### Profile
`/app/profile.tsx` — gated: guests see a sign-in prompt (which routes into the same passwordless OAuth flow as Sign Up); authenticated users see name/email (from Shopify Customer Account `ME_QUERY`), a saved-addresses section (linking to `/addresses`), an order-history section (**currently a placeholder** — the backend already fetches real `orders` in `ME_QUERY`/`get_profile`, but the Profile screen itself has not yet been wired to render them as a real list — this is the most likely quick win for a future iteration), a wishlist link, and Logout.

### Checkout Foundation
`/app/checkout/address.tsx` — no payment. Calls `POST /api/shopify/checkout/prepare` (validates live stock, attaches buyer identity), then lets a signed-in customer pick a saved address (guests are told they'll enter one at actual checkout), and shows a **disabled** "Continue to Payment" button with a "coming in a future update" message.

### Future Rider App / Merchant Dashboard / Admin Dashboard
**Not started, not designed, no code exists.** These would each most likely be **separate Expo/React Native (or web) applications** reusing the same FastAPI backend's future order/rider/merchant endpoints (none of which exist yet) and likely a shared or extended MongoDB schema. No architectural decisions have been made for these yet — treat as a clean slate when the user requests them.

### Database
MongoDB (`motor` async driver). Database name from `DB_NAME` env var. Current collections:
- `status_checks` — legacy pre-existing scaffold collection from the original template, not used by any real Now Kart feature.
- `users` — one document per Shopify customer who has ever signed in; unique index on `shopifyCustomerId`; stores `email`, `firstName`, `lastName`, Fernet-encrypted `shopifyAccessTokenEnc`/`shopifyRefreshTokenEnc`, `shopifyTokenExpiresAt`, timestamps. **Never stores a plaintext Shopify token.**
- `auth_refresh_tokens` — one document per issued refresh token; indexed on `tokenHash` and `userId`; stores a SHA-256 hash of the token (never the raw token), `expiresAt`, `revoked` boolean, `createdAt`.
No product/catalog/cart data is ever persisted in MongoDB — that always lives in Shopify and is fetched live (with a short in-memory TTL cache for a few read endpoints, see `shopify_integration/cache.py`).

### API Structure
All backend routes are prefixed `/api` at the Kubernetes-ingress level (`server.py` mounts routers with that prefix). Two logical sub-APIs:
- `/api/shopify/*` — catalog/cart/checkout-prep (see Section 7 for the full endpoint list).
- `/api/auth/*` — Shopify Customer Account auth + Now Kart sessions + addresses (see Section 9 for the full endpoint list).

### Repository Structure (frontend data-access pattern)
Frontend screens/hooks never call `fetch`/`apiClient` directly for domain data — they go through a small `repositories/` layer (`productRepository`, `cartRepository`, `authRepository`), each of which only knows about `/api/shopify/*` or `/api/auth/*` paths and returns typed domain objects. This is the single seam where the frontend would swap backend implementations without touching any screen.

### Folder Structure
See Section 5 for the complete, annotated tree.

### Deployment Architecture
Currently **dev/preview only**, inside this Emergent container: `supervisor` manages `backend` (uvicorn on port 8001) and `expo` (Metro dev server on port 3000, proxied). Kubernetes ingress routes `/api/*` to port 8001 and everything else to port 3000. **No production deployment has occurred.** Production deployment for this class of project is: click **Publish** (top-right of the Emergent UI) → **Deploy your app** → generate iOS/Android builds. This has not been done yet for Now Kart.

### Security Architecture (see Section 13 for full detail)
BFF-mediated Shopify token custody; Fernet-at-rest encryption of Shopify tokens in MongoDB; HS256 JWT for Now Kart's own access tokens; SHA-256-hashed, single-use, rotating opaque refresh tokens with reuse-detection (family-wide revocation on detected reuse); PKCE generated and held only in device memory; OAuth `state` is single-use (popped, not just read, from a TTL cache); the backend rejects any `platform="web"` OAuth authorize request outright (no web OAuth client is registered, so this closes an unvalidated-redirect attack surface).

### Token Lifecycle
1. Device generates PKCE verifier (64 random bytes, base64url) + SHA-256 S256 challenge, in memory only.
2. Device requests `/api/auth/shopify/authorize-url` with the challenge → backend generates a single-use `state`, builds and returns Shopify's authorize URL + the fixed native `redirectUri`.
3. Device opens that URL via `expo-web-browser`'s `openAuthSessionAsync`, which captures the OS-level custom-scheme redirect directly (no app screen involved for native).
4. Device parses `code`/`state` from the redirect, verifies `state` matches, then POSTs `{code, state, codeVerifier, redirectUri}` to `/api/auth/shopify/token-exchange` — exactly once.
5. Backend exchanges the code with Shopify (`grant_type=authorization_code`), receives Shopify access+refresh tokens, encrypts and stores them in `users` (upsert keyed on `shopifyCustomerId`), and issues Now Kart's own session (JWT access token, 15 min; opaque refresh token, 30 days; refresh token is only ever stored as a SHA-256 hash server-side).
6. Device stores `{accessToken, refreshToken}` via `storage.secureSet` (Keychain/EncryptedSharedPreferences on native, AsyncStorage on web).
7. On every subsequent request, the device attaches `Authorization: Bearer <accessToken>`. On a 401, or proactively ~60s before expiry, the device calls `/api/auth/refresh` with the refresh token — this rotates the refresh token (old one is marked revoked) and issues a new pair. A **single-flight guard** on-device ensures concurrent 401s/proactive-timer firings never race this rotation.
8. Server-side, when Now Kart needs a live Shopify API call (profile/addresses/buyer-identity), it transparently refreshes the *Shopify* token (separate from the app's own session token) if it's within 60s of expiry, using the encrypted refresh token stored in `users`.
9. Logout: device calls `/api/auth/logout` with its refresh token (best-effort; local state is cleared regardless of network success) → backend marks that refresh token `revoked: true` in Mongo. Device clears its stored session via `storage.secureRemove`.

### Session Lifecycle (Now Kart's own, distinct from Shopify's)
- Access token: JWT, HS256, 15-minute expiry (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`), `sub` = Mongo user `_id` string, `type: "access"`.
- Refresh token: opaque (48 random URL-safe bytes), 30-day expiry (`SESSION_REFRESH_TOKEN_EXPIRE_DAYS`), single-use rotation (each refresh revokes the old one and issues a brand-new pair), reuse of an already-revoked refresh token triggers family-wide revocation of every other active session for that user (treated as a compromise signal).

### Deep Linking
`app.json`'s `expo.scheme` array registers two custom URI schemes for the app ("frontend" and a Shopify-shop-specific scheme) — the second one is the one Shopify's Customer Account API redirects back into after a successful login on native. The exact registered redirect URI value lives only in `backend/.env` (`SHOPIFY_CUSTOMER_ACCOUNT_MOBILE_REDIRECT_URI`) and must match exactly what is registered in the Shopify Partner/Customer Account API dashboard. There is also a web-only fallback route `app/auth/callback.tsx` that exists purely so an unexpected hit to that URL never 404s/crashes — it is not part of the real (native-only) sign-in flow today, since no web OAuth client is registered.

### State Management
React Context only, no external state library. Three providers, mounted in this exact order in `app/_layout.tsx`: `AuthProvider` → `WishlistProvider` → `CartProvider`. Order matters only insofar as `CartProvider`'s buyer-identity attachment logic assumes auth state is already available if needed in the future — today `CartProvider` does not actually depend on `AuthContext` directly (the backend resolves buyer identity server-side from the Bearer token), so this ordering is a safe default, not a hard requirement.

### Navigation Architecture
See "Frontend" above — bottom tabs for primary areas, root Stack for everything else, with `presentation`/`animation` options per screen (`slide_from_bottom` for cart/search, `slide_from_right` for detail/profile-type screens, `fade` for the auth callback safety net).

### Component Hierarchy (representative, Home screen)
```
app/_layout.tsx (SafeAreaProvider > AuthProvider > WishlistProvider > CartProvider > Stack)
  app/(tabs)/_layout.tsx (Tabs + CustomTabBar)
    app/(tabs)/index.tsx (Home)
      Header (wordmark, wishlist/account/cart icons+badges)
      DeliverySelector
      SearchBar (navigates to /search)
      CategoryGroupSection (repeated) -> CategoryCard / CategoryCardSkeleton
      ProductRail (repeated) -> ProductCard / ProductCardSkeleton
      FreeDeliveryBanner (dismissible, non-blocking overlay)
```

### Every Important Architectural Decision (consolidated list)
1. React Native + Expo instead of Flutter — environment constraint (`flutter` CLI unavailable) + explicit user approval; **do not revisit without a new explicit user request**.
2. FastAPI BFF — Shopify Storefront token and Customer Account OAuth client secret-less flow must never be reachable from the client; this is non-negotiable for security.
3. Feature-oriented backend (`shopify_integration/`, `auth/`) rather than one monolithic `server.py` — chosen for maintainability as the app grows toward orders/rider/merchant/admin.
4. Repository pattern on the frontend — chosen so the data-access layer can be swapped/extended (e.g., add GraphQL client-side caching, or a future orders repository) without touching UI code.
5. Context-only state management — chosen because the app's actual shared-state surface (auth, wishlist, cart) is small; do not introduce Redux/Zustand without a concrete justification (state complexity growing beyond 3 contexts).
6. Wishlist kept 100% local for now, by explicit design, with a documented forward-compatibility seam for backend sync — **do not silently move it server-side without discussing with the user first**, since it changes data-retention semantics (a guest's wishlist today survives app reinstall only via AsyncStorage, which will be lost on uninstall — this is accepted, known behavior).
7. `src/utils/storage/` abstraction (native/web split) — introduced specifically to fix a real production bug (see Section 14) where `expo-secure-store` has zero web support; all new secure-storage code must use this abstraction, never call `expo-secure-store` directly again.

---

## 4. TECHNOLOGY STACK

### Frontend
| Technology | Version | Why chosen |
|---|---|---|
| Expo (SDK) | 54.0.35 | Managed native tooling, required by this environment's build/preview pipeline. |
| React | 19.1.0 | Required by the Expo SDK 54 baseline. |
| React Native | 0.81.5 | Required by the Expo SDK 54 baseline. |
| expo-router | 6.0.24 | Mandated file-based routing convention for this environment. |
| TypeScript | 5.9.3 | Type safety across repositories/contexts/screens. |
| react-native-reanimated | 4.1.1 (+ react-native-worklets 0.5.1) | Native-thread animations (press scale, fade/zoom) without janky JS-thread transitions. |
| react-native-gesture-handler | 2.28.0 | Underlies reanimated/gesture-based interactions and screen transitions. |
| react-native-screens | 4.16.0 | Native screen optimization required by expo-router/React Navigation. |
| react-native-safe-area-context | 5.6.0 | Safe-area-aware layout on all devices/notches. |
| @react-native-async-storage/async-storage | 2.2.0 | General local persistence (cart ID, wishlist, non-secret storage). |
| expo-secure-store | 15.0.8 | OS Keychain / EncryptedSharedPreferences for session tokens — **native only**, wrapped by `src/utils/storage/`. |
| expo-crypto | ~15.0.9 | On-device PKCE code_verifier/code_challenge generation (SHA-256). |
| expo-web-browser | 15.0.11 | System-browser-based OAuth (never an embedded WebView, per security best practice). |
| expo-linking | 8.0.12 | Parsing the OAuth custom-scheme redirect URL. |
| expo-image | 3.0.11 | Performant, cached remote image loading for product/category images. |
| @expo/vector-icons | 15.1.1 | Ionicons used throughout (heart, bag, person, chevrons, etc.). |
| expo-blur, expo-linear-gradient | 15.0.8 | Visual polish (banners, overlays). |
| expo-haptics | 15.0.8 | Tactile feedback on key interactions. |
| date-fns / dayjs | 4.1.0 / 1.11.13 | Date formatting (both present; **[ASSUMPTION]** — likely one is a leftover/unused dependency; verify before adding new date logic). |

### Backend
| Technology | Version | Why chosen |
|---|---|---|
| FastAPI | 0.110.1 | Async-first Python web framework, required by this environment's template. |
| Uvicorn | 0.25.0 | ASGI server, bound to 0.0.0.0:8001 (never change). |
| Motor | 3.3.1 | Async MongoDB driver, matches FastAPI's async model. |
| PyMongo | 4.6.3 | Underlies Motor. |
| httpx | 0.28.1 | Async HTTP client used for all Shopify GraphQL/OAuth calls. |
| PyJWT | 2.13.0 | Now Kart's own JWT access-token signing/verification (HS256). |
| cryptography (Fernet) | 49.0.0 | At-rest symmetric encryption of Shopify tokens stored in MongoDB. |
| passlib, bcrypt | 1.7.4 / 4.1.3 | Present in the environment for password hashing — **not currently used** by Now Kart's auth (which is passwordless, no passwords are ever stored); kept available in case a future feature needs them. |
| pydantic | 2.13.4 | Request/response schema validation across both `shopify_integration` and `auth`. |
| python-dotenv | 1.2.2 | Loads `backend/.env` — always via `load_dotenv()`, never hardcode env values. |
| pytest | 9.1.1 | Backend test suite (`backend/tests/`). |

### Data / Infra
| Technology | Why chosen |
|---|---|
| MongoDB | Pre-provisioned in this environment (`MONGO_URL` in `backend/.env`); used only for Now Kart's own user/session data, never product data. |
| Shopify (Storefront API + Customer Account API) | The merchant's existing e-commerce platform; source of truth for catalog, inventory, pricing, and customer identity. |

---

## 5. REPOSITORY STRUCTURE

```
/app
├── backend/
│   ├── .env                          # PROTECTED. Mongo config + Shopify config + auth secrets (names only in Section 18)
│   ├── requirements.txt              # Python deps (only update via pip install + pip freeze)
│   ├── server.py                     # FastAPI entrypoint: env load, Mongo connect, router mounting, CORS, startup/shutdown hooks
│   ├── tests/
│   │   ├── test_shopify_integration.py   # pytest coverage for /api/shopify/* (catalog, cart, checkout-prep)
│   │   └── test_auth_endpoints.py        # pytest coverage for /api/auth/* (authorize-url, token-exchange, refresh, logout, guest gating)
│   ├── shopify_integration/          # Shopify Storefront API — unchanged structure
│   │   └── ... (queries.py, service.py, router.py, schemas.py, mappers.py, cache.py, config.py, collection_groups.py, client.py)
│   ├── auth/                         # Shopify Customer Account API + Now Kart sessions
│   │   └── ... (config.py, customer_account_client.py, security.py, db.py, schemas.py, service.py, dependencies.py, router.py)
│   └── tracking/                     # NEW (Iteration 7) — order tracking + Rider App prep
│       ├── __init__.py
│       ├── schemas.py                # TrackingStageOut, TrackingStatusOut (Rider App extension points commented)
│       ├── service.py                # get_tracking_status() — derives tracking from Shopify fulfillment data
│       └── router.py                 # GET /api/tracking/order?id= (query param, NGINX-safe)
│
├── frontend/
│   ├── .env                          # PROTECTED framework vars only (EXPO_PACKAGER_*, EXPO_PUBLIC_BACKEND_URL, etc.)
│   ├── app.json                      # Expo config: name, scheme(s), bundle IDs, splash, plugins — see Section 19
│   ├── package.json                  # Dependencies — ONLY edit via `yarn expo install <pkg>`, never hand-edit versions
│   ├── metro.config.js               # PROTECTED — never modify
│   ├── app/                          # expo-router routes
│   │   ├── _layout.tsx               # Root layout + Stack.Screens (add new screens here)
│   │   ├── (tabs)/
│   │   │   ├── index.tsx             # Home (DeliverySelector wired to AsyncStorage + /addresses?select=1)
│   │   │   ├── categories.tsx
│   │   │   └── orders.tsx            # Full order list (filters/search/thumbnails/status)
│   │   ├── checkout/
│   │   │   ├── address.tsx           # Order review + address selection + delivery instructions
│   │   │   ├── webview.tsx           # NEW: Shopify hosted checkout in WebView
│   │   │   └── confirmation.tsx      # NEW: Order confirmation (items, total, ETA, CTAs)
│   │   ├── order/
│   │   │   ├── detail.tsx            # NEW: Full order detail (timeline, items, reorder, Track button)
│   │   │   └── track.tsx             # NEW: Live tracking (30s polling, AppState-aware, timeline)
│   │   ├── addresses.tsx             # CRUD + select-for-delivery mode (?select=1)
│   │   ├── auth/callback.tsx, cart.tsx, collection/[handle].tsx, product/[handle].tsx, profile.tsx, search.tsx, wishlist.tsx
│   │   └── +html.tsx
│   └── src/
│       ├── features/auth/            # AuthContext (signOut now clears deliveryAddress), useShopifySignIn
│       ├── features/cart/            # CartContext (clearCart() added in Iteration 5)
│       ├── repositories/
│       │   ├── authRepository.ts     # + getOrder(orderId) → /auth/orders?id=
│       │   ├── cartRepository.ts     # + updateNote(), prepareCheckout(cartId, selectedAddress?)
│       │   ├── productRepository.ts
│       │   └── trackingRepository.ts # NEW: getTrackingStatus(orderId) → /tracking/order?id=
│       ├── types/
│       │   ├── auth.ts               # + OrderSummary (expanded), OrderLineItem, OrderFulfillment, OrderDetail
│       │   ├── tracking.ts           # NEW: TrackingStage, TrackingStatus (Rider App extension points)
│       │   └── cart.ts, product.ts, category.ts, home.ts, index.ts
│       └── utils/storage/
│           ├── deliveryAddress.ts    # NEW: getStoredDeliveryAddress / storeDeliveryAddress / clearStoredDeliveryAddress
│           ├── index.ts, index.web.ts, storage-base.ts
│
├── memory/
│   ├── PRD.md                        # Living PRD file (per platform convention)
│   └── test_credentials.md           # Auth test credentials (currently N/A — passwordless flow has no fixed test credentials; real email verification is required)
├── test_reports/                     # testing_agent JSON output per iteration (iteration_3.json, iteration_4.json, etc.)
├── test_result.md                    # Canonical, structured testing history — READ THIS FIRST, before any testing_agent call
├── design_guidelines.json            # Original design-reference extraction from the source Shopify storefront
├── NOWKART_MASTER_HANDOVER.md        # This document
├── PROJECT_MEMORY.md                 # Long-term AI memory document
└── DEVELOPER_PLAYBOOK.md             # Practical day-to-day developer guide
```

---

## 6. EVERY FEATURE IMPLEMENTED

### Home (`app/(tabs)/index.tsx`)
- **Purpose:** Landing screen — category discovery + curated product rails.
- **Architecture:** `useAsyncData(() => productRepository.getHomeSections())` fetches `{categoryGroups, rails}` from `GET /api/shopify/home` in a single round trip.
- **Files:** `app/(tabs)/index.tsx`, `src/features/home/components/{HeroBanner,AboutSection,ProductRail}.tsx`, `src/shared/components/{CategoryGroupSection,CategoryCard,CategoryCardSkeleton,ProductCard,ProductCardSkeleton,FreeDeliveryBanner}.tsx`, `src/repositories/productRepository.ts`, backend `shopify_integration/service.py::get_home_sections/get_category_groups/get_home_rails`.
- **How it works:** Backend fetches all Shopify collections once (cached, 90s TTL by default via `SHOPIFY_CACHE_TTL_SECONDS`), matches them against the static `CATEGORY_GROUPS`/`RAIL_COLLECTIONS` config (`collection_groups.py`), and returns category groups + up to 2 product rails ("Best Sellers", "New Arrivals") each capped at 12 products; if a rail's target collection doesn't exist, it falls back to a sitewide sorted query.
- **Known limitations:** Category-group/rail titles are hardcoded in `collection_groups.py`, not merchant-configurable; if the merchant renames/removes a matching collection handle, that section silently disappears (by design — "never breaks the UI").
- **Future improvements:** Merchant-configurable section titles (would require either a Shopify metafield convention or a small admin-config surface once an Admin Dashboard exists).

### Search (`app/search.tsx`)
- **Purpose:** Live product search.
- **Architecture:** Debounced text input → `productRepository.searchProducts(q)` → `GET /api/shopify/search?q=...&first=20`.
- **Files:** `app/search.tsx`, `src/shared/components/SearchBar.tsx`, `productRepository.ts`, backend `service.py::search_products`, `queries.py::SEARCH_PRODUCTS_QUERY`.
- **How it works:** Backend builds a Shopify search query string `title:*<q>* OR tag:*<q>*` and returns mapped `ProductOut[]`.
- **Known limitations:** No search-history, no autocomplete/suggestions, no fuzzy/typo tolerance beyond whatever Shopify's own search does.
- **Future improvements:** Recent searches, popular searches, category filter chips.

### Collections (`app/collection/[handle].tsx`)
- **Purpose:** Product listing for a single Shopify collection (a "category" from the user's perspective).
- **Architecture:** `GET /api/shopify/collections/{handle}/products?first=24`.
- **Files:** `app/collection/[handle].tsx`, backend `service.py::get_collection_products`, `queries.py::COLLECTION_PRODUCTS_QUERY`.
- **Known limitations:** No pagination beyond the first N products (`first` query param, default 24, capped at 50 server-side) — no infinite scroll/load-more yet.
- **Future improvements:** Cursor-based pagination using Shopify's `pageInfo`/`endCursor` (not currently threaded through the schema).

### Product Detail (`app/product/[handle].tsx`)
- **Purpose:** Full product view — images, variants, price, stock, description, add-to-cart, wishlist toggle.
- **Architecture:** `GET /api/shopify/products/{handle}` → `useAsyncData`, which now also surfaces the HTTP status (`errorStatus`) so the screen can distinguish a genuine 404 ("Product not found") from a transient error (generic retry state) — this was a real bug fixed in Iteration 3 (see Section 14).
- **Files:** `app/product/[handle].tsx`, `useAsyncData.ts`, backend `service.py::get_product_by_handle`, `mappers.py::map_product`.
- **UI decision:** the product image container was changed from a fixed-height rectangle to a true square (`aspectRatio: 1`) in Iteration 3.5 for a cleaner, more premium look (see Section 12).
- **Known limitations:** Multi-variant/out-of-stock UI states were reviewed but could not be exercised end-to-end with live data during testing because the store's real inventory rarely has multiple variants or hard-out-of-stock items.

### Cart (`app/cart.tsx` + `CartContext.tsx`)
- **Purpose:** Guest-first shopping cart, backed by the live Shopify Cart API.
- **Architecture:** See Section 3 "Cart". Increment/decrement/remove; decrementing to 0 removes the line; re-adding the same variant merges into the existing line (native Shopify Cart behavior, not custom logic).
- **Files:** `app/cart.tsx`, `src/features/cart/CartContext.tsx`, `src/repositories/cartRepository.ts`, backend `shopify_integration/service.py` (create/get/add/update/remove cart line functions), `queries.py` (all `CART_*` mutations/query).
- **Known limitations:** Cart ID persistence is per-device/per-app-install only (AsyncStorage) — a cart is lost on app uninstall or if the Shopify cart itself expires server-side; there is graceful handling for an expired/invalid stored cart ID (it's cleared and a fresh cart starts on next add).

### Wishlist (`app/wishlist.tsx` + `WishlistContext.tsx`)
- **Purpose:** Let a shopper save products for later, independent of login state.
- **Architecture:** See Section 3 "Wishlist". 100% local (AsyncStorage), single source of truth shared by every screen.
- **Files:** `app/wishlist.tsx`, `src/features/wishlist/WishlistContext.tsx`, consumed by `Header.tsx` (badge) and Product Detail/Search/Collection cards (heart icon toggle).
- **Known limitations:** No cross-device sync; lost on app uninstall; not yet linked to a signed-in customer's Shopify account (Shopify does have a native "Save for later"-style capability via metafields in some setups, but this has not been implemented).
- **Future improvements:** Sync to backend once authenticated, per the context's own forward-compatibility design comment.

### Profile (`app/profile.tsx`)
- **Purpose:** Account hub — sign-in gate for guests, real profile for authenticated users.
- **Architecture:** Reads `useAuth()` for `isAuthenticated`/`user`; if authenticated, calls `authRepository.getProfile()` (`GET /api/auth/me`) to get name/email/addresses/orders.
- **Files:** `app/profile.tsx`, `src/features/auth/AuthContext.tsx`, `src/features/auth/useShopifySignIn.ts`, `src/repositories/authRepository.ts`, backend `auth/router.py::me`, `auth/service.py::get_profile`.
- **Implementation note (corrected from an earlier, inaccurate draft of this document):** Profile does **not** render an inline order list itself — it shows a "Order History" menu row (`profile-menu-orders`) that navigates to the dedicated Orders tab (`app/(tabs)/orders.tsx`), which is a real, code-complete implementation, not a placeholder (see "Orders" below).
- **Known limitations:** none beyond the shared native-OAuth-completion boundary (Section 8).

### Orders (`app/(tabs)/orders.tsx`) — **Implemented**
Rich order list: filter tabs (All/Active/Completed/Cancelled, client-side), search by order number, pull-to-refresh, order cards with status badge (color-coded), product thumbnail, item count. Tapping card navigates to order detail.

### Order Detail (`app/order/detail.tsx`) — **Implemented — untested boundary**
Full order detail: summary card (name, total, date, payment/fulfillment status), dynamic timeline (derived from Shopify fulfillment data), line items with per-item Add-to-Cart (reorder via Storefront product search), price breakdown (subtotal/shipping/tax/refund/total), delivery address, Reorder All button. "Track Order" button appears for active orders.

### Order Tracking (`app/order/track.tsx`) — **Implemented — untested boundary**
Dedicated tracking screen: hero status card with pulsing live dot, full timeline with Shopify timestamps, delivery address, compact items list, pull-to-refresh. Auto-refresh every 30s (AppState-aware, stops when fulfilled/cancelled). Architecture prep: `TrackingStatus` TypeScript type and `TrackingStatusOut` backend schema have Rider App extension points commented (`riderName`, `riderLocation`, `riderEta`).

### Authentication (Sign Up / Log In / Logout)
See Section 8 for the full deep-dive. Summary: both "Sign Up" and "Log In" buttons call the exact same `useShopifySignIn().signIn()` hook — Shopify's Customer Account API is inherently passwordless, so there is no functional difference between the two entry points; they exist only to match a familiar UX pattern, per an explicit user request.

### Checkout (`app/checkout/address.tsx`, `app/checkout/webview.tsx`, `app/checkout/confirmation.tsx`)
- **address.tsx** — full order review: items list, price breakdown (subtotal/tax/delivery/total), address selection from saved Shopify addresses, delivery instructions (sent as Shopify cart attribute via `PUT /api/shopify/cart/note`). On "Continue to Payment": re-calls `prepareCheckout` with selected address (attaches `deliveryAddressPreferences` in `cartBuyerIdentityUpdate` so Shopify checkout opens with shipping pre-populated), navigates to webview.
- **webview.tsx** — `react-native-webview` displaying `cart.checkoutUrl`. Monitors URL for Shopify completion patterns (`thank_you`, `/orders/`, `order-status`). On completion: navigates to confirmation. Close button exits.
- **confirmation.tsx** — shows order confirmed, order reference (from URL or `/api/auth/me`), estimated delivery (30–45 min generic), ordered items (from CartContext snapshot before `clearCart()`), total paid, "View Orders" and "Continue Shopping" CTAs.

### Profile (`app/profile.tsx`)
Unchanged from Iteration 4 except the Order History menu row now correctly navigates to the fully-implemented Orders tab (not a placeholder — see Orders below).

### Navigation
See Section 3 "Navigation Architecture". `CustomTabBar.tsx` is a bespoke tab bar (not the default `expo-router` Tabs UI) specifically built so every tab reliably renders a `testID` on both native and web — this was a deliberate choice for testability, not just aesthetics.

### Animations
`AnimatedPressable.tsx` wraps `Animated.createAnimatedComponent(Pressable)` (not a `Pressable` containing a separate `Animated.View`, which was a real bug — see Section 14) to provide a press-scale-down micro-interaction used across cards, buttons, and icon buttons app-wide. `ErrorState`/`EmptyState` use `FadeIn`/`ZoomIn` entrance animations. Skeletons (`ProductCardSkeleton`, `CategoryCardSkeleton`, `SkeletonBlock`) provide shimmer-style loading placeholders instead of bare spinners for card-grid content.

### Theme
See Section 12 for full design rationale. Centralized in `src/theme/`; colors/typography/spacing are the single source of truth — never inline a hex color or magic-number spacing value in a screen/component.

### Typography
Platform system font (SF Pro / Roboto) via `Platform.select` — deliberately not a custom Google Font, to stay maximally native-feeling and avoid the platform-prohibited `@expo-google-fonts/*` packages. Scale: `h1` (32/800) → `h2` (24/700) → `h3` (18/700) → `body` (14/400) → `bodyBold` (14/600) → `small` (12/500) → `eyebrow` (10/700, uppercase, letter-spaced) — see `typography.ts`.

### Spacing
8pt-grid-based scale (`xs:4, sm:8, md:12, lg:16, xl:24, xxl:32, xxxl:48`) plus a `radius` scale (`sm:8` → `pill:9999`) and two shadow presets (`soft`, `elevation`) — see `spacing.ts`.

### Loading States
Every data-fetching screen distinguishes `isLoading` (skeletons or `ActivityIndicator`), `error` (`ErrorState` with a working Retry button — or a specific "Product not found" / "No cart to check out" state where the error is not transient), and empty (`EmptyState`) — this pattern is enforced by the shared `useAsyncData` hook and must be followed for any new data-fetching screen.

### Error Handling
Backend: every Shopify-facing service function raises a typed `ShopifyAPIError`/`CustomerAccountAPIError`/`AuthError` with a status code and a **user-safe** message (never a raw Shopify error string with internal details) — routers catch these and turn them into `HTTPException`s. Frontend: `apiClient.ts` throws a typed `ApiError` (message + status) for any non-2xx response; screens branch on `error`/`errorStatus` for the right UI state.

---

## 7. SHOPIFY INTEGRATION

### Storefront API
- **Purpose:** Public catalog (products, collections, search) + Cart mutations/queries.
- **Auth model:** A **private** Storefront API token (`SHOPIFY_STOREFRONT_API_TOKEN`), sent server-side-only as the `Shopify-Storefront-Private-Token` header (note: this is the *private* header, not the public `X-Shopify-Storefront-Access-Token` header used by client-side Storefront integrations — a deliberate choice so the token can never be safely used from a client even if leaked).
- **Endpoint:** `https://{SHOPIFY_STORE_DOMAIN}/api/{SHOPIFY_STOREFRONT_API_VERSION}/graphql.json`.
- **Client:** `backend/shopify_integration/client.py::ShopifyGraphQLClient` — a thin async `httpx` wrapper; also forwards the caller's IP as `Shopify-Storefront-Buyer-IP` for locale/pricing-context accuracy.

### Customer Account API
- **Purpose:** Passwordless customer authentication (OAuth2+PKCE) + customer profile/addresses/orders.
- **Auth model:** A **public, native-mobile OAuth client** (`SHOPIFY_CUSTOMER_ACCOUNT_CLIENT_ID`) — no client secret exists for this client type (PKCE replaces the need for one, per RFC 8252 for native apps).
- **Discovery:** OIDC discovery documents are fetched once and cached in-process:
  - `https://{SHOPIFY_STORE_DOMAIN}/.well-known/openid-configuration` → `authorization_endpoint`, `token_endpoint`.
  - `https://{SHOPIFY_STORE_DOMAIN}/.well-known/customer-account-api` → `graphql_api` endpoint for authenticated profile/address/order queries.
- **Scopes requested:** `openid email customer-account-api:full`.

### OAuth (full flow)
See Section 3 "Token Lifecycle" for the exact step-by-step. In short: Authorization Code + PKCE, native custom-scheme redirect, backend-only token exchange, backend-only token custody.

### PKCE
- **Generation location:** on-device, in `src/services/auth/pkce.ts`, using `expo-crypto`.
- **Verifier:** 64 cryptographically random bytes, base64url-encoded (far exceeds RFC 7636's 43-character minimum).
- **Challenge:** SHA-256 digest of the verifier, base64url-encoded (`code_challenge_method: "S256"`).
- **Lifetime:** held only in a local JS variable for the duration of a single `signIn()` call — never persisted to any storage, never sent anywhere except once, alongside the resulting authorization code, to the backend's token-exchange endpoint.

### Client Type
Native/mobile public client (custom URI scheme redirect), registered in the Shopify Customer Account API admin configuration with an exact, case-sensitive redirect URI matching `SHOPIFY_CUSTOMER_ACCOUNT_MOBILE_REDIRECT_URI`. **No web client is registered** — the backend intentionally hard-rejects any `platform="web"` authorize-url request with HTTP 400 (see Section 14, "SEC-001").

### Endpoints (backend, all under `/api/auth`)
| Method | Path | Purpose | Auth required |
|---|---|---|---|
| POST | `/auth/shopify/authorize-url` | Build Shopify authorize URL (native only). | No |
| POST | `/auth/shopify/token-exchange` | Exchange `{code, state, codeVerifier, redirectUri}` for a Now Kart session. | No |
| POST | `/auth/refresh` | Rotate refresh token. | Refresh token in body |
| POST | `/auth/logout` | Revoke refresh token server-side. | Refresh token in body |
| GET | `/auth/me` | Profile (name/email/addresses/orders with thumbnails). | Yes |
| GET | `/auth/orders?id=` | Full order detail (GID via query param — NOT path segment, NGINX-safe). | Yes |
| GET | `/auth/addresses` | List addresses. | Yes |
| POST | `/auth/addresses` | Create address. | Yes |
| PUT | `/auth/addresses` | Update address. | Yes |
| DELETE | `/auth/addresses` | Delete address. | Yes |

### Endpoints (backend, all under `/api/shopify`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/shopify/home` | Category groups + product rails. |
| GET | `/shopify/categories` | Category groups only. |
| GET | `/shopify/collections/{handle}/products?first=` | Products in a collection. |
| GET | `/shopify/products/{handle}` | Single product detail. |
| GET | `/shopify/search?q=&first=` | Live product search. |
| POST | `/shopify/cart` | Create cart. |
| GET | `/shopify/cart?cart_id=` | Fetch cart. |
| POST | `/shopify/cart/lines` | Add line. |
| PUT | `/shopify/cart/lines` | Update line quantity. |
| DELETE | `/shopify/cart/lines` | Remove line. |
| PUT | `/shopify/cart/note` | Set delivery instructions as cart attribute. |
| POST | `/shopify/checkout/prepare` | Validate stock + attach buyer identity + delivery address preferences; returns `checkoutUrl`. |

### Endpoints (backend, under `/api/tracking`)
| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/tracking/order?id=` | Live tracking status (stages, timeline, address, items, isActive flag). GID via query param (NGINX-safe). | Yes |

### CRITICAL: GID URL encoding rule
Shopify GIDs (`gid://shopify/Order/123`) contain slashes. Kubernetes NGINX double-decodes `%2F` → `/` when used as path segments, causing 404. **All Shopify GID endpoints MUST use `?id=encodeURIComponent(gid)` query params, not path segments.** This applies to both `/api/auth/orders` and `/api/tracking/order`.

### Authentication Flow (see Section 8 for the exhaustive version)
OAuth2 Authorization Code + PKCE, backend-mediated, native-only today.

### Environment Variables (Shopify-related — see Section 18 for the complete list)
`SHOPIFY_STORE_DOMAIN`, `SHOPIFY_STOREFRONT_API_TOKEN`, `SHOPIFY_STOREFRONT_API_VERSION`, `SHOPIFY_CACHE_TTL_SECONDS`, `SHOPIFY_CUSTOMER_ACCOUNT_CLIENT_ID`, `SHOPIFY_CUSTOMER_ACCOUNT_MOBILE_REDIRECT_URI`, `SHOPIFY_SHOP_ID`.

### GraphQL Operations
- **Storefront (`shopify_integration/queries.py`):** `COLLECTIONS_QUERY`, `COLLECTION_PRODUCTS_QUERY`, `SHOP_PRODUCTS_QUERY`, `PRODUCT_BY_HANDLE_QUERY`, `SEARCH_PRODUCTS_QUERY`, `CART_CREATE_MUTATION`, `CART_GET_QUERY`, `CART_LINES_ADD/UPDATE/REMOVE_MUTATION`, `CART_BUYER_IDENTITY_UPDATE_MUTATION` (includes `deliveryAddressPreferences`), `CART_ATTRIBUTES_UPDATE_MUTATION`.
- **Customer Account (`auth/customer_account_client.py`):** `ME_QUERY` (customer/orders[first:4 with images]/addresses), `ORDER_DETAIL_QUERY` (single order by ID with lineItems/fulfillments/shippingAddress/price breakdown), `ADDRESS_CREATE/UPDATE/DELETE_MUTATION`.

### CRITICAL API field: `territoryCode` (not `countryCode`)
Shopify Customer Account API 2026-07 uses `territoryCode` (ISO alpha-2, e.g. "GB") on `CustomerAddress` and `CustomerAddressInput`. The old `countryCode` field causes HTTP 400. This applies in: `ME_QUERY` addresses, `ORDER_DETAIL_QUERY` shippingAddress, `ADDRESS_CREATE/UPDATE_MUTATION` return fields, `PrepareCheckoutRequest` (`deliveryTerritoryCode`), `AddressIn`/`AddressOut` backend schemas, `Address`/`AddressInput` frontend types, and `addresses.tsx` form fields.

### Collections / Products / Cart / Checkout
All covered above and in Sections 3 and 6.

---

## 8. AUTHENTICATION (EXHAUSTIVE)

### OAuth Architecture
Backend-For-Frontend (BFF) pattern. The frontend never has Shopify OAuth client credentials or Shopify tokens. The backend is the only OAuth2 participant that talks to Shopify's token endpoint. See Section 3 "Token Lifecycle" for the numbered step-by-step and Section 7 for endpoint/scope detail.

### PKCE Implementation
See Section 7 "PKCE". Verified correct by an independent `security_audit_agent` review: 512-bit verifier entropy, correct S256 derivation, in-memory-only lifetime, never logged, never persisted.

### Token Flow
See Section 3 "Token Lifecycle" — this is intentionally documented once, in full, there; do not duplicate/diverge — always refer back to that section as the canonical description.

### Deep Linking
See Section 3 "Deep Linking". Native custom-scheme redirect captured directly by `expo-web-browser`'s `openAuthSessionAsync` (the OS intercepts the redirect before it would ever reach a normal app screen) — `app/auth/callback.tsx` is a defensive fallback only, not the primary flow.

### Session Handling
See Section 3 "Session Lifecycle". Access token 15 min, refresh token 30 days, single-use rotation, reuse-detection with family revocation, single-flight refresh guard on-device.

### Secure Storage
`src/utils/storage/` abstraction: `secureGet`/`secureSet`/`secureRemove` map to `expo-secure-store` (Keychain/EncryptedSharedPreferences) on native, and to AsyncStorage on web (there is no browser Keychain equivalent — this is an accepted, documented trade-off, not a security regression, since the web preview was never the intended production security boundary for this app; the real security boundary is the native build).

### Guest Mode
Always available. `isRestoring` (true only briefly on cold start while checking for a stored refresh token) is the only auth-related gate on rendering — it never blocks guest browsing; `isAuthenticated` being `false` simply means Profile shows a sign-in gate and Checkout/Addresses show guest-appropriate copy instead of real data. Guest requests to `/auth/me` and `/auth/addresses` correctly receive HTTP 401 (enforced server-side via `get_current_user_required`, not just hidden client-side).

### Logout
`AuthContext.signOut()`: best-effort `POST /api/auth/logout` (revokes server-side even if the network call fails, local state is cleared regardless — the user is never "stuck" logged in on-device), then `clearSession()` clears the in-memory access token, React state, and the stored refresh token via `storage.secureRemove`.

### Login / Signup
Both trigger `useShopifySignIn().signIn()` — identical flow. Per explicit user request, presented as two separate buttons in the UI for familiar UX, even though Shopify's Customer Account API has no concept of a distinct "signup" vs "login" request — Shopify itself decides whether the entered email is a new or existing customer during its own hosted flow.

### Passwordless Flow
Shopify's Customer Account API (2026) is passwordless by design: the shopper enters their email in Shopify's own hosted UI (reached via the system browser), Shopify emails a verification code or magic link, and upon verification Shopify redirects back to the app with an authorization code. Now Kart never collects, sees, or stores a password.

### Native OAuth Status (read this before assuming authentication is production-ready)
This status is intentionally explicit and uses exactly the four states below — do not summarize it as simply "done" or "working" anywhere else in the project's documentation.
- **Code implemented:** Yes — PKCE generation, authorize-URL building, system-browser launch, redirect capture, code-exchange call, session issuance, storage, refresh, and logout are all fully coded on the frontend (`useShopifySignIn.ts`, `AuthContext.tsx`, `services/auth/*`) and backend (`auth/service.py`, `auth/customer_account_client.py`, `auth/router.py`).
- **Backend implemented:** Yes — the backend performs the actual token exchange with Shopify, encrypts and stores Shopify tokens, and issues Now Kart's own JWT+refresh session; this logic is exercised directly by backend `pytest` (31/31 passing as of the last test round) for every branch that does not require a real Shopify-issued authorization code (native-200/web-400/guest-401/garbage-token-401/invalid-refresh/invalid-logout).
- **Browser/testing-agent verification completed:** Yes, for everything reachable without a real Shopify authorization code — the web-platform short-circuit (`Platform.OS === 'web'` shows a graceful "sign-in is available in the mobile app" message instead of attempting an impossible flow), guest gating (401s enforced server-side), and the Iteration 4 blank-screen bug (Bug 4, Section 14) were all found and fixed via this method.
- **End-to-end native iOS/Android verification: PENDING — this has never been performed.** No one (agent, testing_agent, or user) has completed a real Shopify email-verification login on a real device against this codebase as of this handover.
- **Why this cannot be verified in Expo Go or a browser preview:** The final step of the flow is Shopify redirecting the system browser back into the app via a registered **native custom URI scheme** (`expo.scheme` in `app.json`), which only OS-level deep-link handling can intercept — Expo Go uses its own `exp://` scheme sandbox (it cannot register a third-party app's custom scheme), and a browser has no OS-level app-redirect concept at all (which is also why no web OAuth client is registered for this project — see Section 13). Only a real development or production build, installed on a real device (or emulator/simulator with proper scheme handling), can complete this redirect. This is a platform/protocol constraint, not a testing gap that more browser automation could close.
- **Practical consequence:** Orders-with-real-data and Addresses-CRUD-as-a-real-customer (Section 6) are subject to this exact same boundary — they are code-complete, not feature-incomplete, but unverified against a real signed-in identity.

### Current Implementation Status
**Code-complete and passing every test this preview environment can run** for everything that does not require completing a real email-verification round-trip (see "Native OAuth Status" immediately above, and Section 15/17/24 for how this is tracked going forward).

### Known Issues
- Real OAuth completion (past the point of opening Shopify's hosted login) cannot be exercised in Expo Go or the web preview — **not a bug**, a platform/protocol limitation requiring a native dev/production build.
- No rate limiting on `/auth/refresh`, `/auth/logout`, `/auth/shopify/*` endpoints (P3, deferred — see Section 15).
- CORS is currently `allow_origins=["*"]` with `allow_credentials=True` (P3, deferred — low practical risk since auth uses Bearer tokens, not cookies, but should be tightened before production).

### Remaining Work
- Wire the Profile screen's order-history section to the real `orders` data the backend already fetches.
- Tighten CORS + add rate limiting before production (Section 15).
- Once a native build exists, do a full real-device OAuth completion test (this document explicitly could not verify that end-to-end, by design/necessity).

---

## 9. BACKEND (MODULE-BY-MODULE)

### `server.py`
Entrypoint. Loads `.env` via `load_dotenv()` (must happen **before** importing `shopify_integration`/`auth` modules, which read `os.environ` at import time — this ordering is deliberate and fragile if reordered carelessly). Connects to MongoDB. Mounts a legacy generic `/api` router (pre-existing template scaffold: `GET /api/`, `POST /api/status`, `GET /api/status` — not used by any real Now Kart feature, safe to ignore or eventually remove), `shopify_router` at `/api/shopify`, `auth_router` at `/api/auth`. Adds permissive CORS middleware. Registers a startup hook (`ensure_indexes()` for the auth Mongo collections) and a shutdown hook (close the Mongo client).

### `shopify_integration/` module
- **`config.py`** — `ShopifySettings`, reads `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_STOREFRONT_API_TOKEN`, `SHOPIFY_STOREFRONT_API_VERSION`, `SHOPIFY_CACHE_TTL_SECONDS` (default 90s) from env; exposes `graphql_endpoint` property.
- **`client.py`** — `ShopifyGraphQLClient.execute(query, variables, buyer_ip)`; raises `ShopifyAPIError` with an appropriate status code for 401 (bad token), 429 (rate limit), other 4xx/5xx, or GraphQL-level `errors`.
- **`queries.py`** — all raw GraphQL strings; `PRODUCT_FIELDS`/`CART_FIELDS` are shared fragments interpolated into multiple queries/mutations.
- **`mappers.py`** — pure functions mapping raw Shopify GraphQL nodes to the Pydantic `*Out` schemas (`map_product`, `map_collection`, `map_cart`) — this is the one place that would need updating if Shopify's schema shape changes.
- **`schemas.py`** — see Section 7's endpoint table for the shapes; notably `CheckoutPrepareOut` = `{cart, isValid, issues[], checkoutUrl}`.
- **`collection_groups.py`** — static, hand-maintained mapping; the one place a developer would edit to change which Shopify collections feed which Home sections.
- **`cache.py`** — generic `TTLCache` with `get/set/pop/invalidate_prefix`; used both for Shopify read-through caching here AND (imported into `auth/service.py`) for the OAuth `state` cache — a deliberate, lightweight reuse rather than building a second cache class.
- **`service.py`** — all business logic; notably `_validate_cart_lines` (fixed in Iteration 4, see Section 14) and `attach_buyer_identity`/`prepare_checkout` (checkout foundation, no payment).
- **`router.py`** — thin FastAPI routes; the only place `shopify_integration` imports from `auth` (`get_current_user_optional`, `auth_service.get_valid_shopify_access_token`) to optionally attach buyer identity.

### `auth/` module
- **`config.py`** — `AuthSettings`, reads `SHOPIFY_CUSTOMER_ACCOUNT_CLIENT_ID`, `SHOPIFY_CUSTOMER_ACCOUNT_MOBILE_REDIRECT_URI`, `SHOPIFY_SHOP_ID`, `SHOPIFY_STORE_DOMAIN`, `JWT_SECRET_KEY`, `JWT_ALGORITHM` (default HS256), `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 15), `SESSION_REFRESH_TOKEN_EXPIRE_DAYS` (default 30), `TOKEN_ENCRYPTION_KEY` (Fernet key).
- **`customer_account_client.py`** — OIDC discovery (cached in-process, resets only on process restart), `build_authorize_url`, `exchange_code`, `refresh_access_token`, `customer_graphql` (authenticated profile/address/order calls), plus `ME_QUERY`/`ADDRESS_*_MUTATION` GraphQL strings.
- **`security.py`** — `encrypt_secret`/`decrypt_secret` (Fernet), `create_access_token`/`decode_access_token` (JWT), `generate_refresh_token`/`hash_refresh_token` (SHA-256), `generate_state`.
- **`db.py`** — `users_collection`, `refresh_tokens_collection`, `ensure_indexes()` (unique index on `users.shopifyCustomerId`; non-unique indexes on `auth_refresh_tokens.tokenHash` and `.userId`).
- **`schemas.py`** — see Section 7's endpoint table.
- **`service.py`** — the heart of the auth module: `build_authorize_url` (rejects `platform="web"`), `exchange_code` (validates + single-use-pops `state`, calls the Customer Account client, upserts the `users` doc, issues a session), `refresh_session` (reuse-detection + family revocation), `logout`, `get_valid_shopify_access_token` (transparent Shopify-token refresh, never raises — returns `None` on failure so callers degrade to guest), `get_profile`, `create_address`/`update_address`/`delete_address`.
- **`dependencies.py`** — `get_current_user_optional` (never raises, returns `None` for guests/invalid tokens), `get_current_user_required` (raises 401 if no user) — both are plain FastAPI `Depends` functions used across both `auth/router.py` and `shopify_integration/router.py`.
- **`router.py`** — see Section 7's endpoint table; exports `router`, `get_current_user_optional`, `get_current_user_required` via `__all__` specifically so `shopify_integration.router` can import the dependency functions without needing to duplicate auth logic.

### Backend Security Practices
See Section 13 for the consolidated list.

### Backend Logging
Standard Python `logging`, INFO level, format `%(asctime)s - %(name)s - %(levelname)s - %(message)s`. Every Shopify/Customer-Account error path logs a status code and (for GraphQL errors) the error payload — **never** a token, header value, or full request/response body containing sensitive data. This was explicitly verified (grep of all backend logs + all API responses + the entire frontend source tree found zero token leakage) during Iteration 3 testing.

### Middleware
Only `CORSMiddleware`, currently permissive (`*` origins). No auth middleware at the ASGI level — auth is enforced per-route via FastAPI `Depends`, not a global middleware.

### Error Handling
See Section 6 "Error Handling" and Section 9 module descriptions above — typed exceptions (`ShopifyAPIError`, `CustomerAccountAPIError`, `AuthError`) each carrying a status code and a user-safe message, caught at the router layer and turned into `HTTPException`.

### Token Management
See Section 3 "Token Lifecycle" (canonical) — backend never exposes a Shopify token to any response schema; every schema in both `shopify_integration/schemas.py` and `auth/schemas.py` was reviewed and contains no token field.

---

## 10. FRONTEND (SCREEN-BY-SCREEN + INFRASTRUCTURE)

### Screens
All listed with purpose in Section 6. Full list: `(tabs)/index` (Home), `(tabs)/categories`, `(tabs)/orders` (placeholder), `search`, `collection/[handle]`, `product/[handle]`, `cart`, `profile`, `wishlist`, `addresses`, `checkout/address`, `auth/callback` (safety-net only).

### Navigation
See Section 3 "Navigation Architecture" and "Component Hierarchy".

### Contexts / Providers
- `AuthContext` (`src/features/auth/AuthContext.tsx`) — session state, restore-on-mount, silent refresh (single-flight-guarded), sign-out, `refreshProfile`.
- `WishlistContext` (`src/features/wishlist/WishlistContext.tsx`) — local wishlist CRUD + persistence.
- `CartContext` (`src/features/cart/CartContext.tsx`) — guest-first Shopify cart state + persistence.
All three are mounted once in `app/_layout.tsx` and consumed via their respective `useAuth()`/`useWishlist()`/`useCart()` hooks — **never** re-instantiate a provider inside a nested screen.

### State Management
See Section 3. No Redux/Zustand. `useMemo`/`useCallback` are used pervasively inside contexts to keep consumer re-renders minimal.

### Hooks
- `useAsyncData` (`src/shared/hooks/useAsyncData.ts`) — generic data-fetching hook, the standard for any screen-level fetch.
- `useShopifySignIn` (`src/features/auth/useShopifySignIn.ts`) — the OAuth2+PKCE sign-in flow.
- `useAuth`, `useWishlist`, `useCart` — context accessors (throw if used outside their provider, by design, to catch mounting mistakes early).
- `use-icon-fonts` (`src/hooks/use-icon-fonts.ts`) — loads icon fonts via `expo-font`.

### Services
- `src/services/api/apiClient.ts` — the single fetch wrapper every repository uses; attaches `Authorization: Bearer <token>` automatically, retries exactly once after a successful silent refresh on a 401, throws a typed `ApiError` otherwise.
- `src/services/auth/pkce.ts` — PKCE generation.
- `src/services/auth/sessionToken.ts` — module-level (non-React) current-access-token holder + the registered refresh handler + the single-flight guard (`attemptSilentRefresh`) that both the proactive refresh timer (in `AuthContext`) and the reactive 401-retry (in `apiClient`) funnel through, so they can never race each other.

### Reusable Components (`src/shared/components/`)
`AnimatedPressable`, `Button`, `CategoryCard` (+`CategoryCardSkeleton`), `CategoryGroupSection`, `CustomTabBar`, `DeliverySelector`, `EmptyState`, `ErrorState`, `FormField`, `FreeDeliveryBanner`, `Header`, `IconButton`, `LoadingSpinner`, `PillBadge`, `ProductCard` (+`ProductCardSkeleton`), `QuantityStepper`, `SearchBar`, `SectionHeader`, `SkeletonBlock`, `ThemedText` — all re-exported from `src/shared/components/index.ts` for clean imports (`import { Button, ThemedText } from '@/src/shared/components'`).

### UI Architecture
Every component is a plain functional component + `StyleSheet.create()`; no styled-components, no CSS. `ThemedText` centralizes typography-variant + color application so no screen hand-rolls `fontSize`/`fontWeight`. `IconButton` centralizes the badge-count overlay pattern used by the Header's wishlist/cart icons.

---

## 11. TESTING

### Testing Strategy
Two layers: (1) backend `pytest` suites (`backend/tests/`) exercising every endpoint including error paths and guest-vs-authenticated gating; (2) an autonomous `testing_agent` that drives real Playwright browser automation against the running preview to verify actual UI behavior, screenshots, console/page errors, and navigation flows — this agent also has the authority to find AND fix bugs directly (its fixes are reviewed via `git diff` by whoever invokes it).

### Regression Testing
Every iteration's test pass explicitly re-verified all *previously* passing functionality, not just the new feature — this is a standing project rule (see `test_result.md`'s `agent_communication` log for the full chronological record).

### Testing Agent Usage
Always: (a) read `test_result.md` first; (b) provide the agent full context (it has no memory across invocations) including exactly what to test, which files are relevant, any credentials, and whether backend/frontend/both should be exercised; (c) read its returned `/app/test_reports/iteration_{n}.json` and its summary; (d) fix every reported issue (regardless of severity) before proceeding; (e) re-invoke for a focused retest of just the fixes if the first pass found issues.

### Known Passing Tests
- Backend: **31/31 pytest** as of the final Iteration 4 verification pass (`test_shopify_integration.py` + `test_auth_endpoints.py` combined) — covers home/categories/collections/product/search/full cart lifecycle, duplicate-variant-merge, 404/422 handling, native authorize-url success, web-platform-rejected (400), guest 401 on protected routes, garbage-token 401, refresh/logout invalid-token handling (no 500s).
- Frontend (via Playwright through the testing agent): Home/Categories/Collection/Search/Product/Cart/Navigation, cart add/badge-sync/inc-dec/remove/persistence, wishlist add/remove/badge-sync/persistence, guest browsing, Profile sign-in gate, checkout-prep happy path with real store data, checkout/address no-cartId error state — **all verified passing** as of the final Iteration 4 pass.

### Known Failing Tests
**None outstanding** as of this handover. (Historical failures were found and fixed within the same iteration they were discovered — see Section 14 for the full chronological bug list; none are currently open.)

### Current Authentication Issue
**None open.** The one authentication-adjacent bug (the web blank-screen issue caused by `expo-secure-store` having no web support) was root-caused and fixed in Iteration 4 (see Section 14). If a future engineer encounters a *new* auth-related bug, the standing project rule (see `PROJECT_MEMORY.md`) is: never suggest "clear cache / hard refresh" as a fix; always check `test_credentials.md`, backend logs, and cross-reference against the Shopify Customer Account API playbook before changing auth code.

### Current Debugging Status
Clean. No open investigation.

### Remaining Testing Required
- Real-device native-build OAuth completion (email verification round-trip) — cannot be done in this preview environment by design; must be done after the user generates an iOS/Android build (Section 8, Section 17 Milestone 1).
- Once a native build exists and a real customer can sign in, a dedicated `testing_agent` pass for the Orders tab's authenticated branch (real order list rendering) and Addresses CRUD as a real signed-in customer — both are code-complete but have never rendered against a real authenticated session (see Section 6 "Orders").
- Once checkout completion/payments are implemented, an entirely new, dedicated security + functional test pass (payments are a materially higher-risk surface than anything tested so far).

---

## 12. UI / UX DECISIONS

- **Dark theme, always-on (no light mode toggle exists).** Background `#0B0710` (near-black with a violet tint), surface `#100C18`. This was derived directly from the source Shopify storefront's own visual design — see `design_guidelines.json` and the explicit comment in `colors.ts`: "Source of truth: Shopify storefront... DO NOT invent new colors here."
- **Primary accent violet/purple (`#8B5CF6`, gradient `#9333EA`→`#7C3AED`)** — used for the "KART" wordmark, active states, buttons, borders.
- **Product cards use a white background (`#FFFFFF`)** even though the app is otherwise dark — this mirrors real grocery-app product photography conventions (white product-card backgrounds make food photography pop against a dark shell) and matches the source storefront.
- **Category cards use a soft lavender background (`#F3E8FF`)** for visual distinction from product cards.
- **Typography:** platform-native system font only (no custom webfont) — see Section 6 "Typography". Chosen for maximum native feel and to avoid the platform-prohibited Google-Fonts packages.
- **Spacing:** strict 8pt grid (Section 6 "Spacing") — never use an arbitrary pixel value in a new component; always reference `spacing.*`.
- **Product Detail image:** changed in Iteration 3.5 from a fixed-height rectangle to a true `aspectRatio: 1` square with consistent inner padding, specifically to fix an "unbalanced"/excess-whitespace look the user flagged, benchmarked against Uber Eats/Zepto/Blinkit-quality product imagery presentation. **This is a locked-in decision — do not revert to a fixed-height rectangle without a new explicit request.**
- **Product card titles:** changed in Iteration 3.5 from 1-line truncation to 2-line wrap with a fixed `minHeight`, so every card in a grid/row stays the exact same height regardless of title length (verified via testing: 20+ products measured, zero height variance). **Locked-in decision.**
- **Bottom navigation:** exactly 3 tabs (Home, Categories, Orders) matching the source storefront's own 3-tab pattern — a bespoke `CustomTabBar` (not the default expo-router Tabs UI) was built specifically to guarantee reliable `testID`s cross-platform.
- **Icons:** `@expo/vector-icons` (Ionicons family) exclusively — heart-outline (wishlist), bag-handle-outline (cart), person-outline (account), flash (brand bolt), chevron-back (back buttons), alert-circle-outline (issue rows), cloud-offline-outline (error state), lock-closed-outline (payment-coming-soon).
- **Buttons:** a single shared `Button` component with variants (`outline` used for secondary actions like "Manage Addresses"), always full-width on form-like screens for maximal thumb-friendliness, `disabled` state used explicitly for the not-yet-implemented "Continue to Payment" CTA (rather than hiding it — so users understand the feature exists and is coming, not missing).
- **Loading:** skeleton shimmer for card-grid content (`ProductCardSkeleton`, `CategoryCardSkeleton`, `SkeletonBlock`), plain `ActivityIndicator` for full-screen/section loading (e.g., checkout-prep, profile fetch).
- **Transitions:** `slide_from_bottom` for modal-like screens (cart, search), `slide_from_right` for "drill-in" detail screens (product, collection, profile, wishlist, addresses, checkout address), `fade` for the auth callback safety net — configured per-`Stack.Screen` in `app/_layout.tsx`, never a blanket `transition: all`-style universal animation (explicitly prohibited by the platform's general design guideline).
- **Micro-interactions:** every tappable card/button uses `AnimatedPressable`'s press-scale-down (`scaleTo` prop, typically 0.94–0.98) rather than a flat opacity change, for a more tactile feel.
- **Free-delivery banner:** a dismissible, non-blocking floating banner on Home — a real bug (the entire banner intercepted underlying product-card taps) was fixed so only its own close button is interactive; this must never regress (see Section 14).

---

## 13. SECURITY

### OAuth
Authorization Code + PKCE only; no implicit flow, no resource-owner-password flow (Shopify's Customer Account API doesn't offer one anyway — it's inherently passwordless). `redirect_uri` for native is a fixed, backend-controlled constant (`settings.mobile_redirect_uri`), never derived from client input. `platform="web"` requests are hard-rejected server-side (HTTP 400) precisely because accepting a client-supplied `origin` to build a web `redirect_uri` would be an open-redirect / auth-code-interception vector if a web OAuth client were ever registered — this was a real MEDIUM finding from a `security_audit_agent` review, fixed pre-emptively even though no web client exists today.

### PKCE
See Section 7/8. Independently verified correct (entropy, S256 derivation, in-memory-only lifetime).

### Backend Communication
All Shopify communication happens server-side only, over HTTPS, via `httpx.AsyncClient`. The frontend talks only to Now Kart's own `/api/*` — enforced architecturally (repositories only know `/api/shopify/*` and `/api/auth/*` paths) and verified by a full source-tree grep for any Shopify token/domain reference in frontend code (none found).

### Token Storage
- **Shopify tokens (access + refresh):** MongoDB, Fernet-encrypted at rest, keyed by `shopifyCustomerId`. Never returned in any API response. Never logged (only HTTP status codes and GraphQL error *messages*, never headers/payloads, are logged).
- **Now Kart's own refresh token:** MongoDB, stored only as a SHA-256 hash (never the raw token) — even a full database compromise cannot yield a usable refresh token directly.
- **Now Kart's own access token (JWT):** not stored server-side at all (stateless, verified by signature + expiry on each request).
- **On-device:** `storage.secure*` → Keychain/EncryptedSharedPreferences on native, AsyncStorage on web (documented trade-off, not a regression).

### Secrets
All secrets (`JWT_SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, `SHOPIFY_STOREFRONT_API_TOKEN`, `SHOPIFY_CUSTOMER_ACCOUNT_CLIENT_ID`, `MONGO_URL`) live only in `backend/.env`, loaded via `python-dotenv`, never hardcoded in source, never logged. `.env` was added to `.gitignore` (backend and frontend) during Iteration 4 hardening specifically to reduce the risk of accidental commit.

### API Security
- Guest-vs-authenticated gating enforced server-side via FastAPI `Depends` (`get_current_user_required`), not just client-side UI hiding — verified by direct testing (unauthenticated requests to `/auth/me`/`/auth/addresses` correctly return 401 with no data).
- OAuth `state` parameter: single-use (popped from the TTL cache on first successful exchange, not just read) — prevents replay within the cache's TTL window.
- Refresh-token rotation: single-use; reuse of an already-rotated token triggers **family-wide revocation** of every other active session for that user (treated as a compromise signal), not just a 401 to the one caller.
- Concurrent-refresh race: eliminated on-device via a single-flight guard (`attemptSilentRefresh`) shared by both the reactive (401-triggered) and proactive (timer-based) refresh paths.

### Shopify Communication
Storefront API uses the **private** token header server-side-only; Customer Account API uses PKCE (no client secret needed for this public-native client type); both over HTTPS with 10–15s timeouts and graceful `503`-style user-facing messaging on transport failure.

### Environment Variables
See Section 18 — names only, values never appear in any document, log, or response.

### Future Improvements (not yet implemented — see Section 15)
- Rate limiting on `/api/auth/*` endpoints (P3).
- Tighten CORS from `allow_origins=["*"]` to an explicit allowlist before production (P3).
- Once payments are added: a dedicated, deeper security review of that specific surface (PCI-relevant concerns, webhook signature verification if Shopify webhooks are introduced, etc.) — do not reuse this document's security sign-off as coverage for a not-yet-built payments feature.

---

## 14. BUGS FIXED (CHRONOLOGICAL)

### Bug 1 — `AnimatedPressable` broke tab-bar layout
- **Root cause:** A `Pressable` containing a separate nested `Animated.View` disrupted flex layout/spacing in the custom tab bar.
- **Files modified:** `src/shared/components/AnimatedPressable.tsx`.
- **Solution:** Switched to `Animated.createAnimatedComponent(Pressable)` — a single animated component, not a wrapper-around-a-child pattern.
- **Regression testing:** Verified via screenshot + subsequent full regression passes; never recurred.
- **Lesson:** When animating a `Pressable`, animate the `Pressable` itself via `Animated.createAnimatedComponent`, don't nest an `Animated.View` inside it if the `Pressable`'s own layout participates in a flex row/tab bar.

### Bug 2 — Free-delivery banner intercepted underlying product-card taps
- **Root cause:** The entire floating banner overlay was interactive, creating a dead zone over content beneath it.
- **Files modified:** `src/shared/components/FreeDeliveryBanner.tsx`.
- **Solution:** Restricted interactivity to only the banner's own close button; the informational area no longer blocks touches to underlying content.
- **Regression testing:** Verified via testing_agent interaction/screenshot passes; re-confirmed in later regression runs.
- **Lesson:** Any dismissible floating overlay must scope its touch-handling narrowly — never let a decorative/informational region silently swallow taps meant for content underneath.

### Bug 3 — Product Detail 404 showed a generic retry state instead of "Product not found"
- **Root cause:** `useAsyncData` didn't surface the HTTP status code of a failed fetch, so Product Detail couldn't distinguish a genuine 404 from a transient network error — both rendered the same generic `ErrorState` with a pointless Retry button (retrying a 404 will never succeed).
- **Files modified:** `src/shared/hooks/useAsyncData.ts` (added `errorStatus` to the returned state), `app/product/[handle].tsx` (branches to a dedicated "Product not found" state on 404).
- **Solution:** As above.
- **Regression testing:** Dedicated testing_agent retest confirmed: valid handle still renders unchanged; nonexistent handle shows "Product not found" (not an infinite retry loop); genuine transient errors still show the generic `ErrorState` with a working Retry.
- **Lesson:** Any generic data-fetching hook that powers user-facing error UI should expose enough information (at minimum, HTTP status) for the consuming screen to distinguish "this will never succeed on retry" (404) from "this might succeed on retry" (network blip, 5xx).

### Bug 4 — CRITICAL: Web preview showed a completely blank white screen
- **Root cause:** `AuthContext.tsx`'s session-restore effect called `expo-secure-store` directly (`SecureStore.getItemAsync`/`setItemAsync`/`deleteItemAsync`), which has **zero web support** — it throws (`getValueWithKeyAsync is not a function`) on every web mount. The effect's `try/finally` (no `catch`) let this become an uncaught exception at the React root on every single web page load — manifesting as: 0 DOM children under `#root`, zero console output, zero page/pageerror events (because the crash happened before React ever attached its own dev-mode error-overlay listeners in a way that surfaced to the outer page).
- **Discovery:** Found by an independent `testing_agent` Playwright investigation after the main agent's own repeated screenshot attempts (12+, including full Metro restarts, cache clears, and a `git stash` isolation test proving it was NOT caused by that session's own unrelated edits) reproduced the same blank screen consistently.
- **Files modified:** `src/features/auth/AuthContext.tsx` — all 5 `SecureStore.*` call sites switched to the project's own **pre-existing** `src/utils/storage` abstraction (`storage.secureGet`/`secureSet`/`secureRemove`), which already had the correct native/web split built in.
- **Solution:** No new architecture was invented — the fix reused an abstraction that already existed elsewhere in the codebase but simply hadn't been adopted yet in `AuthContext.tsx`.
- **Regression testing:** Verified: home/categories/product/cart/wishlist/profile all navigate cleanly with zero console/page errors; re-confirmed again in a second, independent follow-up testing pass (~10 fresh navigations, zero blank-screen recurrences).
- **Lesson (critical, add to permanent memory):** **Never call `expo-secure-store` directly in any new code.** Always use `src/utils/storage`'s `secureGet`/`secureSet`/`secureRemove`. This is now a standing, non-negotiable project rule (see `PROJECT_MEMORY.md`).

### Bug 5 — HIGH: Checkout stock-validation false-positive blocked every product
- **Root cause:** `_validate_cart_lines` (backend) flagged a line as invalid whenever `quantityAvailable < quantity`, without checking whether `quantityAvailable` was a genuinely limiting number or simply `0` because the merchant has "continue selling when out of stock" enabled (in which case Shopify's own `availableForSale` remains `true` and the item is genuinely purchasable). This store's real data has `quantityAvailable=0` + `availableForSale=true` on essentially every variant, so checkout-prep always returned `isValid: false` for every real cart.
- **Files modified:** `backend/shopify_integration/service.py::_validate_cart_lines`.
- **Solution:** Only flag a line as blocking when either (a) `availableForSale` is `false` (hard out-of-stock), or (b) `quantityAvailable` is a **positive** number smaller than the requested quantity (a genuine limited-stock overage). A `quantityAvailable` of exactly `0` combined with `availableForSale: true` is no longer treated as an issue.
- **Regression testing:** Verified via a direct API test (`POST /api/shopify/checkout/prepare` now returns `isValid: true, issues: []` for real store data) and the full UI happy path (Categories → add product → Cart → Proceed to Checkout → address-selection screen now renders instead of the previous blocker).
- **Lesson:** When validating Shopify inventory client- or server-side, always account for the merchant's "continue selling when out of stock" policy — `availableForSale` is the authoritative purchasability signal Shopify already computes for you; `quantityAvailable` alone is not sufficient to determine whether an item is blockable.

### Bug 6 — LOW: `/checkout/address` spun forever with no `cartId` param
- **Root cause:** The screen's `load()` callback did an early `if (!cartId) return;` without ever calling `setIsLoading(false)`, leaving the `ActivityIndicator` spinning indefinitely if the screen was ever reached (e.g. via a malformed deep link) without a `cartId` query param.
- **Files modified:** `app/checkout/address.tsx`.
- **Solution:** The no-`cartId` case now immediately sets `isLoading=false` and a clear error ("No cart to check out. Please add items to your cart first."), rendered via the existing `ErrorState` component with a button that navigates back rather than a pointless "Try again" retry.
- **Regression testing:** Verified: navigating with no `cartId` shows the error state immediately (no infinite spinner); navigating with a valid `cartId` still works normally.
- **Lesson:** Any early-return guard clause inside an async `load()`/`fetch` callback must always resolve the loading state on every code path, including the ones that exit before the "main" fetch logic.

### Additional Iteration-4 Hardening (not "bugs" per se, but defense-in-depth changes made proactively after `code_review_agent`/`security_audit_agent` reviews — listed here for completeness)
1. Frontend single-flight guard on silent token refresh (eliminates a theoretical concurrent-refresh race that could have caused spurious sign-outs).
2. Backend hard-rejects `platform="web"` OAuth authorize requests (closes an unvalidated-redirect finding, SEC-001).
3. OAuth `state` made single-use (popped, not just read).
4. Refresh-token reuse now triggers session-family-wide revocation.
5. `.env` added to `.gitignore` (backend and frontend).

---

## 15. KNOWN ISSUES (PRIORITIZED)

### Critical
*(None open.)*

### High
*(None open.)*

### Medium
*(None open — the two MEDIUM findings from the Iteration 4 code/security review were both fixed: the concurrent-refresh race and the unvalidated web-redirect-origin finding. A third MEDIUM code-review concern — the buyer-identity token type used in `cartBuyerIdentityUpdate` — was investigated via live 2026 Shopify documentation research and confirmed to be the **correct** implementation, not a bug.)*

### Low
1. **No rate limiting on `/api/auth/*` endpoints** (authorize-url, token-exchange, refresh, logout). Deferred as low-risk for the current MVP stage. Recommended before production: per-IP/per-identity throttling.
2. **CORS is `allow_origins=["*"]` with `allow_credentials=True`** in `server.py`. Practical risk is limited today because auth uses Bearer tokens (not cookies), but should be tightened to an explicit allowlist before production.
3. **Orders tab and Profile's "Order History" row are code-complete but their authenticated branch has never been exercised against a real signed-in customer** (Implemented — untested boundary; requires native OAuth, see Section 6 "Orders" and Section 8). This is **not** a UI placeholder — an earlier internal draft of this document incorrectly described it as one; that description has been corrected throughout this document.
4. **date-fns and dayjs are both present as dependencies** — likely redundant; verify which is actually used before adding new date-formatting logic, and consider removing the unused one in a future cleanup pass. **[ASSUMPTION — not confirmed which, if either, is dead weight.]**
5. **The generic `/api/`, `/api/status` routes in `server.py`** are leftover template scaffolding, unrelated to any real Now Kart feature — harmless, but could be removed in a future cleanup pass.
6. **`backend/requirements.txt` contains many dependencies unrelated to Now Kart** (e.g. `stripe`, `openai`, `google-generativeai`, `google-genai`, `boto3`, `emergentintegrations`, `litellm`, `python-jose`) — these are pre-provisioned by the base Emergent environment template, not installed for or used by any Now Kart feature. **Do not assume any Stripe/OpenAI/Gemini/AWS integration exists in this app** — none does. See Section 22 "Technical Debt" and the Migration Guide (Section 20).

---

## 16. DEVELOPMENT TIMELINE

### Iteration 1 — Initial Now Kart UI
- **Objective:** Pixel-accurate implementation of an existing Shopify storefront's UI as a mobile app.
- **Implementation:** User initially requested Flutter; the CLI was unavailable in this environment (`flutter: command not found`, shell-verified); user explicitly approved a pivot to React Native + Expo. Built the Shopify-inspired Now Kart UI, Expo Router navigation, shared components, and (at this stage) **mock data** standing in for the eventual live catalog.
- **Files:** Initial versions of `app/(tabs)/*`, `src/shared/components/*`, `src/theme/*`.
- **Problems encountered:** Flutter unavailable.
- **Solutions:** React Native + Expo, user-approved.
- **Testing:** Manual/screenshot-based at this stage.
- **Outcome:** A working, visually-matching UI shell with mock data.

### Iteration 3 — Shopify Storefront API integration
- **Objective:** Replace all mock data with live Shopify Storefront API data: catalog, collections, products, search, variants, inventory, pricing, images, guest cart. Explicit constraints: backend-only Shopify communication; Storefront token in `backend/.env` only; no customer auth, no payments, no checkout completion, no order history, no rider/merchant/admin.
- **Implementation:** Built `backend/shopify_integration/*` end-to-end; migrated frontend to `productRepository`/`cartRepository` + `CartContext`.
- **Files modified:** All of `backend/shopify_integration/`, `frontend/src/repositories/{product,cart}Repository.ts`, `frontend/src/features/cart/CartContext.tsx`, all catalog-facing screens.
- **Problems encountered:** Shopify cart/line IDs are GIDs containing `://` and `?` — decided to always pass them via query string/JSON body, never as raw URL path segments, to avoid encoding pitfalls.
- **Testing:** First full testing_agent pass — 18/18 backend pytest, ~95% frontend pass; found the Product-Detail-404 bug (Bug 3 above), fixed, retested and closed. Full token-leakage grep across logs/responses/frontend source found zero leaks.
- **Outcome:** PASSED, live Shopify data fully integrated, zero mock data remaining.

### Iteration 3.5 — UI polish
- **Objective:** Two small, surgical, style-only fixes requested by the user before starting auth work: Product Detail image container → true square; ProductCard title → 2-line wrap with fixed card height. Explicit instruction: do not touch missing-image fallback behavior (confirmed a Shopify data gap, not a bug).
- **Implementation:** CSS-only changes in the Product Detail screen and `ProductCard.tsx`.
- **Testing:** Full regression pass — zero regressions; image measured exactly 327×327px square on 2 products; card heights measured identical (220px) across 20+ products including long-title cards.
- **Outcome:** PASSED, zero regressions, both changes confirmed style-only.

### Iteration 4 — Customer Authentication + Checkout Foundation
- **Objective:** Shopify Customer Account API passwordless Sign Up/Log In/Logout (OAuth2+PKCE, backend-mediated), session persistence/restoration, guest mode preserved, local wishlist + badge sync, Profile screen (name/email/addresses-placeholder/orders-placeholder/logout), address management, checkout foundation (cart validation + address selection + buyer-identity attachment, explicitly no payments). Preserve existing UI; add only necessary new screens.
- **Architecture research:** Initial architecture proposal (backend holding the PKCE verifier) was challenged by the user and corrected: PKCE must be generated and held **on-device**, in memory only, per native-app OAuth best practice (RFC 8252) — the backend only ever receives the resulting `{code, code_verifier}` pair once, for the actual token exchange.
- **Integration research:** A first `integration_playbook_expert_v2` call incorrectly returned merchant/Admin/Partner OAuth guidance (wrong flow entirely — explicitly not used); a second call returned the correct Shopify Customer Account API (headless, Expo/React Native) playbook, which is what was actually implemented. User then supplied the real Shopify Customer Account API mobile client configuration.
- **Implementation:** Built all of `backend/auth/*`, `frontend/src/features/auth/*`, `frontend/src/services/auth/*`, `frontend/src/repositories/authRepository.ts`, `frontend/src/features/wishlist/WishlistContext.tsx`, and the new screens (`profile`, `wishlist`, `addresses`, `checkout/address`, `auth/callback`).
- **Pre-testing quality gates (explicit user requirement):** A read-only `code_review_agent` pass (found 2 MEDIUM issues — concurrent-refresh race; buyer-identity token type, later confirmed correct via live Shopify docs research) and a read-only `security_audit_agent` pass (found 1 MEDIUM — unvalidated web-redirect origin — plus several P3 hardening items) were both run **before** any functional testing, per explicit user instruction. All MEDIUM findings were fixed pre-emptively.
- **Testing round 1:** `testing_agent` found and root-caused Bug 4 (CRITICAL web blank-screen), fixed it, verified the fix, ran 13/13 backend pytest, verified guest/wishlist/profile-gating on frontend, and reported Bugs 5 and 6 (checkout stock false-positive; checkout/address infinite spinner) as remaining.
- **Fixes:** Bugs 5 and 6 both fixed by the main agent.
- **Testing round 2 (final):** `testing_agent` re-verified both fixes via direct API test + full UI happy path, re-confirmed zero blank-screen recurrence across ~10 fresh navigations, ran 31/31 backend pytest (auth hardening + full Shopify regression), re-confirmed guest/wishlist/badge-sync with zero regressions.
- **Outcome:** Iteration 4 **signed off**, zero outstanding issues. Real Shopify email-verification OAuth completion remains the only untestable boundary in this environment (native build required).

---

## 17. NEXT DEVELOPMENT ROADMAP (EXACT ORDER)

This is the authoritative, exact-order roadmap for all remaining work. Each milestone lists its Objective, Dependencies, Acceptance Criteria, and Definition of Done. **Do not skip ahead** — later milestones assume earlier ones are actually done, not just started.

### Milestone 1 — Native OAuth Verification
- **Status:** Implemented — untested boundary (code complete; real end-to-end login never performed).
- **Objective:** Prove that a real shopper can complete Shopify Customer Account passwordless login (Sign Up or Log In) on a real iOS or Android device, and that Now Kart's session lifecycle (issuance, persistence across relaunch, silent refresh, logout) behaves correctly against a real Shopify customer identity.
- **Dependencies:** User must generate a native development or production build via the Emergent **Publish** button (top-right) → **Deploy your app**. Cannot be done in Expo Go or web preview — see Section 8 "Native OAuth Status" for the exact technical reason.
- **Acceptance Criteria:**
  - Tapping "Log In" or "Sign Up" opens Shopify's hosted login in the system browser.
  - Entering a real email and completing Shopify's emailed verification code/magic link redirects back into the app via the registered custom scheme.
  - The app exchanges the resulting code for a Now Kart session and shows the authenticated Profile (real name/email).
  - Killing and relaunching the app restores the session without requiring login again (within the refresh-token's 30-day window).
  - Logout clears the session and returns the user to the guest experience.
  - The Orders tab and Addresses screen render **real** data for that signed-in customer (not just the guest gate, which was already verified — see Section 6 "Orders").
- **Definition of Done:** All acceptance criteria manually verified on at least one real iOS or Android device by the user or a `testing_agent` pass explicitly run against that build; any bugs found are fixed and re-verified; this document's "Native OAuth Status" language is updated from "untested boundary" to "verified" with the device/OS version noted.

### Milestone 2 — Checkout Sheet Kit / Native Checkout
- **Status:** Planned / Future roadmap — no code exists.
- **Objective:** Let a shopper move from Now Kart's cart into Shopify's actual checkout (address entry, shipping method, order review) with a native-feeling UI, without leaving the app shell.
- **Dependencies:** Milestone 1 complete (checkout requires knowing who the buyer is for buyer-identity-attached carts, though Shopify also supports guest checkout); an architectural decision between (a) Shopify's native **Checkout Sheet Kit** SDK, or (b) handing off the existing `cart.checkoutUrl` (already returned by `prepare_checkout`) to `expo-web-browser`. **Must** go through `integration_playbook_expert_v2` before writing any code — checkout/payment integrations are always third-party integrations per platform rules, and the user must supply/confirm any required Shopify checkout extensibility configuration.
- **Acceptance Criteria:** A shopper with a valid, stock-validated cart can reach Shopify's real checkout UI from the "Continue to Payment" button (currently disabled) and see their cart contents/address correctly reflected there.
- **Definition of Done:** Checkout UI reachable and correct on a native build; `testing_agent` pass covering the hand-off (cart → checkout) with no data mismatch; security review of the hand-off mechanism (no cart/customer data leaked via URL params beyond what Shopify itself requires).

### Milestone 3 — Payments
- **Status:** Planned / Future roadmap — no code exists. Payments are explicitly disabled today (the "Continue to Payment" button is rendered but hard-disabled).
- **Objective:** Complete a real payment for a real order through whichever checkout surface Milestone 2 established.
- **Dependencies:** Milestone 2 complete. Requires `integration_playbook_expert_v2` consultation (payments are always a third-party integration). If Shopify's own Checkout Sheet Kit is used, Shopify itself may handle PCI-scope payment collection; if a custom flow is built instead, a payment processor (e.g. Shopify Payments, Stripe) integration decision is needed — **do not implement any payment code without first asking the user which processor/flow they want**, per platform integration rules.
- **Acceptance Criteria:** A real (or Shopify-test-mode) payment can be completed end-to-end and results in a real Shopify order.
- **Definition of Done:** Payment completes successfully in at least a Shopify test/sandbox mode; a dedicated security review (Section 22 "Technical Debt" flags this explicitly) covering payment-data handling, webhook signature verification (if webhooks are introduced), and idempotency (no duplicate charges on retry) is completed and all findings fixed before this is considered production-ready.

### Milestone 4 — Orders (Order Creation / Placement Confirmation)
- **Status:** Planned / Future roadmap — depends on Milestone 3.
- **Objective:** After a payment succeeds, show the shopper a clear order-confirmation screen (order number, estimated delivery, summary) and ensure the newly created Shopify order is immediately visible to the app.
- **Dependencies:** Milestone 3 complete.
- **Acceptance Criteria:** Immediately after a successful checkout, the shopper sees an order-confirmation screen without needing to manually refresh/re-navigate to Orders.
- **Definition of Done:** Confirmation screen implemented, linked from checkout completion; `testing_agent` pass confirming the new order appears both on the confirmation screen and in the Orders tab within a reasonable time.

### Milestone 5 — Order History
- **Status:** Implemented — untested boundary (this milestone is **substantially already built**, see Section 6 "Orders"; do not re-build it from scratch).
- **Objective:** Let a signed-in customer see their real past Shopify orders (already fetched via `ME_QUERY.customer.orders` → `auth/service.py::get_profile` → `authRepository.getProfile()` → `app/(tabs)/orders.tsx`).
- **Dependencies:** Milestone 1 (Native OAuth Verification) — this is the only real blocker; the code itself needs no further backend or frontend work unless Milestone 1 testing surfaces a bug.
- **Acceptance Criteria:** A real signed-in customer with ≥1 real order sees it listed (order number, date, status, total); a customer with 0 orders sees the existing empty state; a guest sees the existing sign-in prompt (already verified).
- **Definition of Done:** `testing_agent` pass against a real native build with a real signed-in customer confirms the authenticated branch renders correctly; any bugs found fixed and re-verified. **Do not treat this as a from-scratch feature — verify current code first (Section 6 "Orders") before scoping new work.**

### Milestone 6 — Notifications
- **Status:** Planned / Future roadmap — no code exists. **Do not build this speculatively — only build if/when the user explicitly requests it**, per standing platform rule (push notifications are never proactively suggested by the agent).
- **Objective:** Notify a customer of order status changes (confirmed, out for delivery, delivered) if/when the user requests this feature.
- **Dependencies:** Milestone 4/5 (there must be real orders/status to notify about). If requested, this would use Emergent-managed push notifications, which requires the user to supply a Firebase `google-services.json` and only becomes testable after a native build/device.
- **Acceptance Criteria:** *(to be defined at the time the user requests this feature.)*
- **Definition of Done:** *(to be defined at the time the user requests this feature.)*

### Milestone 7 — Live Tracking
- **Status:** Planned / Future roadmap — no code, no architecture decided.
- **Objective:** Show a customer real-time delivery status/location once an order is out for delivery.
- **Dependencies:** Milestones 4–5, plus the Rider App (Milestone 8) or an equivalent fulfillment-status source, since there is no delivery-personnel-facing system yet to generate live location/status data. Architecture (Shopify fulfillment webhooks vs. a custom rider-location backend) not yet decided.
- **Acceptance Criteria:** *(to be defined once the architecture decision above is made.)*
- **Definition of Done:** *(to be defined once the architecture decision above is made.)*

### Milestone 8 — Rider App
- **Status:** Planned / Future roadmap — not started, not designed, no code exists.
- **Objective:** A separate application for delivery personnel to see/accept/complete deliveries.
- **Dependencies:** A real order/fulfillment data model (Milestones 4–5 at minimum); likely a role/auth model distinct from the customer-facing Shopify Customer Account flow (riders are not Shopify customers).
- **Acceptance Criteria:** *(to be defined when this milestone is scoped with the user — treat as greenfield.)*
- **Definition of Done:** *(to be defined when this milestone is scoped with the user.)*

### Milestone 9 — Merchant Dashboard
- **Status:** Planned / Future roadmap — not started, not designed, no code exists.
- **Objective:** Let the grocery merchant view/manage orders (and possibly inventory) alongside their existing Shopify Admin.
- **Dependencies:** Milestones 4–5 at minimum; likely a separate web-based app **[ASSUMPTION]** given typical merchant back-office usage patterns.
- **Acceptance Criteria:** *(to be defined when this milestone is scoped with the user.)*
- **Definition of Done:** *(to be defined when this milestone is scoped with the user.)*

### Milestone 10 — Admin Dashboard
- **Status:** Planned / Future roadmap — not started, not designed, no code exists.
- **Objective:** Platform-level operations: user management, merchant onboarding, monitoring.
- **Dependencies:** Milestones 8–9 likely inform what platform-level oversight is actually needed.
- **Acceptance Criteria:** *(to be defined when this milestone is scoped with the user.)*
- **Definition of Done:** *(to be defined when this milestone is scoped with the user.)*

### Milestone 11 — Production Deployment
- **Status:** Planned / Future roadmap — currently dev/preview only.
- **Objective:** Deploy the FastAPI backend + Expo web/native build to production infrastructure.
- **Dependencies:** All customer-facing milestones the user wants live at launch (at minimum Milestone 1, realistically Milestones 1–5) should be verified first.
- **Acceptance Criteria:** App accessible via a production URL/build outside this preview container; backend running against production-grade MongoDB/Shopify configuration (new env values, not necessarily new code).
- **Definition of Done:** User has clicked **Publish** (top-right of the Emergent UI) → **Deploy your app**; production smoke-test of the core shopping + auth flows passes.

### Milestone 12 — App Store & Google Play Release
- **Status:** Planned / Future roadmap — not started.
- **Objective:** Public release on the Apple App Store and Google Play Store.
- **Dependencies:** Milestone 11; app icons/screenshots/privacy policy; `expo.ios.infoPlist` usage-description strings and `expo.android.permissions` entries for any permission-requiring feature that exists by then (none exist today — see Section 19 "app.json"); Play Store data-safety form; App Store Review Guidelines compliance review.
- **Acceptance Criteria:** App approved and live in both stores.
- **Definition of Done:** Both store listings live and installable by real end users.

---

## 18. ENVIRONMENT VARIABLES (NAMES ONLY — NO VALUES)

### Backend (`/app/backend/.env`)
| Variable | Purpose | Where used |
|---|---|---|
| `MONGO_URL` | MongoDB connection string. **PROTECTED — never modify.** | `server.py`, `auth/db.py` |
| `DB_NAME` | MongoDB database name. | `server.py`, `auth/db.py` |
| `SHOPIFY_STORE_DOMAIN` | The Shopify store's `.myshopify.com` domain. | `shopify_integration/config.py`, `auth/config.py`, `auth/customer_account_client.py` |
| `SHOPIFY_STOREFRONT_API_TOKEN` | Private Storefront API token (server-side only). | `shopify_integration/config.py` → `client.py` |
| `SHOPIFY_STOREFRONT_API_VERSION` | Storefront API version string (e.g. a `YYYY-MM` release). | `shopify_integration/config.py` |
| `SHOPIFY_CACHE_TTL_SECONDS` | In-memory cache TTL for catalog reads (optional, default 90). | `shopify_integration/config.py`/`cache.py` |
| `SHOPIFY_CUSTOMER_ACCOUNT_CLIENT_ID` | Public OAuth client ID for the Customer Account API native client. | `auth/config.py` → `customer_account_client.py` |
| `SHOPIFY_CUSTOMER_ACCOUNT_MOBILE_REDIRECT_URI` | The exact, pre-registered native custom-scheme redirect URI. | `auth/config.py` → `auth/service.py::_redirect_uri_for` |
| `SHOPIFY_SHOP_ID` | Shopify shop numeric ID. | `auth/config.py` |
| `JWT_SECRET_KEY` | Signing key for Now Kart's own JWT access tokens. | `auth/config.py` → `security.py` |
| `JWT_ALGORITHM` | JWT signing algorithm (optional, default `HS256`). | `auth/config.py` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime in minutes (optional, default 15). | `auth/config.py` |
| `SESSION_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh-token lifetime in days (optional, default 30). | `auth/config.py` |
| `TOKEN_ENCRYPTION_KEY` | Fernet key for at-rest encryption of Shopify tokens in Mongo. | `auth/config.py` → `security.py` |

### Frontend (`/app/frontend/.env`)
| Variable | Purpose | Where used |
|---|---|---|
| `EXPO_PACKAGER_PROXY_URL` | **PROTECTED framework variable — never modify.** Preview proxy URL. | Expo/Metro internals |
| `EXPO_PACKAGER_HOSTNAME` | **PROTECTED framework variable — never modify.** | Expo/Metro internals |
| `EXPO_PUBLIC_BACKEND_URL` | Base URL the frontend uses to reach the backend (append `/api`). | `src/services/api/apiClient.ts` |
| `EXPO_TUNNEL_SUBDOMAIN` | Expo tunnel routing (platform-managed). | Expo internals |
| `EXPO_USE_FAST_RESOLVER` | Metro fast-resolver toggle (platform-managed). | Expo/Metro internals |
| `METRO_CACHE_ROOT` | Metro bundler cache location (platform-managed). | Expo/Metro internals |

**Rule:** never hardcode any of the above anywhere in source; never print actual values in any document, log, chat response, or commit message — names only, always.

---

## 19. CONFIGURATION FILES

### `frontend/app.json`
- `expo.name`: "Now Kart"; `expo.slug`: "frontend".
- `expo.scheme`: an array of two custom URI schemes — one generic ("frontend") and one Shopify-shop-specific scheme used as the OAuth native redirect target. **Do not remove or rename either scheme entry without also updating the corresponding Shopify Customer Account API redirect-URI registration.**
- `expo.ios.bundleIdentifier` / `expo.android.package`: both set to the same reverse-DNS-style identifier (`com.emergent.nowkartapptest.sksefz` at time of writing) — this is the app's unique store identity; changing it later would be treated as a *different* app by both app stores.
- `expo.splash`/`expo-splash-screen` plugin: dark background (`#0B0710`) matching the theme, centered splash image.
- `expo.web.bundler: "metro"`, `output: "single"` — single-page web output for the preview.
- `expo.experiments.typedRoutes: true` — TypeScript route typing for `expo-router`.
- **No `expo.android.permissions` or `expo.ios.infoPlist` entries currently exist** — because no device-permission-requiring feature (camera, location, contacts, microphone, notifications) has been implemented yet. Add these only when such a feature is actually built, with concise, benefit-focused usage descriptions (per platform rule).

### `frontend/package.json`
See Section 4 for the full dependency table. `packageManager` is pinned to a specific `yarn@1.22.22` build with an integrity hash — **always respect this**; install new packages via `yarn expo install <package>`, never `npm install`, never hand-edit version numbers.

### `frontend/metro.config.js`
**PROTECTED — never modify.**

### `backend/requirements.txt`
See Section 4. **Only ever update via**: `pip install <package> && pip freeze > backend/requirements.txt` (i.e., install first, then regenerate the full freeze) — never hand-edit version pins.

### `backend/.env` / `frontend/.env`
See Section 18 for names. Both are `.gitignore`d as of Iteration 4's hardening pass.

### Deep Links
See Section 3 "Deep Linking" and this section's `app.json` note above — the second `expo.scheme` entry is the one that matters for OAuth; it must always exactly match the Shopify Customer Account API's registered redirect URI (`SHOPIFY_CUSTOMER_ACCOUNT_MOBILE_REDIRECT_URI`).

### Build Configuration
No EAS/native build configuration has been created yet in this project (no `eas.json`). Production builds are generated exclusively via the Emergent platform's **Publish** button — do not introduce a separate EAS CLI workflow.

---

## 20. MIGRATING TO A NEW EMERGENT ACCOUNT

This section is written so that a new Emergent account/session can pick up this exact project with **zero prior conversational context** — only this document, the two companion documents, and the codebase itself.

### 1. What you need before you start
Ask the current project owner (the human user) for the following **values** (this document intentionally never states the values themselves — only names/purposes, per standing security rule):
- A `backend/.env` file (or the individual values) containing: `MONGO_URL`, `DB_NAME`, `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_STOREFRONT_API_TOKEN`, `SHOPIFY_STOREFRONT_API_VERSION`, `SHOPIFY_CACHE_TTL_SECONDS`, `SHOPIFY_CUSTOMER_ACCOUNT_CLIENT_ID`, `SHOPIFY_CUSTOMER_ACCOUNT_MOBILE_REDIRECT_URI`, `SHOPIFY_SHOP_ID`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `SESSION_REFRESH_TOKEN_EXPIRE_DAYS`, `TOKEN_ENCRYPTION_KEY` (see Section 18 for what each one is for).
- A `frontend/.env` file — in a new Emergent account this is largely **auto-provisioned by the platform** (`EXPO_PACKAGER_PROXY_URL`, `EXPO_PACKAGER_HOSTNAME`, `EXPO_TUNNEL_SUBDOMAIN`, `EXPO_USE_FAST_RESOLVER`, `METRO_CACHE_ROOT`) — you should not need to manually recreate these; only `EXPO_PUBLIC_BACKEND_URL` may need confirming against whatever the new environment's backend URL is.
- Confirmation of which Shopify store this project talks to (`vcq88p-fj.myshopify.com` as of this handover) and that the Storefront API token and Customer Account API client above are still valid for it (tokens/clients can be rotated/revoked independently of this codebase).

### 2. Shopify Storefront API setup (catalog/cart)
1. In the Shopify store's admin, confirm (or create) a **Headless** sales channel / Storefront API access token with at least `unauthenticated_read_product_listings`, `unauthenticated_read_product_inventory`, and cart read/write scopes.
2. Put that token in `backend/.env` as `SHOPIFY_STOREFRONT_API_TOKEN`, sent server-side via the **private** header (`Shopify-Storefront-Private-Token`, not the public client header) — see `backend/shopify_integration/client.py`.
3. Set `SHOPIFY_STORE_DOMAIN` to the store's `.myshopify.com` domain and `SHOPIFY_STOREFRONT_API_VERSION` to a current Storefront API release (e.g. a `YYYY-MM` version Shopify still supports).
4. Restart the backend (`sudo supervisorctl restart backend`) and confirm `GET /api/shopify/home` returns real data.

### 3. Shopify Customer Account API setup (auth)
1. In the Shopify Partner/Customer Account API configuration for this store, register (or confirm) a **native/mobile public OAuth client** (no client secret — PKCE-only, per RFC 8252). Record its Client ID.
2. Register the **exact** native redirect URI this app expects — it must exactly match `frontend/app.json`'s second `expo.scheme` entry (currently `shop.67101655143.app`, i.e. the redirect would be that scheme followed by whatever path Shopify's client registration requires). If you change the scheme in `app.json`, you must also update the Shopify-side registration and `SHOPIFY_CUSTOMER_ACCOUNT_MOBILE_REDIRECT_URI` together — these three must always match.
3. Put the Client ID in `backend/.env` as `SHOPIFY_CUSTOMER_ACCOUNT_CLIENT_ID`, the redirect URI as `SHOPIFY_CUSTOMER_ACCOUNT_MOBILE_REDIRECT_URI`, and the shop's numeric ID as `SHOPIFY_SHOP_ID`.
4. **No web OAuth client is registered for this project by design** — the backend hard-rejects `platform="web"` authorize requests (Section 13). Do not "fix" this by registering one without a deliberate, explicit decision (it changes the security model — see Section 13 "OAuth").

### 4. Client IDs / secrets required (names only)
See Section 18 for the exhaustive list. The two Shopify-specific IDs a new account absolutely needs are `SHOPIFY_CUSTOMER_ACCOUNT_CLIENT_ID` (public, no secret) and `SHOPIFY_STOREFRONT_API_TOKEN` (private, server-side only, treat as a secret even though Shopify calls it a "token" not a "secret"). Now Kart's own `JWT_SECRET_KEY` and `TOKEN_ENCRYPTION_KEY` should be **freshly generated random values** for a new account/deployment, not reused from a previous account (rotating them invalidates all existing sessions, which is expected and safe — refresh tokens are opaque and hashed, not derived from these keys in a way that needs migration).

### 5. Callback URI configuration
The callback/redirect URI is a three-way agreement that must always match exactly:
1. `frontend/app.json` → `expo.scheme` (second array entry).
2. Shopify's Customer Account API client registration (Partner Dashboard / Customer Account API config for the store).
3. `backend/.env` → `SHOPIFY_CUSTOMER_ACCOUNT_MOBILE_REDIRECT_URI`, consumed by `backend/auth/config.py` → `backend/auth/service.py::_redirect_uri_for`.
Changing any one of the three without the other two breaks native login with a Shopify-side "redirect_uri mismatch" error.

### 6. Build configuration
No `eas.json` exists and none should be introduced. Native builds are generated exclusively through the Emergent platform's **Publish** button (top-right) → **Deploy your app**, which handles iOS/Android build generation. Do not set up a separate EAS CLI/Expo account workflow for this project.

### 7. Deep linking
Already implemented and requires no new code in a new account — just correct configuration (Section 5 above). `frontend/app/auth/callback.tsx` is a web-only safety net, not part of the real (native-only) flow, and needs no changes either.

### 8. Expo configuration
`frontend/app.json` is otherwise portable as-is except: `expo.ios.bundleIdentifier` / `expo.android.package` (currently `com.emergent.nowkartapptest.sksefz`) should be changed to whatever bundle identifier the new account/owner wants to publish under — but if changed, this is treated as a **different app** by both app stores, so only change it deliberately and early, not after any store presence exists.

### 9. Backend configuration
`backend/server.py` binds to `0.0.0.0:8001` and must **not** be changed — this is dictated by the platform's ingress/proxy configuration, not by this project. `backend/.env` is loaded via `load_dotenv()` before the `shopify_integration`/`auth` modules are imported (see the exact ordering comment in `server.py`) — preserve this ordering if `server.py` is ever refactored.

### 10. Testing workflow for a new account
1. Read this document, `PROJECT_MEMORY.md`, and `DEVELOPER_PLAYBOOK.md` in full before writing any code.
2. Read `/app/test_result.md` (canonical testing history) and the latest `/app/test_reports/iteration_*.json` before invoking a `testing_agent`.
3. Run backend `pytest` (`backend/tests/`) first — it needs only the Shopify/Mongo env values above, no native build.
4. Use the web/browser preview to verify everything that does **not** require real native OAuth (catalog, search, cart, guest flows, wishlist, UI).
5. Only after generating a native build (Milestone 1 in Section 17) can real Customer Account login, Orders, and Addresses-as-a-real-customer be verified.

---

## 21. ENGINEERING STANDARDS

### Architecture Principles
- Three-tier BFF architecture (Expo client → FastAPI backend → Shopify) — the frontend must never talk to Shopify or hold a Shopify credential directly (Section 3).
- Feature-oriented backend modules (`shopify_integration/`, `auth/`) rather than one monolithic `server.py` — any new domain (e.g. a future `checkout/` or `orders/` module) should follow this same pattern: its own `config.py`/`client.py`/`service.py`/`router.py`/`schemas.py` as needed, not everything crammed into `server.py`.
- Repository pattern on the frontend (`src/repositories/`) — screens/hooks never call `fetch`/`apiClient` directly for domain data.
- Context-only state management on the frontend — do not introduce Redux/Zustand without a concrete justification (state complexity growing beyond the current 3 contexts).

### Coding Conventions
- Backend: Python, `async`/`await` throughout (no blocking I/O in request handlers), typed exceptions (`ShopifyAPIError`, `CustomerAccountAPIError`, `AuthError`) caught at the router layer, Pydantic models for every request/response shape.
- Frontend: TypeScript everywhere, functional components + hooks only (no class components), `StyleSheet.create()` for all styling, no inline style objects for anything reused more than once.
- Never hardcode a URL, port, or secret in source — always via `.env` (backend) or `process.env.EXPO_PUBLIC_*` (frontend).
- Never call `expo-secure-store` or raw `AsyncStorage` directly in new code — always go through `frontend/src/utils/storage/` (this is a **non-negotiable** rule established after Bug 4, Section 14).

### Folder Conventions
- `app/` — routes only (expo-router file-based routing). Non-route code must live in `src/`.
- `backend/<domain>/` — one folder per bounded domain (`shopify_integration/`, `auth/`), each with its own `config.py`, `service.py`, `router.py`, `schemas.py` as needed.
- `frontend/src/repositories/` — the only place frontend code should reach for backend data.
- `frontend/src/shared/components/` — check here before building any new UI primitive from scratch.
- `frontend/src/theme/` — the only place design tokens are defined/extended.

### UI/UX Rules
See Section 12 in full. Summary of the non-negotiable ones: dark theme only (no light mode), 8pt spacing grid, existing color palette only (never invent a new hex value), guest browsing always available (never force login), every async screen has explicit loading/empty/error states, minimum 44×44 (iOS) / 48×48 (Android) touch targets, no universal/blanket transitions.

### Security Rules
See Section 13 in full. Summary of the non-negotiable ones: Shopify tokens never leave the backend; Now Kart's own refresh tokens are stored only as a hash; PKCE is generated and held only on-device, in memory; OAuth `state` is single-use; `platform="web"` OAuth is hard-rejected until a deliberate decision is made to support it; never log a token or full request/response payload containing sensitive data.

### Testing Standards
See Section 11 in full. Summary: every iteration's `testing_agent` pass must re-verify previously-passing functionality, not just the new feature; every issue found must be fixed regardless of severity before declaring an iteration complete; always read `test_result.md` before invoking a `testing_agent`, and always update it afterward.

### Performance Expectations
- Catalog/collection reads are cached in-memory with a TTL (`SHOPIFY_CACHE_TTL_SECONDS`, default 90s) to reduce Shopify API call volume — any new read-heavy Shopify endpoint should use the same `TTLCache` pattern (`shopify_integration/cache.py`) rather than hitting Shopify on every request.
- Images use `expo-image` (not the base `Image` component) for caching/performance.
- No known N+1 or redundant-refetch patterns as of this handover; any new data-fetching screen should use the existing `useAsyncData` hook rather than hand-rolling `useEffect`+`fetch`.

### Code Review Standards
- Any change to authentication, session handling, or payment-adjacent code should go through a read-only `code_review_agent` and `security_audit_agent` pass **before** functional testing, per the precedent set in Iteration 4 (Section 16).
- All MEDIUM-or-higher findings from either review must be fixed before the feature is considered done; LOW/P3 findings may be deferred but must be recorded in Section 15/22, not silently dropped.

### Release Process
- No formal release/versioning process exists yet beyond the Emergent platform's Publish → Deploy flow (Section 17, Milestone 11). `frontend/package.json`'s `version` (currently `1.0.0`) and `app.json`'s `expo.version` should be bumped deliberately before any store submission (Milestone 12).

---

## 22. TECHNICAL DEBT

### Known Technical Debt
1. **CORS is `allow_origins=["*"]` with `allow_credentials=True`** (`backend/server.py`) — should be tightened to an explicit allowlist before production (Section 13, Section 15).
2. **No rate limiting on any `/api/auth/*` endpoint** — authorize-url, token-exchange, refresh, and logout are all currently unthrottled (Section 15).
3. **`backend/requirements.txt` carries many dependencies unrelated to Now Kart** (`stripe`, `openai`, `google-generativeai`, `google-genai`, `boto3`, `emergentintegrations`, `litellm`, `python-jose`, etc.) — these come from the base Emergent project template and are not installed for, or used by, any Now Kart feature. Do not assume any of these integrations exist; do not add new dependencies to this file without first `pip install`-ing and re-freezing (never hand-edit).
4. **`date-fns` and `dayjs` are both present as frontend dependencies** — likely redundant (Section 15). **[ASSUMPTION — not confirmed which is dead weight.]**
5. **The generic `/api/`, `/api/status` routes and `StatusCheck` model in `backend/server.py`** are leftover template scaffolding, unrelated to any real Now Kart feature.
6. **No automated CI pipeline** — testing is currently driven entirely by manual `pytest` runs and `testing_agent` invocations, not a CI/CD trigger on push.

### Architecture Trade-offs (deliberate, not bugs)
1. **Wishlist is 100% client-side (AsyncStorage), not backend-synced** — chosen for simplicity and because it works identically for guests and authenticated users; trade-off is no cross-device sync and data loss on app uninstall. A forward-compatibility seam already exists in `WishlistContext` for adding backend sync later.
2. **On-device secure storage falls back to AsyncStorage on web** (no OS Keychain equivalent exists in browsers) — an accepted trade-off since the web preview is not the intended production security boundary for a native-auth app; the real boundary is the native build.
3. **No product/catalog data is ever cached in MongoDB** — always fetched live from Shopify (with a short in-memory TTL cache only) — trade-off is a hard dependency on Shopify's uptime/latency for every catalog read, in exchange for zero data-staleness/sync-logic complexity.

### Current Limitations
1. Real Shopify Customer Account OAuth completion has never been exercised end-to-end (Section 8, Section 17 Milestone 1) — the single biggest open item in the entire project.
2. The Orders tab's and Addresses screen's authenticated branches are code-complete but have never rendered against a real signed-in customer for the same reason (Section 6).
3. No pagination beyond a fixed `first` param on collection-products and search — no infinite scroll/cursor-based paging yet.
4. Multi-variant and hard-out-of-stock UI states have never been exercised against real store data (this store's catalog currently has neither) — code reviewed as correct, but not empirically observed.

### Future Refactoring Opportunities
1. Remove the unused `/api/`, `/api/status`, `StatusCheck` template scaffolding from `server.py` once confirmed truly unused.
2. Confirm and remove whichever of `date-fns`/`dayjs` is unused.
3. If/when a `checkout/`, `orders/`, or `rider/` backend module is added, consider whether `shopify_integration/cache.py`'s `TTLCache` should be promoted to a shared `backend/common/` location rather than being imported cross-module from `shopify_integration` into `auth` as it is today (a working but slightly unusual reuse pattern — see Section 9).

### Security Improvements (not yet implemented)
1. Rate limiting on `/api/auth/*`.
2. CORS allowlist tightening.
3. A dedicated security review of whatever payment surface is eventually built (Section 17 Milestone 3) — this document's security sign-off does **not** extend to any not-yet-built payments feature.
4. Consider webhook signature verification design work ahead of time if Shopify fulfillment webhooks are chosen for Milestone 7 (Live Tracking).

### Performance Improvements (not yet implemented)
1. Cursor-based pagination for collection products and search (currently a flat `first=N` cap).
2. No CDN/edge caching layer in front of the backend yet — acceptable at current scale, worth revisiting before a production launch with real traffic volume.

---

## 23. AI PROJECT MEMORY

**→ See the dedicated `PROJECT_MEMORY.md` file for the complete, standalone version of this section — it is intentionally duplicated there in full so it can be consulted independently of this master document.**

---

## 24. NEXT IMMEDIATE TASK

### Current Project Status
Iteration 4 (Customer Authentication + Checkout Foundation) code is **complete, code-reviewed, security-audited, and functionally tested (2 rounds) for everything this preview environment can exercise**, with zero outstanding issues in that scope. All previously-known bugs are fixed and regression-verified. The app currently supports: guest and authenticated browsing/search/cart/wishlist, passwordless Shopify Customer Account Sign Up/Log In/Logout with secure backend-mediated session management, address management, a checkout foundation (stock validation + buyer-identity attachment) with an explicitly disabled payment CTA, and — corrected in this handover revision — a **code-complete Order History display** (Orders tab + Profile's "Order History" link) that has not yet been exercised against a real signed-in customer.

### Current Blocker
**None functionally.** The blocker is environmental/protocol, not a bug: completing a real Shopify OAuth login (past opening the hosted login page) requires a **native development/production build** (Section 8) — this cannot be done in Expo Go or the web preview. Everything currently gated behind real authentication (Orders with real data, Addresses CRUD as a real customer) is code-complete and waiting on this same gate, not separately blocked.

### Exact Next Task **[recommendation — confirm with the user before starting, per standing project workflow]**
**Milestone 1 from Section 17: Native OAuth Verification.** Concretely:
1. Ask the user to generate a native development or production build via the Emergent **Publish** button.
2. Once a build exists, walk through: Sign Up → email verification → redirect back into the app → authenticated Profile shows real name/email → Orders tab shows real orders (or the correct empty state) → Addresses screen shows real/creatable addresses → app relaunch restores the session → Logout returns to guest state.
3. Have a `testing_agent` pass (or the user directly) exercise this on the real device/build, since this is precisely the boundary automated Playwright-based testing in this container cannot cross.
4. Fix any bugs found; re-verify; then, and only then, is it accurate to describe Shopify Customer Account authentication as "verified" rather than "code-complete, untested."

**Do not** re-attempt "wire order history to real data" as a task — that work is already done (see Section 6 "Orders"); an earlier draft of this document incorrectly listed it as the next task, and that has been corrected throughout this revision.

### Acceptance Criteria
See Milestone 1's Acceptance Criteria in Section 17 — reproduced here for convenience: real login completes on-device; session persists across relaunch; Orders/Addresses render real data for the signed-in customer; logout works cleanly.

### Definition of Done
- All Milestone 1 acceptance criteria manually verified on at least one real device/build.
- Any bugs found fixed and re-verified via a focused `testing_agent` retest.
- `test_result.md` updated with a new task entry + `agent_communication` log entry, exactly as done for every prior iteration.
- This document's header line and Section 8 "Native OAuth Status" updated from "untested boundary" to "verified," with the device/OS/build noted.

---

## 25. CODEBASE MAPPING

### Major Modules
- **Catalog/Cart domain** → `backend/shopify_integration/` (backend) + `frontend/src/repositories/{product,cart}Repository.ts` + `frontend/src/features/cart/CartContext.tsx` (frontend).
- **Auth/Session/Address domain** → `backend/auth/` (backend) + `frontend/src/features/auth/`, `frontend/src/services/auth/`, `frontend/src/repositories/authRepository.ts` (frontend).
- **Wishlist domain** → `frontend/src/features/wishlist/WishlistContext.tsx` (frontend-only today; no backend module yet).

### Important Files (the ones a new engineer will touch most often)
- `backend/server.py` — app wiring; touch only for new router mounting or top-level middleware changes.
- `backend/shopify_integration/service.py` — almost all new catalog/cart/checkout-prep business logic goes here.
- `backend/shopify_integration/queries.py` / `mappers.py` — touch together whenever a new Shopify field is needed on the frontend.
- `backend/auth/service.py` — almost all new auth/session/profile/address business logic goes here.
- `frontend/app/_layout.tsx` — touch only to add a new global provider or a new top-level Stack screen.
- `frontend/src/repositories/*.ts` — touch whenever a new backend endpoint needs a frontend-facing call.
- `frontend/src/shared/components/*` — check here first before creating any new UI primitive; most patterns (cards, buttons, states, badges) already exist.
- `frontend/src/theme/*` — the only place design tokens should be defined/extended.

### Critical Services
- `backend/shopify_integration/client.py::ShopifyGraphQLClient` — the single choke point for all Storefront API traffic.
- `backend/auth/customer_account_client.py` — the single choke point for all Customer Account API traffic (OAuth + authenticated GraphQL).
- `frontend/src/services/api/apiClient.ts` — the single choke point for all frontend→backend traffic.

### Critical Contexts
- `AuthContext`, `WishlistContext`, `CartContext` — see Section 10. Any new global, cross-screen state need should almost always become a fourth context following the exact same pattern (provider + `useX()` hook that throws outside its provider), not a new state-management library.

### Critical Routes
- `/api/shopify/*` and `/api/auth/*` (backend) — see Section 7's tables.
- `app/(tabs)/index.tsx`, `app/product/[handle].tsx`, `app/cart.tsx`, `app/profile.tsx`, `app/checkout/address.tsx` (frontend) — the highest-traffic user-facing screens.

### Important Models (Pydantic schemas)
- `shopify_integration/schemas.py`: `ProductOut`, `CartOut`, `CheckoutPrepareOut`, `HomeSectionsOut`.
- `auth/schemas.py`: `SessionOut`, `ProfileOut`, `AddressOut`, `OrderSummaryOut`.

### Important Utilities
- `backend/shopify_integration/cache.py::TTLCache` — reused for both catalog caching and OAuth state caching.
- `frontend/src/utils/storage/` — the mandatory abstraction for all persisted data, general or secure; **never bypass this with a direct `AsyncStorage`/`expo-secure-store` call in new code.**
- `frontend/src/shared/hooks/useAsyncData.ts` — the mandatory pattern for any new screen-level data fetch.

### Important Reusable Components
See Section 10's full list — always check `src/shared/components/index.ts` before writing a new UI primitive from scratch.

### Where Future Development Should Occur
- **Order history:** already implemented (`frontend/app/(tabs)/orders.tsx` + `frontend/app/profile.tsx` entry point, backend `auth/service.py::get_profile`) — remaining work is verification-only, gated on Milestone 1 (Section 17, Section 24).
- **Checkout completion/payments:** a new module, most likely `backend/checkout/` (or extending `shopify_integration/`) + new frontend screens under `app/checkout/`; will require a fresh `integration_playbook_expert_v2` consultation and a native build.
- **Rider/Merchant/Admin apps:** entirely new applications/modules; no existing code should be assumed reusable beyond the same FastAPI backend's future extended endpoints and possibly shared MongoDB collections — treat as greenfield when the user requests them.
