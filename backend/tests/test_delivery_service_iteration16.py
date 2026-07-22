"""
Delivery Service backend tests — Iteration 16
Tests:
  - GET /api/delivery/stores (default store seeded on startup)
  - GET /api/delivery/jobs (empty paginated list)
  - POST /api/webhooks/shopify orders/paid (creates delivery job)
  - Idempotency: same webhook_id returns 'duplicate'
  - POST /api/webhooks/shopify orders/cancelled (cancels job)
  - GET /api/delivery/jobs/{jobId} (full detail)
  - GET /api/delivery/jobs?status=pending_assignment (filter)
  - PUT /api/delivery/jobs/{jobId}/status (full lifecycle state machine)
  - PUT invalid transitions → 409
  - Terminal state guard → 409
  - POST /api/delivery/jobs/{jobId}/cancel
  - orders/cancelled on IN_TRANSIT job → does NOT cancel, adds warning event
  - Existing endpoints: GET /api/shopify/home, GET /api/shopify/categories not broken
  - HMAC validation returns 401 when secret is set
  - Delivery job field correctness
"""
import os
import time
import uuid
import hmac
import hashlib
import base64
import json

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback for local dev
    BASE_URL = "https://nowkart-handover.preview.emergentagent.com"

API = f"{BASE_URL}/api"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _shopify_order_payload(order_id: int = None) -> dict:
    """Generate a minimal but realistic Shopify orders/paid payload."""
    if order_id is None:
        order_id = int(time.time() * 1000) % 1_000_000_000  # unique numeric id
    return {
        "id": order_id,
        "name": f"#TEST-{order_id}",
        "email": "customer@example.com",
        "note": "Please leave at door",
        "total_price": "49.99",
        "currency": "GBP",
        "financial_status": "paid",
        "customer": {
            "id": 9876543210,
            "email": "customer@example.com",
            "first_name": "Jane",
            "last_name": "Doe"
        },
        "shipping_address": {
            "first_name": "Jane",
            "last_name": "Doe",
            "address1": "10 Downing Street",
            "address2": "Flat 1",
            "city": "London",
            "province": "England",
            "zip": "SW1A 2AA",
            "country": "GB",
            "phone": "+44 7700 900123"
        },
        "line_items": [
            {
                "id": 1001,
                "title": "Test Product",
                "variant_title": "Small",
                "quantity": 2,
                "price": "19.99"
            },
            {
                "id": 1002,
                "title": "Another Product",
                "variant_title": None,
                "quantity": 1,
                "price": "10.01"
            }
        ]
    }


def _post_webhook(session, topic: str, payload: dict, webhook_id: str = None) -> requests.Response:
    if webhook_id is None:
        webhook_id = str(uuid.uuid4())
    return session.post(
        f"{API}/webhooks/shopify",
        json=payload,
        headers={
            "X-Shopify-Topic": topic,
            "X-Shopify-Webhook-Id": webhook_id,
            "X-Shopify-Shop-Domain": "test.myshopify.com",
        }
    )


# ─── Store tests ──────────────────────────────────────────────────────────────

class TestStores:
    """GET /api/delivery/stores — default store should exist after startup"""

    def test_get_stores_returns_200(self, session):
        r = session.get(f"{API}/delivery/stores")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_get_stores_returns_list(self, session):
        r = session.get(f"{API}/delivery/stores")
        data = r.json()
        assert isinstance(data, list), "Expected a list"
        assert len(data) >= 1, "Expected at least one store (default seeded store)"

    def test_default_store_fields(self, session):
        r = session.get(f"{API}/delivery/stores")
        store = r.json()[0]
        assert "id" in store
        assert "name" in store
        assert store["isDefault"] is True
        assert store["isActive"] is True
        assert "address" in store
        assert "settings" in store
        assert "shopifyDomain" in store
        assert "createdAt" in store

    def test_store_settings_fields(self, session):
        r = session.get(f"{API}/delivery/stores")
        settings = r.json()[0]["settings"]
        assert "defaultEtaMinutes" in settings
        assert "prepTimeMinutes" in settings
        assert "maxConcurrentJobs" in settings
        assert "autoAssignment" in settings


# ─── Jobs list (empty / paginated) ────────────────────────────────────────────

