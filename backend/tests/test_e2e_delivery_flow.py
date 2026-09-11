"""
E2E Operational Verification — NowKart Delivery Flow
=====================================================

Covers the complete delivery lifecycle from job creation to final delivery:

  Step 1.  Synthetic delivery job exists (created via webhook)
  Step 2.  Admin can view the delivery job
  Step 3.  Admin walks job through vendor workflow → pending_assignment
  Step 4.  Admin assigns an available Rider (job → assigned)
  Step 5a. Assigned Rider retrieves the current job (GET /api/rider/job/current)
  Step 5b. Rider delivery detail includes delivery/location data for Maps/GPS
           (pickupAddress + deliveryAddress with coordinates field present)
  Step 6.  Rider push-token registration accepted (POST /api/rider/push-token)
  Step 7.  Rider status transitions through the delivery state machine:
           assigned → at_store → in_transit → arrived → delivered
  Step 8.  Status updates are reflected in the delivery jobs API after each transition
  Step 9.  Customer delivery endpoint returns correct status (no Shopify JWT required path)
  Step 10. Multi-vendor: two-vendor order produces two separate jobs;
           cancelling one does NOT cancel the other
  Step 11. Regression: existing APIs (admin login, rider auth) still work

Synthetic test data is created and cleaned up within the test run.
No permanent production data is created.

Run with:
    LOCAL_BACKEND_URL=http://localhost:8099 pytest tests/test_e2e_delivery_flow.py -v
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get(
    "LOCAL_BACKEND_URL",
    os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8099"),
).rstrip("/")

API = f"{BASE_URL}/api"

ADMIN_EMAIL    = "admin@nowkart.com"
ADMIN_PASSWORD = "Admin2026!"

_RUN_ID = str(uuid.uuid4())[:8]
RIDER_EMAIL    = f"e2e_rider_{_RUN_ID}@nowkart.com"
RIDER_PASSWORD = "E2ERider2026!"

VENDOR_A_NAME = f"E2E-VendorA-{_RUN_ID}"
VENDOR_B_NAME = f"E2E-VendorB-{_RUN_ID}"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _admin_token() -> str:
    r = requests.post(f"{API}/admin/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["accessToken"]


def _webhook(session, topic: str, payload: dict, wh_id: str = None) -> requests.Response:
    return session.post(
        f"{API}/webhooks/shopify",
        json=payload,
        headers={
            "X-Shopify-Topic":       topic,
            "X-Shopify-Webhook-Id":  wh_id or str(uuid.uuid4()),
            "X-Shopify-Shop-Domain": "test.myshopify.com",
        },
        timeout=15,
    )


def _legacy_order(order_id: int = None) -> dict:
    """Shopify order payload with NO vendor field → legacy single-job path."""
    if order_id is None:
        order_id = int(time.time() * 1000 + int(_RUN_ID[:4], 16)) % 1_000_000_000
    return {
        "id":               order_id,
        "name":             f"#E2E-{order_id}",
        "email":            "customer@e2etest.com",
        "total_price":      "29.99",
        "currency":         "GBP",
        "financial_status": "paid",
        "customer": {"id": 9999, "email": "customer@e2etest.com",
                     "first_name": "E2E", "last_name": "Customer"},
        "shipping_address": {
            "first_name": "E2E", "last_name": "Customer",
            "address1": "42 Delivery Lane", "city": "London",
            "zip": "E2 9AB", "country": "GB",
        },
        "line_items": [
            {"id": 1, "title": "Test Groceries", "quantity": 2, "price": "14.99"},
        ],
        "note": "Leave at door",
    }


def _vendor_order(order_id: int, vendor_a: str, vendor_b: str) -> dict:
    """Multi-vendor Shopify order payload."""
    return {
        "id":               order_id,
        "name":             f"#MV-{order_id}",
        "email":            "customer@e2etest.com",
        "total_price":      "45.00",
        "currency":         "GBP",
        "financial_status": "paid",
        "customer": {"id": 9998, "email": "customer@e2etest.com",
                     "first_name": "E2E", "last_name": "MVCustomer"},
        "shipping_address": {
            "first_name": "E2E", "last_name": "MVCustomer",
            "address1": "99 MV Lane", "city": "London",
            "zip": "E3 5XY", "country": "GB",
        },
        "line_items": [
            {"id": 10, "title": "Item-A", "quantity": 1, "price": "20.00", "vendor": vendor_a},
            {"id": 11, "title": "Item-B", "quantity": 1, "price": "25.00", "vendor": vendor_b},
        ],
    }


# ─── Module-level state ───────────────────────────────────────────────────────

_S = {
    "admin_token":  None,
    "rider_token":  None,
    "rider_id":     None,
    "store_id":     None,
    "job_id":       None,          # single-job E2E
    "mv_job_a_id":  None,          # multi-vendor job A
    "mv_job_b_id":  None,          # multi-vendor job B
    "vendor_a_id":  None,
    "vendor_b_id":  None,
}


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    """Create test rider + vendor + synthetic jobs; clean up after all tests."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})

    # Admin login
    tok = _admin_token()
    _S["admin_token"] = tok

    # Default store
    stores = s.get(f"{API}/delivery/stores", timeout=15).json()
    _S["store_id"] = stores[0]["id"]

    # Create test rider
    r = s.post(f"{API}/admin/riders",
               json={"email": RIDER_EMAIL, "phone": "+447001234567",
                     "password": RIDER_PASSWORD, "firstName": "E2E",
                     "lastName": "Rider", "vehicleType": "bicycle"},
               headers=_h(tok), timeout=15)
    assert r.status_code == 201, f"Rider create failed: {r.text}"
    _S["rider_id"] = r.json()["id"]

    # Create vendors for multi-vendor tests
    for name, key in [(VENDOR_A_NAME, "vendor_a_id"), (VENDOR_B_NAME, "vendor_b_id")]:
        vr = s.post(f"{API}/admin/vendors",
                    json={"email": f"{name.lower().replace(' ', '_')}@e2e.com",
                          "phone": "+447009999999", "password": "VendorPass2026!",
                          "businessName": name, "firstName": "E2E", "lastName": "Vendor",
                          "storeId": _S["store_id"]},
                    headers=_h(tok), timeout=15)
        assert vr.status_code in (200, 201), f"Vendor create failed: {vr.text}"
        _S[key] = vr.json()["id"]

    # Rider login
    lr = s.post(f"{API}/rider/auth/login",
                json={"email": RIDER_EMAIL, "password": RIDER_PASSWORD}, timeout=15)
    assert lr.status_code == 200
    _S["rider_token"] = lr.json()["accessToken"]

    # Synthetic legacy job via webhook
    order_data = _legacy_order()
    wh = _webhook(s, "orders/paid", order_data)
    assert wh.status_code == 200, f"Webhook failed: {wh.text}"
    result = wh.json()["result"]
    _S["job_id"] = result["jobId"]

    # Synthetic multi-vendor job
    mv_order_id = int(time.time() * 1000 + 12345) % 1_000_000_000
    mv_wh = _webhook(s, "orders/paid", _vendor_order(mv_order_id, VENDOR_A_NAME, VENDOR_B_NAME))
    assert mv_wh.status_code == 200, f"MV Webhook failed: {mv_wh.text}"
    mv_result = mv_wh.json()["result"]
    for j in mv_result.get("jobs", []):
        if j["vendorName"] == VENDOR_A_NAME:
            _S["mv_job_a_id"] = j["jobId"]
        elif j["vendorName"] == VENDOR_B_NAME:
            _S["mv_job_b_id"] = j["jobId"]

    yield

    # ── Teardown ──────────────────────────────────────────────────────────────
    # Cancel any active jobs
    for jid in [_S["job_id"], _S["mv_job_a_id"], _S["mv_job_b_id"]]:
        if jid:
            s.post(f"{API}/delivery/jobs/{jid}/cancel", timeout=10)

    # Soft-delete rider
    s.delete(f"{API}/admin/riders/{_S['rider_id']}",
             headers=_h(_S["admin_token"]), timeout=10)

    # Soft-delete vendors
    for key in ("vendor_a_id", "vendor_b_id"):
        if _S[key]:
            s.delete(f"{API}/admin/vendors/{_S[key]}",
                     headers=_h(_S["admin_token"]), timeout=10)


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1 — Synthetic delivery job was created via webhook
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep1JobExists:

    def test_job_id_was_returned_by_webhook(self):
        assert _S["job_id"], "Job ID was not returned by the orders/paid webhook"

    def test_job_initial_status_is_waiting_vendor(self):
        r = requests.get(f"{API}/delivery/jobs/{_S['job_id']}", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "waiting_vendor"


# ═══════════════════════════════════════════════════════════════════════════════
# Step 2 — Admin views the delivery job
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep2AdminViewsJob:

    def test_admin_can_list_delivery_jobs(self):
        r = requests.get(f"{API}/delivery/jobs?limit=5",
                         headers=_h(_S["admin_token"]), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] > 0
        ids = [j["id"] for j in data["jobs"]]
        assert _S["job_id"] in ids, "New job not found in job list"

    def test_admin_can_get_full_job_detail(self):
        r = requests.get(f"{API}/delivery/jobs/{_S['job_id']}", timeout=15)
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["id"] == _S["job_id"]
        assert job["shopifyOrderName"].startswith("#E2E-")
        assert job["orderItems"][0]["title"] == "Test Groceries"
        assert job["deliveryInstructions"] == "Leave at door"

    def test_admin_can_view_via_admin_dashboard_endpoint(self):
        r = requests.get(f"{API}/delivery/jobs/{_S['job_id']}",
                         headers=_h(_S["admin_token"]), timeout=15)
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Step 3 — Admin walks job through vendor workflow → pending_assignment
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep3VendorWorkflowToPendingAssignment:
    """
    Walk: waiting_vendor → vendor_accepted → preparing → ready_for_pickup
          → pending_assignment
    Uses the admin status override endpoint since this E2E test doesn't
    exercise the full vendor UI flow (vendor auth is tested separately).
    """

    def _transition(self, new_status: str):
        r = requests.put(
            f"{API}/delivery/jobs/{_S['job_id']}/status",
            json={"status": new_status, "actor": "admin", "note": f"E2E test: → {new_status}"},
            timeout=15,
        )
        assert r.status_code == 200, f"Transition to {new_status} failed: {r.text}"
        return r.json()

    def test_01_to_vendor_accepted(self):
        job = self._transition("vendor_accepted")
        assert job["status"] == "vendor_accepted"

    def test_02_to_preparing(self):
        job = self._transition("preparing")
        assert job["status"] == "preparing"

    def test_03_to_ready_for_pickup(self):
        job = self._transition("ready_for_pickup")
        assert job["status"] == "ready_for_pickup"

    def test_04_to_pending_assignment(self):
        job = self._transition("pending_assignment")
        assert job["status"] == "pending_assignment"
        assert job["assignedRiderId"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Step 4 — Admin assigns a Rider
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep4AdminAssignsRider:

    def test_assign_rider_via_admin_endpoint(self):
        r = requests.post(
            f"{API}/admin/riders/{_S['rider_id']}/assign-job/{_S['job_id']}",
            headers=_h(_S["admin_token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        job = r.json()["job"]
        assert job["status"] == "assigned"
        assert job["assignedRiderId"] == _S["rider_id"]

    def test_job_status_is_assigned_after_assignment(self):
        r = requests.get(f"{API}/delivery/jobs/{_S['job_id']}", timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "assigned"
        assert r.json()["assignedRiderId"] == _S["rider_id"]


# ═══════════════════════════════════════════════════════════════════════════════
# Step 5a — Rider retrieves current job
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep5aRiderGetsCurrentJob:

    def test_rider_current_job_returns_assigned_job(self):
        r = requests.get(f"{API}/rider/job/current",
                         headers=_h(_S["rider_token"]), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["job"] is not None, "Rider has no current job after assignment"
        assert body["job"]["id"] == _S["job_id"]
        assert body["job"]["status"] == "assigned"

    def test_rider_current_job_shape_is_full_delivery_job_out(self):
        """Rider App Maps/GPS needs the full DeliveryJobOut shape."""
        r = requests.get(f"{API}/rider/job/current",
                         headers=_h(_S["rider_token"]), timeout=15)
        job = r.json()["job"]
        # All required fields present
        for field in ["id", "shopifyOrderId", "status", "deliveryAddress",
                       "pickupAddress", "orderItems", "assignedRiderId",
                       "orderTotal", "shopifyOrderName"]:
            assert field in job, f"Missing field: {field}"


# ═══════════════════════════════════════════════════════════════════════════════
# Step 5b — Rider delivery detail includes location data contract for Maps/GPS
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep5bLocationDataContract:
    """
    Verifies that the delivery job response includes the `coordinates` field
    on both deliveryAddress and pickupAddress as per the Maps/GPS contract.
    The field may be null (ETA module not yet implemented) but MUST be present
    in the schema so the Rider App can render the map correctly.
    """

    def test_delivery_address_has_coordinates_field(self):
        r = requests.get(f"{API}/rider/job/current",
                         headers=_h(_S["rider_token"]), timeout=15)
        job = r.json()["job"]
        assert "coordinates" in job["deliveryAddress"], \
            "deliveryAddress.coordinates field missing — Rider App Maps cannot render"

    def test_pickup_address_has_coordinates_field(self):
        r = requests.get(f"{API}/rider/job/current",
                         headers=_h(_S["rider_token"]), timeout=15)
        job = r.json()["job"]
        assert "coordinates" in job["pickupAddress"], \
            "pickupAddress.coordinates field missing — Rider App Maps cannot render"

    def test_delivery_address_has_human_readable_fields(self):
        r = requests.get(f"{API}/rider/job/current",
                         headers=_h(_S["rider_token"]), timeout=15)
        addr = r.json()["job"]["deliveryAddress"]
        assert addr["line1"], "deliveryAddress.line1 is empty"
        assert addr["city"],  "deliveryAddress.city is empty"

    def test_pickup_address_has_human_readable_fields(self):
        r = requests.get(f"{API}/rider/job/current",
                         headers=_h(_S["rider_token"]), timeout=15)
        addr = r.json()["job"]["pickupAddress"]
        assert addr["line1"], "pickupAddress.line1 is empty"
        assert addr["city"],  "pickupAddress.city is empty"

    def test_coordinates_null_is_valid_api_contract(self):
        """
        coordinates=null is expected (ETA/geocoding not yet implemented).
        Documents the current state for the Rider App Maps feature:
        the app must handle null gracefully (fall back to address text).
        """
        r = requests.get(f"{API}/rider/job/current",
                         headers=_h(_S["rider_token"]), timeout=15)
        job = r.json()["job"]
        # null is acceptable — the field must exist, value may be null
        da_coords = job["deliveryAddress"]["coordinates"]
        pa_coords = job["pickupAddress"]["coordinates"]
        assert da_coords is None or isinstance(da_coords, dict), \
            "coordinates must be null or {lat, lng}"
        assert pa_coords is None or isinstance(pa_coords, dict), \
            "coordinates must be null or {lat, lng}"


# ═══════════════════════════════════════════════════════════════════════════════
# Step 6 — Rider push-token registration
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep6PushTokenRegistration:

    def test_push_token_accepted_by_backend(self):
        r = requests.post(
            f"{API}/rider/push-token",
            json={"token": f"ExponentPushToken[test_{_RUN_ID}]", "platform": "ios"},
            headers=_h(_S["rider_token"]),
            timeout=15,
        )
        assert r.status_code == 204, f"Push token registration failed: {r.text}"

    def test_push_token_stored_on_rider_document(self):
        r = requests.get(f"{API}/admin/riders/{_S['rider_id']}",
                         headers=_h(_S["admin_token"]), timeout=15)
        assert r.status_code == 200
        rider = r.json()
        assert rider["devicePushToken"] == f"ExponentPushToken[test_{_RUN_ID}]"
        assert rider["platformOS"] == "ios"


# ═══════════════════════════════════════════════════════════════════════════════
# Step 7 — Rider status transitions: assigned → at_store → in_transit
#          → arrived → delivered
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep7RiderStatusTransitions:
    """
    Uses PUT /api/delivery/jobs/{jobId}/status with actor="rider:{riderId}".
    This is the currently available contract for rider-side status updates.
    Dedicated rider-action endpoints (POST /api/rider/job/{id}/at-store etc.)
    are noted as a future Rider App backend addition (see ROADMAP.md).
    """

    def _transition(self, new_status: str):
        r = requests.put(
            f"{API}/delivery/jobs/{_S['job_id']}/status",
            json={"status": new_status,
                  "actor": f"rider:{_S['rider_id']}",
                  "note": f"E2E rider transition → {new_status}"},
            timeout=15,
        )
        assert r.status_code == 200, f"Transition to {new_status} failed ({r.status_code}): {r.text}"
        return r.json()

    def test_01_assigned_to_at_store(self):
        job = self._transition("at_store")
        assert job["status"] == "at_store"

    def test_02_at_store_to_in_transit(self):
        job = self._transition("in_transit")
        assert job["status"] == "in_transit"
        assert job["pickedUpAt"] is not None, "pickedUpAt should be set on IN_TRANSIT"

    def test_03_in_transit_to_arrived(self):
        job = self._transition("arrived")
        assert job["status"] == "arrived"
        assert job["arrivedAt"] is not None, "arrivedAt should be set on ARRIVED"

    def test_04_arrived_to_delivered(self):
        job = self._transition("delivered")
        assert job["status"] == "delivered"
        assert job["completedAt"] is not None, "completedAt should be set on DELIVERED"

    def test_05_delivered_is_terminal_cannot_transition(self):
        """Terminal state — any further transition must return 409."""
        r = requests.put(
            f"{API}/delivery/jobs/{_S['job_id']}/status",
            json={"status": "cancelled", "actor": "admin"},
            timeout=15,
        )
        assert r.status_code == 409, (
            f"Expected 409 for terminal-state transition, got {r.status_code}: {r.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 8 — Status updates are reflected in the backend
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep8StatusReflected:

    def test_job_is_delivered_in_detail_api(self):
        r = requests.get(f"{API}/delivery/jobs/{_S['job_id']}", timeout=15)
        assert r.status_code == 200
        job = r.json()
        assert job["status"] == "delivered"
        assert job["statusLabel"]  # non-empty label

    def test_recent_events_trail_contains_all_transitions(self):
        r = requests.get(f"{API}/delivery/jobs/{_S['job_id']}", timeout=15)
        events = r.json()["recentEvents"]
        statuses = [e["status"] for e in events]
        expected = ["at_store", "in_transit", "arrived", "delivered"]
        for s in expected:
            assert s in statuses, f"Expected status '{s}' in recentEvents; found: {statuses}"

    def test_rider_actor_recorded_in_events(self):
        r = requests.get(f"{API}/delivery/jobs/{_S['job_id']}", timeout=15)
        events = r.json()["recentEvents"]
        actors = [e["actor"] for e in events]
        assert any(a.startswith("rider:") for a in actors), \
            f"No rider actor recorded in events: {actors}"

    def test_rider_current_job_is_null_after_delivery(self):
        """After delivery, rider should have no active job."""
        r = requests.get(f"{API}/rider/job/current",
                         headers=_h(_S["rider_token"]), timeout=15)
        assert r.status_code == 200
        assert r.json()["job"] is None, "Rider still shows a current job after delivery"

    def test_delivered_job_appears_in_rider_history(self):
        r = requests.get(f"{API}/rider/job/history",
                         headers=_h(_S["rider_token"]), timeout=15)
        assert r.status_code == 200
        history = r.json()["jobs"]
        ids = [j["id"] for j in history]
        assert _S["job_id"] in ids, "Delivered job not in rider history"


# ═══════════════════════════════════════════════════════════════════════════════
# Step 9 — Customer delivery endpoint reflects updated status
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep9CustomerFacingDeliveryStatus:
    """
    GET /api/delivery/job requires a customer JWT (Shopify OAuth).
    Full OAuth login requires a native device build — cannot be exercised here.
    This step verifies:
      (a) the endpoint exists and enforces auth (returns 401 without a token)
      (b) the DeliveryJobCustomerOut schema is populated on the full-detail endpoint
      (c) the statusLabel is user-facing for the delivered status
    """

    def test_customer_delivery_endpoint_exists_and_requires_auth(self):
        shopify_gid = f"gid://shopify/Order/99999999"
        r = requests.get(
            f"{API}/delivery/job",
            params={"orderId": shopify_gid},
            timeout=15,
        )
        assert r.status_code == 401, (
            f"Expected 401 (auth required) for /delivery/job without token, got {r.status_code}"
        )

    def test_delivered_status_label_is_human_readable(self):
        """Verify the statusLabel for delivered jobs is a non-empty string."""
        r = requests.get(f"{API}/delivery/jobs/{_S['job_id']}", timeout=15)
        job = r.json()
        assert job["status"] == "delivered"
        label = job["statusLabel"]
        assert label, "statusLabel is empty for delivered job"
        # STATUS_LABELS in delivery/service.py maps delivered → "Delivered"
        assert label == "Delivered", f"Unexpected statusLabel for delivered: {label!r}"

    def test_delivery_address_in_delivered_job(self):
        r = requests.get(f"{API}/delivery/jobs/{_S['job_id']}", timeout=15)
        job = r.json()
        assert job["deliveryAddress"]["city"] == "London"
        assert job["deliveryAddress"]["postcode"] == "E2 9AB"


# ═══════════════════════════════════════════════════════════════════════════════
# Step 10 — Multi-vendor jobs remain correctly separated
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep10MultiVendorSeparation:

    def test_two_vendor_jobs_were_created(self):
        assert _S["mv_job_a_id"], "No job created for Vendor A"
        assert _S["mv_job_b_id"], "No job created for Vendor B"
        assert _S["mv_job_a_id"] != _S["mv_job_b_id"], "Vendor A and B share the same job ID"

    def test_each_job_has_correct_items(self):
        def item_titles(job_id: str):
            r = requests.get(f"{API}/delivery/jobs/{job_id}", timeout=15)
            return {i["title"] for i in r.json()["orderItems"]}

        titles_a = item_titles(_S["mv_job_a_id"])
        titles_b = item_titles(_S["mv_job_b_id"])

        assert "Item-A" in titles_a, f"Item-A not in vendor A job: {titles_a}"
        assert "Item-B" in titles_b, f"Item-B not in vendor B job: {titles_b}"
        assert "Item-B" not in titles_a, f"Item-B leaked into vendor A job"
        assert "Item-A" not in titles_b, f"Item-A leaked into vendor B job"

    def test_jobs_share_same_shopify_order_id(self):
        def shopify_id(job_id: str):
            r = requests.get(f"{API}/delivery/jobs/{job_id}", timeout=15)
            return r.json()["shopifyOrderId"]

        assert shopify_id(_S["mv_job_a_id"]) == shopify_id(_S["mv_job_b_id"]), \
            "Multi-vendor jobs for same order have different shopifyOrderIds"

    def test_cancelling_one_job_does_not_cancel_other(self):
        # Cancel only vendor B's job
        r = requests.post(f"{API}/delivery/jobs/{_S['mv_job_b_id']}/cancel",
                          params={"reason": "E2E test cancel"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

        # Vendor A's job must remain untouched
        r2 = requests.get(f"{API}/delivery/jobs/{_S['mv_job_a_id']}", timeout=15)
        assert r2.status_code == 200
        assert r2.json()["status"] == "waiting_vendor", \
            f"Vendor A job was affected by cancelling vendor B: {r2.json()['status']}"

    def test_each_job_has_different_vendor_id(self):
        def vendor_id(job_id: str):
            r = requests.get(f"{API}/delivery/jobs/{job_id}", timeout=15)
            return r.json().get("vendorId")

        vid_a = vendor_id(_S["mv_job_a_id"])
        vid_b = vendor_id(_S["mv_job_b_id"])
        assert vid_a and vid_b, "One or both vendor jobs have no vendorId"
        assert vid_a != vid_b, "Both vendor jobs share the same vendorId"


# ═══════════════════════════════════════════════════════════════════════════════
# Step 11 — Regression: existing APIs still work
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep11Regression:

    def test_admin_login_still_works(self):
        r = requests.post(f"{API}/admin/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                          timeout=15)
        assert r.status_code == 200
        assert "accessToken" in r.json()

    def test_rider_auth_login_still_works(self):
        r = requests.post(f"{API}/rider/auth/login",
                          json={"email": RIDER_EMAIL, "password": RIDER_PASSWORD},
                          timeout=15)
        assert r.status_code == 200
        assert "accessToken" in r.json()

    def test_rider_stats_endpoint(self):
        r = requests.get(f"{API}/rider/stats",
                         headers=_h(_S["rider_token"]), timeout=15)
        assert r.status_code == 200
        stats = r.json()
        for field in ["totalDeliveries", "completedDeliveries", "successRate"]:
            assert field in stats

    def test_rider_history_returns_delivered_job(self):
        r = requests.get(f"{API}/rider/job/history?limit=10",
                         headers=_h(_S["rider_token"]), timeout=15)
        assert r.status_code == 200
        jobs = r.json()["jobs"]
        assert any(j["id"] == _S["job_id"] for j in jobs)

    def test_admin_can_view_rider_stats(self):
        r = requests.get(f"{API}/admin/riders/{_S['rider_id']}/stats",
                         headers=_h(_S["admin_token"]), timeout=15)
        assert r.status_code == 200
