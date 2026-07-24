"""
Vendor Backend Platform - Comprehensive Tests (Iteration 18)

Covers:
  - Admin CRUD: create vendor, 409 duplicate email, assign-store
  - Vendor Auth: login (8h JWT, expiresIn=28800), wrong password 401, refresh, logout
  - Vendor profile (JWT required, 401 without token)
  - Role isolation: rider JWT cannot access vendor endpoints; customer JWT cannot
  - PUT /vendor/status
  - Vendor order queue (GET /vendor/orders)
  - Full workflow: create job → accept → unavailable-items → preparing → ready → assign rider
  - accept/reject state transitions and 409 guards
  - GET /vendor/orders/history, GET /vendor/stats
  - Rider assignment from READY_FOR_PICKUP works; from WAITING_VENDOR returns 409
  - Regression: GET /api/delivery/jobs, GET /api/shopify/home, POST /api/rider/auth/login
  - Suspend vendor revokes all sessions
"""
import pytest
import requests
import os
import time
import random

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")

# Pre-existing test data from context
VENDOR_EMAIL = "vendor1@nowkart.com"
VENDOR_PASSWORD = "Vendor2026!"
VENDOR_ID = "6a6388672d04871fafaed76d"
STORE_ID = "6a60df3375edb5d63a6a465f"

RIDER_EMAIL = "rider1@nowkart.com"
RIDER_PASSWORD = "NowKart2026!"

# Unique email for tests that create a new vendor
_UNIQUE = int(time.time()) % 100000
NEW_VENDOR_EMAIL = f"TEST_vendor_{_UNIQUE}@nowkart.com"
NEW_VENDOR_PASSWORD = "VendorTest2026!"

