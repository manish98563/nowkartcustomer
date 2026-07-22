# NOW KART — AI PROJECT MEMORY

**Purpose of this file:** This is the long-term, standalone memory of this project for any AI agent (or human) picking it up cold. It captures *why* decisions were made, what was tried and rejected, every lesson learned from a real bug, and the standing rules that must never be silently violated. It intentionally duplicates the "AI Project Memory" pointer section of `NOWKART_MASTER_HANDOVER.md` (Section 23) in full, so it can be read independently.

**How to use this file:** Read it fully before making any change to authentication, checkout, or any "locked-in" UI decision listed below. If you are about to do something this file says not to do, stop and re-read the relevant entry — it exists because someone already tried it (or a close variant) and it caused a real, verified problem.

---

## 1. WHAT THIS PROJECT IS (one paragraph)
Now Kart is a React Native + Expo (Expo Router) grocery-delivery customer app, backed by a FastAPI BFF and MongoDB, that is a headless mobile front-end for a real, live Shopify store (`vcq88p-fj.myshopify.com`). Shopify is and must remain the system of record for catalog, inventory, pricing, and customer identity. As of this memory's last update (Iteration 7), the complete customer shopping experience is code-complete: live catalog/search/cart (guest-first), local wishlist, Shopify Customer Account passwordless auth, address management, Shopify hosted checkout (WebView), order history with detail and reorder, live order tracking with 30s polling, and tracking architecture prep for the Rider App. All auth-gated features are "Implemented — untested boundary" until a real native build + Shopify OAuth login is performed. Full detail in `NOWKART_MASTER_HANDOVER.md`.

---

## 2. STANDING RULES (non-negotiable — do not violate without a new, explicit user instruction)

1. **Never call `expo-secure-store` or raw `AsyncStorage` directly in new code.** Always go through `frontend/src/utils/storage/` (`secureGet`/`secureSet`/`secureRemove`/`getItem`/`setItem`/`removeItem`). This exists specifically because `expo-secure-store` has zero web support and calling it directly crashed the entire web preview once (Bug 4 — see Section 5 below). This is the single most important lesson in this project's history.
2. **Never let the frontend talk to Shopify directly, or hold a real Shopify token.** All Shopify communication (Storefront and Customer Account APIs) is backend-only. The frontend only ever holds a Now Kart–issued session (JWT + refresh token), never a Shopify token.
3. **Never let the backend send the Storefront token as anything other than the private `Shopify-Storefront-Private-Token` header, server-side only.**
4. **PKCE verifier generation and custody belongs on the device, in memory only, for the lifetime of a single sign-in attempt — never on the backend, never persisted anywhere.** (See Section 4, "PKCE architecture correction" — this was an actual mistake in an early design draft, caught by the user, and fixed before any code was written against the wrong design.)
5. **Never change the missing-image fallback behavior** (collection image → branded placeholder icon) to "fix" missing product/collection photography. The user explicitly confirmed this is a Shopify data gap (images not uploaded), not an app bug, and explicitly asked that this not be changed.
6. **Never revert the Product Detail square image container or the ProductCard 2-line title/fixed-height change** without a new, explicit user request — both are locked-in UI decisions from Iteration 3.5, verified via testing to have zero variance across dozens of real products.
7. **Never treat a browser-preview or Expo Go pass as proof that native Shopify OAuth login works.** The final leg of the OAuth flow is an OS-level custom-scheme redirect that neither Expo Go nor a browser can complete for this app. Only a real native development/production build can prove this.
8. **Never suggest push notifications as a feature unless the user explicitly asks for it.** This is a platform-wide rule, not project-specific.
9. **Never add a new backend dependency by hand-editing `requirements.txt`.** Always `pip install <package>` then `pip freeze > backend/requirements.txt`. Same for frontend: always `yarn expo install <package>`, never `npm install`, never hand-edit `package.json` version pins.
10. **Never modify `metro.config.js`, `EXPO_PACKAGER_PROXY_URL`, `EXPO_PACKAGER_HOSTNAME`, or `MONGO_URL`.** These are platform-protected.
11. **Never disclose an actual secret/credential value in any document, log, chat message, or commit message.** Environment variable *names* are always fine to document; *values* never are.
12. **Every `testing_agent` pass must re-verify previously-passing functionality, not just the new feature** — this has been the standing rule since Iteration 3 and has caught real regressions in later rounds.
13. **Every bug found by a `testing_agent`, of any severity, must be fixed and re-verified before an iteration is declared complete.** Do not defer a bug just because it's LOW priority without at least recording it explicitly (Section 15/22 of the master handover) — silent deferral is not allowed, explicit deferral with a documented reason is.

---

## 3. DEAD-END LEDGER (tried, rejected, or corrected — do not re-attempt without a new environment/requirement change)