class TestJobsList:
    """GET /api/delivery/jobs — paginated list"""

    def test_list_jobs_returns_200(self, session):
        r = session.get(f"{API}/delivery/jobs")
        assert r.status_code == 200, r.text

    def test_list_jobs_paginated_shape(self, session):
        r = session.get(f"{API}/delivery/jobs")
        data = r.json()
        assert "jobs" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["jobs"], list)
        assert isinstance(data["total"], int)

    def test_list_jobs_default_pagination(self, session):
        r = session.get(f"{API}/delivery/jobs")
        data = r.json()
        assert data["limit"] == 50
        assert data["offset"] == 0


# ─── Webhook: orders/paid ─────────────────────────────────────────────────────

class TestWebhookOrdersPaid:
    """POST /api/webhooks/shopify with orders/paid"""

    # Shared state across tests in this class
    order_id: int = None
    webhook_id: str = None
    job_id: str = None

    def test_orders_paid_creates_job(self, session):
        TestWebhookOrdersPaid.order_id = int(time.time() * 1000) % 1_000_000_000
        TestWebhookOrdersPaid.webhook_id = str(uuid.uuid4())
        payload = _shopify_order_payload(TestWebhookOrdersPaid.order_id)

        r = _post_webhook(session, "orders/paid", payload, TestWebhookOrdersPaid.webhook_id)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "ok", f"Expected ok, got: {data}"
        assert "result" in data
        result = data["result"]
        assert result["action"] == "delivery_job_created"
        assert "jobId" in result
        TestWebhookOrdersPaid.job_id = result["jobId"]

    def test_job_has_correct_shopify_gid(self, session):
        assert TestWebhookOrdersPaid.job_id, "No job_id from previous test"
        r = session.get(f"{API}/delivery/jobs/{TestWebhookOrdersPaid.job_id}")
        assert r.status_code == 200, r.text
        job = r.json()
        expected_gid = f"gid://shopify/Order/{TestWebhookOrdersPaid.order_id}"
        assert job["shopifyOrderId"] == expected_gid

    def test_job_has_correct_order_name(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestWebhookOrdersPaid.job_id}")
        job = r.json()
        assert f"{TestWebhookOrdersPaid.order_id}" in job["shopifyOrderName"]

    def test_job_initial_status_pending_assignment(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestWebhookOrdersPaid.job_id}")
        job = r.json()
        assert job["status"] == "pending_assignment"

    def test_job_has_customer_email(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestWebhookOrdersPaid.job_id}")
        job = r.json()
        assert job["customerEmail"] == "customer@example.com"

    def test_job_has_delivery_address(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestWebhookOrdersPaid.job_id}")
        job = r.json()
        addr = job["deliveryAddress"]
        assert addr["line1"] == "10 Downing Street"
        assert addr["city"] == "London"
        assert addr["postcode"] == "SW1A 2AA"

    def test_job_has_order_items(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestWebhookOrdersPaid.job_id}")
        job = r.json()
        assert len(job["orderItems"]) == 2
        titles = [i["title"] for i in job["orderItems"]]
        assert "Test Product" in titles

    def test_job_has_order_total(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestWebhookOrdersPaid.job_id}")
        job = r.json()
        assert job["orderTotal"] == 49.99
        assert job["currencyCode"] == "GBP"

    def test_job_has_delivery_instructions(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestWebhookOrdersPaid.job_id}")
        job = r.json()
        assert job["deliveryInstructions"] == "Please leave at door"

    def test_job_has_recent_events_with_webhook_actor(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestWebhookOrdersPaid.job_id}")
        job = r.json()
        assert len(job["recentEvents"]) >= 1
        first_event = job["recentEvents"][0]
        assert first_event["actor"] == "webhook:orders/paid"
        assert first_event["status"] == "pending_assignment"

    def test_idempotency_duplicate_webhook_returns_duplicate(self, session):
        """Same webhook_id → returns 'duplicate'"""
        assert TestWebhookOrdersPaid.webhook_id, "No webhook_id from previous test"
        payload = _shopify_order_payload(TestWebhookOrdersPaid.order_id)
        r = _post_webhook(session, "orders/paid", payload, TestWebhookOrdersPaid.webhook_id)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "duplicate", f"Expected duplicate, got: {data}"


# ─── Webhook: orders/cancelled ────────────────────────────────────────────────

