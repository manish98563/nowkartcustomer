# NOW KART — DEVELOPER PLAYBOOK

A practical, day-to-day guide for continuing development on Now Kart. For the exhaustive architecture/feature/security reference, see `NOWKART_MASTER_HANDOVER.md`. For decision history/lessons/standing rules, see `PROJECT_MEMORY.md`. This file assumes you have already read both once.

---

## 1. PROJECT AT A GLANCE

- **Frontend:** Expo (SDK 54) + React Native 0.81.5 + `expo-router`, in `/app/frontend`.
- **Backend:** FastAPI, in `/app/backend`, bound to `0.0.0.0:8001`, managed by `supervisor`.
- **Database:** MongoDB — only for `users`/`auth_refresh_tokens`; never product data.
- **External system of record:** Shopify (`vcq88p-fj.myshopify.com`) — Storefront API for catalog/cart, Customer Account API for auth/orders.
- **Routing:** file-based via `expo-router`, routes in `frontend/app/`; everything else in `frontend/src/`.
- **All backend routes are under `/api`**: `/api/shopify/*`, `/api/auth/*`, `/api/tracking/*`
- **Kubernetes ingress:** `/api/*` → port 8001; everything else → port 3000 (Expo Metro).
- **NGINX GID rule:** Shopify GIDs contain slashes — always use `?id=encodeURIComponent(gid)` query params (not path segments) for GID-based endpoints.

---

## 2. RUNNING THE PROJECT

```bash
# Restart backend after any backend code change
sudo supervisorctl restart backend

# Restart frontend (Expo/Metro) after any frontend code change,
# and ALWAYS before handing control back to the user or finishing a task
sudo supervisorctl restart expo

# Check status of both
sudo supervisorctl status
```

- Backend logs: check via supervisor's log paths, or add `logger.info(...)` calls (standard Python `logging`, already configured in `server.py`).
- Frontend: the web preview is served through Metro on port 3000; a QR code is also available for Expo Go — but see Section 6 below for what Expo Go **cannot** do in this project.
- Never start a server yourself in the foreground; always use supervisor.

---

## 3. ADDING A NEW BACKEND ENDPOINT (worked example pattern)

1. Decide module: `shopify_integration/` (Storefront), `auth/` (Customer Account/sessions/addresses/orders), `tracking/` (tracking + Rider App future) — or create `backend/<new_domain>/` with `schemas.py`/`service.py`/`router.py` layout.
2. For **new GID-based endpoints**: use `?id=` query param (not path segments) — NGINX double-decodes `%2F` in path segments (see Bug 8 in `PROJECT_MEMORY.md`).
3. Add GraphQL query/mutation to `queries.py` (Storefront) or `auth/customer_account_client.py` (Customer Account). Never add `countryCode` — always use `territoryCode` for address fields.
4. Add Pydantic schema, service logic, route; mount in `server.py` if new module.
5. Add pytest test. Restart backend. Verify.

---

## 4. ADDING A NEW FRONTEND SCREEN (worked example pattern)

1. Create the route file under `frontend/app/` — its path becomes its URL (e.g. `app/checkout/confirmation.tsx` → `/checkout/confirmation`). Do **not** put non-route logic in this file beyond the screen component itself.
2. If it needs backend data, add a method to the relevant `frontend/src/repositories/*.ts` file (never call `apiClient`/`fetch` directly from the screen).
3. Use the shared `useAsyncData` hook (`src/shared/hooks/useAsyncData.ts`) for the standard loading/error/empty pattern, unless the screen has genuinely different needs (e.g. Orders/Profile, which manage their own auth-gated fetch).
4. Reuse existing components from `src/shared/components/` before writing a new UI primitive — check `src/shared/components/index.ts` first.
5. Use `colors`/`spacing`/`typography`/`radius`/`shadows` from `src/theme/` — never a magic hex value or pixel number.
6. If the screen needs to be reachable from the Stack (not the bottom tabs), add a `Stack.Screen` entry in `frontend/app/_layout.tsx` with an appropriate `animation`/`presentation`.
7. Run `mcp_lint_javascript` (or `expo lint`) on the touched files before considering the screen done.

---

## 5. TESTING WORKFLOW

1. **Always read `/app/test_result.md` first** — it is the canonical, structured testing history and communication log between main agent and `testing_agent`. Update it (new task entries, `agent_communication` log) **before** calling `testing_agent`.
2. **Backend:** run the existing `pytest` suite (`backend/tests/test_shopify_integration.py`, `backend/tests/test_auth_endpoints.py`) after any backend change. Add new tests alongside new endpoints.
3. **Frontend/integration:** invoke `testing_agent_v4_expo` for anything beyond a trivial style tweak. Always give it: (a) the original problem statement/scope, (b) exactly what to test, (c) relevant files, (d) any credentials, (e) whether backend/frontend/both. It has no memory across invocations.
4. **Read the returned `/app/test_reports/iteration_{n}.json` file** and fix every issue found, regardless of severity, before declaring the task done. Re-invoke for a focused retest of just the fixes.
5. **The one thing `testing_agent` (and Expo Go, and the web preview) cannot verify in this project:** real Shopify Customer Account OAuth login end-to-end (Section 8/17 of the master handover). This requires a real native build. Do not ask `testing_agent` to "prove" this in this environment — it is a known, documented boundary, not a gap in the agent's capability.

---