1. **Flutter.** User originally wanted Flutter; the `flutter` CLI was confirmed unavailable in this environment via a direct shell check. User explicitly approved React Native + Expo instead. Do not revisit unless the environment changes and the user asks again.
2. **Legacy Shopify Storefront `customerAccessTokenCreate` auth flow.** This is the deprecated, password-based Storefront customer-auth mutation. Now Kart uses the modern (2026) Shopify **Customer Account API** (OAuth2 + PKCE, passwordless) instead — this is the correct, current Shopify-recommended approach for headless apps, not a downgrade.
3. **Shopify Admin/Partner merchant OAuth for shopper login.** A first `integration_playbook_expert_v2` call returned merchant/Admin-oriented OAuth guidance — this is the wrong flow entirely for authenticating a *shopper* and was not used. A second, corrected call returned the right Customer Account API (headless, Expo/React Native) playbook, which is what was actually implemented.
4. **PKCE verifier held/generated on the backend.** An initial architecture proposal had the backend generating and holding the PKCE verifier. The user challenged this directly, and it was corrected: the verifier must be generated and held on-device, in memory, per RFC 8252 native-app best practice — the backend only ever receives the resulting `{code, code_verifier}` pair once, for the token exchange itself.
5. **Registering a web OAuth client "to make testing easier."** Explicitly not done — no web Shopify Customer Account OAuth client exists, and the backend hard-rejects `platform="web"` authorize requests with HTTP 400 by design (this closes a real, audited security finding about unvalidated web-redirect origins). Do not add a web client just to make browser-based testing more complete; that would be trading away a real security property for testing convenience.
6. **Nesting `Animated.View` inside a `Pressable` for press-scale animation.** Broke the custom tab bar's flex layout (Bug 1). Fixed by animating the `Pressable` itself via `Animated.createAnimatedComponent(Pressable)`. Do not reintroduce the nested pattern.
7. **A fully-interactive floating banner overlay.** The Free Delivery banner used to intercept taps on content beneath it (Bug 2). Fixed by scoping interactivity to only its own close button. Any future dismissible overlay must follow this same narrow-interactivity pattern.
8. **Treating `quantityAvailable < quantity` alone as "out of stock."** This store has `quantityAvailable = 0` with "continue selling when out of stock" enabled on effectively every variant, so a naive check flagged every real cart as invalid (Bug 5). `availableForSale` is the authoritative Shopify-computed purchasability signal — always check that first; only treat a *positive* `quantityAvailable` smaller than the requested quantity as a genuine overage.

---

## 4. KEY ARCHITECTURAL DECISIONS (with rationale, so they are not accidentally re-litigated)

1. **FastAPI BFF pattern, not a thin passthrough.** Chosen so Shopify credentials (Storefront token, Customer Account OAuth client interactions) never need to exist on the client, and so Now Kart can issue its own independent session lifecycle (shorter-lived JWT + rotating refresh token) rather than exposing Shopify's own token lifetimes/semantics to the client.
2. **Feature-oriented backend modules (`shopify_integration/`, `auth/`), one-directional dependency.** `shopify_integration.router` imports `auth.dependencies`/`auth.service` to optionally attach a buyer identity to carts; `auth` never imports from `shopify_integration`. This keeps the auth domain independently reasoned-about and testable.
3. **Repository pattern on the frontend.** `src/repositories/*` is the only seam that knows about `/api/shopify/*` or `/api/auth/*` paths — chosen so a future backend change (new endpoint, GraphQL client-side caching, etc.) never requires touching screen code.
4. **Context-only state management, no Redux/Zustand.** The actual shared-state surface (auth, wishlist, cart) is small enough that three React Contexts are sufficient; do not introduce a state library without a concrete justification (state complexity meaningfully growing beyond these three).
5. **Wishlist kept 100% local/device-only, by explicit design, with a documented forward-compatibility seam.** A guest's wishlist survives app reinstall only via AsyncStorage (lost on uninstall) — this is accepted, known behavior, not a bug. `WishlistContext` is written so a future backend-sync feature can swap its load/persist functions without any consuming screen changing.
6. **`src/utils/storage/` native/web split abstraction.** Introduced specifically because of Bug 4 (a real production-breaking bug) — this abstraction must be the only way any new code touches persisted storage, secure or otherwise.
7. **Two entry points ("Sign Up" / "Log In") that trigger the identical OAuth flow.** Shopify's Customer Account API is inherently passwordless and has no distinct signup-vs-login request — Shopify itself decides based on whether the entered email is new or existing. The two buttons exist purely for familiar UX, per an explicit user request; do not try to differentiate their backend behavior.

---

## 5. BUG LESSONS LEDGER

