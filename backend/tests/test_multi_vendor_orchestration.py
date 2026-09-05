"""
Multi-Vendor Order Orchestration — Backend Tests (Iteration 20)

Tests:
  1.  Legacy mode           — no vendor field → backward-compatible single job
  2.  Single vendor         — one vendor string, matched → one job
  3.  Two vendors           — two distinct vendor strings → two jobs
  4.  Same vendor grouping  — multiple items, same vendor → one job (items merged)
  5.  Missing vendor field  — mixed: some items have vendor, some don't → unmapped reported
  6.  Unmatched vendor      — vendor string not in NowKart → no job, failure reported
  7.  Idempotent same wh-id — duplicate X-Shopify-Webhook-Id → "duplicate" at webhook level
  8.  Idempotent diff wh-id — same Shopify order, different webhook ID → same parent_order returned
  9.  Multi-vendor cancel   — orders/cancelled cancels both jobs
  10. Existing legacy flow  — verify full backward compatibility of the original single-job path

SETUP NOTES
-----------
Tests run against a live backend (EXPO_BACKEND_URL or LOCAL_BACKEND_URL env var).
Vendor-matching tests first create NowKart vendors with known businessNames via the
admin API, then clean them up in teardown.
"""
import os
import time
import uuid
import pytest
import requests

