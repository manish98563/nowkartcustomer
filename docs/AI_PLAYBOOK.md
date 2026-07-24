# NOW KART — AI PLAYBOOK

> For future AI assistants continuing this project.
> Read this before making ANY changes. 5 minutes now saves hours of debugging.

---

## Project Context

Now Kart is a **headless Shopify** mobile commerce platform at **Iteration 11**.
- Backend: fully built (Customer + Rider + Vendor + Admin modules)
- Customer App: production-ready
- 3 mobile/web apps not yet built (Rider App, Vendor App, Admin Dashboard)

**Start every session by reading:**
1. `/app/memory/PRD.md` — living task list
2. `/app/memory/test_credentials.md` — auth credentials for testing
3. `/app/docs/PROJECT_HANDOVER.md` — current status

---

## Architecture Rules (never violate)

| Rule | Reason |
|---|---|
| Shopify is the system of record for catalog, inventory, pricing, orders | Never duplicate product data in MongoDB |
| All Shopify API calls go through the FastAPI backend only | Storefront token must never reach the client |
| Frontend never holds a real Shopify token | BFF pattern — client holds only Now Kart JWT |
| All backend routes must start with `/api` | Kubernetes NGINX routing rule |
| Shopify GIDs in URLs → use `?id=encodeURIComponent(gid)` | NGINX double-decodes `%2F` in path segments |
| All storage on frontend → use `src/utils/storage/` | `expo-secure-store` has zero web support |
| New Python packages → `pip install X && pip freeze > requirements.txt` | Never hand-edit requirements.txt |
| New JS packages → `yarn expo install <pkg>` | Never hand-edit package.json versions |

---

## Files Never to Modify

```
frontend/metro.config.js              — NGINX proxy config
frontend/.env EXPO_PACKAGER_*         — preview URL generation
backend/.env MONGO_URL                — pre-configured MongoDB connection
```

---

## Module Boundaries

```
shopify_integration  ← auth (imports for buyer identity)
tracking             ← auth (imports for order data)
delivery             ← auth (lazy: user lookup), rider (lazy: assign), vendor (lazy: assign)
rider                ← delivery (lazy: current job, history)
vendor               ← delivery (lazy: order queue, state transitions)
admin                ← delivery, rider, vendor, stores (read + override)
webhooks             ← delivery (creates jobs)
```

> Only add a cross-module import if it's in this map. Use lazy imports (inside functions) to avoid circular dependencies.

---

## Extending the Backend

### Adding a new endpoint to an existing module
1. Add function to `<module>/service.py`
2. Add route to `<module>/router.py`
3. Add test to `backend/tests/test_<module>.py`
4. Restart backend: `supervisorctl restart backend`

### Adding a new module
1. Create `backend/<module>/` with: `__init__.py`, `db.py`, `schemas.py`, `service.py`, `router.py`
2. Follow db.py pattern from `rider/db.py` (separate Motor client)
3. Follow security.py pattern from `rider/security.py` if auth needed
4. Mount router in `server.py` after `load_dotenv()`
5. Add `ensure_<module>_indexes()` to startup event

### State machine changes
All delivery state logic lives in `delivery/service.py`:
- `STATUS_LABELS` dict
- `VALID_TRANSITIONS` dict
- `TERMINAL_STATES` frozenset
- `_TRANSITION_TIMESTAMPS` dict

Never add state logic elsewhere.

---

## Adding a New Frontend Screen

1. Create file under `frontend/app/` (path = URL route)
2. Add data method to relevant `src/repositories/*.ts`
3. Use `useAsyncData` hook for loading/error/empty pattern
4. Add `Stack.Screen` to `frontend/app/_layout.tsx`
5. Use theme tokens only — never inline hex values

---

## Things AI Must Never Do

- ❌ Change the delivery state machine without updating ALL four constants
- ❌ Call `expo-secure-store` or `AsyncStorage` directly in frontend (use `src/utils/storage/`)
- ❌ Store product/catalog data in MongoDB
- ❌ Return raw Shopify tokens to the client
- ❌ Use `@expo-google-fonts/*` packages
- ❌ Use `expo-av` (use `expo-audio` / `expo-video` instead)
- ❌ Use `expo-barcode-scanner` (use `expo-camera` instead)
- ❌ Let the frontend communicate directly with Shopify APIs
- ❌ Add a web Shopify OAuth client (no web OAuth client is registered)
- ❌ Assume native OAuth works in Expo Go (it requires a real native build)
- ❌ Remove or bypass admin JWT from `/api/admin/*` endpoints

---

## Testing Protocol

1. Always call `testing_agent_v3_expo` after significant feature implementation
2. Read the test report JSON from `/app/test_reports/iteration_{n}.json`
3. Fix ALL issues before declaring the iteration complete
4. Update `/app/memory/test_credentials.md` whenever credentials are created/changed

---

## Prompting Recommendations

- Be explicit about which module you're extending
- Reference specific file paths when asking about bugs
- When extending delivery states, say "I need to modify the state machine in delivery/service.py"
- When building a new app (Rider/Vendor/Admin), create a **separate repository** — do not add frontend code here