| # | Bug | One-line lesson |
|---|---|---|
| 1 | `AnimatedPressable` broke tab-bar flex layout | Animate the `Pressable` itself via `createAnimatedComponent`, never nest `Animated.View` inside a layout-critical `Pressable`. |
| 2 | Free-delivery banner blocked underlying taps | Any dismissible overlay must scope touch-handling to only its own interactive elements. |
| 3 | Product 404 showed generic retry loop | Fetch hooks must expose HTTP status, not just a boolean error. |
| 4 | **CRITICAL** — web preview totally blank | Never call `expo-secure-store` directly; zero web support. Always use `src/utils/storage/`. |
| 5 | Checkout blocked every real product | `availableForSale` is the authoritative signal, not `quantityAvailable` alone. |
| 6 | `/checkout/address` spun forever with no `cartId` | Every async guard must resolve loading state on EVERY code path. |
| 7 | **CRITICAL** — auth 502 on Log In | `countryCode` → `territoryCode`: Shopify Customer Account API 2026-07 renamed this field. Every query/mutation/schema using customer addresses must use `territoryCode`. |
| 8 | **CRITICAL** — GID path param → 404 | Shopify GIDs (`gid://shopify/Order/123`) contain slashes. NGINX double-decodes `%2F` in path segments. Always use `?id=encodeURIComponent(gid)` query params for GID endpoints. |
| 9 | Duplicate `export const` in repository files | After search-replace edits, always verify no duplicate `export const` declarations remain. Metro silently uses the first declaration; the second is unreachable. |

---

## 6. CORRECTION LOG (mistakes found and fixed *within this documentation itself* — read this so you don't repeat them)

1. **"Order history is a UI placeholder" — this was WRONG and has been corrected.** An earlier internal draft of `NOWKART_MASTER_HANDOVER.md` (and, historically, `test_result.md`) described the Profile/Orders order-history feature as an unbuilt placeholder and recommended "wire it up" as the next task. Direct inspection of the current codebase (git commit `c19e713`, 2026-07-20) shows this is **factually incorrect** — `frontend/app/(tabs)/orders.tsx` already calls `authRepository.getProfile()` and renders real `profile.orders` data when authenticated, with a proper guest sign-in gate; `frontend/app/profile.tsx` links to it via an "Order History" menu row. The backend (`auth/service.py::get_profile`, `auth/customer_account_client.py::ME_QUERY`) already returns real order summaries. **Corrected status: Implemented — untested boundary** (code-complete, but never exercised against a real signed-in customer, for the same native-OAuth reason everything else authenticated is unverified). **Lesson for future agents: before recommending "the next task" based on an old document's claims, always re-verify against the actual current codebase — documentation can go stale even within the same project, especially after a large single commit that isn't fully narrated in `test_result.md`.**
2. **Always cross-check `git log --stat` against `test_result.md`'s narrative before trusting the narrative as complete.** In this project, the single Iteration 4 implementation commit (`c19e713`) touched more files (including the Orders/Profile order-history wiring) than `test_result.md`'s task list explicitly called out as a separate task — the feature existed but wasn't given its own tracked task entry. This does not mean the feature doesn't exist; verify the actual files.

---

## 7. USER SENTIMENT / COMMUNICATION STYLE NOTES

- The user is highly thorough, detail-oriented, and explicitly values **accuracy over optimism**. They have directly challenged an incorrect architecture proposal (PKCE-on-backend) and explicitly requested full code review + security audit before functional testing on the auth iteration, rather than accepting a quick "it works" claim.
- The user explicitly does not want features described as "done"/"signed off"/"production-ready" without qualification when a real acceptance gate (native OAuth) has not been crossed. Always use the four-state maturity language from `NOWKART_MASTER_HANDOVER.md`'s header (Implemented / Implemented — untested boundary / Partially implemented / Planned).
- The user explicitly does not want UI redesigns of things confirmed as intentional (missing images, square product photo, 2-line card titles) — treat these as locked-in unless a new explicit request says otherwise.
- The user prefers exact, ordered roadmaps with explicit Objective/Dependencies/Acceptance Criteria/Definition of Done per milestone, rather than a loose bullet list — see `NOWKART_MASTER_HANDOVER.md` Section 17 for the format to continue using for any new roadmap items.

---

## 8. CURRENT STATUS SNAPSHOT

As of this memory's last update: **Iterations 1–7 complete**. Customer shopping experience (~98%): catalog, search, cart, auth, wishlist, addresses, checkout (WebView), order management, live tracking. The tracking module (`backend/tracking/`) has architecture prep for the Rider App.

**Single largest open item**: Generate native iOS/Android build (Emergent Publish) → verify real Shopify OAuth login + checkout + order tracking. All auth-gated features remain "Implemented — untested boundary" until this is done.

**Next milestones** (ordered):
1. Native production build
2. Shopify Checkout Sheet Kit (Apple Pay / Google Pay)
3. Rider App (backend tracking/ extension points ready)
4. Merchant/Admin Dashboards
5. Push Notifications (order webhook → device)