# ── Backend URL ───────────────────────────────────────────────────────────────
BASE_URL = os.environ.get("LOCAL_BACKEND_URL", os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
if not BASE_URL:
    BASE_URL = "http://localhost:8099"

API = f"{BASE_URL}/api"

# Admin credentials (seeded by seed_default_admin() on startup)
ADMIN_EMAIL    = "admin@nowkart.com"
ADMIN_PASSWORD = "Admin2026!"

# Unique suffix so parallel test runs don't collide on businessName
_RUN_ID = str(uuid.uuid4())[:8]

VENDOR_A_NAME = f"MV-VendorA-{_RUN_ID}"
VENDOR_B_NAME = f"MV-VendorB-{_RUN_ID}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _admin_token(session) -> str:
    r = session.post(f"{API}/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["accessToken"]


def _default_store_id(session, token: str) -> str:
    r = session.get(f"{API}/delivery/stores", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    stores = r.json()
    for s in stores:
        if s["isDefault"]:
            return s["id"]
    return stores[0]["id"]


def _create_vendor(session, token: str, business_name: str, store_id: str) -> str:
    """Create a test vendor and return its id."""
    payload = {
        "email":        f"test-{uuid.uuid4().hex[:8]}@example.com",
        "phone":        "+44700000000",
        "password":     "Test1234!",
        "businessName": business_name,
        "firstName":    "Test",
        "lastName":     "Vendor",
        "storeId":      store_id,
    }
    r = session.post(
        f"{API}/admin/vendors",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (200, 201), f"Create vendor failed: {r.text}"
    return r.json()["id"]


def _delete_vendor(session, token: str, vendor_id: str) -> None:
    session.delete(
        f"{API}/admin/vendors/{vendor_id}",
        headers={"Authorization": f"Bearer {token}"},
    )


def _post_webhook(session, topic: str, payload: dict, webhook_id: str = None) -> requests.Response:
    if webhook_id is None:
        webhook_id = str(uuid.uuid4())
    return session.post(
        f"{API}/webhooks/shopify",
        json=payload,
        headers={
            "X-Shopify-Topic":      topic,
            "X-Shopify-Webhook-Id": webhook_id,
            "X-Shopify-Shop-Domain": "test.myshopify.com",
        },
    )


def _order_payload(order_id: int = None, line_items=None, note=None) -> dict:
    if order_id is None:
        order_id = int(time.time() * 1000) % 1_000_000_000
    if line_items is None:
        line_items = [{"id": 1, "title": "Default Item", "quantity": 1, "price": "10.00"}]
    p = {
        "id":              order_id,
        "name":            f"#TEST-{order_id}",
        "email":           "customer@example.com",
        "total_price":     "49.99",
        "currency":        "GBP",
        "financial_status": "paid",
        "customer":        {"id": 11111, "email": "customer@example.com", "first_name": "Test", "last_name": "User"},
        "shipping_address": {
            "first_name": "Test", "last_name": "User",
            "address1": "1 Test St", "city": "London",
            "zip": "E1 1AA", "country": "GB",
        },
        "line_items": line_items,
    }
    if note:
        p["note"] = note
    return p


# ── Module-scoped setup/teardown: create test vendors once ────────────────────

@pytest.fixture(scope="module")
def admin_session():
    return _session()


@pytest.fixture(scope="module")
def admin_token(admin_session):
    return _admin_token(admin_session)


@pytest.fixture(scope="module")
def store_id(admin_session, admin_token):
    return _default_store_id(admin_session, admin_token)


@pytest.fixture(scope="module")
def vendor_a_id(admin_session, admin_token, store_id):
    vid = _create_vendor(admin_session, admin_token, VENDOR_A_NAME, store_id)
    yield vid
    _delete_vendor(admin_session, admin_token, vid)


@pytest.fixture(scope="module")
def vendor_b_id(admin_session, admin_token, store_id):
    vid = _create_vendor(admin_session, admin_token, VENDOR_B_NAME, store_id)
    yield vid
    _delete_vendor(admin_session, admin_token, vid)


@pytest.fixture(scope="module")
def http(admin_session):
    return admin_session   # reuse module-scoped session for all HTTP calls


# ══════════════════════════════════════════════════════════════════════════════
# Test 1 — LEGACY MODE: no vendor field → backward-compatible single job
# ══════════════════════════════════════════════════════════════════════════════

class TestLegacyMode:
    """No vendor field in any line item → existing single-job behaviour preserved."""

    order_id  = None
    webhook_id = None
    job_id     = None

    def test_legacy_creates_single_job(self, http):
        TestLegacyMode.order_id   = int(time.time() * 1000 + 10) % 1_000_000_000
        TestLegacyMode.webhook_id = str(uuid.uuid4())
        payload = _order_payload(TestLegacyMode.order_id, line_items=[
            {"id": 1, "title": "Milk 2L",       "quantity": 2, "price": "1.50"},
            {"id": 2, "title": "Bread Wholemeal","quantity": 1, "price": "2.00"},
        ])
        r = _post_webhook(http, "orders/paid", payload, TestLegacyMode.webhook_id)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "ok"
        result = data["result"]
        # Must be backward-compatible: action key and jobId must be present
        assert result["action"] == "delivery_job_created", f"Expected 'delivery_job_created', got: {result}"
        assert "jobId" in result
        assert result["mode"] == "legacy"
        assert "parentOrderId" in result
        TestLegacyMode.job_id = result["jobId"]

    def test_legacy_job_exists_in_delivery_jobs(self, http):
        assert TestLegacyMode.job_id
        r = http.get(f"{API}/delivery/jobs/{TestLegacyMode.job_id}")
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["id"] == TestLegacyMode.job_id

    def test_legacy_job_has_all_items(self, http):
        r = http.get(f"{API}/delivery/jobs/{TestLegacyMode.job_id}")
        items = r.json()["orderItems"]
        assert len(items) == 2

    def test_legacy_idempotent_same_webhook_id(self, http):
        """Same X-Shopify-Webhook-Id → 'duplicate', no second job created."""
        assert TestLegacyMode.webhook_id
        payload = _order_payload(TestLegacyMode.order_id)
        r = _post_webhook(http, "orders/paid", payload, TestLegacyMode.webhook_id)
        assert r.status_code == 200
        assert r.json()["status"] == "duplicate"


# ══════════════════════════════════════════════════════════════════════════════
# Test 2 — SINGLE VENDOR: one vendor, matched → one job
# ══════════════════════════════════════════════════════════════════════════════

class TestSingleVendorMatched:
    """One Shopify vendor string, matched to an active NowKart vendor → one job."""

    order_id  = None
    job_id    = None

    def test_single_vendor_creates_one_job(self, http, vendor_a_id):
        TestSingleVendorMatched.order_id = int(time.time() * 1000 + 20) % 1_000_000_000
        payload = _order_payload(TestSingleVendorMatched.order_id, line_items=[
            {"id": 10, "title": "Apple 1kg",  "quantity": 3, "price": "2.00", "vendor": VENDOR_A_NAME},
            {"id": 11, "title": "Mango 500g", "quantity": 2, "price": "3.50", "vendor": VENDOR_A_NAME},
        ])
        r = _post_webhook(http, "orders/paid", payload)
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        assert result["action"] == "delivery_jobs_created"
        assert len(result["jobs"]) == 1
        assert result["jobs"][0]["vendorName"] == VENDOR_A_NAME
        assert result["mode"] in ("single_vendor",)
        assert result["status"] == "created"
        assert result["unmappedGroups"] == []
        TestSingleVendorMatched.job_id = result["jobs"][0]["jobId"]

    def test_single_vendor_job_has_correct_items(self, http):
        assert TestSingleVendorMatched.job_id
        r = http.get(f"{API}/delivery/jobs/{TestSingleVendorMatched.job_id}")
        assert r.status_code == 200
        items = r.json()["orderItems"]
        assert len(items) == 2
        titles = {i["title"] for i in items}
        assert "Apple 1kg" in titles
        assert "Mango 500g" in titles

    def test_single_vendor_job_status_waiting_vendor(self, http):
        r = http.get(f"{API}/delivery/jobs/{TestSingleVendorMatched.job_id}")
        assert r.json()["status"] == "waiting_vendor"

    def test_single_vendor_parent_order_created(self, http):
        r = _post_webhook(http, "orders/paid",
            _order_payload(TestSingleVendorMatched.order_id,
                           line_items=[{"id": 10, "title": "X", "quantity": 1, "price": "1.00",
                                        "vendor": VENDOR_A_NAME}]),
            str(uuid.uuid4()))
        result = r.json()["result"]
        # Idempotent — returns existing parent_order, same parentOrderId
        assert "parentOrderId" in result


# ══════════════════════════════════════════════════════════════════════════════
# Test 3 — TWO VENDORS: two distinct vendor strings → two jobs
# ══════════════════════════════════════════════════════════════════════════════

class TestTwoVendors:
    """Two distinct Shopify vendor strings, both matched → two separate delivery jobs."""

    order_id    = None
    parent_id   = None
    job_a_id    = None
    job_b_id    = None
    webhook_id  = None

    def test_two_vendors_creates_two_jobs(self, http, vendor_a_id, vendor_b_id):
        TestTwoVendors.order_id   = int(time.time() * 1000 + 30) % 1_000_000_000
        TestTwoVendors.webhook_id = str(uuid.uuid4())
        payload = _order_payload(TestTwoVendors.order_id, line_items=[
            {"id": 20, "title": "Banana 1kg",  "quantity": 1, "price": "1.20", "vendor": VENDOR_A_NAME},
            {"id": 21, "title": "Pasta 500g",  "quantity": 2, "price": "1.00", "vendor": VENDOR_B_NAME},
        ])
        r = _post_webhook(http, "orders/paid", payload, TestTwoVendors.webhook_id)
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        assert result["action"] == "delivery_jobs_created"
        assert result["mode"] in ("multi_vendor",)
        assert result["status"] == "created"
        assert len(result["jobs"]) == 2
        assert result["unmappedGroups"] == []
        TestTwoVendors.parent_id = result["parentOrderId"]
        vendor_names = {j["vendorName"] for j in result["jobs"]}
        assert VENDOR_A_NAME in vendor_names
        assert VENDOR_B_NAME in vendor_names
        for j in result["jobs"]:
            if j["vendorName"] == VENDOR_A_NAME:
                TestTwoVendors.job_a_id = j["jobId"]
            else:
                TestTwoVendors.job_b_id = j["jobId"]

    def test_two_vendors_job_a_has_correct_item(self, http):
        assert TestTwoVendors.job_a_id
        r = http.get(f"{API}/delivery/jobs/{TestTwoVendors.job_a_id}")
        assert r.status_code == 200
        titles = [i["title"] for i in r.json()["orderItems"]]
        assert "Banana 1kg" in titles

    def test_two_vendors_job_b_has_correct_item(self, http):
        assert TestTwoVendors.job_b_id
        r = http.get(f"{API}/delivery/jobs/{TestTwoVendors.job_b_id}")
        assert r.status_code == 200
        titles = [i["title"] for i in r.json()["orderItems"]]
        assert "Pasta 500g" in titles

    def test_two_vendors_jobs_share_shopify_order_id(self, http):
        """Both jobs must reference the same Shopify order GID."""
        expected_gid = f"gid://shopify/Order/{TestTwoVendors.order_id}"
        for jid in [TestTwoVendors.job_a_id, TestTwoVendors.job_b_id]:
            r = http.get(f"{API}/delivery/jobs/{jid}")
            assert r.json()["shopifyOrderId"] == expected_gid

    def test_two_vendors_jobs_have_different_vendor_ids(self, http):
        """Each job must be assigned to a different vendor."""
        j_a = http.get(f"{API}/delivery/jobs/{TestTwoVendors.job_a_id}").json()
        j_b = http.get(f"{API}/delivery/jobs/{TestTwoVendors.job_b_id}").json()
        assert j_a["vendorId"] != j_b["vendorId"]


# ══════════════════════════════════════════════════════════════════════════════
# Test 4 — SAME VENDOR GROUPING: multiple items, same vendor → one job
# ══════════════════════════════════════════════════════════════════════════════

class TestSameVendorGrouping:
    """Three line items, all with the same Shopify vendor → grouped into one delivery job."""

    order_id = None
    job_id   = None

    def test_same_vendor_three_items_one_job(self, http, vendor_a_id):
        TestSameVendorGrouping.order_id = int(time.time() * 1000 + 40) % 1_000_000_000
        payload = _order_payload(TestSameVendorGrouping.order_id, line_items=[
            {"id": 30, "title": "Item Alpha",  "quantity": 1, "price": "5.00", "vendor": VENDOR_A_NAME},
            {"id": 31, "title": "Item Beta",   "quantity": 2, "price": "3.00", "vendor": VENDOR_A_NAME},
            {"id": 32, "title": "Item Gamma",  "quantity": 1, "price": "7.00", "vendor": VENDOR_A_NAME},
        ])
        r = _post_webhook(http, "orders/paid", payload)
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        assert result["action"] == "delivery_jobs_created"
        assert len(result["jobs"]) == 1, f"Expected 1 job, got {len(result['jobs'])}"
        assert result["mode"] == "single_vendor"
        TestSameVendorGrouping.job_id = result["jobs"][0]["jobId"]

    def test_same_vendor_job_has_all_three_items(self, http):
        assert TestSameVendorGrouping.job_id
        r = http.get(f"{API}/delivery/jobs/{TestSameVendorGrouping.job_id}")
        items = r.json()["orderItems"]
        assert len(items) == 3
        titles = {i["title"] for i in items}
        assert {"Item Alpha", "Item Beta", "Item Gamma"} == titles


# ══════════════════════════════════════════════════════════════════════════════
# Test 5 — MISSING VENDOR FIELD: mixed order (some with vendor, some without)
# ══════════════════════════════════════════════════════════════════════════════

class TestMissingVendorField:
    """Order where SOME items have vendor and SOME don't.
    Items without vendor → reported in unmappedGroups, no job created for them.
    Items with vendor → normal job creation."""

    order_id = None
    job_id   = None

    def test_mixed_order_creates_job_for_known_vendor_only(self, http, vendor_a_id):
        TestMissingVendorField.order_id = int(time.time() * 1000 + 50) % 1_000_000_000
        payload = _order_payload(TestMissingVendorField.order_id, line_items=[
            {"id": 40, "title": "Known Item",   "quantity": 1, "price": "5.00", "vendor": VENDOR_A_NAME},
            {"id": 41, "title": "Unknown Item", "quantity": 1, "price": "3.00"},   # no vendor field
        ])
        r = _post_webhook(http, "orders/paid", payload)
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        assert result["action"] == "delivery_jobs_created"
        assert len(result["jobs"]) == 1
        assert result["jobs"][0]["vendorName"] == VENDOR_A_NAME
        # unmapped item must be reported
        assert len(result["unmappedGroups"]) == 1
        unmap = result["unmappedGroups"][0]
        assert unmap["reason"] == "no_vendor_field"
        assert unmap["shopifyVendorName"] is None
        TestMissingVendorField.job_id = result["jobs"][0]["jobId"]

    def test_missing_vendor_job_has_only_known_item(self, http):
        assert TestMissingVendorField.job_id
        r = http.get(f"{API}/delivery/jobs/{TestMissingVendorField.job_id}")
        items = r.json()["orderItems"]
        assert len(items) == 1
        assert items[0]["title"] == "Known Item"

    def test_missing_vendor_no_job_for_unknown_item(self, http):
        """The 'Unknown Item' must NOT have a delivery job anywhere in the system."""
        r = http.get(f"{API}/delivery/jobs")
        jobs_data = r.json()
        all_items = [
            item
            for job in jobs_data["jobs"]
            for item in job["orderItems"]
            if job.get("shopifyOrderId", "").endswith(str(TestMissingVendorField.order_id))
        ]
        titles = [i["title"] for i in all_items]
        assert "Unknown Item" not in titles, "Unknown Item should not appear in any delivery job"


# ══════════════════════════════════════════════════════════════════════════════
# Test 6 — UNMATCHED VENDOR: vendor string not in NowKart
# ══════════════════════════════════════════════════════════════════════════════

class TestUnmatchedVendor:
    """Shopify vendor string does not match any active NowKart vendor.
    No delivery job must be created; failure is reported explicitly."""

    order_id = None

    def test_unmatched_vendor_no_job_created(self, http):
        TestUnmatchedVendor.order_id = int(time.time() * 1000 + 60) % 1_000_000_000
        unknown_vendor = f"UNKNOWN-BRAND-{uuid.uuid4().hex[:6]}"
        payload = _order_payload(TestUnmatchedVendor.order_id, line_items=[
            {"id": 50, "title": "Ghost Product", "quantity": 1, "price": "9.99", "vendor": unknown_vendor},
        ])
        r = _post_webhook(http, "orders/paid", payload)
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        assert result["action"] == "delivery_jobs_created"
        assert len(result["jobs"]) == 0, "No jobs should be created for unmatched vendor"
        assert result["status"] == "failed"
        assert len(result["unmappedGroups"]) == 1
        unmap = result["unmappedGroups"][0]
        assert unmap["reason"] == "unmatched_vendor"
        assert unmap["shopifyVendorName"] == unknown_vendor

    def test_unmatched_vendor_no_delivery_job_in_db(self, http):
        shopify_gid = f"gid://shopify/Order/{TestUnmatchedVendor.order_id}"
        r = http.get(f"{API}/delivery/jobs")
        all_jobs = r.json()["jobs"]
        jobs_for_order = [j for j in all_jobs if j.get("shopifyOrderId") == shopify_gid]
        assert len(jobs_for_order) == 0, "No delivery job must exist for an unmatched vendor order"


# ══════════════════════════════════════════════════════════════════════════════
# Test 7 — IDEMPOTENT: same webhook ID twice → "duplicate"
# ══════════════════════════════════════════════════════════════════════════════

class TestIdempotentSameWebhookId:
    """Duplicate X-Shopify-Webhook-Id → 'duplicate' response, no second job."""

    def test_duplicate_webhook_id_returns_duplicate(self, http, vendor_a_id):
        order_id   = int(time.time() * 1000 + 70) % 1_000_000_000
        webhook_id = str(uuid.uuid4())
        payload = _order_payload(order_id, line_items=[
            {"id": 60, "title": "Idem Item", "quantity": 1, "price": "5.00", "vendor": VENDOR_A_NAME},
        ])
        # First delivery
        r1 = _post_webhook(http, "orders/paid", payload, webhook_id)
        assert r1.status_code == 200
        assert r1.json()["status"] == "ok"
        # Second delivery — same webhook_id
        r2 = _post_webhook(http, "orders/paid", payload, webhook_id)
        assert r2.status_code == 200
        assert r2.json()["status"] == "duplicate"


# ══════════════════════════════════════════════════════════════════════════════
# Test 8 — IDEMPOTENT: same Shopify order, DIFFERENT webhook ID
# ══════════════════════════════════════════════════════════════════════════════

class TestIdempotentDifferentWebhookId:
    """Same Shopify order ID but different X-Shopify-Webhook-Id (Shopify retry).
    Must return the same parent_order and not create duplicate delivery jobs."""

    order_id      = None
    parent_id_1   = None
    job_count_1   = None

    def test_first_delivery(self, http, vendor_a_id):
        TestIdempotentDifferentWebhookId.order_id = (
            int(time.time() * 1000 + 80) % 1_000_000_000
        )
        payload = _order_payload(TestIdempotentDifferentWebhookId.order_id, line_items=[
            {"id": 70, "title": "Retry Item", "quantity": 1, "price": "4.00", "vendor": VENDOR_A_NAME},
        ])
        r = _post_webhook(http, "orders/paid", payload)
        assert r.status_code == 200
        result = r.json()["result"]
        assert result["action"] == "delivery_jobs_created"
        TestIdempotentDifferentWebhookId.parent_id_1 = result["parentOrderId"]
        TestIdempotentDifferentWebhookId.job_count_1 = len(result["jobs"])

    def test_second_delivery_same_order_different_webhook(self, http, vendor_a_id):
        """Second delivery (Shopify retry) must return same parentOrderId, no new jobs."""
        payload = _order_payload(
            TestIdempotentDifferentWebhookId.order_id,
            line_items=[
                {"id": 70, "title": "Retry Item", "quantity": 1, "price": "4.00", "vendor": VENDOR_A_NAME},
            ],
        )
        r = _post_webhook(http, "orders/paid", payload)   # new webhook_id auto-generated
        assert r.status_code == 200
        result = r.json()["result"]
        # Parent order must be identical
        assert result["parentOrderId"] == TestIdempotentDifferentWebhookId.parent_id_1, (
            "Second delivery should return the SAME parentOrderId — idempotency violated"
        )

    def test_no_duplicate_jobs_in_db(self, http):
        shopify_gid = f"gid://shopify/Order/{TestIdempotentDifferentWebhookId.order_id}"
        r = http.get(f"{API}/delivery/jobs")
        all_jobs = r.json()["jobs"]
        jobs_for_order = [j for j in all_jobs if j.get("shopifyOrderId") == shopify_gid]
        assert len(jobs_for_order) == TestIdempotentDifferentWebhookId.job_count_1, (
            f"Expected {TestIdempotentDifferentWebhookId.job_count_1} job(s), "
            f"found {len(jobs_for_order)} — duplicate jobs created"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Test 9 — MULTI-VENDOR CANCEL: orders/cancelled cancels both jobs
# ══════════════════════════════════════════════════════════════════════════════

class TestMultiVendorCancel:
    """orders/cancelled on a two-vendor order cancels both delivery jobs."""

    order_id = None
    job_a_id = None
    job_b_id = None

    def test_setup_create_two_vendor_order(self, http, vendor_a_id, vendor_b_id):
        TestMultiVendorCancel.order_id = int(time.time() * 1000 + 90) % 1_000_000_000
        payload = _order_payload(TestMultiVendorCancel.order_id, line_items=[
            {"id": 80, "title": "Cancel-A", "quantity": 1, "price": "5.00", "vendor": VENDOR_A_NAME},
            {"id": 81, "title": "Cancel-B", "quantity": 1, "price": "6.00", "vendor": VENDOR_B_NAME},
        ])
        r = _post_webhook(http, "orders/paid", payload)
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        assert len(result["jobs"]) == 2
        for j in result["jobs"]:
            if j["vendorName"] == VENDOR_A_NAME:
                TestMultiVendorCancel.job_a_id = j["jobId"]
            else:
                TestMultiVendorCancel.job_b_id = j["jobId"]

    def test_orders_cancelled_cancels_both_jobs(self, http):
        payload = {"id": TestMultiVendorCancel.order_id, "cancel_reason": "customer"}
        r = _post_webhook(http, "orders/cancelled", payload)
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        assert result["action"] == "delivery_jobs_updated"
        assert len(result["jobs"]) == 2
        for j in result["jobs"]:
            assert j["status"] == "cancelled"

    def test_both_jobs_are_cancelled_in_db(self, http):
        for jid in [TestMultiVendorCancel.job_a_id, TestMultiVendorCancel.job_b_id]:
            r = http.get(f"{API}/delivery/jobs/{jid}")
            assert r.status_code == 200
            assert r.json()["status"] == "cancelled", f"Job {jid} not cancelled"


# ══════════════════════════════════════════════════════════════════════════════
# Test 10 — EXISTING FLOW REGRESSION: full single-job (legacy) lifecycle intact
# ══════════════════════════════════════════════════════════════════════════════

class TestExistingFlowRegression:
    """Verify the existing single-vendor (no vendor field) flow is fully intact."""

    order_id   = None
    webhook_id = None
    job_id     = None

    def test_regression_job_created_with_correct_fields(self, http):
        TestExistingFlowRegression.order_id   = int(time.time() * 1000 + 100) % 1_000_000_000
        TestExistingFlowRegression.webhook_id = str(uuid.uuid4())
        payload = _order_payload(TestExistingFlowRegression.order_id, line_items=[
            {"id": 90, "title": "Regr Product", "quantity": 3, "price": "4.99"},
        ], note="Leave at door")
        r = _post_webhook(http, "orders/paid", payload, TestExistingFlowRegression.webhook_id)
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        assert result["action"] == "delivery_job_created"
        assert "jobId" in result
        TestExistingFlowRegression.job_id = result["jobId"]

    def test_regression_job_has_delivery_address(self, http):
        r = http.get(f"{API}/delivery/jobs/{TestExistingFlowRegression.job_id}")
        addr = r.json()["deliveryAddress"]
        assert addr["line1"] == "1 Test St"
        assert addr["city"] == "London"

    def test_regression_job_has_delivery_instructions(self, http):
        r = http.get(f"{API}/delivery/jobs/{TestExistingFlowRegression.job_id}")
        assert r.json()["deliveryInstructions"] == "Leave at door"

    def test_regression_cancel_via_webhook(self, http):
        payload = {"id": TestExistingFlowRegression.order_id, "cancel_reason": "customer"}
        r = _post_webhook(http, "orders/cancelled", payload)
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        # Single-job cancel → backward-compatible response
        assert result["action"] == "delivery_job_updated"
        assert result["status"] == "cancelled"

    def test_regression_job_is_cancelled_in_db(self, http):
        r = http.get(f"{API}/delivery/jobs/{TestExistingFlowRegression.job_id}")
        assert r.json()["status"] == "cancelled"

    def test_regression_idempotent_cancel(self, http):
        """Cancelling an already-cancelled job → still returns ok (terminal state guard)."""
        payload = {"id": TestExistingFlowRegression.order_id, "cancel_reason": "retry"}
        r = _post_webhook(http, "orders/cancelled", payload)
        assert r.status_code == 200
        # Job is in terminal state — cancel handler returns the job unchanged
        result = r.json()["result"]
        assert result["action"] == "delivery_job_updated"
        assert result["status"] == "cancelled"
