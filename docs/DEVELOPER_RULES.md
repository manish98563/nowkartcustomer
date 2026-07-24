# NOW KART — DEVELOPER RULES

> Engineering standards for this codebase. Non-negotiable.

---

## Repository Structure

```
/app
├── backend/              FastAPI backend (Python 3.11)
│   ├── server.py         Entry point — load_dotenv FIRST, then all imports
│   ├── <module>/         db.py · schemas.py · service.py · router.py
│   └── tests/            pytest test files per iteration
├── frontend/             Customer App (Expo SDK 54, React Native)
│   ├── app/              expo-router file-based routes
│   └── src/              features/ · repositories/ · services/ · shared/ · theme/ · types/ · utils/
├── docs/                 This documentation
└── memory/               PRD.md · test_credentials.md (AI session memory)
```

---

## Backend Rules

### Module Structure
Every backend module follows this pattern:
```
<module>/
├── __init__.py
├── db.py         Motor client + collections + ensure_indexes()
├── schemas.py    Pydantic models (no business logic)
├── service.py    All business logic + custom exception class
└── router.py     FastAPI routes + HTTP error handling only
```

### Coding Standards
- **DateTime:** `datetime.now(timezone.utc)` — never `datetime.utcnow()`
- **ObjectId serialisation:** always `str(doc["_id"])` — never return raw MongoDB documents
- **Error classes:** Each module defines its own `<Module>Error(Exception)` with `status_code`
- **Lazy imports:** Use `from module.db import col` inside functions for cross-module references
- **Auth:** Call `integration_playbook_expert_v2` before writing ANY auth code
- **Dependencies:** Only `pip install X && pip freeze > requirements.txt` — never hand-edit

### Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Collections | snake_case | `delivery_jobs`, `admin_users` |
| Pydantic models | PascalCase + In/Out suffix | `RiderCreateIn`, `DeliveryJobOut` |
| Service functions | snake_case verbs | `create_rider`, `update_job_status` |
| Route prefixes | lowercase | `/api/rider`, `/api/admin` |
| Enums | PascalCase class, UPPER_VALUE | `DeliveryJobStatus.WAITING_VENDOR` |

### Security
- Never log or return plaintext passwords, tokens, or secrets
- Refresh tokens: always stored as SHA-256 hash
- Shopify tokens: always encrypted with Fernet at rest
- Admin endpoints: always require `Depends(require_min_role(...))`
- Webhook: verify `X-Shopify-Hmac-Sha256` — skip only when `SHOPIFY_WEBHOOK_SECRET` is unset (dev)

---

## Frontend Rules

### Components
- React Native components only — no HTML elements
- `StyleSheet.create()` for ALL styles — no inline objects, no CSS
- Use theme tokens: `colors.*`, `typography.*`, `spacing.*`, `radius.*`, `shadows.*`
- Minimum touch target: 44×44pt
- Every interactive element needs a `testID` (kebab-case by role)

### Navigation
- All routes = files under `frontend/app/`
- Non-route code lives in `frontend/src/`
- New screens → add `Stack.Screen` entry to `frontend/app/_layout.tsx`
- Never use `expo-router` outside `app/` directory

### Data Access
- Screens never call `fetch` or `apiClient` directly
- All API calls go through `src/repositories/*.ts`
- Auth state → `useAuth()` from `AuthContext`
- Cart state → `useCart()` from `CartContext`
- Wishlist → `useWishlist()` from `WishlistContext`

### Storage
```
✅ import { storage } from "@/src/utils/storage"
✅ await storage.secureSet(key, value)
✅ await storage.getItem(key, fallback)

❌ import * as SecureStore from "expo-secure-store"
❌ import AsyncStorage from "@react-native-async-storage/async-storage"
```

---

## Testing Requirements

- Call `testing_agent_v3_expo` after every significant feature
- Every backend module must have tests in `backend/tests/test_<module>_iteration<N>.py`
- All issues in test report must be fixed before declaring iteration complete
- Credentials: always update `memory/test_credentials.md` when accounts are created

---

## Git & Environment

- Never commit `.env` values to git (already in `.gitignore`)
- Never run `rm -rf` commands
- Use `git log --oneline` to find commits (not `git diff`)
- Protected files: never modify `metro.config.js`, `EXPO_PACKAGER_*` env vars, `MONGO_URL`

---

## Deprecation / TODO Markers

Use these exact comment formats:

```python
# TODO: Restrict to admin JWT when Admin Dashboard module is implemented.
# TODO: Add Google Maps ETA calculation when GOOGLE_MAPS_API_KEY is configured.
```

```typescript
// TODO: Add rider GPS location when Rider App ships.
// EXTENSION POINT: riderLocation, riderEta (see tracking/schemas.py)
```