# Module-level shared state
_state = {
    "vendor_access_token": None,
    "vendor_refresh_token": None,
    "rider_access_token": None,
    "new_vendor_id": None,
    "test_job_id": None,       # created via webhook for the workflow tests
    "reject_job_id": None,     # separate job for rejection test
    "rider_id": None,
}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def vendor_auth_headers(session):
    """Login with known vendor and return auth headers."""
    resp = session.post(f"{BASE_URL}/api/vendor/auth/login", json={
        "email": VENDOR_EMAIL,
        "password": VENDOR_PASSWORD,
    })
    assert resp.status_code == 200, f"Vendor login failed: {resp.text}"
    data = resp.json()
    _state["vendor_access_token"] = data["accessToken"]
    _state["vendor_refresh_token"] = data["refreshToken"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


# ─── Admin: Vendor CRUD ───────────────────────────────────────────────────────

class TestAdminVendorCreate:
    """Admin vendor creation and duplicate email checks"""

    def test_create_vendor_success(self, session):
        resp = session.post(f"{BASE_URL}/api/admin/vendors", json={
            "email": NEW_VENDOR_EMAIL,
            "phone": "+441234567890",
            "password": NEW_VENDOR_PASSWORD,
            "businessName": "TEST Business",
            "firstName": "TEST",
            "lastName": "Vendor",
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "id" in data
        assert data["email"] == NEW_VENDOR_EMAIL.lower()
        assert data["isActive"] is True
        assert data["isDeleted"] is False
        _state["new_vendor_id"] = data["id"]
        print(f"Created vendor: {data['id']}")

    def test_create_vendor_duplicate_email_returns_409(self, session):
        resp = session.post(f"{BASE_URL}/api/admin/vendors", json={
            "email": NEW_VENDOR_EMAIL,
            "phone": "+441234567890",
            "password": NEW_VENDOR_PASSWORD,
            "businessName": "TEST Business 2",
            "firstName": "TEST",
            "lastName": "Vendor2",
        })
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"

    def test_assign_store_to_vendor(self, session):
        vid = _state.get("new_vendor_id")
        if not vid:
            pytest.skip("new vendor not created")
        resp = session.put(f"{BASE_URL}/api/admin/vendors/{vid}/assign-store/{STORE_ID}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["storeId"] == STORE_ID, f"Expected storeId={STORE_ID}, got {data.get('storeId')}"


# ─── Vendor Auth ──────────────────────────────────────────────────────────────

class TestVendorAuth:
    """Vendor authentication flows"""

    def test_login_success_returns_tokens(self, session):
        resp = session.post(f"{BASE_URL}/api/vendor/auth/login", json={
            "email": VENDOR_EMAIL,
            "password": VENDOR_PASSWORD,
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "accessToken" in data
        assert "refreshToken" in data
        assert data["expiresIn"] == 28800, f"Expected expiresIn=28800 (8h), got {data.get('expiresIn')}"
        assert "vendor" in data
        assert data["vendor"]["email"] == VENDOR_EMAIL.lower()
        _state["vendor_access_token"] = data["accessToken"]
        _state["vendor_refresh_token"] = data["refreshToken"]

    def test_login_wrong_password_returns_401(self, session):
        resp = session.post(f"{BASE_URL}/api/vendor/auth/login", json={
            "email": VENDOR_EMAIL,
            "password": "wrongpassword",
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    def test_refresh_token_rotates(self, session):
        old_refresh = _state.get("vendor_refresh_token")
        if not old_refresh:
            pytest.skip("no refresh token available")
        resp = session.post(f"{BASE_URL}/api/vendor/auth/refresh", json={"refreshToken": old_refresh})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "accessToken" in data
        assert "refreshToken" in data
        assert data["refreshToken"] != old_refresh, "Refresh token should be rotated"
        # Update state for subsequent tests
        _state["vendor_access_token"] = data["accessToken"]
        _state["vendor_refresh_token"] = data["refreshToken"]

    def test_logout_revokes_token(self, session):
        # Login fresh to get tokens to revoke
        login_resp = session.post(f"{BASE_URL}/api/vendor/auth/login", json={
            "email": VENDOR_EMAIL,
            "password": VENDOR_PASSWORD,
        })
        assert login_resp.status_code == 200
        tokens = login_resp.json()
        logout_resp = session.post(f"{BASE_URL}/api/vendor/auth/logout", json={
            "refreshToken": tokens["refreshToken"]
        })
        assert logout_resp.status_code == 204, f"Expected 204, got {logout_resp.status_code}"
        # Revoked token should fail refresh
        refresh_resp = session.post(f"{BASE_URL}/api/vendor/auth/refresh", json={
            "refreshToken": tokens["refreshToken"]
        })
        assert refresh_resp.status_code == 401, "Revoked token should return 401 on refresh"


# ─── Vendor Profile ───────────────────────────────────────────────────────────

class TestVendorProfile:
    """Vendor profile endpoint"""

    def test_get_profile_with_jwt(self, session, vendor_auth_headers):
        resp = session.get(f"{BASE_URL}/api/vendor/profile", headers=vendor_auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "id" in data
        assert data["email"] == VENDOR_EMAIL.lower()
        assert "status" in data
        assert "stats" in data

    def test_get_profile_without_token_returns_401(self, session):
        resp = session.get(f"{BASE_URL}/api/vendor/profile")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_update_status_open(self, session, vendor_auth_headers):
        resp = session.put(f"{BASE_URL}/api/vendor/status",
                           headers=vendor_auth_headers,
                           json={"status": "open"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "open"

    def test_update_status_busy(self, session, vendor_auth_headers):
        resp = session.put(f"{BASE_URL}/api/vendor/status",
                           headers=vendor_auth_headers,
                           json={"status": "busy"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "busy"


# ─── Role Isolation ───────────────────────────────────────────────────────────

class TestRoleIsolation:
    """Verify that Rider and Customer JWTs cannot access vendor endpoints"""

    def test_rider_jwt_cannot_access_vendor_profile(self, session):
        # Login as rider to get rider JWT
        resp = session.post(f"{BASE_URL}/api/rider/auth/login", json={
            "email": RIDER_EMAIL,
            "password": RIDER_PASSWORD,
        })
        assert resp.status_code == 200, f"Rider login failed: {resp.text}"
        rider_data = resp.json()
        _state["rider_access_token"] = rider_data["accessToken"]
        _state["rider_id"] = rider_data["rider"]["id"]

        # Use rider token to hit vendor endpoint
        resp2 = session.get(f"{BASE_URL}/api/vendor/profile",
                            headers={"Authorization": f"Bearer {rider_data['accessToken']}"})
        assert resp2.status_code == 401, f"Rider JWT should be rejected by vendor endpoint, got {resp2.status_code}"

    def test_customer_jwt_cannot_access_vendor_profile(self, session):
        # Try to login as customer — get a customer token if possible
        cust_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@example.com",
            "password": "TestPass123!",
        })
        if cust_resp.status_code != 200:
            pytest.skip("No customer credentials available for role isolation test")
        cust_token = cust_resp.json().get("accessToken") or cust_resp.json().get("token")
        resp = session.get(f"{BASE_URL}/api/vendor/profile",
                           headers={"Authorization": f"Bearer {cust_token}"})
        assert resp.status_code == 401, f"Customer JWT should be rejected, got {resp.status_code}"


# ─── Shopify Webhook: Creates job with status=waiting_vendor ─────────────────

class TestWebhookVendorIntegration:
    """Shopify webhook creates jobs with waiting_vendor status and auto-links vendor"""

    def _create_webhook_job(self, session, order_id_suffix=None):
        """Helper: fire a fake Shopify orders/paid webhook and return response."""
        order_id = int(time.time()) + random.randint(1, 9999)
        if order_id_suffix:
            order_id = order_id + order_id_suffix
        payload = {
            "id": order_id,
            "name": f"#TEST{order_id}",
            "email": "testcustomer@example.com",
            "total_price": "29.99",
            "currency": "GBP",
            "financial_status": "paid",
            "note": "Leave at door",
            "customer": {"id": 999999999, "email": "testcustomer@example.com",
                         "first_name": "Test", "last_name": "Customer"},
            "shipping_address": {
                "first_name": "Test", "last_name": "Customer",
                "address1": "123 Test Street", "city": "London",
                "zip": "E1 1AA", "country": "GB",
            },
            "line_items": [
                {"title": "Test Product", "variant_title": "Size M",
                 "quantity": 2, "price": "14.99"}
            ],
        }
        resp = session.post(
            f"{BASE_URL}/api/webhooks/shopify",
            json=payload,
            headers={"X-Shopify-Topic": "orders/paid",
                     "X-Shopify-Hmac-Sha256": "test",
                     "X-Shopify-Shop-Domain": "test.myshopify.com"},
        )
        return resp, order_id

    def test_webhook_creates_job_with_waiting_vendor_status(self, session):
        resp, order_id = self._create_webhook_job(session)
        assert resp.status_code in (200, 201), f"Webhook failed: {resp.status_code}: {resp.text}"
        data = resp.json()
        # Webhook returns {"status": "ok", "result": {"jobId": ..., "status": "waiting_vendor"}}
        assert data.get("status") == "ok", f"Webhook status not ok: {data}"
        result = data.get("result", {})
        assert result.get("status") == "waiting_vendor", \
            f"Expected job status=waiting_vendor, got {result.get('status')}"
        _state["test_job_id"] = result["jobId"]
        print(f"Created test job: {result['jobId']}")

    def test_webhook_auto_links_vendor_id(self, session):
        job_id = _state.get("test_job_id")
        if not job_id:
            pytest.skip("test_job_id not set")
        resp = session.get(f"{BASE_URL}/api/delivery/jobs/{job_id}")
        assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
        data = resp.json()
        print(f"vendorId on job: {data.get('vendorId')}")
        assert data.get("vendorId") is not None, "vendorId should be auto-linked when vendor is assigned to store"

    def test_webhook_creates_separate_job_for_reject(self, session):
        """Create a second job to test rejection flow separately."""
        resp, _ = self._create_webhook_job(session, order_id_suffix=1)
        assert resp.status_code in (200, 201), f"Webhook failed: {resp.text}"
        data = resp.json()
        result = data.get("result", {})
        _state["reject_job_id"] = result["jobId"]
        print(f"Created reject test job: {result['jobId']}")


# ─── Vendor Order Queue ───────────────────────────────────────────────────────

class TestVendorOrderQueue:
    """GET /vendor/orders returns active order queue"""

    def test_get_order_queue(self, session, vendor_auth_headers):
        resp = session.get(f"{BASE_URL}/api/vendor/orders", headers=vendor_auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"Vendor order queue has {len(data)} items")
        if data:
            order = data[0]
            assert "id" in order
            assert "status" in order
            assert "orderItems" in order


# ─── Full Vendor Workflow ─────────────────────────────────────────────────────

class TestVendorWorkflow:
    """Full workflow: accept → unavailable-items → preparing → ready → assign rider"""

    def _get_headers(self):
        return {"Authorization": f"Bearer {_state['vendor_access_token']}"}

    def test_01_accept_order_transitions_to_vendor_accepted(self, session):
        job_id = _state.get("test_job_id")
        if not job_id:
            pytest.skip("test_job_id not set")
        resp = session.post(
            f"{BASE_URL}/api/vendor/orders/{job_id}/accept",
            headers=self._get_headers(),
            json={"note": "Will prepare shortly"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "vendor_accepted", f"Expected vendor_accepted, got {data['status']}"
        assert data["vendorAcceptedAt"] is not None

    def test_02_accept_again_returns_409(self, session):
        """Cannot accept an already-accepted order."""
        job_id = _state.get("test_job_id")
        if not job_id:
            pytest.skip("test_job_id not set")
        resp = session.post(
            f"{BASE_URL}/api/vendor/orders/{job_id}/accept",
            headers=self._get_headers(),
            json={},
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"

    def test_03_mark_unavailable_items(self, session):
        job_id = _state.get("test_job_id")
        if not job_id:
            pytest.skip("test_job_id not set")
        resp = session.put(
            f"{BASE_URL}/api/vendor/orders/{job_id}/unavailable-items",
            headers=self._get_headers(),
            json={
                "items": [{"itemTitle": "Test Product", "reason": "out_of_stock"}],
                "vendorNote": "Size M is out of stock",
            },
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert len(data["unavailableItems"]) > 0, "Should have unavailable items"
        assert data["unavailableItems"][0]["itemTitle"] == "Test Product"

    def test_04_start_preparing_transitions_to_preparing(self, session):
        job_id = _state.get("test_job_id")
        if not job_id:
            pytest.skip("test_job_id not set")
        resp = session.post(
            f"{BASE_URL}/api/vendor/orders/{job_id}/preparing",
            headers=self._get_headers(),
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "preparing", f"Expected preparing, got {data['status']}"
        assert data["preparingAt"] is not None

    def test_05_mark_ready_transitions_to_ready_for_pickup(self, session):
        job_id = _state.get("test_job_id")
        if not job_id:
            pytest.skip("test_job_id not set")
        resp = session.post(
            f"{BASE_URL}/api/vendor/orders/{job_id}/ready",
            headers=self._get_headers(),
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "ready_for_pickup", f"Expected ready_for_pickup, got {data['status']}"
        assert data["readyForPickupAt"] is not None

    def test_06_assign_rider_from_ready_for_pickup_succeeds(self, session):
        """Rider assignment should work on READY_FOR_PICKUP status."""
        job_id = _state.get("test_job_id")
        rider_id = _state.get("rider_id")
        if not job_id or not rider_id:
            pytest.skip("job_id or rider_id not set")
        resp = session.post(f"{BASE_URL}/api/admin/riders/{rider_id}/assign-job/{job_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Assign endpoint returns {"message": ..., "job": {...}}
        job = data.get("job", data)
        assert job["status"] == "assigned", f"Expected assigned, got {job.get('status')}"
        assert job["assignedRiderId"] == rider_id


# ─── Reject Flow ─────────────────────────────────────────────────────────────

class TestVendorRejectFlow:
    """Vendor rejection: waiting_vendor → rejected, and 409 guard"""

    def _get_headers(self):
        return {"Authorization": f"Bearer {_state['vendor_access_token']}"}

    def test_reject_order_from_waiting_vendor(self, session):
        job_id = _state.get("reject_job_id")
        if not job_id:
            pytest.skip("reject_job_id not set")
        resp = session.post(
            f"{BASE_URL}/api/vendor/orders/{job_id}/reject",
            headers=self._get_headers(),
            json={"reason": "Out of ingredients"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "rejected", f"Expected rejected, got {data['status']}"

    def test_reject_already_rejected_returns_409(self, session):
        job_id = _state.get("reject_job_id")
        if not job_id:
            pytest.skip("reject_job_id not set")
        resp = session.post(
            f"{BASE_URL}/api/vendor/orders/{job_id}/reject",
            headers=self._get_headers(),
            json={"reason": "Duplicate rejection"},
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"

    def test_assign_rider_to_waiting_vendor_job_returns_409(self, session):
        """Rider cannot be assigned to a job still in WAITING_VENDOR state."""
        rider_id = _state.get("rider_id")
        if not rider_id:
            pytest.skip("rider_id not set")
        # Create another job at waiting_vendor
        import random
        order_id = int(time.time()) + random.randint(10000, 99999)
        payload = {
            "id": order_id,
            "name": f"#WAITTEST{order_id}",
            "email": "test@example.com",
            "total_price": "10.00",
            "currency": "GBP",
            "financial_status": "paid",
            "customer": {"id": 111222, "email": "test@example.com",
                         "first_name": "A", "last_name": "B"},
            "shipping_address": {
                "first_name": "A", "last_name": "B",
                "address1": "1 Test Road", "city": "London",
                "zip": "E2 2BB", "country": "GB",
            },
            "line_items": [{"title": "Item", "quantity": 1, "price": "10.00"}],
        }
        wh_resp = session.post(
            f"{BASE_URL}/api/webhooks/shopify",
            json=payload,
            headers={"X-Shopify-Topic": "orders/paid",
                     "X-Shopify-Hmac-Sha256": "test",
                     "X-Shopify-Shop-Domain": "test.myshopify.com"},
        )
        if wh_resp.status_code not in (200, 201):
            pytest.skip("Could not create waiting_vendor job")
        wh_data = wh_resp.json()
        wh_result = wh_data.get("result", {})
        wait_job_id = wh_result.get("jobId")
        if not wait_job_id:
            pytest.skip("No jobId in webhook response")
        assert wh_result.get("status") == "waiting_vendor"

        # Now try to assign rider — should be 409
        assign_resp = session.post(f"{BASE_URL}/api/admin/riders/{rider_id}/assign-job/{wait_job_id}")
        assert assign_resp.status_code == 409, \
            f"Expected 409 for WAITING_VENDOR assignment, got {assign_resp.status_code}: {assign_resp.text}"


# ─── History & Stats ─────────────────────────────────────────────────────────

class TestVendorHistoryAndStats:
    """History and stats endpoints"""

    def _get_headers(self):
        return {"Authorization": f"Bearer {_state['vendor_access_token']}"}

    def test_get_order_history(self, session):
        resp = session.get(f"{BASE_URL}/api/vendor/orders/history", headers=self._get_headers())
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "orders" in data
        assert "total" in data
        assert isinstance(data["orders"], list)

    def test_get_stats(self, session):
        resp = session.get(f"{BASE_URL}/api/vendor/stats", headers=self._get_headers())
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "totalOrders" in data
        assert "acceptedOrders" in data
        assert "rejectedOrders" in data
        assert "completedOrders" in data
        assert "averagePreparationMinutes" in data


# ─── Suspend Vendor Revokes Sessions ─────────────────────────────────────────

class TestSuspendVendorRevokesSession:
    """Suspending vendor should revoke all active sessions"""

    def test_suspend_vendor_revokes_refresh_token(self, session):
        new_vid = _state.get("new_vendor_id")
        if not new_vid:
            pytest.skip("new_vendor_id not set")
        # Login as new vendor
        login_resp = session.post(f"{BASE_URL}/api/vendor/auth/login", json={
            "email": NEW_VENDOR_EMAIL,
            "password": NEW_VENDOR_PASSWORD,
        })
        assert login_resp.status_code == 200, f"New vendor login failed: {login_resp.text}"
        tokens = login_resp.json()
        refresh_tok = tokens["refreshToken"]

        # Suspend the vendor via admin
        suspend_resp = session.put(f"{BASE_URL}/api/admin/vendors/{new_vid}/suspend")
        assert suspend_resp.status_code == 200, f"Suspend failed: {suspend_resp.text}"
        assert suspend_resp.json()["isActive"] is False

        # The refresh token should now be revoked
        refresh_resp = session.post(f"{BASE_URL}/api/vendor/auth/refresh",
                                    json={"refreshToken": refresh_tok})
        assert refresh_resp.status_code in (401, 403), \
            f"Suspended vendor's refresh token should be revoked, got {refresh_resp.status_code}"


# ─── Regression Tests ────────────────────────────────────────────────────────

class TestRegression:
    """Ensure existing endpoints still work"""

    def test_get_delivery_jobs_list(self, session):
        resp = session.get(f"{BASE_URL}/api/delivery/jobs")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "jobs" in data
        assert "total" in data

    def test_shopify_home_still_works(self, session):
        resp = session.get(f"{BASE_URL}/api/shopify/home")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_rider_auth_login_regression(self, session):
        resp = session.post(f"{BASE_URL}/api/rider/auth/login", json={
            "email": RIDER_EMAIL,
            "password": RIDER_PASSWORD,
        })
        assert resp.status_code == 200, f"Rider login regression failed: {resp.text}"
        data = resp.json()
        assert "accessToken" in data
        assert data["rider"]["email"] == RIDER_EMAIL.lower()