## 6. WHAT WORKS WHERE (validation boundaries)

| Environment | Can verify | Cannot verify |
|---|---|---|
| **Web browser preview** | Guest browsing, catalog/search/cart, wishlist, UI/layout, error states, backend integration for everything not requiring a real Shopify OAuth code | Real native OAuth redirect, `expo-secure-store` behavior (falls back to AsyncStorage on web by design), Checkout Sheet Kit |
| **Expo Go** | General navigation/UI on a real device | Real native OAuth redirect (Expo Go's own `exp://` scheme sandbox can't register this app's custom scheme), Checkout Sheet Kit, any future native-module-requiring feature |
| **Real dev/production build** (via Emergent **Publish**) | Everything, including real OAuth login, secure storage on-device, future native checkout | — |

---

## 7. COMMON ISSUES & HOW TO DEBUG THEM

- **Web preview blank:** direct `expo-secure-store`/raw `AsyncStorage` call outside `src/utils/storage/` (Bug 4). Check browser console.
- **401 on `/api/auth/me`:** expected for guests. Check `isAuthenticated` + Bearer token.
- **HTTP 400 from Customer Account GraphQL:** likely `countryCode` used instead of `territoryCode`. Check all address-related queries/mutations/schemas (Bug 7).
- **404 on GID endpoint:** Shopify GID passed as path segment — NGINX decoded the slashes. Use `?id=encodeURIComponent(gid)` query param instead (Bug 8).
- **Duplicate `export const` in a repository:** Metro silently picks the first one. The second is dead code. Check the file after any search-replace edit (Bug 9).
- **Checkout-prepare `isValid: false`:** `_validate_cart_lines` in `shopify_integration/service.py` — check `availableForSale` logic (Bug 5).
- **Auth-related bug:** check backend logs, re-read `integration_playbook_expert_v2` for Customer Account API playbook. Never suggest "clear cache/hard refresh."
- **Tracking screen infinite spinner:** check `isAuthenticated && !isRestoring` guard in `useEffect`. Also check `AppState.addEventListener` cleanup.
- **CORS errors:** `server.py` allows `*` — if CORS error occurs, the problem is elsewhere (wrong base URL).

---

## 8. DEPLOYMENT

- This project has **never been deployed to production**. It runs only in this preview container today.
- To deploy: use the Emergent platform's **Publish** button (top-right of the UI) → **Deploy your app**. This is also how you generate iOS/Android builds needed for Milestone 1 (Native OAuth Verification) — see `NOWKART_MASTER_HANDOVER.md` Section 17/24.
- Do **not** set up a separate EAS CLI workflow or personal Expo account for builds — the platform's Publish flow is the only supported path for this project.
- Before any production deployment or store submission, revisit `NOWKART_MASTER_HANDOVER.md` Section 22 "Technical Debt" (CORS, rate limiting) and Section 17 Milestones 11–12.

---

## 9. FILE LOCATION CHEAT-SHEET

| I want to... | Look here |
|---|---|
| Add/change a Shopify catalog/cart endpoint | `backend/shopify_integration/{router,service,queries,mappers,schemas}.py` |
| Add/change auth/session/address/order endpoint | `backend/auth/{router,service,customer_account_client,schemas}.py` |
| Add/change tracking (Rider App prep) | `backend/tracking/{router,service,schemas}.py` |
| Change how the frontend calls the backend | `frontend/src/repositories/*.ts` |
| Change auth state/session logic | `frontend/src/features/auth/AuthContext.tsx`, `frontend/src/services/auth/*.ts` |
| Change delivery address storage (home selector) | `frontend/src/utils/storage/deliveryAddress.ts` |
| Add/change persisted storage (secure or general) | `frontend/src/utils/storage/` — never bypass this |
| Add a new reusable UI component | Check `frontend/src/shared/components/index.ts` first |
| Change color/spacing/typography | `frontend/src/theme/*.ts` — never inline values |
| Add a new screen/route | `frontend/app/**` + add `Stack.Screen` in `frontend/app/_layout.tsx` |
| Change Shopify Customer Account address fields | **Always use `territoryCode`**, never `countryCode` (Shopify 2026-07 field rename — Bug 7) |
| Add a GID-based backend endpoint | Use `?id=encodeURIComponent(gid)` query param — **never a path segment** (NGINX Bug 8) |
| Change deep-link/OAuth redirect config | `frontend/app.json` + `backend/.env` + Shopify client registration — all three must match |
| Update Python deps | `pip install <pkg> && pip freeze > backend/requirements.txt` |
| Update JS deps | `yarn expo install <pkg>` — never `npm install`, never hand-edit versions |

---

## 10. BEFORE YOU START ANY NEW WORK

1. Read `NOWKART_MASTER_HANDOVER.md` in full (or at minimum Sections 1, 8, 15, 17, 22, 24).
2. Read `PROJECT_MEMORY.md` in full (it's short, and every rule in it exists because of a real, verified incident or explicit user correction).
3. Read `/app/test_result.md`'s `agent_communication` log for the most recent narrative.
4. Cross-check any claim in the above against the actual current code before repeating it — this project has at least one documented case (Section 6 "Correction Log" in `PROJECT_MEMORY.md`) of a stale claim being carried forward without re-verification.
5. Confirm the plan with the user before starting, per standing project workflow — especially for anything touching authentication, payments, or a "locked-in" UI decision.
