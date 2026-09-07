"""
Focused tests for PUT /api/admin/riders/{riderId}/restore

Covers:
  1. Restore a soft-deleted rider           → 200, isDeleted=False, isActive=True
  2. Restore a non-existent rider           → 404
  3. Restore an already-active rider        → 200 (idempotent)
  4. RBAC: support role cannot restore      → 403
  5. No-auth request                        → 401
  6. passwordHash and unrelated fields unchanged after restore
  7. Confirm rider can log in after restore

All tests run against the local nowkartcustomer backend.
Run with:
    EXPO_PUBLIC_BACKEND_URL=http://localhost:8099 pytest tests/test_rider_restore_endpoint.py -v
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    os.environ.get("LOCAL_BACKEND_URL", "http://localhost:8099")
).rstrip("/")

ADMIN_EMAIL    = "admin@nowkart.com"
ADMIN_PASSWORD = "Admin2026!"

SUPPORT_EMAIL    = "support_restore_test@nowkart.com"
SUPPORT_PASSWORD = "Support2026!!"

# Unique suffix so parallel test runs don't collide
_TS = str(int(time.time()))
RIDER_EMAIL    = f"TEST_restore_{_TS}@nowkart.com"
RIDER_PASSWORD = "RestorePass2026!"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def admin_login() -> str:
    """Return a fresh super_admin access token (does NOT print the token)."""
    r = requests.post(
        f"{BASE_URL}/api/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["accessToken"]


def create_test_rider(token: str) -> dict:
    """Create a fresh test rider and return the full response body."""
    r = requests.post(
        f"{BASE_URL}/api/admin/riders",
        json={
            "email": RIDER_EMAIL,
            "phone": "+441111222333",
            "password": RIDER_PASSWORD,
            "firstName": "Restore",
            "lastName": "TestRider",
            "vehicleType": "motorcycle",
        },
        headers=auth_headers(token),
        timeout=15,
    )
    assert r.status_code == 201, f"Rider create failed: {r.text}"
    return r.json()


def soft_delete_rider(token: str, rider_id: str) -> None:
    """Soft-delete a rider via the admin DELETE endpoint."""
    r = requests.delete(
        f"{BASE_URL}/api/admin/riders/{rider_id}",
        headers=auth_headers(token),
        timeout=15,
    )
    assert r.status_code == 204, f"Delete failed: {r.text}"


# ─── Module-level shared state ───────────────────────────────────────────────

_state: dict = {
    "admin_token": None,
    "rider_id": None,
    "rider_phone": "+441111222333",
    "rider_vehicle_type": "motorcycle",
}


# ─── Setup fixture ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def setup_test_state():
    """
    Before all tests: login as admin, create a test rider, then soft-delete it
    so the restore tests have a valid deleted target.
    After all tests: attempt cleanup (best-effort).
    """
    token = admin_login()
    _state["admin_token"] = token

    # Create rider
    rider = create_test_rider(token)
    _state["rider_id"] = rider["id"]
    # Record some fields to verify they are preserved after restore
    _state["rider_phone"]        = rider["phone"]
    _state["rider_vehicle_type"] = rider["vehicleType"]

    # Soft-delete it so we have a deleted rider to restore
    soft_delete_rider(token, rider["id"])

    yield

    # Cleanup: delete restored rider (best-effort — might already be deleted)
    try:
        requests.delete(
            f"{BASE_URL}/api/admin/riders/{_state['rider_id']}",
            headers=auth_headers(_state["admin_token"]),
            timeout=15,
        )
    except Exception:
        pass


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestRiderRestore:

    def test_restore_soft_deleted_rider_returns_200(self):
        """Core test: restore a soft-deleted rider → HTTP 200."""
        token = _state["admin_token"]
        rider_id = _state["rider_id"]

        r = requests.put(
            f"{BASE_URL}/api/admin/riders/{rider_id}/restore",
            headers=auth_headers(token),
            timeout=15,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()

        # Soft-delete flags reset
        assert data["isDeleted"] is False, "isDeleted must be False after restore"
        assert data["isActive"]  is True,  "isActive must be True after restore"

        # Core identity fields preserved
        assert data["id"]    == rider_id,              "ID must not change"
        assert data["email"] == RIDER_EMAIL.lower(),   "email must not change"
        assert data["phone"] == _state["rider_phone"], "phone must not change"
        assert data["vehicleType"] == _state["rider_vehicle_type"], "vehicleType must not change"

        # passwordHash MUST NOT be exposed in the response
        assert "passwordHash" not in data, "passwordHash must never appear in response"

        print(f"RESTORE OK — rider {rider_id} isDeleted=False isActive=True")

    def test_restore_non_existent_rider_returns_404(self):
        """Non-existent ID → 404."""
        token = _state["admin_token"]
        fake_id = "000000000000000000000000"

        r = requests.put(
            f"{BASE_URL}/api/admin/riders/{fake_id}/restore",
            headers=auth_headers(token),
            timeout=15,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_restore_already_active_rider_is_idempotent(self):
        """
        Restore an already-active rider → 200 (idempotent).
        The rider was restored by the first test; calling restore again must succeed.
        """
        token = _state["admin_token"]
        rider_id = _state["rider_id"]

        r = requests.put(
            f"{BASE_URL}/api/admin/riders/{rider_id}/restore",
            headers=auth_headers(token),
            timeout=15,
        )
        assert r.status_code == 200, f"Expected 200 (idempotent), got {r.status_code}: {r.text}"
        data = r.json()
        assert data["isDeleted"] is False
        assert data["isActive"]  is True
        print("IDEMPOTENT OK — second restore on active rider still returns 200")

    def test_restore_requires_admin_role_not_support(self):
        """
        A token with only the 'support' role must receive 403.
        We obtain a support token via a freshly-created support admin.
        If the admin already exists (prior test run), we log in directly.
        """
        super_token = _state["admin_token"]
        rider_id    = _state["rider_id"]
        support_id  = None

        # Try to create a support admin; if it already exists (409), proceed to login
        support_create = requests.post(
            f"{BASE_URL}/api/admin/admins",
            json={
                "email":     SUPPORT_EMAIL,
                "password":  SUPPORT_PASSWORD,
                "firstName": "Support",
                "lastName":  "RestoreTest",
                "role":      "support",
            },
            headers=auth_headers(super_token),
            timeout=15,
        )
        if support_create.status_code in (200, 201):
            support_id = support_create.json().get("id")
        elif support_create.status_code != 409:
            pytest.skip(f"Could not create support admin: {support_create.text}")
        # 409 means it already exists — we can still login with the same credentials

        # Login as support
        support_login = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"email": SUPPORT_EMAIL, "password": SUPPORT_PASSWORD},
            timeout=15,
        )
        if support_login.status_code != 200:
            pytest.skip(f"Support login failed: {support_login.text}")

        support_token = support_login.json()["accessToken"]

        # Attempt restore — must be rejected (support cannot manage riders)
        r = requests.put(
            f"{BASE_URL}/api/admin/riders/{rider_id}/restore",
            headers=auth_headers(support_token),
            timeout=15,
        )
        assert r.status_code == 403, f"Expected 403 for support role, got {r.status_code}: {r.text}"
        print("RBAC OK — support role correctly denied restore (403)")

        # Cleanup: delete the temporary support admin
        if support_id:
            requests.delete(
                f"{BASE_URL}/api/admin/admins/{support_id}",
                headers=auth_headers(super_token),
                timeout=15,
            )

    def test_restore_without_auth_returns_401(self):
        """No Authorization header → 401."""
        rider_id = _state["rider_id"]

        r = requests.put(
            f"{BASE_URL}/api/admin/riders/{rider_id}/restore",
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        assert r.status_code == 401, f"Expected 401 with no auth, got {r.status_code}: {r.text}"

    def test_rider_can_login_after_restore(self):
        """
        The restored rider must be able to authenticate via
        POST /api/rider/auth/login with the original password.
        (Verifies passwordHash was preserved, not wiped, during restore.)
        """
        r = requests.post(
            f"{BASE_URL}/api/rider/auth/login",
            json={"email": RIDER_EMAIL, "password": RIDER_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200, f"Rider login after restore failed: {r.status_code}: {r.text}"
        data = r.json()
        rider = data.get("rider", {})
        assert rider.get("isActive") is True, "Rider must be active after restore"
        assert rider.get("email") == RIDER_EMAIL.lower()
        assert "accessToken" in data, "accessToken must be present in login response"
        # DO NOT print or assert on the token value itself
        print(f"RIDER LOGIN AFTER RESTORE OK — rider.isActive={rider.get('isActive')}")
