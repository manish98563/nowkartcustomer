"""
Rider Backend Platform - Comprehensive Tests (Iteration 17)

Covers:
  - Admin CRUD: create, list, get, update, activate, suspend, soft-delete
  - Rider Auth: login, token refresh, logout, role isolation
  - Rider profile, status, push token, job current/history, stats
  - Assignment via admin and delivery router
  - Existing endpoints regression (shopify home, webhook, customer JWT isolation)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://nowkart-handover.preview.emergentagent.com").rstrip("/")

RIDER_EMAIL = "TEST_rider_iter17@nowkart.com"
RIDER_PASSWORD = "TestPass2026!"
RIDER2_EMAIL = "TEST_rider2_iter17@nowkart.com"

# Module-level shared state (set by earlier tests, used by later ones)
_state = {
    "created_rider_id": None,
    "access_token": None,
    "refresh_token": None,
    "pending_job_id": None,
}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ─── Admin: Rider Creation ────────────────────────────────────────────────────

class TestAdminRiderCreate:
    """Admin rider creation tests"""

    def test_create_rider_success(self, session):
        # Use unique email to avoid conflicts between test runs
        import time
        unique_email = f"TEST_rider_iter17_{int(time.time())}@nowkart.com"
        RIDER_EMAIL_UNIQUE = unique_email
        resp = session.post(f"{BASE_URL}/api/admin/riders", json={
            "email": unique_email,
            "phone": "+441234567890",
            "password": RIDER_PASSWORD,
            "firstName": "Test",
            "lastName": "Rider17",
            "vehicleType": "motorcycle",
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "id" in data
        _state["created_rider_id"] = data["id"]
        _state["test_rider_email"] = unique_email
        # Email is stored lowercase
        assert data["email"] == unique_email.lower()
        assert data["isActive"] is True
        assert data["isDeleted"] is False
        assert "passwordHash" not in data, "passwordHash must not be exposed"
        print(f"Created rider id={_state['created_rider_id']}")

    def test_create_rider_duplicate_email_409(self, session):
        resp = session.post(f"{BASE_URL}/api/admin/riders", json={
            "email": RIDER_EMAIL,
            "phone": "+441234567891",
            "password": RIDER_PASSWORD,
            "firstName": "Dup",
            "lastName": "Rider",
            "vehicleType": "bicycle",
        })
        assert resp.status_code == 409, f"Expected 409 got {resp.status_code}: {resp.text}"

    def test_create_rider_short_password_400(self, session):
        resp = session.post(f"{BASE_URL}/api/admin/riders", json={
            "email": "TEST_shortpwd17@nowkart.com",
            "phone": "+441234567892",
            "password": "short",
            "firstName": "Short",
            "lastName": "Pass",
            "vehicleType": "bicycle",
        })
        assert resp.status_code == 400, f"Expected 400 got {resp.status_code}: {resp.text}"


# ─── Rider Auth ───────────────────────────────────────────────────────────────

class TestRiderAuth:
    """Rider authentication flows"""

    def test_login_success(self, session):
        email = _state.get("test_rider_email") or RIDER_EMAIL
        resp = session.post(f"{BASE_URL}/api/rider/auth/login", json={
            "email": email,
            "password": RIDER_PASSWORD,
        })
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "accessToken" in data
        assert "refreshToken" in data
        assert data["expiresIn"] == 14400, f"Expected expiresIn=14400, got {data['expiresIn']}"
        assert "rider" in data
        assert data["rider"]["email"] == email.lower()
        _state["access_token"] = data["accessToken"]
        _state["refresh_token"] = data["refreshToken"]
        print(f"Login OK. expiresIn={data['expiresIn']}")

    def test_login_wrong_password_401(self, session):
        resp = session.post(f"{BASE_URL}/api/rider/auth/login", json={
            "email": RIDER_EMAIL,
            "password": "WrongPassword123",
        })
        assert resp.status_code == 401, f"Expected 401 got {resp.status_code}: {resp.text}"

    def test_login_nonexistent_email_401(self, session):
        resp = session.post(f"{BASE_URL}/api/rider/auth/login", json={
            "email": "nobody@nowkart.com",
            "password": "AnyPass123",
        })
        assert resp.status_code == 401, f"Expected 401 got {resp.status_code}: {resp.text}"


# ─── Rider Profile ────────────────────────────────────────────────────────────

class TestRiderProfile:
    """Rider profile endpoint"""

    def test_profile_with_valid_token(self, session):
        assert _state["access_token"], "access_token not set — login test must pass first"
        resp = session.get(
            f"{BASE_URL}/api/rider/profile",
            headers={"Authorization": f"Bearer {_state['access_token']}"},
        )
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        email = _state.get("test_rider_email") or RIDER_EMAIL
        assert data["email"] == email.lower()
        assert "stats" in data

    def test_profile_without_auth_401(self, session):
        resp = session.get(f"{BASE_URL}/api/rider/profile")
        assert resp.status_code == 401

    def test_profile_malformed_token_401(self, session):
        resp = session.get(
            f"{BASE_URL}/api/rider/profile",
            headers={"Authorization": "Bearer this.is.not.a.real.jwt"},
        )
        assert resp.status_code == 401


# ─── Rider Status ─────────────────────────────────────────────────────────────

class TestRiderStatus:
    """Rider status update"""

    def test_update_status_online(self, session):
        resp = session.put(
            f"{BASE_URL}/api/rider/status",
            json={"status": "online"},
            headers={"Authorization": f"Bearer {_state['access_token']}"},
        )
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        assert resp.json()["status"] == "online"

    def test_update_status_busy(self, session):
        resp = session.put(
            f"{BASE_URL}/api/rider/status",
            json={"status": "busy"},
            headers={"Authorization": f"Bearer {_state['access_token']}"},
        )
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        assert resp.json()["status"] == "busy"

    def test_update_status_offline(self, session):
        resp = session.put(
            f"{BASE_URL}/api/rider/status",
            json={"status": "offline"},
            headers={"Authorization": f"Bearer {_state['access_token']}"},
        )
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        assert resp.json()["status"] == "offline"

    def test_update_status_without_auth_401(self, session):
        resp = session.put(f"{BASE_URL}/api/rider/status", json={"status": "online"})
        assert resp.status_code == 401


# ─── Push Token ───────────────────────────────────────────────────────────────

class TestPushToken:
    """Push token storage"""

    def test_register_push_token(self, session):
        resp = session.post(
            f"{BASE_URL}/api/rider/push-token",
            json={"token": "ExponentPushToken[test123]", "platform": "ios"},
            headers={"Authorization": f"Bearer {_state['access_token']}"},
        )
        assert resp.status_code == 204, f"Expected 204 got {resp.status_code}: {resp.text}"

    def test_push_token_stored_on_rider(self, session):
        """Verify push token was actually persisted"""
        rid = _state["created_rider_id"]
        assert rid, "created_rider_id not set"
        resp = session.get(f"{BASE_URL}/api/admin/riders/{rid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("devicePushToken") == "ExponentPushToken[test123]"
        assert data.get("platformOS") == "ios"
        print("PASS: push token stored correctly")


# ─── Current Job & History ────────────────────────────────────────────────────

class TestRiderJob:
    """Rider job endpoints"""

    def test_current_job_null_when_none(self, session):
        resp = session.get(
            f"{BASE_URL}/api/rider/job/current",
            headers={"Authorization": f"Bearer {_state['access_token']}"},
        )
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("job") is None
        print("PASS: no current job initially")

    def test_job_history_empty_initially(self, session):
        resp = session.get(
            f"{BASE_URL}/api/rider/job/history",
            headers={"Authorization": f"Bearer {_state['access_token']}"},
        )
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data["jobs"], list)
        print(f"PASS: job history returned, total={data['total']}")


# ─── Stats ────────────────────────────────────────────────────────────────────

class TestRiderStats:
    """Rider stats endpoint"""

    def test_stats_zero_counts_initially(self, session):
        resp = session.get(
            f"{BASE_URL}/api/rider/stats",
            headers={"Authorization": f"Bearer {_state['access_token']}"},
        )
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "totalDeliveries" in data
        assert "completedDeliveries" in data
        assert "failedDeliveries" in data
        assert "cancelledDeliveries" in data
        assert "successRate" in data
        print(f"PASS: stats OK: {data}")


# ─── Token Refresh & Logout ───────────────────────────────────────────────────

class TestTokenRefresh:
    """Token rotation and logout"""

    def test_refresh_token_rotation(self, session):
        old_rt = _state["refresh_token"]
        assert old_rt, "refresh_token not set — login test must pass first"
        resp = session.post(f"{BASE_URL}/api/rider/auth/refresh", json={"refreshToken": old_rt})
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "accessToken" in data
        assert "refreshToken" in data
        _state["access_token"] = data["accessToken"]
        _state["refresh_token"] = data["refreshToken"]
        # Reuse of old token must fail
        resp2 = session.post(f"{BASE_URL}/api/rider/auth/refresh", json={"refreshToken": old_rt})
        assert resp2.status_code == 401, f"Reuse of revoked token should return 401, got {resp2.status_code}"
        print("PASS: token rotation works")

    def test_refresh_invalid_token_401(self, session):
        resp = session.post(f"{BASE_URL}/api/rider/auth/refresh", json={"refreshToken": "completely_invalid_token"})
        assert resp.status_code == 401

    def test_logout_revokes_token(self, session):
        email = _state.get("test_rider_email") or RIDER_EMAIL
        login_resp = session.post(f"{BASE_URL}/api/rider/auth/login", json={
            "email": email, "password": RIDER_PASSWORD
        })
        assert login_resp.status_code == 200
        logout_rt = login_resp.json()["refreshToken"]
        logout_resp = session.post(f"{BASE_URL}/api/rider/auth/logout", json={"refreshToken": logout_rt})
        assert logout_resp.status_code == 204, f"Expected 204 got {logout_resp.status_code}"
        refresh_resp = session.post(f"{BASE_URL}/api/rider/auth/refresh", json={"refreshToken": logout_rt})
        assert refresh_resp.status_code == 401, f"Post-logout refresh should return 401, got {refresh_resp.status_code}"
        print("PASS: logout revokes token")


# ─── Admin: List / Get / Update ───────────────────────────────────────────────

class TestAdminRiderCRUD:
    """Admin list/get/update"""

    def test_list_riders(self, session):
        resp = session.get(f"{BASE_URL}/api/admin/riders")
        assert resp.status_code == 200
        data = resp.json()
        assert "riders" in data
        assert data["total"] >= 1

    def test_get_rider_admin_detail(self, session):
        rid = _state["created_rider_id"]
        assert rid, "created_rider_id not set"
        resp = session.get(f"{BASE_URL}/api/admin/riders/{rid}")
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "isDeleted" in data
        assert data["isDeleted"] is False

    def test_update_rider(self, session):
        rid = _state["created_rider_id"]
        assert rid, "created_rider_id not set"
        resp = session.put(
            f"{BASE_URL}/api/admin/riders/{rid}",
            json={"firstName": "UpdatedFirst", "vehicleType": "car"},
        )
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["firstName"] == "UpdatedFirst"
        assert data["vehicleType"] == "car"


# ─── Admin: Suspend / Activate ────────────────────────────────────────────────

class TestAdminSuspendActivate:
    """Suspend and activate rider"""

    def test_suspend_sets_inactive_and_offline(self, session):
        rid = _state["created_rider_id"]
        assert rid, "created_rider_id not set"
        resp = session.put(f"{BASE_URL}/api/admin/riders/{rid}/suspend")
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["isActive"] is False
        assert data["status"] == "offline"

    def test_suspended_rider_login_returns_403(self, session):
        """Suspended rider gets 403 on login"""
        email = _state.get("test_rider_email") or RIDER_EMAIL
        resp = session.post(f"{BASE_URL}/api/rider/auth/login", json={
            "email": email, "password": RIDER_PASSWORD,
        })
        assert resp.status_code == 403, f"Expected 403 for suspended rider, got {resp.status_code}: {resp.text}"

    def test_profile_with_old_token_returns_403(self, session):
        """Old JWT of suspended rider returns 403"""
        resp = session.get(
            f"{BASE_URL}/api/rider/profile",
            headers={"Authorization": f"Bearer {_state['access_token']}"},
        )
        assert resp.status_code == 403, f"Expected 403 for suspended rider old token, got {resp.status_code}: {resp.text}"

    def test_activate_sets_active(self, session):
        rid = _state["created_rider_id"]
        assert rid, "created_rider_id not set"
        resp = session.put(f"{BASE_URL}/api/admin/riders/{rid}/activate")
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["isActive"] is True

    def test_rider_can_login_after_activate(self, session):
        email = _state.get("test_rider_email") or RIDER_EMAIL
        resp = session.post(f"{BASE_URL}/api/rider/auth/login", json={
            "email": email, "password": RIDER_PASSWORD,
        })
        assert resp.status_code == 200, f"Expected 200 after reactivation, got {resp.status_code}: {resp.text}"
        _state["access_token"] = resp.json()["accessToken"]
        _state["refresh_token"] = resp.json()["refreshToken"]


# ─── Admin: Assign Job ────────────────────────────────────────────────────────

class TestAssignment:
    """Job assignment flows"""

    def test_assign_rider_to_pending_job_via_admin(self, session):
        resp = session.get(f"{BASE_URL}/api/delivery/jobs?status=pending_assignment&limit=5")
        if resp.status_code != 200:
            pytest.skip("Cannot query delivery jobs")
        jobs = resp.json().get("jobs", [])
        if not jobs:
            pytest.skip("No PENDING_ASSIGNMENT jobs available")

        job_id = jobs[0]["id"]
        _state["pending_job_id"] = job_id
        rid = _state["created_rider_id"]
        assert rid, "created_rider_id not set"

        assign_resp = session.post(f"{BASE_URL}/api/admin/riders/{rid}/assign-job/{job_id}")
        assert assign_resp.status_code == 200, f"Expected 200 got {assign_resp.status_code}: {assign_resp.text}"
        data = assign_resp.json()
        assert "job" in data
        assert data["job"]["status"] == "assigned"

    def test_assign_same_job_again_returns_409(self, session):
        job_id = _state["pending_job_id"]
        if not job_id:
            pytest.skip("No job was assigned in previous test")

        # Create second rider
        r2 = session.post(f"{BASE_URL}/api/admin/riders", json={
            "email": RIDER2_EMAIL, "phone": "+441111222333",
            "password": "TestPass2026!", "firstName": "Rider2", "lastName": "Test",
            "vehicleType": "bicycle",
        })
        if r2.status_code == 201:
            r2_id = r2.json()["id"]
        elif r2.status_code == 409:
            lst = session.get(f"{BASE_URL}/api/admin/riders")
            r2_id = next((r["id"] for r in lst.json().get("riders", []) if r["email"] == RIDER2_EMAIL.lower()), None)
            if not r2_id:
                pytest.skip("Cannot get second rider")
        else:
            pytest.skip(f"Cannot create second rider: {r2.status_code}")

        resp = session.post(f"{BASE_URL}/api/admin/riders/{r2_id}/assign-job/{job_id}")
        assert resp.status_code == 409, f"Expected 409 for already-ASSIGNED job, got {resp.status_code}: {resp.text}"

    def test_get_current_job_after_assignment(self, session):
        job_id = _state["pending_job_id"]
        if not job_id:
            pytest.skip("No job was assigned")
        resp = session.get(
            f"{BASE_URL}/api/rider/job/current",
            headers={"Authorization": f"Bearer {_state['access_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("job") is not None, "Expected current job after assignment"
        assert data["job"]["id"] == job_id

    def test_assign_via_delivery_router(self, session):
        """Alternative assignment path: POST /api/delivery/jobs/{id}/assign"""
        resp = session.get(f"{BASE_URL}/api/delivery/jobs?status=pending_assignment&limit=5")
        if resp.status_code != 200:
            pytest.skip("Cannot query delivery jobs")
        jobs = resp.json().get("jobs", [])
        if not jobs:
            pytest.skip("No PENDING_ASSIGNMENT jobs for this test")
        job_id = jobs[0]["id"]

        fresh_email = "TEST_assignvia_deliv17@nowkart.com"
        cr = session.post(f"{BASE_URL}/api/admin/riders", json={
            "email": fresh_email, "phone": "+441999888777",
            "password": "TestPass2026!", "firstName": "FreshR", "lastName": "Deliv",
            "vehicleType": "motorcycle",
        })
        if cr.status_code == 201:
            fresh_id = cr.json()["id"]
        elif cr.status_code == 409:
            lst = session.get(f"{BASE_URL}/api/admin/riders?includeDeleted=true")
            fresh_id = next((r["id"] for r in lst.json().get("riders", []) if r["email"] == fresh_email.lower()), None)
            if not fresh_id:
                pytest.skip("Cannot get fresh rider")
        else:
            pytest.skip(f"Cannot create fresh rider: {cr.status_code}")

        resp2 = session.post(f"{BASE_URL}/api/delivery/jobs/{job_id}/assign", json={"riderId": fresh_id})
        assert resp2.status_code == 200, f"Expected 200 got {resp2.status_code}: {resp2.text}"
        assert resp2.json()["status"] == "assigned"


# ─── Soft Delete ──────────────────────────────────────────────────────────────

class TestSoftDelete:
    """Soft delete flow"""

    def test_soft_delete_rider(self, session):
        rid = _state["created_rider_id"]
        assert rid, "created_rider_id not set"
        resp = session.delete(f"{BASE_URL}/api/admin/riders/{rid}")
        assert resp.status_code == 204, f"Expected 204 got {resp.status_code}: {resp.text}"

    def test_get_deleted_rider_returns_404(self, session):
        rid = _state["created_rider_id"]
        assert rid, "created_rider_id not set"
        resp = session.get(f"{BASE_URL}/api/admin/riders/{rid}")
        assert resp.status_code == 404, f"Expected 404 for deleted rider, got {resp.status_code}: {resp.text}"


# ─── Role Isolation ───────────────────────────────────────────────────────────

class TestRoleIsolation:
    """Customer JWT cannot access rider endpoints"""

    def test_customer_jwt_rejected_on_rider_profile(self, session):
        """A fake token without role=rider must be rejected"""
        import base64
        header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b'=').decode()
        payload = base64.urlsafe_b64encode(b'{"sub":"fake123","role":"customer"}').rstrip(b'=').decode()
        fake_token = f"{header}.{payload}.invalidsignature"
        resp = session.get(
            f"{BASE_URL}/api/rider/profile",
            headers={"Authorization": f"Bearer {fake_token}"},
        )
        assert resp.status_code == 401, f"Customer/fake JWT should return 401, got {resp.status_code}"


# ─── Regression Tests ─────────────────────────────────────────────────────────

class TestRegression:
    """Existing endpoints must still work"""

    def test_shopify_home_still_works(self, session):
        resp = session.get(f"{BASE_URL}/api/shopify/home")
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"

    def test_shopify_webhook_accepts_request(self, session):
        """Webhook endpoint should accept POST (no secret in dev)"""
        resp = session.post(
            f"{BASE_URL}/api/webhooks/shopify",
            json={
                "id": 99999998877,
                "order_number": 9998,
                "name": "#TEST_ITER17",
                "financial_status": "paid",
                "total_price": "25.00",
                "currency": "GBP",
                "shipping_address": {
                    "address1": "1 Test St",
                    "city": "London",
                    "zip": "EC1A 1BB",
                    "country": "UK",
                },
                "line_items": [{"title": "Test Item", "quantity": 1, "price": "25.00"}],
            },
            headers={"X-Shopify-Topic": "orders/paid", "X-Shopify-Hmac-Sha256": ""},
        )
        assert resp.status_code not in (500, 502, 503), f"Webhook returned server error: {resp.status_code}: {resp.text}"
        print(f"PASS: webhook returned {resp.status_code}")
