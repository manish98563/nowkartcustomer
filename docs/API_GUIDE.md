# NOW KART — API GUIDE

> Full endpoint reference. See [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) for module map.

---

## Base URL & Routing

```
/api/*  → FastAPI :8001
/       → Expo Metro :3000
```

**GID Rule:** Shopify GIDs contain slashes. Always use `?id=encodeURIComponent(gid)` — never path segments.

---

## Authentication Matrix

| Route group | Required header | Token type |
|---|---|---|
| `/api/shopify/*` | None (public catalog) | — |
| `/api/auth/shopify/*` | None | — |
| `/api/auth/me`, `/api/auth/addresses`, `/api/auth/orders` | `Authorization: Bearer <token>` | Customer JWT |
| `/api/tracking/order` | `Authorization: Bearer <token>` | Customer JWT |
| `/api/delivery/job` | `Authorization: Bearer <token>` | Customer JWT |
| `/api/rider/*` (except auth) | `Authorization: Bearer <token>` | Rider JWT |
| `/api/vendor/*` (except auth) | `Authorization: Bearer <token>` | Vendor JWT |
| `/api/admin/*` (except auth/login/refresh) | `Authorization: Bearer <token>` | Admin JWT |
| `/api/webhooks/shopify` | `X-Shopify-Hmac-Sha256` header | HMAC-SHA256 |

---

## Customer APIs

### Shopify Storefront (public)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/shopify/home` | Category groups + product rails |
| GET | `/api/shopify/categories` | Category groups only |
| GET | `/api/shopify/collections/{handle}/products` | Products in a collection |
| GET | `/api/shopify/products/{handle}` | Single product detail |
| GET | `/api/shopify/search?q=&first=` | Live product search |
| POST | `/api/shopify/cart` | Create cart |
| GET | `/api/shopify/cart?cart_id=` | Fetch cart |
| POST | `/api/shopify/cart/lines` | Add line |
| PUT | `/api/shopify/cart/lines` | Update line quantity |
| DELETE | `/api/shopify/cart/lines` | Remove line |
| PUT | `/api/shopify/cart/note` | Set delivery instructions |
| POST | `/api/shopify/checkout/prepare` | Validate stock + attach buyer + return checkoutUrl |

### Customer Auth (Shopify OAuth)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/shopify/authorize-url` | Get Shopify authorize URL |
| POST | `/api/auth/shopify/token-exchange` | Exchange code for Now Kart session |
| POST | `/api/auth/refresh` | Rotate refresh token |
| POST | `/api/auth/logout` | Revoke refresh token |
| GET | `/api/auth/me` | Profile + addresses + recent orders |
| GET | `/api/auth/orders?id=` | Full order detail (GID query param) |
| GET | `/api/auth/addresses` | List addresses |
| POST | `/api/auth/addresses` | Create address |
| PUT | `/api/auth/addresses` | Update address |
| DELETE | `/api/auth/addresses` | Delete address |

### Tracking & Delivery (customer-facing)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/tracking/order?id=` | Customer JWT | Shopify-derived order tracking |
| GET | `/api/delivery/job?orderId=` | Customer JWT | Delivery job status (limited view) |

---

## Rider APIs

All require Rider JWT (`role="rider"`).

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/rider/auth/login` | Login (email + password) |
| POST | `/api/rider/auth/refresh` | Rotate refresh token |
| POST | `/api/rider/auth/logout` | Revoke refresh token |
| GET | `/api/rider/profile` | Rider's own profile |
| PUT | `/api/rider/status` | Set ONLINE / OFFLINE / BUSY |
| POST | `/api/rider/push-token` | Register push token (stored, not yet used) |
| GET | `/api/rider/job/current` | Currently assigned delivery job |
| GET | `/api/rider/job/history` | Completed/cancelled delivery history |
| GET | `/api/rider/stats` | Live delivery statistics |

---

## Vendor APIs

All require Vendor JWT (`role="vendor"`).

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/vendor/auth/login` | Login (email + password) |
| POST | `/api/vendor/auth/refresh` | Rotate refresh token |
| POST | `/api/vendor/auth/logout` | Revoke refresh token |
| GET | `/api/vendor/profile` | Vendor's own profile |
| PUT | `/api/vendor/status` | Set OPEN / CLOSED / BUSY |
| POST | `/api/vendor/push-token` | Register push token |
| GET | `/api/vendor/orders` | Active order queue |
| GET | `/api/vendor/orders/history` | Completed/terminal order history |
| GET | `/api/vendor/orders/{jobId}` | Single order detail |
| POST | `/api/vendor/orders/{jobId}/accept` | Accept order → VENDOR_ACCEPTED |
| POST | `/api/vendor/orders/{jobId}/reject` | Reject order → REJECTED (terminal) |
| PUT | `/api/vendor/orders/{jobId}/unavailable-items` | Mark items unavailable |
| POST | `/api/vendor/orders/{jobId}/preparing` | Start preparing → PREPARING |
| POST | `/api/vendor/orders/{jobId}/ready` | Mark ready → READY_FOR_PICKUP |
| GET | `/api/vendor/stats` | Live order statistics |

---

