# NOW KART — BUSINESS WORKFLOW

→ See [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) for system context.

---

## Order Lifecycle

```mermaid
sequenceDiagram
    participant C as Customer
    participant S as Shopify
    participant B as Backend
    participant V as Vendor
    participant R as Rider

    C->>S: Checkout + Payment
    S->>B: webhook orders/paid
    B->>B: Create DeliveryJob\n(WAITING_VENDOR)
    B->>V: Notify vendor (future: push)

    V->>B: Accept order
    B->>B: VENDOR_ACCEPTED
    V->>B: Mark unavailable items (optional)
    V->>B: Start preparing
    B->>B: PREPARING
    V->>B: Mark ready for pickup
    B->>B: READY_FOR_PICKUP

    Note over B: Rider assignment unlocked

    B->>R: Admin assigns rider
    B->>B: ASSIGNED
    R->>B: Arrives at store
    B->>B: AT_STORE
    R->>B: Picks up order
    B->>B: IN_TRANSIT
    C->>B: Tracks live (polling/WebSocket future)
    R->>B: Arrives at customer
    B->>B: ARRIVED
    R->>B: Delivers + photo proof
    B->>B: DELIVERED ✅
```

---

## Delivery Job State Machine

```mermaid
stateDiagram-v2
    [*] --> WAITING_VENDOR : orders/paid webhook

    WAITING_VENDOR --> VENDOR_ACCEPTED : vendor accepts
    WAITING_VENDOR --> REJECTED : vendor rejects
    WAITING_VENDOR --> CANCELLED : Shopify cancels / admin

    VENDOR_ACCEPTED --> PREPARING : vendor starts prep
    VENDOR_ACCEPTED --> CANCELLED

    PREPARING --> READY_FOR_PICKUP : vendor marks ready
    PREPARING --> CANCELLED

    READY_FOR_PICKUP --> ASSIGNED : admin assigns rider
    READY_FOR_PICKUP --> PENDING_ASSIGNMENT : enters rider queue
    READY_FOR_PICKUP --> CANCELLED

    PENDING_ASSIGNMENT --> ASSIGNED : rider assigned
    PENDING_ASSIGNMENT --> CANCELLED

    ASSIGNED --> AT_STORE : rider arrives at store
    ASSIGNED --> PENDING_ASSIGNMENT : unassign/reassign
    ASSIGNED --> CANCELLED

    AT_STORE --> IN_TRANSIT : rider picks up
    AT_STORE --> CANCELLED

    IN_TRANSIT --> ARRIVED : rider at customer door
    IN_TRANSIT --> FAILED_DELIVERY : delivery attempt failed

    ARRIVED --> DELIVERED : confirmed + proof
    ARRIVED --> FAILED_DELIVERY

    FAILED_DELIVERY --> PENDING_ASSIGNMENT : retry
    FAILED_DELIVERY --> CANCELLED

    DELIVERED --> [*]
    CANCELLED --> [*]
    REJECTED --> [*]
```

### State Labels (shown in UI)

| Status | Customer Label | Internal |
|---|---|---|
| `waiting_vendor` | Waiting for Vendor | WAITING_VENDOR |
| `vendor_accepted` | Vendor Accepted | VENDOR_ACCEPTED |
| `preparing` | Preparing Order | PREPARING |
| `ready_for_pickup` | Ready for Pickup | READY_FOR_PICKUP |
| `pending_assignment` | Awaiting Rider | PENDING_ASSIGNMENT |
| `assigned` | Rider Assigned | ASSIGNED |
| `at_store` | Rider at Store | AT_STORE |
| `in_transit` | Out for Delivery | IN_TRANSIT |
| `arrived` | Rider Arrived | ARRIVED |
| `delivered` | Delivered ✅ | DELIVERED (terminal) |
| `failed_delivery` | Delivery Failed | FAILED_DELIVERY |
| `cancelled` | Cancelled | CANCELLED (terminal) |
| `rejected` | Order Rejected | REJECTED (terminal) |

---

## Vendor Flow

1. Vendor logs in → sets status **OPEN**
2. New order arrives in queue (`WAITING_VENDOR`)
3. Vendor reviews items → **accepts** or **rejects** (with reason)
4. Vendor marks any unavailable items (stored on delivery job)
5. Vendor taps **Start Preparing** → `PREPARING`
6. Vendor taps **Ready for Pickup** → `READY_FOR_PICKUP`
7. Admin dashboard shows job as assignable

> Rider assignment is **blocked** until `READY_FOR_PICKUP` or `PENDING_ASSIGNMENT`.

---

## Rider Flow

1. Rider logs in → sets status **ONLINE**
2. Admin assigns job → status `ASSIGNED`, rider → BUSY
3. Rider navigates to store (deep-link to Google Maps / Apple Maps)
4. Rider marks **At Store** → `AT_STORE`
5. Rider collects order → marks **Picked Up** → `IN_TRANSIT`
6. Rider navigates to customer
7. Rider marks **Arrived** → `ARRIVED`
8. Rider takes mandatory proof photo → marks **Delivered** → `DELIVERED`
9. Rider status returns to ONLINE

---

## Cancellation Rules

| Status at Cancellation | Behaviour |
|---|---|
| `WAITING_VENDOR` | Auto-cancel. Notify vendor. |
| `VENDOR_ACCEPTED`, `PREPARING`, `READY_FOR_PICKUP` | Auto-cancel. Notify vendor. |
| `ASSIGNED` | Auto-cancel. Notify rider. |
| `AT_STORE` | Auto-cancel. Notify rider. |
| `IN_TRANSIT` | **NOT auto-cancelled.** Alert event added. Admin must intervene. |
| `DELIVERED`, `CANCELLED`, `REJECTED` | Terminal — no further transitions. |

---

## Shopify Webhook Topics Handled

| Topic | Action |
|---|---|
| `orders/paid` | Create delivery job (`WAITING_VENDOR`) + link vendor from store |
| `orders/cancelled` | Cancel delivery job (except IN_TRANSIT — alert only) |

> Webhook idempotency key: `X-Shopify-Webhook-Id` stored in `webhook_events` collection.

---

## Future Workflows (placeholders — not implemented)

- **Auto-assignment**: proximity-based rider selection using MongoDB 2dsphere index
- **Live GPS tracking**: Redis pub/sub + WebSocket fan-out to Customer App
- **Dynamic ETA**: Google Distance Matrix API, server-side, cached 90s
- **Push notifications**: Expo Push / FCM on every state transition
- **Rejected order refunds**: Shopify Admin API call from admin module