class TestWebhookOrdersCancelled:
    """POST /api/webhooks/shopify with orders/cancelled"""

    # Create a fresh job to cancel
    order_id: int = None
    job_id: str = None

    def test_setup_create_job_to_cancel(self, session):
        TestWebhookOrdersCancelled.order_id = int(time.time() * 1000 + 1) % 1_000_000_000
        payload = _shopify_order_payload(TestWebhookOrdersCancelled.order_id)
        r = _post_webhook(session, "orders/paid", payload)
        assert r.status_code == 200
        result = r.json()["result"]
        assert result["action"] == "delivery_job_created"
        TestWebhookOrdersCancelled.job_id = result["jobId"]

    def test_orders_cancelled_cancels_job(self, session):
        assert TestWebhookOrdersCancelled.order_id
        payload = {"id": TestWebhookOrdersCancelled.order_id, "cancel_reason": "customer"}
        r = _post_webhook(session, "orders/cancelled", payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "ok"
        result = data["result"]
        assert result["action"] == "delivery_job_updated"
        assert result["status"] == "cancelled"

    def test_cancelled_job_status_is_cancelled(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestWebhookOrdersCancelled.job_id}")
        assert r.status_code == 200
        job = r.json()
        assert job["status"] == "cancelled"

    def test_orders_cancelled_no_job_returns_no_job_found(self, session):
        """orders/cancelled for an order that never had a delivery job"""
        payload = {"id": 999999999999, "cancel_reason": "customer"}
        r = _post_webhook(session, "orders/cancelled", payload)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["result"]["action"] == "no_job_found"


# ─── Job detail & filter ──────────────────────────────────────────────────────

class TestJobDetail:
    """GET /api/delivery/jobs/{jobId} and filtering"""

    job_id: str = None
    order_id: int = None

    def test_setup_create_job(self, session):
        TestJobDetail.order_id = int(time.time() * 1000 + 2) % 1_000_000_000
        payload = _shopify_order_payload(TestJobDetail.order_id)
        r = _post_webhook(session, "orders/paid", payload)
        assert r.status_code == 200
        TestJobDetail.job_id = r.json()["result"]["jobId"]

    def test_get_job_detail_200(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestJobDetail.job_id}")
        assert r.status_code == 200

    def test_get_job_detail_fields(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestJobDetail.job_id}")
        job = r.json()
        # All required fields from PRD
        required_fields = [
            "id", "shopifyOrderId", "shopifyOrderName", "shopifyNumericId",
            "storeId", "status", "statusLabel", "customerEmail",
            "deliveryAddress", "orderItems", "orderTotal", "currencyCode",
            "deliveryInstructions", "recentEvents", "createdAt", "updatedAt"
        ]
        for field in required_fields:
            assert field in job, f"Missing field: {field}"

    def test_get_job_detail_404_for_unknown_id(self, session):
        r = session.get(f"{API}/delivery/jobs/000000000000000000000000")
        assert r.status_code == 404

    def test_filter_by_status_pending_assignment(self, session):
        r = session.get(f"{API}/delivery/jobs?status=pending_assignment")
        assert r.status_code == 200
        data = r.json()
        # All returned jobs should be pending_assignment
        for job in data["jobs"]:
            assert job["status"] == "pending_assignment", f"Unexpected status: {job['status']}"

    def test_filter_by_status_excludes_others(self, session):
        """Filter on a rare status — should be 0 jobs (or only matching ones)"""
        r = session.get(f"{API}/delivery/jobs?status=arrived")
        assert r.status_code == 200
        data = r.json()
        for job in data["jobs"]:
            assert job["status"] == "arrived"


# ─── State machine: full lifecycle ───────────────────────────────────────────

class TestStateMachine:
    """PUT /api/delivery/jobs/{jobId}/status — full lifecycle and invalid transitions"""

    job_id: str = None

    def test_setup_create_job_for_lifecycle(self, session):
        order_id = int(time.time() * 1000 + 3) % 1_000_000_000
        payload = _shopify_order_payload(order_id)
        r = _post_webhook(session, "orders/paid", payload)
        assert r.status_code == 200
        TestStateMachine.job_id = r.json()["result"]["jobId"]

    def test_transition_pending_to_assigned(self, session):
        r = session.put(
            f"{API}/delivery/jobs/{TestStateMachine.job_id}/status",
            json={"status": "assigned", "actor": "admin", "note": "Rider John assigned"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "assigned"

    def test_transition_assigned_to_at_store(self, session):
        r = session.put(
            f"{API}/delivery/jobs/{TestStateMachine.job_id}/status",
            json={"status": "at_store", "actor": "admin"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "at_store"

    def test_transition_at_store_to_in_transit(self, session):
        r = session.put(
            f"{API}/delivery/jobs/{TestStateMachine.job_id}/status",
            json={"status": "in_transit", "actor": "admin"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "in_transit"

    def test_transition_in_transit_to_arrived(self, session):
        r = session.put(
            f"{API}/delivery/jobs/{TestStateMachine.job_id}/status",
            json={"status": "arrived", "actor": "admin"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "arrived"

    def test_transition_arrived_to_delivered(self, session):
        r = session.put(
            f"{API}/delivery/jobs/{TestStateMachine.job_id}/status",
            json={"status": "delivered", "actor": "admin"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "delivered"

    def test_terminal_delivered_cannot_be_modified(self, session):
        """Terminal state guard: delivered → any = 409"""
        r = session.put(
            f"{API}/delivery/jobs/{TestStateMachine.job_id}/status",
            json={"status": "assigned", "actor": "admin"}
        )
        assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"

    def test_events_accumulated_during_lifecycle(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestStateMachine.job_id}")
        job = r.json()
        # Should have at least 6 events: initial + 5 transitions
        assert len(job["recentEvents"]) >= 6


class TestInvalidTransitions:
    """Invalid state machine transitions should return 409"""

    job_id: str = None

    def test_setup_create_job_for_invalid_transitions(self, session):
        order_id = int(time.time() * 1000 + 4) % 1_000_000_000
        payload = _shopify_order_payload(order_id)
        r = _post_webhook(session, "orders/paid", payload)
        assert r.status_code == 200
        TestInvalidTransitions.job_id = r.json()["result"]["jobId"]
        # Advance to in_transit
        jid = TestInvalidTransitions.job_id
        for status in ["assigned", "at_store", "in_transit"]:
            session.put(f"{API}/delivery/jobs/{jid}/status", json={"status": status, "actor": "admin"})

    def test_in_transit_to_assigned_is_invalid(self, session):
        """in_transit → assigned: invalid"""
        r = session.put(
            f"{API}/delivery/jobs/{TestInvalidTransitions.job_id}/status",
            json={"status": "assigned", "actor": "admin"}
        )
        assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"

    def test_in_transit_to_cancelled_is_invalid(self, session):
        """in_transit → cancelled: not allowed (must go through admin intervention)"""
        r = session.put(
            f"{API}/delivery/jobs/{TestInvalidTransitions.job_id}/status",
            json={"status": "cancelled", "actor": "admin"}
        )
        assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"


# ─── Cancel endpoint ──────────────────────────────────────────────────────────

class TestCancelEndpoint:
    """POST /api/delivery/jobs/{jobId}/cancel"""

    job_id: str = None

    def test_setup_create_job_to_cancel(self, session):
        order_id = int(time.time() * 1000 + 5) % 1_000_000_000
        payload = _shopify_order_payload(order_id)
        r = _post_webhook(session, "orders/paid", payload)
        assert r.status_code == 200
        TestCancelEndpoint.job_id = r.json()["result"]["jobId"]

    def test_cancel_pending_job(self, session):
        r = session.post(
            f"{API}/delivery/jobs/{TestCancelEndpoint.job_id}/cancel?reason=Test+cancel"
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"

    def test_cancel_already_cancelled_returns_409(self, session):
        """Terminal state: already cancelled → 409"""
        r = session.post(
            f"{API}/delivery/jobs/{TestCancelEndpoint.job_id}/cancel"
        )
        assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"


# ─── IN_TRANSIT + orders/cancelled guard ─────────────────────────────────────

class TestInTransitCancelGuard:
    """orders/cancelled on an IN_TRANSIT job → NOT cancelled, adds warning event"""

    job_id: str = None
    order_id: int = None

    def test_setup_create_and_advance_to_in_transit(self, session):
        TestInTransitCancelGuard.order_id = int(time.time() * 1000 + 6) % 1_000_000_000
        payload = _shopify_order_payload(TestInTransitCancelGuard.order_id)
        r = _post_webhook(session, "orders/paid", payload)
        assert r.status_code == 200
        TestInTransitCancelGuard.job_id = r.json()["result"]["jobId"]
        jid = TestInTransitCancelGuard.job_id
        for status in ["assigned", "at_store", "in_transit"]:
            resp = session.put(f"{API}/delivery/jobs/{jid}/status", json={"status": status, "actor": "admin"})
            assert resp.status_code == 200, f"Failed to advance to {status}: {resp.text}"

    def test_orders_cancelled_does_not_cancel_in_transit(self, session):
        payload = {"id": TestInTransitCancelGuard.order_id, "cancel_reason": "customer"}
        r = _post_webhook(session, "orders/cancelled", payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "ok"
        # The result action should reflect an update (not no_job_found), but the job is NOT cancelled
        result = data["result"]
        assert result["action"] == "delivery_job_updated"

    def test_in_transit_job_still_in_transit_after_cancel_webhook(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestInTransitCancelGuard.job_id}")
        assert r.status_code == 200
        job = r.json()
        assert job["status"] == "in_transit", f"Expected in_transit, got: {job['status']}"

    def test_in_transit_job_has_warning_event(self, session):
        r = session.get(f"{API}/delivery/jobs/{TestInTransitCancelGuard.job_id}")
        job = r.json()
        events = job["recentEvents"]
        warning_events = [
            e for e in events
            if e.get("actor") == "webhook:orders/cancelled"
        ]
        assert len(warning_events) >= 1, "Expected a warning event from webhook:orders/cancelled"
        # The event note should mention "ALERT"
        assert "ALERT" in (warning_events[-1].get("note") or ""), \
            f"Warning event note should contain ALERT: {warning_events[-1]}"


# ─── Existing endpoints not broken ───────────────────────────────────────────

class TestExistingEndpoints:
    """Regression: existing Shopify endpoints still work"""

    def test_shopify_home_returns_200(self, session):
        r = session.get(f"{API}/shopify/home")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"

    def test_shopify_categories_returns_200(self, session):
        r = session.get(f"{API}/shopify/categories")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"


# ─── HMAC verification when secret IS set ────────────────────────────────────

class TestHmacVerification:
    """
    POST /api/webhooks/shopify with invalid HMAC when SHOPIFY_WEBHOOK_SECRET is set → 401.
    NOTE: In current dev environment SHOPIFY_WEBHOOK_SECRET is empty — this test uses
    a subprocess to temporarily test the logic via a direct call with a known-bad signature.
    Since we can't set env vars in the running server from the test, we verify the
    verify_shopify_webhook function logic directly via import.
    """

    def test_invalid_hmac_returns_false_when_secret_set(self):
        """Unit test: verify_shopify_webhook returns False on bad sig when secret is configured"""
        import sys, os
        sys.path.insert(0, "/app/backend")
        # Temporarily set the secret
        original = os.environ.get("SHOPIFY_WEBHOOK_SECRET", "")
        os.environ["SHOPIFY_WEBHOOK_SECRET"] = "test_secret_for_hmac_test"
        try:
            from webhooks.verification import verify_shopify_webhook
            result = verify_shopify_webhook(b'{"id": 123}', "invalid_signature")
            assert result is False, "Expected False for invalid HMAC"
        finally:
            os.environ["SHOPIFY_WEBHOOK_SECRET"] = original

    def test_valid_hmac_returns_true_when_secret_set(self):
        """Unit test: verify_shopify_webhook returns True on correct sig"""
        import sys, os
        sys.path.insert(0, "/app/backend")
        original = os.environ.get("SHOPIFY_WEBHOOK_SECRET", "")
        secret = "test_secret_for_hmac_test"
        os.environ["SHOPIFY_WEBHOOK_SECRET"] = secret
        try:
            from webhooks.verification import verify_shopify_webhook
            body = b'{"id": 123}'
            digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
            sig = base64.b64encode(digest).decode("utf-8")
            result = verify_shopify_webhook(body, sig)
            assert result is True, "Expected True for valid HMAC"
        finally:
            os.environ["SHOPIFY_WEBHOOK_SECRET"] = original

    def test_empty_secret_always_passes(self):
        """Unit test: empty secret skips verification (dev mode returns True)"""
        import sys, os
        sys.path.insert(0, "/app/backend")
        original = os.environ.get("SHOPIFY_WEBHOOK_SECRET", "")
        os.environ["SHOPIFY_WEBHOOK_SECRET"] = ""
        try:
            from webhooks.verification import verify_shopify_webhook
            result = verify_shopify_webhook(b'{"id": 123}', "")
            assert result is True, "Expected True in dev mode (empty secret)"
        finally:
            os.environ["SHOPIFY_WEBHOOK_SECRET"] = original