## Admin APIs

All require Admin JWT (role in `{super_admin, admin, operations_manager, support}`).

### Auth & Profile

| Method | Path | Min Role | Purpose |
|---|---|---|---|
| POST | `/api/admin/auth/login` | — | Admin login |
| POST | `/api/admin/auth/refresh` | — | Rotate token |
| POST | `/api/admin/auth/logout` | support | Revoke token |
| GET | `/api/admin/profile` | support | Own profile |
| POST | `/api/admin/change-password` | support | Change own password |

### Admin User Management

| Method | Path | Min Role | Purpose |
|---|---|---|---|
| POST | `/api/admin/admins` | super_admin | Create admin account |
| GET | `/api/admin/admins` | super_admin | List all admins |
| PUT | `/api/admin/admins/{id}/activate` | super_admin | Re-activate admin |
| PUT | `/api/admin/admins/{id}/suspend` | super_admin | Suspend admin |
| DELETE | `/api/admin/admins/{id}` | super_admin | Soft-delete admin |
| GET | `/api/admin/audit-logs` | admin | Paginated audit trail |

### Dashboard

| Method | Path | Min Role | Purpose |
|---|---|---|---|
| GET | `/api/admin/dashboard/stats` | support | Platform-wide KPIs |
| GET | `/api/admin/dashboard/health` | support | System health check |

### Rider Management

| Method | Path | Min Role | Purpose |
|---|---|---|---|
| POST | `/api/admin/riders` | admin | Create rider |
| GET | `/api/admin/riders` | support | List riders |
| GET | `/api/admin/riders/{id}` | support | Rider detail |
| PUT | `/api/admin/riders/{id}` | admin | Update rider |
| PUT | `/api/admin/riders/{id}/activate` | admin | Re-activate |
| PUT | `/api/admin/riders/{id}/suspend` | admin | Suspend + revoke sessions |
| DELETE | `/api/admin/riders/{id}` | admin | Soft delete |
| GET | `/api/admin/riders/{id}/history` | support | Delivery history |
| GET | `/api/admin/riders/{id}/stats` | support | Live stats |
| POST | `/api/admin/riders/{id}/assign-job/{jobId}` | operations_manager | Assign rider to job |

### Vendor Management

| Method | Path | Min Role | Purpose |
|---|---|---|---|
| POST | `/api/admin/vendors` | admin | Create vendor |
| GET | `/api/admin/vendors` | support | List vendors |
| GET | `/api/admin/vendors/{id}` | support | Vendor detail |
| PUT | `/api/admin/vendors/{id}` | admin | Update vendor |
| PUT | `/api/admin/vendors/{id}/activate` | admin | Re-activate |
| PUT | `/api/admin/vendors/{id}/suspend` | admin | Suspend + revoke sessions |
| DELETE | `/api/admin/vendors/{id}` | admin | Soft delete |
| PUT | `/api/admin/vendors/{id}/assign-store/{storeId}` | admin | Link vendor to store |

### Delivery Management

| Method | Path | Min Role | Purpose |
|---|---|---|---|
| GET | `/api/admin/delivery/jobs` | support | List jobs (filters: status, store, vendor, rider) |
| GET | `/api/admin/delivery/jobs/{id}` | support | Full job detail |
| PUT | `/api/admin/delivery/jobs/{id}/status` | operations_manager | Override status |
| POST | `/api/admin/delivery/jobs/{id}/cancel` | operations_manager | Cancel job |
| POST | `/api/admin/delivery/jobs/{id}/force-complete` | admin | Force mark delivered |
| POST | `/api/admin/delivery/jobs/{id}/assign-rider/{riderId}` | operations_manager | Assign rider |
| POST | `/api/admin/delivery/jobs/{id}/reassign-vendor` | admin | Reassign vendor |

### Store Management

| Method | Path | Min Role | Purpose |
|---|---|---|---|
| GET | `/api/admin/stores` | support | List stores |
| POST | `/api/admin/stores` | admin | Create store |
| GET | `/api/admin/stores/{id}` | support | Store detail |
| PUT | `/api/admin/stores/{id}` | admin | Update store |
| PUT | `/api/admin/stores/{id}/activate` | admin | Activate |
| PUT | `/api/admin/stores/{id}/suspend` | admin | Suspend |

---

## Webhooks

| Method | Path | Auth | Topics |
|---|---|---|---|
| POST | `/api/webhooks/shopify` | HMAC-SHA256 header | `orders/paid`, `orders/cancelled` |

---

## Common Response Patterns

### Success
```json
{ "id": "...", "status": "...", ... }
```

### Paginated
```json
{ "items": [...], "total": 42, "limit": 50, "offset": 0 }
```

### Error
```json
{ "detail": "Human-readable error message" }
```

### HTTP Status Conventions

| Code | Meaning |
|---|---|
| 200 | Success |
| 201 | Created |
| 204 | No content (logout, delete) |
| 400 | Bad request / validation |
| 401 | Authentication required or invalid |
| 403 | Authenticated but insufficient role |
| 404 | Resource not found |
| 409 | Conflict (duplicate, invalid state transition) |
| 500 | Internal server error |
